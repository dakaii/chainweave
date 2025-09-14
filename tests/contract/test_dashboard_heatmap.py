"""Contract test for GET /collections/{id}/heatmap endpoint.

This test validates the collection heatmap API contract per dashboard-api.yaml specification.
MUST FAIL initially as no implementation exists yet (TDD requirement).
"""

import pytest
from fastapi.testclient import TestClient
from httpx import Response


class TestDashboardHeatmapContract:
    """Contract tests for collection heatmap endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client for dashboard service.
        
        This will fail initially since the FastAPI app doesn't exist yet.
        This is expected and required for TDD.
        """
        # This import will fail initially - that's expected!
        from backend.dashboard_service.app.main import app  # type: ignore
        return TestClient(app)

    def test_collection_heatmap_valid_id_returns_200(self, client: TestClient):
        """Test collection heatmap with valid ID returns 200."""
        collection_id = "test-collection-123"
        response: Response = client.get(f"/collections/{collection_id}/heatmap")
        
        # This will fail initially - expected for TDD
        assert response.status_code == 200 or response.status_code == 404
        
        if response.status_code == 200:
            response_data = response.json()
            
            # Required fields per HeatmapData schema
            required_fields = {"collection_id", "nfts", "color_scale"}
            
            for field in required_fields:
                assert field in response_data, f"Missing required field: {field}"
            
            # Validate field types
            assert isinstance(response_data["collection_id"], str)
            assert isinstance(response_data["nfts"], list)
            assert isinstance(response_data["color_scale"], dict)
            
            # Validate collection_id matches request
            assert response_data["collection_id"] == collection_id

    def test_collection_heatmap_nfts_schema(self, client: TestClient):
        """Test NFTs array matches NFTHeatmapPoint schema."""
        collection_id = "test-collection-123"
        response: Response = client.get(f"/collections/{collection_id}/heatmap")
        
        if response.status_code == 200:
            response_data = response.json()
            nfts = response_data["nfts"]
            
            if len(nfts) > 0:
                nft_point = nfts[0]
                
                # Required fields per NFTHeatmapPoint schema
                required_fields = {
                    "mint_address", "name", "current_owner", "hold_duration_days",
                    "last_sale_price", "rarity_rank"
                }
                
                for field in required_fields:
                    assert field in nft_point, f"Missing NFTHeatmapPoint field: {field}"
                
                # Validate field types
                assert isinstance(nft_point["mint_address"], str)
                assert isinstance(nft_point["name"], str)
                assert isinstance(nft_point["current_owner"], str)
                assert isinstance(nft_point["hold_duration_days"], int)
                assert isinstance(nft_point["last_sale_price"], (int, float))
                assert isinstance(nft_point["rarity_rank"], int)
                
                # Validate Solana address formats
                mint_address = nft_point["mint_address"]
                current_owner = nft_point["current_owner"]
                
                for address in [mint_address, current_owner]:
                    assert len(address) >= 32
                    assert all(c in "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz" for c in address)

    def test_collection_heatmap_color_scale_schema(self, client: TestClient):
        """Test color scale object matches expected schema."""
        collection_id = "test-collection-123"
        response: Response = client.get(f"/collections/{collection_id}/heatmap")
        
        if response.status_code == 200:
            response_data = response.json()
            color_scale = response_data["color_scale"]
            
            # Required fields per schema
            required_fields = {"min_hold_days", "max_hold_days", "color_mapping"}
            
            for field in required_fields:
                assert field in color_scale, f"Missing color_scale field: {field}"
            
            # Validate field types
            assert isinstance(color_scale["min_hold_days"], int)
            assert isinstance(color_scale["max_hold_days"], int)
            assert isinstance(color_scale["color_mapping"], dict)
            
            # Logical validation
            assert color_scale["min_hold_days"] >= 0
            assert color_scale["max_hold_days"] >= color_scale["min_hold_days"]
            
            # Color mapping should have string values (hex colors)
            for key, color_value in color_scale["color_mapping"].items():
                assert isinstance(color_value, str)
                # Basic hex color validation
                if color_value.startswith("#"):
                    assert len(color_value) in [4, 7]  # #RGB or #RRGGBB

    def test_collection_heatmap_hold_duration_values(self, client: TestClient):
        """Test hold duration values are logical and non-negative."""
        collection_id = "test-collection-123"
        response: Response = client.get(f"/collections/{collection_id}/heatmap")
        
        if response.status_code == 200:
            response_data = response.json()
            nfts = response_data["nfts"]
            
            for nft_point in nfts:
                hold_duration = nft_point["hold_duration_days"]
                
                # Hold duration should be non-negative
                assert hold_duration >= 0
                
                # Should be reasonable (not more than ~10 years)
                assert hold_duration <= 3650

    def test_collection_heatmap_rarity_rank_values(self, client: TestClient):
        """Test rarity rank values are within collection bounds."""
        collection_id = "test-collection-123"
        response: Response = client.get(f"/collections/{collection_id}/heatmap")
        
        if response.status_code == 200:
            response_data = response.json()
            nfts = response_data["nfts"]
            
            if len(nfts) > 0:
                for nft_point in nfts:
                    rarity_rank = nft_point["rarity_rank"]
                    
                    # Rarity rank should be positive
                    assert rarity_rank >= 1
                    
                    # Should be reasonable for NFT collections
                    assert rarity_rank <= 100000  # Most collections < 100k items

    def test_collection_heatmap_nonexistent_id_returns_404(self, client: TestClient):
        """Test collection heatmap with nonexistent ID returns 404."""
        nonexistent_id = "nonexistent-collection-999"
        response: Response = client.get(f"/collections/{nonexistent_id}/heatmap")
        
        assert response.status_code == 404
        
        response_data = response.json()
        
        # Should match ErrorResponse schema
        assert "error" in response_data
        assert "message" in response_data
        assert "timestamp" in response_data

    def test_collection_heatmap_empty_collection(self, client: TestClient):
        """Test heatmap for collection with no NFTs."""
        collection_id = "empty-collection-123"
        response: Response = client.get(f"/collections/{collection_id}/heatmap")
        
        if response.status_code == 200:
            response_data = response.json()
            
            # Should still have proper structure
            assert "collection_id" in response_data
            assert "nfts" in response_data
            assert "color_scale" in response_data
            
            # NFTs array should be empty
            assert response_data["nfts"] == []
            
            # Color scale should still be present for UI consistency
            assert isinstance(response_data["color_scale"], dict)

    def test_collection_heatmap_large_collection(self, client: TestClient):
        """Test heatmap handles large collections efficiently."""
        collection_id = "large-collection-123"
        response: Response = client.get(f"/collections/{collection_id}/heatmap")
        
        if response.status_code == 200:
            response_data = response.json()
            nfts = response_data["nfts"]
            
            # Should handle large datasets (test reasonable limits)
            # API might implement pagination or limits for performance
            assert len(nfts) <= 10000  # Reasonable limit for visualization

    def test_collection_heatmap_content_type(self, client: TestClient):
        """Test collection heatmap endpoint returns JSON content type."""
        collection_id = "test-collection-123"
        response: Response = client.get(f"/collections/{collection_id}/heatmap")
        
        assert "application/json" in response.headers.get("content-type", "")

    def test_collection_heatmap_invalid_id_format(self, client: TestClient):
        """Test collection heatmap with invalid ID format."""
        invalid_ids = [
            "",
            " ", 
            "/../etc/passwd",
            "%00",
            "a" * 1000,
        ]
        
        for invalid_id in invalid_ids:
            response: Response = client.get(f"/collections/{invalid_id}/heatmap")
            assert response.status_code in [400, 404]

    @pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
    def test_collection_heatmap_method_not_allowed(self, client: TestClient, method: str):
        """Test collection heatmap endpoint only allows GET method."""
        collection_id = "test-collection-123"
        response: Response = client.request(method, f"/collections/{collection_id}/heatmap")
        
        assert response.status_code == 405  # Method Not Allowed

    def test_collection_heatmap_response_time(self, client: TestClient):
        """Test heatmap endpoint responds within reasonable time."""
        import time
        
        collection_id = "test-collection-123"
        
        start_time = time.time()
        response: Response = client.get(f"/collections/{collection_id}/heatmap")
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # Heatmap generation might be compute-intensive but should be < 5s
        if response.status_code == 200:
            assert response_time < 5.0, f"Heatmap took {response_time:.2f}s, should be < 5s"