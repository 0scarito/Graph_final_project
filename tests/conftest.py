"""Pytest configuration and shared fixtures."""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.services.graph_service import GraphService


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def mock_graph_service():
    """Create a mocked GraphService instance."""
    mock_service = Mock(spec=GraphService)
    return mock_service


@pytest.fixture
def patched_graph_service(mock_graph_service):
    """Patch GraphService in routers to use the mock."""
    with patch('app.routers.entities.graph_service', mock_graph_service), \
         patch('app.routers.networks.graph_service', mock_graph_service):
        yield mock_graph_service

