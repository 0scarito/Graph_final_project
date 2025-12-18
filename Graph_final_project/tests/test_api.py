"""Comprehensive API endpoint tests with mocked GraphService."""

import pytest
from fastapi.testclient import TestClient


class TestRootEndpoints:
    """Tests for root-level endpoints."""

    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint returns welcome message."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "Graph-Backed Analysis API"
        assert "version" in data
        assert "docs" in data

    def test_health_endpoint_healthy(self, client: TestClient):
        """Test health endpoint when Neo4j is available."""
        # Note: This may fail if Neo4j is not running, which is acceptable
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "neo4j" in data


class TestEntityEndpoints:
    """Tests for entity-related endpoints."""

    def test_get_ownership_paths_success(self, client: TestClient, patched_graph_service):
        """Test successful ownership paths retrieval."""
        # Mock the service response
        mock_paths = [
            {
                "nodes": [
                    {
                        "id": "12000001",
                        "labels": ["Officer"],
                        "properties": {"name": "John Doe", "id": "12000001"}
                    },
                    {
                        "id": "10000001",
                        "labels": ["Entity"],
                        "properties": {"name": "Test Entity", "id": "10000001"}
                    }
                ],
                "relationships": [
                    {
                        "type": "OFFICER_OF",
                        "start_node": "12000001",
                        "end_node": "10000001",
                        "properties": {}
                    }
                ],
                "length": 1
            }
        ]
        patched_graph_service.get_entity_ownership_paths.return_value = mock_paths

        response = client.get("/api/entities/10000001/ownership/paths?max_length=5")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert "nodes" in data[0]
        assert "relationships" in data[0]
        assert "length" in data[0]
        patched_graph_service.get_entity_ownership_paths.assert_called_once_with(
            "10000001", max_depth=5
        )

    def test_get_ownership_paths_with_default_max_length(self, client: TestClient, patched_graph_service):
        """Test ownership paths with default max_length parameter."""
        patched_graph_service.get_entity_ownership_paths.return_value = []

        response = client.get("/api/entities/10000001/ownership/paths")
        assert response.status_code == 200
        assert response.json() == []
        patched_graph_service.get_entity_ownership_paths.assert_called_once_with(
            "10000001", max_depth=5
        )

    def test_get_ownership_paths_invalid_max_length(self, client: TestClient):
        """Test ownership paths with invalid max_length parameter."""
        response = client.get("/api/entities/10000001/ownership/paths?max_length=0")
        assert response.status_code == 422  # Validation error

        response = client.get("/api/entities/10000001/ownership/paths?max_length=11")
        assert response.status_code == 422  # Validation error

    def test_get_ownership_paths_service_error(self, client: TestClient, patched_graph_service):
        """Test ownership paths endpoint handles service errors."""
        patched_graph_service.get_entity_ownership_paths.side_effect = Exception("Database error")

        response = client.get("/api/entities/10000001/ownership/paths")
        assert response.status_code == 500
        assert "Error finding ownership paths" in response.json()["detail"]


class TestNetworkEndpoints:
    """Tests for network analysis endpoints."""

    def test_get_top_intermediaries_success(self, client: TestClient, patched_graph_service):
        """Test successful top intermediaries retrieval."""
        mock_intermediaries = [
            {
                "intermediary_id": "11000001",
                "name": "Test Intermediary",
                "entity_count": 100
            }
        ]
        patched_graph_service.get_top_intermediaries.return_value = mock_intermediaries

        response = client.get("/api/networks/intermediaries/top?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["intermediary_id"] == "11000001"
        assert data[0]["intermediary_name"] == "Test Intermediary"
        assert data[0]["entity_count"] == 100
        patched_graph_service.get_top_intermediaries.assert_called_once_with(limit=10)

    def test_get_top_intermediaries_default_limit(self, client: TestClient, patched_graph_service):
        """Test top intermediaries with default limit."""
        patched_graph_service.get_top_intermediaries.return_value = []

        response = client.get("/api/networks/intermediaries/top")
        assert response.status_code == 200
        patched_graph_service.get_top_intermediaries.assert_called_once_with(limit=10)

    def test_get_top_intermediaries_invalid_limit(self, client: TestClient):
        """Test top intermediaries with invalid limit."""
        response = client.get("/api/networks/intermediaries/top?limit=0")
        assert response.status_code == 422

        response = client.get("/api/networks/intermediaries/top?limit=101")
        assert response.status_code == 422

    def test_get_top_intermediaries_service_error(self, client: TestClient, patched_graph_service):
        """Test top intermediaries endpoint handles service errors."""
        patched_graph_service.get_top_intermediaries.side_effect = Exception("Database error")

        response = client.get("/api/networks/intermediaries/top")
        assert response.status_code == 500
        assert "Error finding top intermediaries" in response.json()["detail"]

    def test_get_red_flags_success(self, client: TestClient, patched_graph_service):
        """Test successful red flags retrieval."""
        mock_red_flags = [
            {
                "address_id": "24000001",
                "address": "Test Address",
                "entity_count": 50,
                "sample_entities": ["Entity 1", "Entity 2", "Entity 3"]
            }
        ]
        patched_graph_service.detect_red_flags.return_value = mock_red_flags

        response = client.get("/api/networks/redflags?min_entities=10&limit=50")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["address_id"] == "24000001"
        assert data[0]["address"] == "Test Address"
        assert data[0]["entity_count"] == 50
        assert len(data[0]["entities"]) == 3
        patched_graph_service.detect_red_flags.assert_called_once_with(
            min_entities=10, limit=50
        )

    def test_get_red_flags_default_params(self, client: TestClient, patched_graph_service):
        """Test red flags with default parameters."""
        patched_graph_service.detect_red_flags.return_value = []

        response = client.get("/api/networks/redflags")
        assert response.status_code == 200
        patched_graph_service.detect_red_flags.assert_called_once_with(
            min_entities=2, limit=50
        )

    def test_get_red_flags_invalid_params(self, client: TestClient):
        """Test red flags with invalid parameters."""
        response = client.get("/api/networks/redflags?min_entities=1")
        assert response.status_code == 422  # min_entities must be >= 2

        response = client.get("/api/networks/redflags?limit=0")
        assert response.status_code == 422

    def test_get_red_flags_service_error(self, client: TestClient, patched_graph_service):
        """Test red flags endpoint handles service errors."""
        patched_graph_service.detect_red_flags.side_effect = Exception("Database error")

        response = client.get("/api/networks/redflags")
        assert response.status_code == 500
        assert "Error finding red flags" in response.json()["detail"]

    def test_get_shortest_path_success(self, client: TestClient, patched_graph_service):
        """Test successful shortest path retrieval."""
        mock_path = {
            "nodes": [
                {
                    "id": "10000001",
                    "labels": ["Entity"],
                    "properties": {"name": "Start Entity", "id": "10000001"}
                },
                {
                    "id": "10000002",
                    "labels": ["Entity"],
                    "properties": {"name": "End Entity", "id": "10000002"}
                }
            ],
            "relationships": [
                {
                    "type": "OFFICER_OF",
                    "start_node": "10000001",
                    "end_node": "10000002",
                    "properties": {}
                }
            ],
            "length": 1
        }
        patched_graph_service.get_shortest_path.return_value = mock_path

        response = client.get(
            "/api/networks/path/shortest?start_node_id=10000001&end_node_id=10000002"
        )
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "relationships" in data
        assert "length" in data
        assert len(data["nodes"]) == 2
        patched_graph_service.get_shortest_path.assert_called_once_with(
            "10000001", "10000002"
        )

    def test_get_shortest_path_no_path(self, client: TestClient, patched_graph_service):
        """Test shortest path when no path exists."""
        patched_graph_service.get_shortest_path.return_value = None

        response = client.get(
            "/api/networks/path/shortest?start_node_id=10000001&end_node_id=99999999"
        )
        assert response.status_code == 200
        assert response.json() is None

    def test_get_shortest_path_missing_params(self, client: TestClient):
        """Test shortest path with missing required parameters."""
        response = client.get("/api/networks/path/shortest?start_node_id=10000001")
        assert response.status_code == 422  # Missing end_node_id

        response = client.get("/api/networks/path/shortest?end_node_id=10000002")
        assert response.status_code == 422  # Missing start_node_id

    def test_get_shortest_path_service_error(self, client: TestClient, patched_graph_service):
        """Test shortest path endpoint handles service errors."""
        patched_graph_service.get_shortest_path.side_effect = Exception("Database error")

        response = client.get(
            "/api/networks/path/shortest?start_node_id=10000001&end_node_id=10000002"
        )
        assert response.status_code == 500
        assert "Error finding shortest path" in response.json()["detail"]

    def test_get_most_connected_officers_success(self, client: TestClient, patched_graph_service):
        """Test successful most connected officers retrieval."""
        mock_officers = [
            {
                "officer_id": "12000001",
                "name": "John Doe",
                "degree": 50
            },
            {
                "officer_id": "12000002",
                "name": "Jane Smith",
                "degree": 45
            }
        ]
        patched_graph_service.get_most_connected_officers.return_value = mock_officers

        response = client.get("/api/networks/stats/centrality?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["officer_id"] == "12000001"
        assert data[0]["name"] == "John Doe"
        assert data[0]["degree"] == 50
        patched_graph_service.get_most_connected_officers.assert_called_once_with(limit=10)

    def test_get_most_connected_officers_default_limit(self, client: TestClient, patched_graph_service):
        """Test most connected officers with default limit."""
        patched_graph_service.get_most_connected_officers.return_value = []

        response = client.get("/api/networks/stats/centrality")
        assert response.status_code == 200
        patched_graph_service.get_most_connected_officers.assert_called_once_with(limit=10)

    def test_get_most_connected_officers_invalid_limit(self, client: TestClient):
        """Test most connected officers with invalid limit."""
        response = client.get("/api/networks/stats/centrality?limit=0")
        assert response.status_code == 422

        response = client.get("/api/networks/stats/centrality?limit=101")
        assert response.status_code == 422

    def test_get_most_connected_officers_service_error(self, client: TestClient, patched_graph_service):
        """Test most connected officers endpoint handles service errors."""
        patched_graph_service.get_most_connected_officers.side_effect = Exception("Database error")

        response = client.get("/api/networks/stats/centrality")
        assert response.status_code == 500
        assert "Error finding most connected officers" in response.json()["detail"]
