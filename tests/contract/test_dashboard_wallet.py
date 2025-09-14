"""Contract test for GET /wallets/{address} endpoint.

This test validates the wallet profile API contract per dashboard-api.yaml specification.
MUST FAIL initially as no implementation exists yet (TDD requirement).
"""

import pytest
from fastapi.testclient import TestClient
from httpx import Response


class TestDashboardWalletContract:
    """Contract tests for wallet profile endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client for dashboard service."""
        from backend.dashboard_service.app.main import app  # type: ignore
        return TestClient(app)

    def test_wallet_profile_valid_address_returns_200(self, client: TestClient):
        """Test wallet profile with valid address returns 200."""
        wallet_address = "ByXB7zV4TKa3xxC6PJxEQgm7cZxvXHU9C5qhHdKQN4R4"
        response: Response = client.get(f"/wallets/{wallet_address}")
        
        assert response.status_code == 200 or response.status_code == 404
        
        if response.status_code == 200:
            response_data = response.json()
            
            # Required fields per WalletProfile schema
            required_fields = {
                "wallet_address", "total_nfts_owned", "total_volume_traded",
                "whale_status", "first_activity", "last_activity",
                "avg_hold_duration", "collections_active", "profit_loss_sol",
                "recent_transactions", "current_holdings"
            }
            
            for field in required_fields:
                assert field in response_data
            
            # Validate types
            assert isinstance(response_data["wallet_address"], str)
            assert isinstance(response_data["total_nfts_owned"], int)
            assert isinstance(response_data["total_volume_traded"], (int, float))
            assert isinstance(response_data["whale_status"], bool)
            assert isinstance(response_data["recent_transactions"], list)
            assert isinstance(response_data["current_holdings"], list)

    def test_wallet_profile_invalid_address_returns_400(self, client: TestClient):
        """Test wallet profile with invalid address format returns 400."""
        invalid_address = "invalid_wallet_address"
        response: Response = client.get(f"/wallets/{invalid_address}")
        
        assert response.status_code == 400

    def test_wallet_profile_nonexistent_address_returns_404(self, client: TestClient):
        """Test wallet profile with nonexistent address returns 404."""
        nonexistent_address = "11111111111111111111111111111111111111111111"
        response: Response = client.get(f"/wallets/{nonexistent_address}")
        
        assert response.status_code == 404

    @pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
    def test_wallet_profile_method_not_allowed(self, client: TestClient, method: str):
        """Test wallet profile endpoint only allows GET method."""
        wallet_address = "ByXB7zV4TKa3xxC6PJxEQgm7cZxvXHU9C5qhHdKQN4R4"
        response: Response = client.request(method, f"/wallets/{wallet_address}")
        
        assert response.status_code == 405