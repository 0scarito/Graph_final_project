"""
Panama Papers API - Neo4j Database Connection Management
=========================================================

Async Neo4j driver wrapper for FastAPI application.

Features:
    - Async connection with connection pooling
    - Retry logic with exponential backoff
    - Session and transaction management
    - Health check functionality
    - Query execution helpers

Usage:
    from database import Neo4jDatabase, get_db_session, run_query
    
    # In FastAPI lifespan
    async with lifespan(app):
        await Neo4jDatabase.init()
    
    # In route handlers
    @app.get("/entities")
    async def get_entities(session: AsyncSession = Depends(get_db_session)):
        result = await session.run("MATCH (e:Entity) RETURN e LIMIT 10")
        return await result.data()

Environment Variables:
    NEO4J_URI: Bolt URI (default: bolt://localhost:7687)
    NEO4J_USER: Username (default: neo4j)
    NEO4J_PASSWORD: Password (required)
    NEO4J_DATABASE: Database name (default: neo4j)
    NEO4J_MAX_POOL_SIZE: Connection pool size (default: 50)

Python Version: 3.11+
Neo4j Driver: 5.x
"""

from __future__ import annotations

import asyncio
import os
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Optional,
    ParamSpec,
    TypeVar,
)

from dotenv import load_dotenv
from neo4j import (
    AsyncGraphDatabase,
    AsyncDriver,
    AsyncSession,
    AsyncTransaction,
    AsyncManagedTransaction,
    Query,
)
from neo4j.exceptions import (
    ServiceUnavailable,
    SessionExpired,
    TransientError,
    AuthError,
    DriverError,
    Neo4jError,
    ClientError,
)

# Load environment variables
load_dotenv()

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass(frozen=True)
class Neo4jConfig:
    """Neo4j connection configuration."""
    
    uri: str = field(
        default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687")
    )
    user: str = field(
        default_factory=lambda: os.getenv("NEO4J_USER", "neo4j")
    )
    password: str = field(
        default_factory=lambda: os.getenv("NEO4J_PASSWORD", "")
    )
    database: str = field(
        default_factory=lambda: os.getenv("NEO4J_DATABASE", "neo4j")
    )
    max_pool_size: int = field(
        default_factory=lambda: int(os.getenv("NEO4J_MAX_POOL_SIZE", "50"))
    )
    connection_timeout: float = field(
        default_factory=lambda: float(os.getenv("NEO4J_CONNECTION_TIMEOUT", "30"))
    )
    max_transaction_retry_time: float = field(
        default_factory=lambda: float(os.getenv("NEO4J_MAX_RETRY_TIME", "30"))
    )
    connection_acquisition_timeout: float = field(
        default_factory=lambda: float(os.getenv("NEO4J_ACQUISITION_TIMEOUT", "60"))
    )
    
    def validate(self) -> None:
        """Validate configuration."""
        if not self.password:
            raise ValueError(
                "NEO4J_PASSWORD environment variable is required. "
                "Set it in your .env file or environment."
            )
        if not self.uri.startswith(("bolt://", "bolt+s://", "neo4j://", "neo4j+s://")):
            raise ValueError(
                f"Invalid NEO4J_URI scheme: {self.uri}. "
                "Must start with bolt://, bolt+s://, neo4j://, or neo4j+s://"
            )


# Global configuration instance
config = Neo4jConfig()

# ============================================================================
# RETRY DECORATOR
# ============================================================================

P = ParamSpec("P")
T = TypeVar("T")


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (
        ServiceUnavailable,
        SessionExpired,
        TransientError,
    ),
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """
    Decorator for retry logic with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exponential_base: Base for exponential backoff calculation
        retryable_exceptions: Tuple of exceptions to retry on
    
    Returns:
        Decorated async function with retry logic
    """
    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Optional[Exception] = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                    
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}: {e}"
                        )
                        raise
                    
                    # Calculate delay with exponential backoff and jitter
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    # Add jitter (±25%)
                    import random
                    delay *= (0.75 + random.random() * 0.5)
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry loop exit")
        
        return wrapper
    return decorator


# ============================================================================
# NEO4J DATABASE CLASS
# ============================================================================

class Neo4jDatabase:
    """
    Async Neo4j database connection manager.
    
    Singleton pattern for managing a single driver instance across
    the application lifecycle.
    
    Usage:
        # Initialize during app startup
        await Neo4jDatabase.init()
        
        # Use in request handlers
        async with Neo4jDatabase.session() as session:
            result = await session.run("MATCH (n) RETURN n LIMIT 10")
            data = await result.data()
        
        # Cleanup during app shutdown
        await Neo4jDatabase.close()
    """
    
    _driver: Optional[AsyncDriver] = None
    _config: Optional[Neo4jConfig] = None
    _initialized: bool = False
    _init_time: Optional[datetime] = None
    
    @classmethod
    async def init(cls, config: Optional[Neo4jConfig] = None) -> None:
        """
        Initialize the Neo4j driver.
        
        Args:
            config: Optional configuration override
        
        Raises:
            ValueError: If configuration is invalid
            ServiceUnavailable: If Neo4j is not reachable
            AuthError: If authentication fails
        """
        if cls._initialized and cls._driver:
            logger.warning("Neo4j driver already initialized, skipping")
            return
        
        cls._config = config or Neo4jConfig()
        cls._config.validate()
        
        logger.info(f"Initializing Neo4j driver for {cls._config.uri}...")
        
        try:
            cls._driver = AsyncGraphDatabase.driver(
                cls._config.uri,
                auth=(cls._config.user, cls._config.password),
                max_connection_pool_size=cls._config.max_pool_size,
                connection_timeout=cls._config.connection_timeout,
                max_transaction_retry_time=cls._config.max_transaction_retry_time,
                connection_acquisition_timeout=cls._config.connection_acquisition_timeout,
            )
            
            # Verify connectivity
            await cls._driver.verify_connectivity()
            
            # Get server info
            server_info = await cls._get_server_info()
            
            cls._initialized = True
            cls._init_time = datetime.utcnow()
            
            logger.info(
                f"✓ Neo4j driver initialized successfully\n"
                f"  URI: {cls._config.uri}\n"
                f"  Database: {cls._config.database}\n"
                f"  Pool Size: {cls._config.max_pool_size}\n"
                f"  Server: {server_info.get('version', 'unknown')}"
            )
            
        except AuthError as e:
            logger.error(f"✗ Neo4j authentication failed: {e}")
            raise
        except ServiceUnavailable as e:
            logger.error(f"✗ Neo4j service unavailable at {cls._config.uri}: {e}")
            raise
        except Exception as e:
            logger.error(f"✗ Neo4j driver initialization failed: {e}")
            raise
    
    @classmethod
    async def _get_server_info(cls) -> dict[str, Any]:
        """Get Neo4j server information."""
        try:
            async with cls._driver.session(database=cls._config.database) as session:
                result = await session.run(
                    "CALL dbms.components() YIELD name, versions, edition "
                    "RETURN name, versions[0] AS version, edition"
                )
                record = await result.single()
                return {
                    "name": record["name"],
                    "version": record["version"],
                    "edition": record["edition"],
                } if record else {}
        except Exception as e:
            logger.warning(f"Could not retrieve server info: {e}")
            return {}
    
    @classmethod
    async def close(cls) -> None:
        """
        Close the Neo4j driver and release all resources.
        
        Should be called during application shutdown.
        """
        if cls._driver:
            await cls._driver.close()
            cls._driver = None
            cls._initialized = False
            logger.info("✓ Neo4j driver closed")
        else:
            logger.warning("Neo4j driver was not initialized or already closed")
    
    @classmethod
    def get_driver(cls) -> AsyncDriver:
        """
        Get the active driver instance.
        
        Returns:
            AsyncDriver instance
        
        Raises:
            RuntimeError: If driver is not initialized
        """
        if not cls._driver or not cls._initialized:
            raise RuntimeError(
                "Neo4j driver not initialized. "
                "Call 'await Neo4jDatabase.init()' first."
            )
        return cls._driver
    
    @classmethod
    def is_initialized(cls) -> bool:
        """Check if driver is initialized."""
        return cls._initialized and cls._driver is not None
    
    @classmethod
    def get_config(cls) -> Optional[Neo4jConfig]:
        """Get current configuration."""
        return cls._config
    
    @classmethod
    def get_uptime(cls) -> Optional[float]:
        """Get driver uptime in seconds."""
        if cls._init_time:
            return (datetime.utcnow() - cls._init_time).total_seconds()
        return None
    
    @classmethod
    @asynccontextmanager
    async def session(
        cls,
        database: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[AsyncSession, None]:
        """
        Get an async session context manager.
        
        Args:
            database: Optional database name override
            **kwargs: Additional session configuration
        
        Yields:
            AsyncSession instance
        
        Usage:
            async with Neo4jDatabase.session() as session:
                result = await session.run("MATCH (n) RETURN n")
        """
        driver = cls.get_driver()
        db = database or cls._config.database
        session = driver.session(database=db, **kwargs)
        
        try:
            yield session
        finally:
            await session.close()
    
    @classmethod
    @asynccontextmanager
    async def transaction(
        cls,
        database: Optional[str] = None,
    ) -> AsyncGenerator[AsyncTransaction, None]:
        """
        Get an explicit transaction context manager.
        
        Automatically commits on success, rolls back on exception.
        
        Args:
            database: Optional database name override
        
        Yields:
            AsyncTransaction instance
        
        Usage:
            async with Neo4jDatabase.transaction() as tx:
                await tx.run("CREATE (n:Node {name: $name})", name="Test")
                await tx.run("CREATE (m:Node {name: $name})", name="Test2")
                # Auto-commits if no exception
        """
        async with cls.session(database=database) as session:
            tx = await session.begin_transaction()
            try:
                yield tx
                await tx.commit()
            except Exception:
                await tx.rollback()
                raise
            finally:
                if tx.closed() is False:
                    await tx.close()


# ============================================================================
# FASTAPI DEPENDENCIES
# ============================================================================

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for Neo4j session injection.
    
    Usage:
        @app.get("/entities")
        async def get_entities(session: AsyncSession = Depends(get_db_session)):
            result = await session.run("MATCH (e:Entity) RETURN e LIMIT 10")
            return await result.data()
    """
    async with Neo4jDatabase.session() as session:
        yield session


async def get_db_driver() -> AsyncDriver:
    """
    FastAPI dependency for Neo4j driver injection.
    
    Use when you need direct driver access (e.g., for multiple sessions).
    """
    return Neo4jDatabase.get_driver()


# ============================================================================
# HEALTH CHECK
# ============================================================================

@dataclass
class HealthCheckResult:
    """Health check result structure."""
    
    status: str  # "healthy", "degraded", "unhealthy"
    neo4j_connected: bool
    neo4j_version: Optional[str] = None
    neo4j_edition: Optional[str] = None
    database: Optional[str] = None
    gds_available: Optional[bool] = None
    gds_version: Optional[str] = None
    latency_ms: Optional[float] = None
    uptime_seconds: Optional[float] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status,
            "neo4j_connected": self.neo4j_connected,
            "neo4j_version": self.neo4j_version,
            "neo4j_edition": self.neo4j_edition,
            "database": self.database,
            "gds_available": self.gds_available,
            "gds_version": self.gds_version,
            "latency_ms": self.latency_ms,
            "uptime_seconds": self.uptime_seconds,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


async def health_check(detailed: bool = True) -> HealthCheckResult:
    """
    Perform Neo4j health check.
    
    Args:
        detailed: Include detailed server information
    
    Returns:
        HealthCheckResult with connection status and server info
    """
    import time
    start_time = time.perf_counter()
    
    try:
        if not Neo4jDatabase.is_initialized():
            return HealthCheckResult(
                status="unhealthy",
                neo4j_connected=False,
                error="Neo4j driver not initialized",
            )
        
        driver = Neo4jDatabase.get_driver()
        config = Neo4jDatabase.get_config()
        
        async with driver.session(database=config.database) as session:
            # Basic connectivity check
            result = await session.run("RETURN 1 AS healthcheck")
            record = await result.single()
            
            if not record or record["healthcheck"] != 1:
                return HealthCheckResult(
                    status="unhealthy",
                    neo4j_connected=False,
                    error="Health check query returned unexpected result",
                )
            
            latency = (time.perf_counter() - start_time) * 1000
            
            if not detailed:
                return HealthCheckResult(
                    status="healthy",
                    neo4j_connected=True,
                    database=config.database,
                    latency_ms=round(latency, 2),
                    uptime_seconds=Neo4jDatabase.get_uptime(),
                )
            
            # Get detailed server info
            server_result = await session.run(
                "CALL dbms.components() YIELD name, versions, edition "
                "RETURN name, versions[0] AS version, edition"
            )
            server_record = await server_result.single()
            
            # Check GDS availability
            gds_available = False
            gds_version = None
            try:
                gds_result = await session.run("RETURN gds.version() AS version")
                gds_record = await gds_result.single()
                if gds_record:
                    gds_available = True
                    gds_version = gds_record["version"]
            except (ClientError, Neo4jError):
                pass  # GDS not installed
            
            return HealthCheckResult(
                status="healthy",
                neo4j_connected=True,
                neo4j_version=server_record["version"] if server_record else None,
                neo4j_edition=server_record["edition"] if server_record else None,
                database=config.database,
                gds_available=gds_available,
                gds_version=gds_version,
                latency_ms=round(latency, 2),
                uptime_seconds=Neo4jDatabase.get_uptime(),
            )
            
    except ServiceUnavailable as e:
        return HealthCheckResult(
            status="unhealthy",
            neo4j_connected=False,
            error=f"Service unavailable: {e}",
        )
    except AuthError as e:
        return HealthCheckResult(
            status="unhealthy",
            neo4j_connected=False,
            error=f"Authentication failed: {e}",
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheckResult(
            status="unhealthy",
            neo4j_connected=False,
            error=str(e),
        )


# ============================================================================
# QUERY EXECUTION HELPERS
# ============================================================================

@with_retry(max_retries=3, base_delay=1.0)
async def run_query(
    query: str,
    params: Optional[dict[str, Any]] = None,
    database: Optional[str] = None,
    fetch_size: int = 1000,
) -> list[dict[str, Any]]:
    """
    Execute a read-only Cypher query.
    
    Args:
        query: Cypher query string
        params: Query parameters (optional)
        database: Database name override (optional)
        fetch_size: Number of records to fetch at once
    
    Returns:
        List of record dictionaries
    
    Example:
        results = await run_query(
            "MATCH (e:Entity) WHERE e.status = $status RETURN e LIMIT 100",
            params={"status": "Active"}
        )
    """
    params = params or {}
    
    async with Neo4jDatabase.session(database=database) as session:
        result = await session.run(query, params)
        records = await result.fetch(fetch_size)
        return [record.data() for record in records]


@with_retry(max_retries=3, base_delay=1.0)
async def run_query_single(
    query: str,
    params: Optional[dict[str, Any]] = None,
    database: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Execute a query expecting a single result.
    
    Args:
        query: Cypher query string
        params: Query parameters (optional)
        database: Database name override (optional)
    
    Returns:
        Single record dictionary or None
    """
    params = params or {}
    
    async with Neo4jDatabase.session(database=database) as session:
        result = await session.run(query, params)
        record = await result.single()
        return record.data() if record else None


@with_retry(max_retries=3, base_delay=1.0)
async def run_write(
    query: str,
    params: Optional[dict[str, Any]] = None,
    database: Optional[str] = None,
) -> dict[str, Any]:
    """
    Execute a write query within an auto-commit transaction.
    
    Args:
        query: Cypher write query string
        params: Query parameters (optional)
        database: Database name override (optional)
    
    Returns:
        Dictionary with query counters:
        - nodes_created
        - nodes_deleted
        - relationships_created
        - relationships_deleted
        - properties_set
        - labels_added
        - labels_removed
    
    Example:
        result = await run_write(
            "CREATE (e:Entity {entity_id: $id, name: $name})",
            params={"id": "ENT-001", "name": "Acme Holdings"}
        )
        print(f"Created {result['nodes_created']} nodes")
    """
    params = params or {}
    
    async with Neo4jDatabase.session(database=database) as session:
        result = await session.run(query, params)
        summary = await result.consume()
        
        counters = summary.counters
        return {
            "nodes_created": counters.nodes_created,
            "nodes_deleted": counters.nodes_deleted,
            "relationships_created": counters.relationships_created,
            "relationships_deleted": counters.relationships_deleted,
            "properties_set": counters.properties_set,
            "labels_added": counters.labels_added,
            "labels_removed": counters.labels_removed,
            "indexes_added": counters.indexes_added,
            "indexes_removed": counters.indexes_removed,
            "constraints_added": counters.constraints_added,
            "constraints_removed": counters.constraints_removed,
        }


async def run_transaction(
    queries: list[tuple[str, Optional[dict[str, Any]]]],
    database: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Execute multiple queries within a single transaction.
    
    All queries succeed or all are rolled back.
    
    Args:
        queries: List of (query_string, params) tuples
        database: Database name override (optional)
    
    Returns:
        List of result dictionaries (one per query)
    
    Example:
        results = await run_transaction([
            ("CREATE (a:Entity {id: $id1})", {"id1": "E1"}),
            ("CREATE (b:Entity {id: $id2})", {"id2": "E2"}),
            ("MATCH (a:Entity {id: $id1}), (b:Entity {id: $id2}) "
             "CREATE (a)-[:OWNS]->(b)", {"id1": "E1", "id2": "E2"}),
        ])
    """
    results = []
    
    async with Neo4jDatabase.transaction(database=database) as tx:
        for query, params in queries:
            params = params or {}
            result = await tx.run(query, params)
            summary = await result.consume()
            results.append({
                "query": query[:100] + "..." if len(query) > 100 else query,
                "nodes_created": summary.counters.nodes_created,
                "relationships_created": summary.counters.relationships_created,
            })
    
    return results


async def run_read_transaction(
    work: Callable[[AsyncManagedTransaction], Awaitable[T]],
    database: Optional[str] = None,
) -> T:
    """
    Execute a read transaction with automatic retry.
    
    Uses Neo4j's managed transaction pattern for automatic
    retry on transient errors.
    
    Args:
        work: Async function that receives transaction and returns result
        database: Database name override (optional)
    
    Returns:
        Result from work function
    
    Example:
        async def get_entities(tx: AsyncManagedTransaction):
            result = await tx.run("MATCH (e:Entity) RETURN e LIMIT 10")
            return await result.data()
        
        entities = await run_read_transaction(get_entities)
    """
    async with Neo4jDatabase.session(database=database) as session:
        return await session.execute_read(work)


async def run_write_transaction(
    work: Callable[[AsyncManagedTransaction], Awaitable[T]],
    database: Optional[str] = None,
) -> T:
    """
    Execute a write transaction with automatic retry.
    
    Uses Neo4j's managed transaction pattern for automatic
    retry on transient errors.
    
    Args:
        work: Async function that receives transaction and returns result
        database: Database name override (optional)
    
    Returns:
        Result from work function
    
    Example:
        async def create_entity(tx: AsyncManagedTransaction):
            result = await tx.run(
                "CREATE (e:Entity {id: $id, name: $name}) RETURN e",
                id="E1", name="Test"
            )
            return await result.single()
        
        entity = await run_write_transaction(create_entity)
    """
    async with Neo4jDatabase.session(database=database) as session:
        return await session.execute_write(work)


# ============================================================================
# FASTAPI LIFESPAN INTEGRATION
# ============================================================================

@asynccontextmanager
async def neo4j_lifespan(app: Any) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager for Neo4j.
    
    Usage:
        from fastapi import FastAPI
        from database import neo4j_lifespan
        
        app = FastAPI(lifespan=neo4j_lifespan)
    """
    # Startup
    await Neo4jDatabase.init()
    
    yield
    
    # Shutdown
    await Neo4jDatabase.close()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def cypher_escape(value: str) -> str:
    """
    Escape a string for safe use in Cypher queries.
    
    Note: Always prefer parameterized queries over string escaping.
    This is provided for edge cases only.
    """
    return value.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


def build_match_clause(
    label: str,
    filters: dict[str, Any],
    alias: str = "n",
) -> tuple[str, dict[str, Any]]:
    """
    Build a MATCH clause with WHERE conditions.
    
    Args:
        label: Node label
        filters: Property filters (key-value pairs)
        alias: Node alias in query
    
    Returns:
        Tuple of (query_fragment, parameters)
    
    Example:
        clause, params = build_match_clause(
            "Entity",
            {"status": "Active", "jurisdiction": "BVI"},
            alias="e"
        )
        # Returns: ("MATCH (e:Entity) WHERE e.status = $status AND e.jurisdiction = $jurisdiction", {...})
    """
    where_parts = []
    params = {}
    
    for key, value in filters.items():
        if value is not None:
            param_name = f"filter_{key}"
            where_parts.append(f"{alias}.{key} = ${param_name}")
            params[param_name] = value
    
    query = f"MATCH ({alias}:{label})"
    if where_parts:
        query += " WHERE " + " AND ".join(where_parts)
    
    return query, params


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Configuration
    "Neo4jConfig",
    "config",
    
    # Main database class
    "Neo4jDatabase",
    
    # FastAPI dependencies
    "get_db_session",
    "get_db_driver",
    
    # Health check
    "HealthCheckResult",
    "health_check",
    
    # Query helpers
    "run_query",
    "run_query_single",
    "run_write",
    "run_transaction",
    "run_read_transaction",
    "run_write_transaction",
    
    # FastAPI integration
    "neo4j_lifespan",
    
    # Utilities
    "cypher_escape",
    "build_match_clause",
    "with_retry",
]
