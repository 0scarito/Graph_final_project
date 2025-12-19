"""
Panama Papers API - Pytest Configuration
==========================================

Pytest fixtures for testing the Panama Papers FastAPI application.

Fixtures Provided:
    - event_loop: Async event loop for tests
    - neo4j_driver: Test Neo4j driver connection
    - async_client: FastAPI AsyncClient for API testing
    - sample_entity: Single test entity
    - sample_entities: Multiple test entities
    - sample_person: Single test person
    - sample_relationships: Test ownership relationships
    - sample_ownership_chain: Multi-hop ownership chain

Configuration:
    - Uses pytest-asyncio for async test support
    - Automatic database cleanup before/after each test
    - Separate test database configuration via .env.test

Usage:
    pytest tests/ -v --asyncio-mode=auto
    pytest tests/test_entities.py -v -k "test_get_entity"

Environment Variables (via .env.test):
    TEST_NEO4J_URI: Test Neo4j URI (default: bolt://localhost:7687)
    TEST_NEO4J_USER: Test database user (default: neo4j)
    TEST_NEO4J_PASSWORD: Test database password (required)
    TEST_NEO4J_DATABASE: Test database name (default: neo4j)
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import date, datetime
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession

# ============================================================================
# ENVIRONMENT CONFIGURATION
# ============================================================================

# Load test environment variables (override production settings)
load_dotenv(".env.test", override=True)

# Test database configuration
TEST_NEO4J_URI = os.getenv("TEST_NEO4J_URI", "bolt://localhost:7687")
TEST_NEO4J_USER = os.getenv("TEST_NEO4J_USER", "neo4j")
TEST_NEO4J_PASSWORD = os.getenv("TEST_NEO4J_PASSWORD", "testpassword")
TEST_NEO4J_DATABASE = os.getenv("TEST_NEO4J_DATABASE", "neo4j")

# Test settings
SKIP_DB_TESTS = os.getenv("SKIP_DB_TESTS", "false").lower() == "true"
USE_MOCK_DB = os.getenv("USE_MOCK_DB", "false").lower() == "true"


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (requires Neo4j)"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (no external dependencies)"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers."""
    # Skip integration tests if database is not available
    if SKIP_DB_TESTS:
        skip_db = pytest.mark.skip(reason="Database tests disabled via SKIP_DB_TESTS")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_db)


# ============================================================================
# EVENT LOOP CONFIGURATION
# ============================================================================

@pytest.fixture(scope="session")
def event_loop_policy():
    """
    Configure event loop policy for async tests.
    
    Handles platform-specific event loop configuration:
    - Windows: Uses ProactorEventLoop for better subprocess support
    - Unix: Uses default SelectorEventLoop
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    return asyncio.get_event_loop_policy()


@pytest.fixture(scope="session")
def event_loop(event_loop_policy) -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Create event loop for session-scoped async fixtures.
    
    Scope: session (shared across all tests)
    """
    policy = event_loop_policy
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)
    
    yield loop
    
    # Cleanup pending tasks
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    
    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    loop.close()


# ============================================================================
# NEO4J DRIVER FIXTURES
# ============================================================================

@pytest_asyncio.fixture(scope="session")
async def neo4j_driver_session() -> AsyncGenerator[AsyncDriver, None]:
    """
    Create session-scoped Neo4j driver for test database.
    
    This driver is shared across all tests in the session for efficiency.
    Individual tests should use the function-scoped `neo4j_driver` fixture
    which wraps this with per-test cleanup.
    
    Scope: session
    """
    if USE_MOCK_DB:
        # Return mock driver for unit tests
        mock_driver = AsyncMock(spec=AsyncDriver)
        mock_driver.verify_connectivity = AsyncMock()
        yield mock_driver
        return
    
    driver = AsyncGraphDatabase.driver(
        TEST_NEO4J_URI,
        auth=(TEST_NEO4J_USER, TEST_NEO4J_PASSWORD),
        max_connection_pool_size=10,
        connection_acquisition_timeout=30,
    )
    
    # Verify connection
    try:
        await driver.verify_connectivity()
    except Exception as e:
        await driver.close()
        pytest.skip(f"Neo4j not available at {TEST_NEO4J_URI}: {e}")
    
    yield driver
    
    # Final cleanup
    try:
        async with driver.session(database=TEST_NEO4J_DATABASE) as session:
            await session.run("MATCH (n) WHERE n.entity_id STARTS WITH 'TEST-' DETACH DELETE n")
            await session.run("MATCH (n) WHERE n.person_id STARTS WITH 'TEST-' DETACH DELETE n")
    except Exception:
        pass  # Ignore cleanup errors
    
    await driver.close()


@pytest_asyncio.fixture
async def neo4j_driver(
    neo4j_driver_session: AsyncDriver,
) -> AsyncGenerator[AsyncDriver, None]:
    """
    Function-scoped Neo4j driver with per-test cleanup.
    
    Uses the session-scoped driver but adds cleanup before and after each test.
    
    Scope: function (per test)
    """
    if USE_MOCK_DB:
        yield neo4j_driver_session
        return
    
    # Pre-test cleanup: Remove any leftover test data
    async with neo4j_driver_session.session(database=TEST_NEO4J_DATABASE) as session:
        await session.run("MATCH (n) WHERE n.entity_id STARTS WITH 'TEST-' DETACH DELETE n")
        await session.run("MATCH (n) WHERE n.person_id STARTS WITH 'TEST-' DETACH DELETE n")
        await session.run("MATCH (n) WHERE n.intermediary_id STARTS WITH 'TEST-' DETACH DELETE n")
        await session.run("MATCH (n) WHERE n.address_id STARTS WITH 'TEST-' DETACH DELETE n")
    
    yield neo4j_driver_session
    
    # Post-test cleanup
    async with neo4j_driver_session.session(database=TEST_NEO4J_DATABASE) as session:
        await session.run("MATCH (n) WHERE n.entity_id STARTS WITH 'TEST-' DETACH DELETE n")
        await session.run("MATCH (n) WHERE n.person_id STARTS WITH 'TEST-' DETACH DELETE n")
        await session.run("MATCH (n) WHERE n.intermediary_id STARTS WITH 'TEST-' DETACH DELETE n")
        await session.run("MATCH (n) WHERE n.address_id STARTS WITH 'TEST-' DETACH DELETE n")


@pytest_asyncio.fixture
async def neo4j_session(
    neo4j_driver: AsyncDriver,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a Neo4j session for direct database operations in tests.
    
    Scope: function
    """
    async with neo4j_driver.session(database=TEST_NEO4J_DATABASE) as session:
        yield session


# ============================================================================
# APPLICATION FIXTURES
# ============================================================================

@pytest_asyncio.fixture
async def app_instance():
    """
    Create FastAPI application instance for testing.
    
    Imports the app and overrides settings for testing.
    """
    # Import here to allow patching before import
    from main import app
    
    return app


@pytest_asyncio.fixture
async def async_client(
    app_instance,
    neo4j_driver: AsyncDriver,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Create async HTTP client for FastAPI testing.
    
    This client can be used to make requests to the API endpoints.
    The Neo4j driver is initialized for the test database.
    
    Scope: function
    
    Example:
        async def test_get_entity(async_client):
            response = await async_client.get("/entities/TEST-001")
            assert response.status_code == 200
    """
    # Import and initialize database
    from database import Neo4jDatabase, Neo4jConfig
    
    # Override config for testing
    test_config = Neo4jConfig(
        uri=TEST_NEO4J_URI,
        user=TEST_NEO4J_USER,
        password=TEST_NEO4J_PASSWORD,
        database=TEST_NEO4J_DATABASE,
    )
    
    # Initialize with test config
    if not Neo4jDatabase.is_initialized():
        await Neo4jDatabase.init(config=test_config)
    
    # Create async client
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    
    # Cleanup
    if Neo4jDatabase.is_initialized():
        await Neo4jDatabase.close()


@pytest_asyncio.fixture
async def async_client_no_db(app_instance) -> AsyncGenerator[AsyncClient, None]:
    """
    Create async client without database initialization.
    
    Useful for testing endpoints that don't require database access
    or for testing error handling when database is unavailable.
    """
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ============================================================================
# SAMPLE DATA FIXTURES - ENTITIES
# ============================================================================

@pytest_asyncio.fixture
async def sample_entity(neo4j_driver: AsyncDriver) -> dict[str, Any]:
    """
    Create a single sample entity in the test database.
    
    Returns:
        Dictionary with entity properties
    
    Entity Properties:
        - entity_id: TEST-ENTITY-001
        - name: Test Holdings Ltd
        - jurisdiction_code: BVI
        - entity_type: Company
        - status: Active
    """
    async with neo4j_driver.session(database=TEST_NEO4J_DATABASE) as session:
        query = """
        CREATE (e:Entity {
            entity_id: 'TEST-ENTITY-001',
            name: 'Test Holdings Ltd',
            jurisdiction_code: 'BVI',
            entity_type: 'Company',
            status: 'Active',
            incorporation_date: date('2015-03-15'),
            source: 'Test Data',
            pagerank_score: 0.125,
            community_id: 1,
            degree_centrality: 5
        })
        RETURN e {.*} AS entity
        """
        result = await session.run(query)
        record = await result.single()
        return dict(record["entity"]) if record else {}


@pytest_asyncio.fixture
async def sample_entities(neo4j_driver: AsyncDriver) -> list[dict[str, Any]]:
    """
    Create multiple sample entities for testing.
    
    Creates:
        - 3 Entity nodes (Company, Trust, Foundation)
        - Different jurisdictions (BVI, PAN, CYM)
        - Varying PageRank scores for ranking tests
    """
    async with neo4j_driver.session(database=TEST_NEO4J_DATABASE) as session:
        query = """
        CREATE 
            (e1:Entity {
                entity_id: 'TEST-ENTITY-001',
                name: 'Test Holdings Ltd',
                jurisdiction_code: 'BVI',
                entity_type: 'Company',
                status: 'Active',
                incorporation_date: date('2015-03-15'),
                pagerank_score: 0.250,
                community_id: 1
            }),
            (e2:Entity {
                entity_id: 'TEST-ENTITY-002',
                name: 'Global Ventures Trust',
                jurisdiction_code: 'PAN',
                entity_type: 'Trust',
                status: 'Active',
                incorporation_date: date('2012-07-22'),
                pagerank_score: 0.150,
                community_id: 1
            }),
            (e3:Entity {
                entity_id: 'TEST-ENTITY-003',
                name: 'Offshore Foundation',
                jurisdiction_code: 'CYM',
                entity_type: 'Foundation',
                status: 'Dissolved',
                incorporation_date: date('2010-01-10'),
                inactivation_date: date('2020-06-30'),
                pagerank_score: 0.050,
                community_id: 2
            })
        RETURN [e1 {.*}, e2 {.*}, e3 {.*}] AS entities
        """
        result = await session.run(query)
        record = await result.single()
        return [dict(e) for e in record["entities"]] if record else []


@pytest_asyncio.fixture
async def sample_entity_with_jurisdiction(
    neo4j_driver: AsyncDriver,
) -> dict[str, Any]:
    """
    Create entity with jurisdiction node relationship.
    """
    async with neo4j_driver.session(database=TEST_NEO4J_DATABASE) as session:
        query = """
        MERGE (j:Jurisdiction {
            jurisdiction_code: 'BVI',
            name: 'British Virgin Islands',
            is_tax_haven: true,
            secrecy_score: 71,
            risk_level: 'HIGH'
        })
        CREATE (e:Entity {
            entity_id: 'TEST-ENTITY-010',
            name: 'Test BVI Company',
            jurisdiction_code: 'BVI',
            entity_type: 'Company',
            status: 'Active'
        })
        CREATE (e)-[:REGISTERED_IN]->(j)
        RETURN e {.*, jurisdiction_name: j.name, is_tax_haven: j.is_tax_haven} AS entity
        """
        result = await session.run(query)
        record = await result.single()
        return dict(record["entity"]) if record else {}


# ============================================================================
# SAMPLE DATA FIXTURES - PERSONS
# ============================================================================

@pytest_asyncio.fixture
async def sample_person(neo4j_driver: AsyncDriver) -> dict[str, Any]:
    """
    Create a single sample person (beneficial owner).
    """
    async with neo4j_driver.session(database=TEST_NEO4J_DATABASE) as session:
        query = """
        CREATE (p:Person {
            person_id: 'TEST-PERSON-001',
            full_name: 'John Smith',
            first_name: 'John',
            last_name: 'Smith',
            nationality: 'USA',
            country_of_residence: 'USA',
            is_pep: false,
            source: 'Test Data'
        })
        RETURN p {.*} AS person
        """
        result = await session.run(query)
        record = await result.single()
        return dict(record["person"]) if record else {}


@pytest_asyncio.fixture
async def sample_pep(neo4j_driver: AsyncDriver) -> dict[str, Any]:
    """
    Create a Politically Exposed Person for risk testing.
    """
    async with neo4j_driver.session(database=TEST_NEO4J_DATABASE) as session:
        query = """
        CREATE (p:Person {
            person_id: 'TEST-PEP-001',
            full_name: 'Jane Politician',
            nationality: 'GBR',
            is_pep: true,
            pep_details: 'Former Cabinet Minister'
        })
        RETURN p {.*} AS person
        """
        result = await session.run(query)
        record = await result.single()
        return dict(record["person"]) if record else {}


# ============================================================================
# SAMPLE DATA FIXTURES - RELATIONSHIPS
# ============================================================================

@pytest_asyncio.fixture
async def sample_ownership(neo4j_driver: AsyncDriver) -> dict[str, Any]:
    """
    Create a simple ownership relationship (Person -> Entity).
    """
    async with neo4j_driver.session(database=TEST_NEO4J_DATABASE) as session:
        query = """
        CREATE (p:Person {
            person_id: 'TEST-PERSON-001',
            full_name: 'John Smith',
            nationality: 'USA',
            is_pep: false
        })
        CREATE (e:Entity {
            entity_id: 'TEST-ENTITY-001',
            name: 'Test Holdings Ltd',
            jurisdiction_code: 'BVI',
            entity_type: 'Company',
            status: 'Active'
        })
        CREATE (p)-[r:OWNS {
            ownership_percentage: 100.0,
            status: 'Active',
            is_nominee: false,
            acquisition_date: date('2015-03-15')
        }]->(e)
        RETURN {
            person: p {.*},
            entity: e {.*},
            relationship: {
                type: type(r),
                ownership_percentage: r.ownership_percentage,
                status: r.status
            }
        } AS data
        """
        result = await session.run(query)
        record = await result.single()
        return dict(record["data"]) if record else {}


@pytest_asyncio.fixture
async def sample_ownership_chain(neo4j_driver: AsyncDriver) -> dict[str, Any]:
    """
    Create a multi-hop ownership chain for path testing.
    
    Creates:
        Person -> Entity1 (75%) -> Entity2 (50%) -> Entity3 (100%)
    
    Effective ownership: 75% * 50% * 100% = 37.5%
    """
    async with neo4j_driver.session(database=TEST_NEO4J_DATABASE) as session:
        query = """
        // Create nodes
        CREATE (p:Person {
            person_id: 'TEST-PERSON-CHAIN-001',
            full_name: 'Chain Owner',
            nationality: 'CHE',
            is_pep: false
        })
        CREATE (e1:Entity {
            entity_id: 'TEST-CHAIN-001',
            name: 'Holding Company A',
            jurisdiction_code: 'CHE',
            entity_type: 'Company',
            status: 'Active'
        })
        CREATE (e2:Entity {
            entity_id: 'TEST-CHAIN-002',
            name: 'Intermediate B Ltd',
            jurisdiction_code: 'BVI',
            entity_type: 'Company',
            status: 'Active'
        })
        CREATE (e3:Entity {
            entity_id: 'TEST-CHAIN-003',
            name: 'Target Corp',
            jurisdiction_code: 'PAN',
            entity_type: 'Company',
            status: 'Active'
        })
        
        // Create ownership chain
        CREATE (p)-[r1:OWNS {ownership_percentage: 75.0, status: 'Active'}]->(e1)
        CREATE (e1)-[r2:OWNS {ownership_percentage: 50.0, status: 'Active'}]->(e2)
        CREATE (e2)-[r3:OWNS {ownership_percentage: 100.0, status: 'Active'}]->(e3)
        
        RETURN {
            person: p {.*},
            entities: [e1 {.*}, e2 {.*}, e3 {.*}],
            chain_length: 3,
            effective_ownership: 37.5
        } AS data
        """
        result = await session.run(query)
        record = await result.single()
        return dict(record["data"]) if record else {}


@pytest_asyncio.fixture
async def sample_complex_network(neo4j_driver: AsyncDriver) -> dict[str, Any]:
    """
    Create a complex ownership network for network analysis testing.
    
    Creates:
        - 2 Persons (one PEP)
        - 4 Entities across multiple jurisdictions
        - Multiple ownership relationships
        - Shared address (mass registration indicator)
    """
    async with neo4j_driver.session(database=TEST_NEO4J_DATABASE) as session:
        query = """
        // Create jurisdictions
        MERGE (j_bvi:Jurisdiction {jurisdiction_code: 'BVI', name: 'British Virgin Islands', is_tax_haven: true})
        MERGE (j_pan:Jurisdiction {jurisdiction_code: 'PAN', name: 'Panama', is_tax_haven: true})
        
        // Create shared address (red flag)
        CREATE (addr:Address {
            address_id: 'TEST-ADDR-001',
            full_address: '123 Offshore Plaza, Road Town, BVI',
            city: 'Road Town',
            country_code: 'VGB',
            is_nominee_address: true
        })
        
        // Create persons
        CREATE (p1:Person {
            person_id: 'TEST-NET-PERSON-001',
            full_name: 'Regular Investor',
            nationality: 'USA',
            is_pep: false
        })
        CREATE (p2:Person {
            person_id: 'TEST-NET-PEP-001',
            full_name: 'Political Figure',
            nationality: 'RUS',
            is_pep: true,
            pep_details: 'Government Official'
        })
        
        // Create entities
        CREATE (e1:Entity {
            entity_id: 'TEST-NET-001',
            name: 'Alpha Holdings',
            jurisdiction_code: 'BVI',
            entity_type: 'Company',
            status: 'Active',
            pagerank_score: 0.35,
            community_id: 1
        })
        CREATE (e2:Entity {
            entity_id: 'TEST-NET-002',
            name: 'Beta Investments',
            jurisdiction_code: 'BVI',
            entity_type: 'Company',
            status: 'Active',
            pagerank_score: 0.25,
            community_id: 1
        })
        CREATE (e3:Entity {
            entity_id: 'TEST-NET-003',
            name: 'Gamma Trust',
            jurisdiction_code: 'PAN',
            entity_type: 'Trust',
            status: 'Active',
            pagerank_score: 0.15,
            community_id: 1
        })
        CREATE (e4:Entity {
            entity_id: 'TEST-NET-004',
            name: 'Delta Corp',
            jurisdiction_code: 'PAN',
            entity_type: 'Company',
            status: 'Active',
            pagerank_score: 0.10,
            community_id: 2
        })
        
        // Create relationships
        CREATE (p1)-[:OWNS {ownership_percentage: 60.0, status: 'Active'}]->(e1)
        CREATE (p2)-[:OWNS {ownership_percentage: 40.0, status: 'Active'}]->(e1)
        CREATE (e1)-[:OWNS {ownership_percentage: 100.0, status: 'Active'}]->(e2)
        CREATE (e1)-[:OWNS {ownership_percentage: 75.0, status: 'Active'}]->(e3)
        CREATE (e2)-[:OWNS {ownership_percentage: 50.0, status: 'Active'}]->(e4)
        CREATE (e3)-[:OWNS {ownership_percentage: 50.0, status: 'Active'}]->(e4)
        
        // Create jurisdiction relationships
        CREATE (e1)-[:REGISTERED_IN]->(j_bvi)
        CREATE (e2)-[:REGISTERED_IN]->(j_bvi)
        CREATE (e3)-[:REGISTERED_IN]->(j_pan)
        CREATE (e4)-[:REGISTERED_IN]->(j_pan)
        
        // Create address relationships (shared address = red flag)
        CREATE (e1)-[:HAS_ADDRESS {address_type: 'Registered', is_primary: true}]->(addr)
        CREATE (e2)-[:HAS_ADDRESS {address_type: 'Registered', is_primary: true}]->(addr)
        
        RETURN {
            persons: [p1 {.*}, p2 {.*}],
            entities: [e1 {.*}, e2 {.*}, e3 {.*}, e4 {.*}],
            address: addr {.*},
            entity_count: 4,
            person_count: 2,
            relationship_count: 6,
            pep_involved: true
        } AS data
        """
        result = await session.run(query)
        record = await result.single()
        return dict(record["data"]) if record else {}


# ============================================================================
# SAMPLE DATA FIXTURES - INTERMEDIARIES
# ============================================================================

@pytest_asyncio.fixture
async def sample_intermediary(neo4j_driver: AsyncDriver) -> dict[str, Any]:
    """
    Create a sample intermediary (law firm/service provider).
    """
    async with neo4j_driver.session(database=TEST_NEO4J_DATABASE) as session:
        query = """
        CREATE (i:Intermediary {
            intermediary_id: 'TEST-INTER-001',
            name: 'Test Law Firm LLP',
            type: 'Law Firm',
            country_code: 'PAN',
            status: 'Active'
        })
        CREATE (e:Entity {
            entity_id: 'TEST-INTER-ENTITY-001',
            name: 'Client Company',
            jurisdiction_code: 'BVI',
            entity_type: 'Company',
            status: 'Active'
        })
        CREATE (e)-[:CREATED_BY {
            creation_date: date('2015-01-01'),
            relationship_status: 'Active'
        }]->(i)
        RETURN {
            intermediary: i {.*},
            entity: e {.*}
        } AS data
        """
        result = await session.run(query)
        record = await result.single()
        return dict(record["data"]) if record else {}


# ============================================================================
# DATABASE SCHEMA FIXTURES
# ============================================================================

@pytest_asyncio.fixture
async def setup_schema(neo4j_driver: AsyncDriver) -> None:
    """
    Set up database schema (constraints and indexes) for testing.
    
    This fixture should be used when testing schema-dependent functionality.
    """
    async with neo4j_driver.session(database=TEST_NEO4J_DATABASE) as session:
        # Create constraints (idempotent with IF NOT EXISTS)
        constraints = [
            "CREATE CONSTRAINT test_entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",
            "CREATE CONSTRAINT test_person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.person_id IS UNIQUE",
            "CREATE CONSTRAINT test_intermediary_id IF NOT EXISTS FOR (i:Intermediary) REQUIRE i.intermediary_id IS UNIQUE",
        ]
        
        for constraint in constraints:
            try:
                await session.run(constraint)
            except Exception:
                pass  # Constraint may already exist
        
        # Create indexes
        indexes = [
            "CREATE INDEX test_entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)",
            "CREATE INDEX test_entity_jurisdiction IF NOT EXISTS FOR (e:Entity) ON (e.jurisdiction_code)",
            "CREATE INDEX test_person_name IF NOT EXISTS FOR (p:Person) ON (p.full_name)",
        ]
        
        for index in indexes:
            try:
                await session.run(index)
            except Exception:
                pass


# ============================================================================
# UTILITY FIXTURES
# ============================================================================

@pytest_asyncio.fixture
async def clear_test_data(neo4j_driver: AsyncDriver) -> AsyncGenerator[None, None]:
    """
    Fixture that clears test data before and after the test.
    
    Use this explicitly when you need guaranteed clean state.
    """
    # Pre-test cleanup
    async with neo4j_driver.session(database=TEST_NEO4J_DATABASE) as session:
        await session.run("MATCH (n) WHERE n.entity_id STARTS WITH 'TEST-' DETACH DELETE n")
        await session.run("MATCH (n) WHERE n.person_id STARTS WITH 'TEST-' DETACH DELETE n")
    
    yield
    
    # Post-test cleanup
    async with neo4j_driver.session(database=TEST_NEO4J_DATABASE) as session:
        await session.run("MATCH (n) WHERE n.entity_id STARTS WITH 'TEST-' DETACH DELETE n")
        await session.run("MATCH (n) WHERE n.person_id STARTS WITH 'TEST-' DETACH DELETE n")


@pytest.fixture
def mock_neo4j_session() -> MagicMock:
    """
    Create a mock Neo4j session for unit testing.
    
    Returns a MagicMock configured to behave like AsyncSession.
    """
    mock_session = MagicMock(spec=AsyncSession)
    
    # Configure async methods
    mock_result = AsyncMock()
    mock_result.single = AsyncMock(return_value=None)
    mock_result.fetch = AsyncMock(return_value=[])
    mock_result.data = AsyncMock(return_value=[])
    
    mock_session.run = AsyncMock(return_value=mock_result)
    mock_session.close = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    
    return mock_session


# ============================================================================
# TEST DATA GENERATORS
# ============================================================================

@pytest.fixture
def entity_data_factory():
    """
    Factory fixture for generating entity test data.
    
    Usage:
        def test_something(entity_data_factory):
            entity = entity_data_factory(name="Custom Name")
    """
    def _factory(
        entity_id: str = "TEST-FACTORY-001",
        name: str = "Factory Entity",
        jurisdiction_code: str = "BVI",
        entity_type: str = "Company",
        status: str = "Active",
        **kwargs,
    ) -> dict[str, Any]:
        return {
            "entity_id": entity_id,
            "name": name,
            "jurisdiction_code": jurisdiction_code,
            "entity_type": entity_type,
            "status": status,
            **kwargs,
        }
    
    return _factory


@pytest.fixture
def person_data_factory():
    """
    Factory fixture for generating person test data.
    """
    def _factory(
        person_id: str = "TEST-PERSON-FACTORY-001",
        full_name: str = "Test Person",
        nationality: str = "USA",
        is_pep: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        return {
            "person_id": person_id,
            "full_name": full_name,
            "nationality": nationality,
            "is_pep": is_pep,
            **kwargs,
        }
    
    return _factory


# ============================================================================
# EXPORTED FIXTURES
# ============================================================================

__all__ = [
    # Event loop
    "event_loop",
    "event_loop_policy",
    
    # Database
    "neo4j_driver",
    "neo4j_driver_session",
    "neo4j_session",
    "setup_schema",
    "clear_test_data",
    
    # Application
    "app_instance",
    "async_client",
    "async_client_no_db",
    
    # Sample entities
    "sample_entity",
    "sample_entities",
    "sample_entity_with_jurisdiction",
    
    # Sample persons
    "sample_person",
    "sample_pep",
    
    # Sample relationships
    "sample_ownership",
    "sample_ownership_chain",
    "sample_complex_network",
    
    # Sample intermediaries
    "sample_intermediary",
    
    # Utilities
    "mock_neo4j_session",
    "entity_data_factory",
    "person_data_factory",
]
