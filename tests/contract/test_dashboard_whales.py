"""Contract test for GET /whales endpoint.

This test validates the whale tracking API contract per dashboard-api.yaml specification.
MUST FAIL initially as no implementation exists yet (TDD requirement).
"""

import pytest
from fastapi.testclient import TestClient
from httpx import Response


class TestDashboardWhalesContract:
    """Contract tests for whale tracking endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client for dashboard service."""
        from backend.dashboard_service.app.main import app  # type: ignore
        return TestClient(app)

    def test_whales_list_returns_200(self, client: TestClient):
        """Test whales list returns 200 with proper schema."""
        response: Response = client.get("/whales")
        
        assert response.status_code == 200
        
        response_data = response.json()
        
        # Required fields per WhaleListResponse schema
        assert "whales" in response_data
        assert "activity_period_days" in response_data  
        assert "total_count" in response_data
        
        assert isinstance(response_data["whales"], list)
        assert isinstance(response_data["activity_period_days"], int)
        assert isinstance(response_data["total_count"], int)

    def test_whales_list_with_params(self, client: TestClient):
        """Test whales list with custom parameters."""
        response: Response = client.get("/whales?limit=10&activity_days=30")
        
        assert response.status_code == 200
        
        response_data = response.json()
        assert response_data["activity_period_days"] == 30

    def test_whales_list_whale_schema(self, client: TestClient):
        """Test whale objects match WhaleSummary schema."""
        response: Response = client.get("/whales")
        
        if response.status_code == 200:
            response_data = response.json()
            whales = response_data["whales"]
            
            if len(whales) > 0:
                whale = whales[0]
                
                required_fields = {
                    "wallet_address", "total_volume_traded", "total_nfts_owned",
                    "last_activity", "recent_activity_count"
                }
                
                for field in required_fields:
                    assert field in whale
                
                # Validate field types
                assert isinstance(whale["wallet_address"], str)
                assert isinstance(whale["total_volume_traded"], (int, float))
                assert isinstance(whale["total_nfts_owned"], int)
                assert isinstance(whale["last_activity"], str)
                assert isinstance(whale["recent_activity_count"], int)

    def test_whales_list_limit_validation(self, client: TestClient):
        """Test whales list validates limit parameter."""
        # Test maximum limit
        response: Response = client.get("/whales?limit=51")
        assert response.status_code == 400  # Should reject > 50
        
        # Test valid limit
        response: Response = client.get("/whales?limit=20")
        assert response.status_code == 200

    @pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
    def test_whales_method_not_allowed(self, client: TestClient, method: str):
        """Test whales endpoint only allows GET method."""
        response: Response = client.request(method, "/whales")
        assert response.status_code == 405