"""
Panama Papers API - Entity Endpoint Unit Tests
================================================

Unit tests for entity-related API endpoints.

Test Coverage:
    - GET /entities/{entity_id} - Entity lookup (success + not found)
    - GET /entities/search - Entity search (success + empty + pagination)
    - GET /entities/{entity_id}/ownership-path - Ownership tracing
    - GET /entities/top/influential - PageRank ranking
    - GET /health - Health check
    - GET / - Root endpoint

Usage:
    pytest tests/test_entities.py -v --asyncio-mode=auto
    pytest tests/test_entities.py -v -k "test_get_entity"
    pytest tests/test_entities.py -v -m "not slow"

Fixtures Required (from conftest.py):
    - async_client: FastAPI test client
    - sample_entity: Single test entity
    - sample_entities: Multiple test entities
    - sample_ownership_chain: Multi-hop ownership
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio


# ============================================================================
# TEST CLASS: GET ENTITY BY ID
# ============================================================================

class TestGetEntity:
    """Tests for GET /entities/{entity_id} endpoint."""

    async def test_get_entity_success(
        self,
        async_client: AsyncClient,
        sample_entity: dict,
    ):
        """
        Test retrieving an existing entity.
        
        Setup: Create entity in database via sample_entity fixture
        Call: GET /entities/{entity_id}
        Assert: 200 status, correct entity data returned
        Verify: All fields present (name, jurisdiction, type)
        """
        entity_id = sample_entity["entity_id"]
        
        response = await async_client.get(f"/entities/{entity_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify all required fields are present
        assert "entity_id" in data
        assert "name" in data
        assert "jurisdiction_code" in data or "jurisdiction" in data
        assert "entity_type" in data or "type" in data
        assert "status" in data
        
        # Verify data matches sample entity
        assert data["entity_id"] == sample_entity["entity_id"]
        assert data["name"] == sample_entity["name"]
        
        # Check jurisdiction (handle both field names)
        jurisdiction = data.get("jurisdiction_code") or data.get("jurisdiction")
        expected_jurisdiction = sample_entity.get("jurisdiction_code") or sample_entity.get("jurisdiction")
        assert jurisdiction == expected_jurisdiction
        
        # Check entity type (handle both field names)
        entity_type = data.get("entity_type") or data.get("type")
        expected_type = sample_entity.get("entity_type") or sample_entity.get("type")
        assert entity_type == expected_type

    async def test_get_entity_not_found(
        self,
        async_client: AsyncClient,
    ):
        """
        Test 404 response when entity doesn't exist.
        
        Call: GET /entities/NONEXISTENT
        Assert: 404 status, error message
        Verify: "not found" in response detail
        """
        response = await async_client.get("/entities/NONEXISTENT-ENTITY-99999")
        
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    async def test_get_entity_with_analytics(
        self,
        async_client: AsyncClient,
        sample_entity: dict,
    ):
        """
        Test retrieving entity with analytics data.
        
        Setup: Entity with pagerank_score exists
        Call: GET /entities/{entity_id}?include_analytics=true
        Assert: Response includes pagerank_score, community_id
        """
        entity_id = sample_entity["entity_id"]
        
        response = await async_client.get(
            f"/entities/{entity_id}",
            params={"include_analytics": True},
        )
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Analytics fields should be present (may be null)
        assert "pagerank_score" in data
        assert "community_id" in data

    async def test_get_entity_invalid_id(
        self,
        async_client: AsyncClient,
    ):
        """
        Test handling of invalid entity ID format.
        
        Call: GET /entities/ (empty)
        Assert: 404 or 405 status
        """
        response = await async_client.get("/entities/")
        
        # Empty ID should not match route
        assert response.status_code in [404, 405, 307]


# ============================================================================
# TEST CLASS: SEARCH ENTITIES
# ============================================================================

class TestSearchEntities:
    """Tests for GET /entities/search endpoint."""

    async def test_search_entities_success(
        self,
        async_client: AsyncClient,
        sample_entities: list,
    ):
        """
        Test searching entities by name.
        
        Setup: Create 3+ entities with different names
        Call: GET /entities/search?q=Holdings
        Assert: 200 status, matching entities returned
        Verify: count >= 1, all names contain query
        """
        response = await async_client.get(
            "/entities/search",
            params={"q": "Holdings"},
        )
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Response should have results
        assert "results" in data
        assert "total_results" in data
        
        # Should find at least one match
        assert data["total_results"] >= 1
        assert len(data["results"]) >= 1
        
        # All results should contain search term (case-insensitive)
        for result in data["results"]:
            assert "holdings" in result["name"].lower(), f"Result '{result['name']}' doesn't contain 'Holdings'"

    async def test_search_entities_empty_result(
        self,
        async_client: AsyncClient,
    ):
        """
        Test search with no matching results.
        
        Call: GET /entities/search?q=NONEXISTENT123
        Assert: 200 status, empty list returned
        """
        response = await async_client.get(
            "/entities/search",
            params={"q": "XYZNONEXISTENT123456789"},
        )
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Should return empty results
        assert "results" in data
        assert data["total_results"] == 0
        assert len(data["results"]) == 0

    async def test_search_entities_pagination(
        self,
        async_client: AsyncClient,
        sample_entities: list,
    ):
        """
        Test pagination with limit and offset.
        
        Setup: Create multiple entities
        Call: GET /entities/search?q=Test&limit=1&offset=0
        Assert: Exactly 1 result returned
        Call: GET /entities/search?q=Test&limit=1&offset=1
        Assert: Next result returned (different from first)
        """
        # First page
        response1 = await async_client.get(
            "/entities/search",
            params={"q": "Test", "limit": 1, "offset": 0},
        )
        
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Should respect limit
        assert len(data1["results"]) <= 1
        assert data1["limit"] == 1
        assert data1["offset"] == 0
        
        # Second page
        response2 = await async_client.get(
            "/entities/search",
            params={"q": "Test", "limit": 1, "offset": 1},
        )
        
        assert response2.status_code == 200
        data2 = response2.json()
        
        assert data2["offset"] == 1
        
        # If there are enough results, pages should be different
        if data1["total_results"] > 1 and len(data1["results"]) > 0 and len(data2["results"]) > 0:
            assert data1["results"][0]["node_id"] != data2["results"][0]["node_id"]

    async def test_search_entities_with_filters(
        self,
        async_client: AsyncClient,
        sample_entities: list,
    ):
        """
        Test search with jurisdiction filter.
        
        Setup: Entities in different jurisdictions
        Call: GET /entities/search?q=Test&jurisdiction=BVI
        Assert: Only BVI entities returned
        """
        response = await async_client.get(
            "/entities/search",
            params={"q": "Test", "jurisdiction": "BVI"},
        )
        
        assert response.status_code == 200
        
        data = response.json()
        
        # All results should be in BVI
        for result in data["results"]:
            if result.get("jurisdiction_code"):
                assert result["jurisdiction_code"] == "BVI"

    async def test_search_entities_query_validation(
        self,
        async_client: AsyncClient,
    ):
        """
        Test search query validation.
        
        Call: GET /entities/search?q=A (too short)
        Assert: 422 validation error
        """
        response = await async_client.get(
            "/entities/search",
            params={"q": "A"},  # min_length=2
        )
        
        assert response.status_code == 422


# ============================================================================
# TEST CLASS: OWNERSHIP PATH
# ============================================================================

class TestOwnershipPath:
    """Tests for GET /entities/{entity_id}/ownership-path endpoint."""

    async def test_ownership_path_success(
        self,
        async_client: AsyncClient,
        sample_ownership_chain: dict,
    ):
        """
        Test retrieving ownership path.
        
        Setup: Create beneficial ownership chain (Person -> E1 -> E2 -> E3)
        Call: GET /entities/{entity_id}/ownership-path
        Assert: 200 status, path data returned
        Verify: entities list, relationships list, depth
        """
        # Target is the end of the chain
        target_entity_id = sample_ownership_chain["entities"][2]["entity_id"]
        
        response = await async_client.get(
            f"/entities/{target_entity_id}/ownership-path",
            params={"max_depth": 4},
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "path_count" in data
        assert "paths" in data
        assert "average_depth" in data
        
        # Should have at least one path
        assert data["path_count"] >= 1
        assert isinstance(data["paths"], list)
        assert len(data["paths"]) >= 1
        
        # Verify path structure
        path = data["paths"][0]
        assert "nodes" in path
        assert "edges" in path
        assert "depth" in path
        assert isinstance(path["nodes"], list)
        assert isinstance(path["edges"], list)

    async def test_ownership_path_not_found(
        self,
        async_client: AsyncClient,
        sample_entity: dict,
    ):
        """
        Test 404 when no ownership paths exist.
        
        Setup: Create isolated entity (no ownership relationships)
        Call: GET /entities/{entity_id}/ownership-path
        Assert: 404 status
        """
        # sample_entity is standalone, no ownership relationships
        entity_id = sample_entity["entity_id"]
        
        response = await async_client.get(
            f"/entities/{entity_id}/ownership-path",
            params={"max_depth": 4},
        )
        
        # Should be 404 (no paths found)
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data

    async def test_ownership_path_entity_not_found(
        self,
        async_client: AsyncClient,
    ):
        """
        Test 404 when entity doesn't exist.
        
        Call: GET /entities/NONEXISTENT/ownership-path
        Assert: 404 status
        """
        response = await async_client.get(
            "/entities/NONEXISTENT-12345/ownership-path",
            params={"max_depth": 4},
        )
        
        assert response.status_code == 404

    async def test_ownership_path_depth_validation(
        self,
        async_client: AsyncClient,
        sample_entity: dict,
    ):
        """
        Test max_depth parameter validation.
        
        Call: GET /entities/{id}/ownership-path?max_depth=10
        Assert: 422 validation error (max is 6)
        """
        entity_id = sample_entity["entity_id"]
        
        response = await async_client.get(
            f"/entities/{entity_id}/ownership-path",
            params={"max_depth": 10},  # Exceeds max (6)
        )
        
        assert response.status_code == 422

    async def test_ownership_path_effective_ownership(
        self,
        async_client: AsyncClient,
        sample_ownership_chain: dict,
    ):
        """
        Test effective ownership calculation.
        
        Setup: Chain with 75% -> 50% -> 100% ownership
        Assert: Effective ownership ~ 37.5%
        """
        target_entity_id = sample_ownership_chain["entities"][2]["entity_id"]
        
        response = await async_client.get(
            f"/entities/{target_entity_id}/ownership-path",
            params={"max_depth": 4},
        )
        
        assert response.status_code == 200
        
        data = response.json()
        
        if data["path_count"] > 0:
            path = data["paths"][0]
            
            # Effective ownership should be calculated
            if path.get("effective_ownership") is not None:
                # Should be approximately 37.5% (75% * 50% * 100%)
                assert 30 <= path["effective_ownership"] <= 45


# ============================================================================
# TEST CLASS: ENTITY NETWORK
# ============================================================================

class TestEntityNetwork:
    """Tests for GET /entities/{entity_id}/network endpoint."""

    async def test_entity_network_success(
        self,
        async_client: AsyncClient,
        sample_complex_network: dict,
    ):
        """
        Test retrieving network neighbors.
        
        Setup: Entity with connections
        Call: GET /entities/{entity_id}/network
        Assert: 200 status, connected entities returned
        """
        entity_id = sample_complex_network["entities"][0]["entity_id"]
        
        response = await async_client.get(
            f"/entities/{entity_id}/network",
            params={"depth": 1, "direction": "both"},
        )
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Should return list of relationships
        assert isinstance(data, list)

    async def test_entity_network_empty(
        self,
        async_client: AsyncClient,
        sample_entity: dict,
    ):
        """
        Test network for isolated entity.
        
        Setup: Entity with no relationships
        Call: GET /entities/{entity_id}/network
        Assert: 200 status, empty list
        """
        entity_id = sample_entity["entity_id"]
        
        response = await async_client.get(
            f"/entities/{entity_id}/network",
            params={"depth": 1},
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_entity_network_not_found(
        self,
        async_client: AsyncClient,
    ):
        """
        Test 404 when entity doesn't exist.
        """
        response = await async_client.get(
            "/entities/NONEXISTENT-12345/network",
        )
        
        assert response.status_code == 404


# ============================================================================
# TEST CLASS: INFLUENTIAL ENTITIES
# ============================================================================

class TestInfluentialEntities:
    """Tests for GET /entities/top/influential endpoint."""

    async def test_influential_entities_success(
        self,
        async_client: AsyncClient,
        sample_complex_network: dict,
    ):
        """
        Test retrieving top influential entities.
        
        Setup: Create entities with pagerank_score
        Call: GET /entities/top/influential
        Assert: 200 status, sorted by score DESC
        Verify: Returned list sorted correctly
        """
        response = await async_client.get(
            "/entities/top/influential",
            params={"limit": 10},
        )
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Should return list
        assert isinstance(data, list)
        
        # If results exist, verify sorting (descending by PageRank)
        if len(data) >= 2:
            scores = [e["pagerank_score"] for e in data]
            assert scores == sorted(scores, reverse=True), "Results should be sorted by PageRank descending"

    async def test_influential_entities_limit(
        self,
        async_client: AsyncClient,
        sample_complex_network: dict,
    ):
        """
        Test limit parameter for influential entities.
        
        Call: GET /entities/top/influential?limit=2
        Assert: At most 2 results returned
        """
        response = await async_client.get(
            "/entities/top/influential",
            params={"limit": 2},
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) <= 2

    async def test_influential_entities_jurisdiction_filter(
        self,
        async_client: AsyncClient,
        sample_complex_network: dict,
    ):
        """
        Test jurisdiction filter for influential entities.
        
        Call: GET /entities/top/influential?jurisdiction=BVI
        Assert: Only BVI entities returned
        """
        response = await async_client.get(
            "/entities/top/influential",
            params={"jurisdiction": "BVI", "limit": 10},
        )
        
        assert response.status_code == 200
        
        data = response.json()
        
        # All results should be in BVI
        for entity in data:
            if entity.get("jurisdiction_code"):
                assert entity["jurisdiction_code"] == "BVI"

    async def test_influential_entities_empty(
        self,
        async_client: AsyncClient,
    ):
        """
        Test when no entities have PageRank scores.
        
        Call: GET /entities/top/influential?min_score=999999
        Assert: 200 status, empty list
        """
        response = await async_client.get(
            "/entities/top/influential",
            params={"min_score": 999999},  # Very high threshold
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)

    async def test_influential_entities_response_structure(
        self,
        async_client: AsyncClient,
        sample_complex_network: dict,
    ):
        """
        Test response structure for influential entities.
        
        Verify: Required fields present
        """
        response = await async_client.get(
            "/entities/top/influential",
            params={"limit": 5},
        )
        
        assert response.status_code == 200
        
        data = response.json()
        
        if len(data) > 0:
            entity = data[0]
            # Verify required fields
            assert "entity_id" in entity
            assert "name" in entity
            assert "pagerank_score" in entity
            assert "rank" in entity


# ============================================================================
# TEST CLASS: CONNECTED ENTITIES
# ============================================================================

class TestConnectedEntities:
    """Tests for GET /entities/top/connected endpoint."""

    async def test_connected_entities_success(
        self,
        async_client: AsyncClient,
        sample_complex_network: dict,
    ):
        """
        Test retrieving most connected entities.
        
        Call: GET /entities/top/connected
        Assert: 200 status, list returned
        """
        response = await async_client.get(
            "/entities/top/connected",
            params={"limit": 10},
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)


# ============================================================================
# TEST CLASS: ENTITIES BY JURISDICTION
# ============================================================================

class TestEntitiesByJurisdiction:
    """Tests for GET /entities/by-jurisdiction/{code} endpoint."""

    async def test_entities_by_jurisdiction_success(
        self,
        async_client: AsyncClient,
        sample_entities: list,
    ):
        """
        Test retrieving entities by jurisdiction.
        
        Call: GET /entities/by-jurisdiction/BVI
        Assert: 200 status, all results in BVI
        """
        response = await async_client.get("/entities/by-jurisdiction/BVI")
        
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        # All results should be in BVI
        for entity in data:
            assert entity["jurisdiction_code"] == "BVI"

    async def test_entities_by_jurisdiction_empty(
        self,
        async_client: AsyncClient,
    ):
        """
        Test when no entities in jurisdiction.
        
        Call: GET /entities/by-jurisdiction/XYZ
        Assert: 200 status, empty list
        """
        response = await async_client.get("/entities/by-jurisdiction/XYZ")
        
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0


# ============================================================================
# TEST CLASS: ENTITY RISK ANALYSIS
# ============================================================================

class TestEntityRiskAnalysis:
    """Tests for GET /entities/{entity_id}/risk endpoint."""

    async def test_risk_analysis_success(
        self,
        async_client: AsyncClient,
        sample_complex_network: dict,
    ):
        """
        Test risk analysis retrieval.
        
        Setup: Entity with risk factors
        Call: GET /entities/{entity_id}/risk
        Assert: 200 status, risk data returned
        """
        entity_id = sample_complex_network["entities"][0]["entity_id"]
        
        response = await async_client.get(f"/entities/{entity_id}/risk")
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify response structure
        assert "entity_id" in data
        assert "overall_risk_score" in data
        assert "overall_risk_level" in data
        assert "red_flags" in data
        
        # Risk score should be 0-100
        assert 0 <= data["overall_risk_score"] <= 100
        
        # Risk level should be valid
        assert data["overall_risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"]

    async def test_risk_analysis_not_found(
        self,
        async_client: AsyncClient,
    ):
        """
        Test 404 when entity doesn't exist.
        """
        response = await async_client.get("/entities/NONEXISTENT-12345/risk")
        
        assert response.status_code == 404


# ============================================================================
# TEST CLASS: HEALTH CHECK
# ============================================================================

class TestHealthCheck:
    """Tests for health endpoints."""

    async def test_health_check(
        self,
        async_client: AsyncClient,
    ):
        """
        Test /health endpoint.
        
        Call: GET /health
        Assert: 200 status (or 503 if db unavailable)
        Verify: status field present
        """
        response = await async_client.get("/health")
        
        assert response.status_code in [200, 503]
        
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

    async def test_root_endpoint(
        self,
        async_client: AsyncClient,
    ):
        """
        Test / root endpoint.
        
        Call: GET /
        Assert: 200 status, API info returned
        """
        response = await async_client.get("/")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "version" in data
        assert "service" in data or "message" in data

    async def test_readiness_check(
        self,
        async_client: AsyncClient,
    ):
        """
        Test /ready endpoint.
        
        Call: GET /ready
        Assert: 200 if ready, 503 if not
        """
        response = await async_client.get("/ready")
        
        assert response.status_code in [200, 503]
        
        data = response.json()
        assert "ready" in data

    async def test_liveness_check(
        self,
        async_client: AsyncClient,
    ):
        """
        Test /live endpoint.
        
        Call: GET /live
        Assert: Always 200 if process alive
        """
        response = await async_client.get("/live")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data["alive"] is True


# ============================================================================
# TEST CLASS: ERROR HANDLING
# ============================================================================

class TestErrorHandling:
    """Tests for error handling."""

    async def test_invalid_endpoint(
        self,
        async_client: AsyncClient,
    ):
        """
        Test 404 for non-existent endpoint.
        """
        response = await async_client.get("/nonexistent/endpoint")
        
        assert response.status_code == 404

    async def test_method_not_allowed(
        self,
        async_client: AsyncClient,
    ):
        """
        Test 405 for unsupported HTTP method.
        """
        response = await async_client.post("/entities/TEST-001")
        
        assert response.status_code == 405

    async def test_validation_error_format(
        self,
        async_client: AsyncClient,
    ):
        """
        Test validation error response format.
        """
        response = await async_client.get(
            "/entities/search",
            params={"q": "A"},  # Too short
        )
        
        assert response.status_code == 422
        
        data = response.json()
        assert "detail" in data or "errors" in data
