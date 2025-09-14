"""Contract test for POST /attributes/analysis endpoint.

This test validates the attribute analysis API contract per dashboard-api.yaml specification.
MUST FAIL initially as no implementation exists yet (TDD requirement).
"""

import pytest
from fastapi.testclient import TestClient
from httpx import Response


class TestDashboardAttributesContract:
    """Contract tests for attribute analysis endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client for dashboard service."""
        from backend.dashboard_service.app.main import app  # type: ignore
        return TestClient(app)

    def test_attributes_analysis_valid_request_returns_200(self, client: TestClient):
        """Test attribute analysis with valid request returns 200."""
        valid_request = {
            "collection_ids": ["collection-1", "collection-2"],
            "time_range_days": 30
        }
        
        response: Response = client.post("/attributes/analysis", json=valid_request)
        
        assert response.status_code == 200
        
        response_data = response.json()
        
        # Required fields per AttributeAnalysisResponse schema
        assert "analysis_date" in response_data
        assert "collections" in response_data
        
        assert isinstance(response_data["collections"], list)

    def test_attributes_analysis_missing_collection_ids_returns_400(self, client: TestClient):
        """Test attribute analysis without collection_ids returns 400."""
        invalid_request = {
            "time_range_days": 30
            # Missing required collection_ids
        }
        
        response: Response = client.post("/attributes/analysis", json=invalid_request)
        
        assert response.status_code == 400

    def test_attributes_analysis_too_many_collections_returns_400(self, client: TestClient):
        """Test attribute analysis with too many collections returns 400."""
        invalid_request = {
            "collection_ids": [f"collection-{i}" for i in range(10)],  # > 5 max
            "time_range_days": 30
        }
        
        response: Response = client.post("/attributes/analysis", json=invalid_request)
        
        assert response.status_code == 400

    def test_attributes_analysis_invalid_time_range_returns_400(self, client: TestClient):
        """Test attribute analysis with invalid time range returns 400."""
        # Test too small
        invalid_request = {
            "collection_ids": ["collection-1"],
            "time_range_days": 5  # < 7 minimum
        }
        
        response: Response = client.post("/attributes/analysis", json=invalid_request)
        assert response.status_code == 400
        
        # Test too large
        invalid_request = {
            "collection_ids": ["collection-1"],
            "time_range_days": 400  # > 365 maximum
        }
        
        response: Response = client.post("/attributes/analysis", json=invalid_request)
        assert response.status_code == 400

    @pytest.mark.parametrize("method", ["GET", "PUT", "DELETE", "PATCH"])
    def test_attributes_analysis_method_not_allowed(self, client: TestClient, method: str):
        """Test attributes analysis endpoint only allows POST method."""
        response: Response = client.request(method, "/attributes/analysis")
        
        assert response.status_code == 405