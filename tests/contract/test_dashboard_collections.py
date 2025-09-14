"""Contract test for GET /collections endpoint.

This test validates the collections list API contract per dashboard-api.yaml specification.
MUST FAIL initially as no implementation exists yet (TDD requirement).
"""

import pytest
from fastapi.testclient import TestClient
from httpx import Response


class TestDashboardCollectionsContract:
    """Contract tests for collections list endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client for dashboard service.
        
        This will fail initially since the FastAPI app doesn't exist yet.
        This is expected and required for TDD.
        """
        # This import will fail initially - that's expected!
        from backend.dashboard_service.app.main import app  # type: ignore
        return TestClient(app)

    def test_collections_list_default_params_returns_200(self, client: TestClient):
        """Test collections list with default parameters returns 200."""
        response: Response = client.get("/collections")
        
        # Contract assertions per OpenAPI spec
        assert response.status_code == 200
        
        response_data = response.json()
        
        # Required top-level fields
        assert "collections" in response_data
        assert "total_count" in response_data
        assert "pagination" in response_data
        
        # Collections should be array
        assert isinstance(response_data["collections"], list)
        
        # Pagination object structure
        pagination = response_data["pagination"]
        assert "limit" in pagination
        assert "offset" in pagination
        assert "has_next" in pagination
        
        # Default values per spec
        assert pagination["limit"] == 20  # Default limit
        assert pagination["offset"] == 0   # Default offset
        assert isinstance(pagination["has_next"], bool)

    def test_collections_list_with_pagination_params(self, client: TestClient):
        """Test collections list with custom pagination parameters."""
        response: Response = client.get("/collections?limit=10&offset=5")
        
        assert response.status_code == 200
        
        response_data = response.json()
        pagination = response_data["pagination"]
        
        # Should respect provided parameters
        assert pagination["limit"] == 10
        assert pagination["offset"] == 5

    def test_collections_list_with_sorting_params(self, client: TestClient):
        """Test collections list with sorting parameters."""
        response: Response = client.get("/collections?sort_by=floor_price&order=asc")
        
        assert response.status_code == 200
        
        response_data = response.json()
        collections = response_data["collections"]
        
        # If collections exist, verify sorting is applied
        # (Actual sorting validation will be in integration tests)
        assert isinstance(collections, list)

    def test_collections_list_collection_schema(self, client: TestClient):
        """Test each collection item matches the expected schema."""
        response: Response = client.get("/collections")
        
        assert response.status_code == 200
        
        response_data = response.json()
        collections = response_data["collections"]
        
        if len(collections) > 0:
            collection = collections[0]
            
            # Required fields per CollectionSummary schema
            required_fields = {
                "collection_id", "name", "symbol", "total_supply",
                "floor_price", "total_volume", "holder_count",
                "avg_price_24h", "volume_24h"
            }
            
            for field in required_fields:
                assert field in collection, f"Missing required field: {field}"
            
            # Validate field types
            assert isinstance(collection["collection_id"], str)
            assert isinstance(collection["name"], str)
            assert isinstance(collection["symbol"], str)
            assert isinstance(collection["total_supply"], int)
            assert isinstance(collection["floor_price"], (int, float))
            assert isinstance(collection["total_volume"], (int, float))
            assert isinstance(collection["holder_count"], int)
            assert isinstance(collection["avg_price_24h"], (int, float))
            assert isinstance(collection["volume_24h"], (int, float))

    def test_collections_list_limit_validation(self, client: TestClient):
        """Test collections list validates limit parameter bounds."""
        # Test maximum limit
        response: Response = client.get("/collections?limit=101")
        assert response.status_code == 400  # Should reject > 100
        
        # Test minimum limit
        response: Response = client.get("/collections?limit=0")
        assert response.status_code == 400  # Should reject < 1
        
        # Test valid limit
        response: Response = client.get("/collections?limit=50")
        assert response.status_code == 200

    def test_collections_list_offset_validation(self, client: TestClient):
        """Test collections list validates offset parameter."""
        # Test negative offset
        response: Response = client.get("/collections?offset=-1")
        assert response.status_code == 400  # Should reject negative
        
        # Test valid offset
        response: Response = client.get("/collections?offset=0")
        assert response.status_code == 200

    def test_collections_list_sort_by_validation(self, client: TestClient):
        """Test collections list validates sort_by parameter."""
        valid_sort_fields = ["total_volume", "floor_price", "created_at", "holder_count"]
        
        for sort_field in valid_sort_fields:
            response: Response = client.get(f"/collections?sort_by={sort_field}")
            assert response.status_code == 200, f"Valid sort field {sort_field} should be accepted"
        
        # Test invalid sort field
        response: Response = client.get("/collections?sort_by=invalid_field")
        assert response.status_code == 400

    def test_collections_list_order_validation(self, client: TestClient):
        """Test collections list validates order parameter."""
        # Test valid order values
        for order in ["asc", "desc"]:
            response: Response = client.get(f"/collections?order={order}")
            assert response.status_code == 200
        
        # Test invalid order
        response: Response = client.get("/collections?order=invalid")
        assert response.status_code == 400

    def test_collections_list_empty_result(self, client: TestClient):
        """Test collections list handles empty results gracefully."""
        # This tests the case where no collections exist yet
        response: Response = client.get("/collections")
        
        assert response.status_code == 200
        
        response_data = response.json()
        
        # Should still have proper structure
        assert "collections" in response_data
        assert "total_count" in response_data  
        assert "pagination" in response_data
        
        # Empty collections case
        if response_data["total_count"] == 0:
            assert response_data["collections"] == []
            assert response_data["pagination"]["has_next"] == False

    def test_collections_list_content_type(self, client: TestClient):
        """Test collections endpoint returns JSON content type."""
        response: Response = client.get("/collections")
        
        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
    def test_collections_list_method_not_allowed(self, client: TestClient, method: str):
        """Test collections endpoint only allows GET method."""
        response: Response = client.request(method, "/collections")
        
        assert response.status_code == 405  # Method Not Allowed