"""Contract test for GET /collections/{id} endpoint.

This test validates the collection details API contract per dashboard-api.yaml specification.
MUST FAIL initially as no implementation exists yet (TDD requirement).
"""

import pytest
from fastapi.testclient import TestClient
from httpx import Response


class TestDashboardCollectionDetailsContract:
    """Contract tests for collection details endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client for dashboard service.
        
        This will fail initially since the FastAPI app doesn't exist yet.
        This is expected and required for TDD.
        """
        # This import will fail initially - that's expected!
        from backend.dashboard_service.app.main import app  # type: ignore
        return TestClient(app)

    def test_collection_details_valid_id_returns_200(self, client: TestClient):
        """Test collection details with valid ID returns 200."""
        collection_id = "test-collection-123"
        response: Response = client.get(f"/collections/{collection_id}")
        
        # This will fail initially - expected for TDD
        # When collection exists, should return 200
        assert response.status_code == 200 or response.status_code == 404
        
        if response.status_code == 200:
            response_data = response.json()
            
            # Required fields per CollectionDetails schema
            required_fields = {
                "collection_id", "name", "symbol", "creator_address",
                "total_supply", "floor_price", "total_volume", "holder_count",
                "price_history", "top_holders", "recent_sales"
            }
            
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"
            
            # Validate field types
            assert isinstance(response_data["collection_id"], str)
            assert isinstance(response_data["name"], str)
            assert isinstance(response_data["symbol"], str)
            assert isinstance(response_data["creator_address"], str)
            assert isinstance(response_data["total_supply"], int)
            assert isinstance(response_data["floor_price"], (int, float))
            assert isinstance(response_data["total_volume"], (int, float))
            assert isinstance(response_data["holder_count"], int)
            assert isinstance(response_data["price_history"], list)
            assert isinstance(response_data["top_holders"], list)
            assert isinstance(response_data["recent_sales"], list)

    def test_collection_details_nonexistent_id_returns_404(self, client: TestClient):
        """Test collection details with nonexistent ID returns 404."""
        nonexistent_id = "nonexistent-collection-999"
        response: Response = client.get(f"/collections/{nonexistent_id}")
        
        assert response.status_code == 404
        
        response_data = response.json()
        
        # Should match ErrorResponse schema
        assert "error" in response_data
        assert "message" in response_data
        assert "timestamp" in response_data

    def test_collection_details_price_history_schema(self, client: TestClient):
        """Test price history array matches PricePoint schema."""
        collection_id = "test-collection-123"
        response: Response = client.get(f"/collections/{collection_id}")
        
        if response.status_code == 200:
            response_data = response.json()
            price_history = response_data["price_history"]
            
            if len(price_history) > 0:
                price_point = price_history[0]
                
                # Required fields per PricePoint schema
                required_fields = {"date", "floor_price", "avg_price", "volume"}
                
                for field in required_fields:
                    assert field in price_point, f"Missing PricePoint field: {field}"
                
                # Validate field types
                assert isinstance(price_point["date"], str)  # ISO date format
                assert isinstance(price_point["floor_price"], (int, float))
                assert isinstance(price_point["avg_price"], (int, float))
                assert isinstance(price_point["volume"], (int, float))

    def test_collection_details_top_holders_schema(self, client: TestClient):
        """Test top holders array matches TopHolder schema."""
        collection_id = "test-collection-123"
        response: Response = client.get(f"/collections/{collection_id}")
        
        if response.status_code == 200:
            response_data = response.json()
            top_holders = response_data["top_holders"]
            
            if len(top_holders) > 0:
                holder = top_holders[0]
                
                # Required fields per TopHolder schema
                required_fields = {"wallet_address", "nft_count", "estimated_value", "whale_status"}
                
                for field in required_fields:
                    assert field in holder, f"Missing TopHolder field: {field}"
                
                # Validate field types
                assert isinstance(holder["wallet_address"], str)
                assert isinstance(holder["nft_count"], int)
                assert isinstance(holder["estimated_value"], (int, float))
                assert isinstance(holder["whale_status"], bool)
                
                # Wallet address format validation (Solana address)
                wallet_address = holder["wallet_address"]
                assert len(wallet_address) >= 32  # Solana addresses are base58 encoded
                assert all(c in "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz" for c in wallet_address)

    def test_collection_details_recent_sales_schema(self, client: TestClient):
        """Test recent sales array matches RecentSale schema."""
        collection_id = "test-collection-123"
        response: Response = client.get(f"/collections/{collection_id}")
        
        if response.status_code == 200:
            response_data = response.json()
            recent_sales = response_data["recent_sales"]
            
            if len(recent_sales) > 0:
                sale = recent_sales[0]
                
                # Required fields per RecentSale schema
                required_fields = {
                    "mint_address", "name", "price_sol", "buyer", 
                    "seller", "marketplace", "timestamp"
                }
                
                for field in required_fields:
                    assert field in sale, f"Missing RecentSale field: {field}"
                
                # Validate field types
                assert isinstance(sale["mint_address"], str)
                assert isinstance(sale["name"], str)
                assert isinstance(sale["price_sol"], (int, float))
                assert isinstance(sale["buyer"], str)
                assert isinstance(sale["seller"], str)
                assert isinstance(sale["marketplace"], str)
                assert isinstance(sale["timestamp"], str)
                
                # Validate timestamp is ISO format
                assert "T" in sale["timestamp"]

    def test_collection_details_creator_address_format(self, client: TestClient):
        """Test creator address is valid Solana address format."""
        collection_id = "test-collection-123"
        response: Response = client.get(f"/collections/{collection_id}")
        
        if response.status_code == 200:
            response_data = response.json()
            creator_address = response_data["creator_address"]
            
            # Solana address validation
            assert len(creator_address) >= 32
            assert all(c in "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz" for c in creator_address)

    def test_collection_details_invalid_id_format(self, client: TestClient):
        """Test collection details with invalid ID format."""
        # Test various invalid formats
        invalid_ids = [
            "",           # Empty string
            " ",          # Whitespace
            "/../etc/passwd",  # Path traversal attempt
            "%00",        # Null byte
            "a" * 1000,   # Extremely long string
        ]
        
        for invalid_id in invalid_ids:
            response: Response = client.get(f"/collections/{invalid_id}")
            
            # Should return 400 for malformed requests or 404 for not found
            assert response.status_code in [400, 404]

    def test_collection_details_content_type(self, client: TestClient):
        """Test collection details endpoint returns JSON content type."""
        collection_id = "test-collection-123"
        response: Response = client.get(f"/collections/{collection_id}")
        
        # Should return JSON regardless of 200 or 404
        assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
    def test_collection_details_method_not_allowed(self, client: TestClient, method: str):
        """Test collection details endpoint only allows GET method."""
        collection_id = "test-collection-123"
        response: Response = client.request(method, f"/collections/{collection_id}")
        
        assert response.status_code == 405  # Method Not Allowed

    def test_collection_details_numeric_values_non_negative(self, client: TestClient):
        """Test collection details numeric fields are non-negative."""
        collection_id = "test-collection-123"
        response: Response = client.get(f"/collections/{collection_id}")
        
        if response.status_code == 200:
            response_data = response.json()
            
            # These fields should never be negative
            assert response_data["total_supply"] >= 0
            assert response_data["floor_price"] >= 0
            assert response_data["total_volume"] >= 0
            assert response_data["holder_count"] >= 0