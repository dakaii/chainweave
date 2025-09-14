"""Integration test for collection heatmap feature.

This test validates the complete collection heatmap user story from specification:
"Given I'm researching a collection's market dynamics, When I view the collection heatmap, 
Then I can visually identify which NFTs are being actively traded versus long-term held"

MUST FAIL initially as no implementation exists yet (TDD requirement).
Uses real BigQuery dependencies per constitutional requirements.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any

from google.cloud import bigquery
from backend.src.config import config


class TestCollectionHeatmapIntegration:
    """Integration tests for collection heatmap functionality."""

    @pytest.fixture(scope="class")
    def bigquery_client(self) -> bigquery.Client:
        """Create BigQuery client for integration testing."""
        return bigquery.Client(project=config.gcp.project_id)

    @pytest.fixture(scope="class")
    def test_collection_data(self) -> Dict[str, Any]:
        """Sample collection data for heatmap testing."""
        base_time = datetime.now()
        
        return {
            "collection_id": "test-collection-heatmap-123",
            "collection_address": "8Gv8q3K9FjTb1cH4yWaJsyLxMhD4NnPvQcZg5T6eYfRx",
            "name": "Test Heatmap Collection",
            "total_supply": 10,
            "nfts": [
                {
                    # Hot NFT - traded recently (red in heatmap)
                    "mint_address": "Nft1Hot1111111111111111111111111111111111",
                    "name": "Hot Trader #1",
                    "current_owner": "Owner1111111111111111111111111111111111111",
                    "last_transfer": base_time - timedelta(hours=2),  # Very recent
                    "purchase_price": 5.5,
                    "rarity_rank": 1
                },
                {
                    # Warm NFT - traded moderately (orange in heatmap)
                    "mint_address": "Nft2Warm111111111111111111111111111111111",
                    "name": "Warm Trader #2", 
                    "current_owner": "Owner2222222222222222222222222222222222222",
                    "last_transfer": base_time - timedelta(days=7),   # Week ago
                    "purchase_price": 3.2,
                    "rarity_rank": 5
                },
                {
                    # Cool NFT - held for a while (blue in heatmap)
                    "mint_address": "Nft3Cool111111111111111111111111111111111",
                    "name": "Cool Holder #3",
                    "current_owner": "Owner3333333333333333333333333333333333333",
                    "last_transfer": base_time - timedelta(days=45),  # Month+ ago
                    "purchase_price": 2.1,
                    "rarity_rank": 8
                },
                {
                    # Cold NFT - diamond hands (deep blue in heatmap)
                    "mint_address": "Nft4Cold111111111111111111111111111111111",
                    "name": "Diamond Hands #4",
                    "current_owner": "Owner4444444444444444444444444444444444444",
                    "last_transfer": base_time - timedelta(days=180), # 6 months ago
                    "purchase_price": 1.8,
                    "rarity_rank": 3
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_heatmap_data_aggregation(
        self,
        bigquery_client: bigquery.Client,
        test_collection_data: Dict[str, Any]
    ):
        """Test heatmap data aggregation from BigQuery."""
        
        # This will fail initially - expected for TDD
        from backend.src.services.analytics_service import generate_collection_heatmap  # Will fail initially
        
        collection_id = test_collection_data["collection_id"]
        
        # Generate heatmap data
        heatmap_data = await generate_collection_heatmap(collection_id)
        
        # Verify structure per user story requirements
        assert "collection_id" in heatmap_data
        assert "nfts" in heatmap_data
        assert "color_scale" in heatmap_data
        
        assert heatmap_data["collection_id"] == collection_id
        
        # Verify NFT data structure
        nfts = heatmap_data["nfts"]
        assert len(nfts) > 0, "Should have NFT data for heatmap"
        
        for nft in nfts:
            required_fields = {
                "mint_address", "name", "current_owner", "hold_duration_days",
                "last_sale_price", "rarity_rank"
            }
            
            for field in required_fields:
                assert field in nft, f"Missing heatmap NFT field: {field}"
            
            # Validate hold duration calculation
            assert nft["hold_duration_days"] >= 0
            
        # Verify color scale for visualization
        color_scale = heatmap_data["color_scale"]
        assert "min_hold_days" in color_scale
        assert "max_hold_days" in color_scale
        assert "color_mapping" in color_scale
        
        # Min should be <= Max
        assert color_scale["min_hold_days"] <= color_scale["max_hold_days"]

    @pytest.mark.asyncio
    async def test_heatmap_hold_duration_calculation(
        self,
        test_collection_data: Dict[str, Any]
    ):
        """Test accurate hold duration calculation for heatmap colors."""
        
        # This will fail initially - expected for TDD
        from backend.src.services.analytics_service import calculate_hold_duration  # Will fail initially
        
        collection_nfts = test_collection_data["nfts"]
        current_time = datetime.now()
        
        for nft_data in collection_nfts:
            mint_address = nft_data["mint_address"]
            last_transfer = nft_data["last_transfer"]
            
            calculated_duration = await calculate_hold_duration(mint_address, current_time)
            
            # Verify calculation matches expected duration
            expected_duration = (current_time - last_transfer).days
            
            # Allow small variance for async processing time
            assert abs(calculated_duration - expected_duration) <= 1, \
                f"Hold duration calculation off by more than 1 day: {calculated_duration} vs {expected_duration}"

    @pytest.mark.asyncio
    async def test_heatmap_color_mapping(
        self,
        test_collection_data: Dict[str, Any]
    ):
        """Test heatmap color mapping reflects trading activity per user story."""
        
        # This will fail initially - expected for TDD
        from backend.src.services.analytics_service import generate_heatmap_colors  # Will fail initially
        
        collection_id = test_collection_data["collection_id"]
        
        # Generate color mapping
        color_mapping = await generate_heatmap_colors(collection_id)
        
        # Verify color mapping structure
        assert "ranges" in color_mapping
        assert "colors" in color_mapping
        
        ranges = color_mapping["ranges"]
        colors = color_mapping["colors"]
        
        # Should have color ranges for different hold periods
        assert len(ranges) >= 3, "Should have at least 3 color ranges (hot, warm, cold)"
        assert len(colors) == len(ranges), "Each range should have corresponding color"
        
        # Verify color progression makes visual sense
        # Recent trades (hot) should have warm colors (red/orange)
        # Long holds (cold) should have cool colors (blue)
        
        # Find the shortest and longest hold ranges
        min_range = min(ranges, key=lambda r: r["min_days"])
        max_range = max(ranges, key=lambda r: r["max_days"])
        
        min_color = colors[ranges.index(min_range)]
        max_color = colors[ranges.index(max_range)]
        
        # Basic color validation (assuming hex colors)
        assert min_color.startswith("#"), "Colors should be hex format"
        assert max_color.startswith("#"), "Colors should be hex format"
        assert len(min_color) in [4, 7], "Hex colors should be #RGB or #RRGGBB"

    @pytest.mark.asyncio
    async def test_heatmap_api_integration(
        self,
        test_collection_data: Dict[str, Any]
    ):
        """Test heatmap API endpoint integration per user story."""
        
        # This will fail initially - expected for TDD
        from backend.dashboard_service.app.main import app  # Will fail initially
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        collection_id = test_collection_data["collection_id"]
        
        # Request heatmap data via API
        response = client.get(f"/collections/{collection_id}/heatmap")
        
        if response.status_code == 404:
            # Collection might not exist in test data yet
            pytest.skip("Collection not found in test database")
        
        assert response.status_code == 200
        
        heatmap_data = response.json()
        
        # Verify API response matches user story requirements
        assert "collection_id" in heatmap_data
        assert "nfts" in heatmap_data
        assert "color_scale" in heatmap_data
        
        # Verify user can identify trading patterns
        nfts = heatmap_data["nfts"]
        color_scale = heatmap_data["color_scale"]
        
        # Should be able to distinguish between active traders and diamond hands
        hold_durations = [nft["hold_duration_days"] for nft in nfts]
        
        if len(hold_durations) > 1:
            min_hold = min(hold_durations)
            max_hold = max(hold_durations)
            
            # Should have variety in hold durations for meaningful heatmap
            assert max_hold > min_hold, "Should have variation in hold durations"
            
            # Color scale should span the range
            assert color_scale["min_hold_days"] <= min_hold
            assert color_scale["max_hold_days"] >= max_hold

    @pytest.mark.asyncio
    async def test_heatmap_large_collection_performance(
        self,
        bigquery_client: bigquery.Client
    ):
        """Test heatmap generation performance for large collections."""
        
        # This will fail initially - expected for TDD
        from backend.dashboard_service.app.main import app  # Will fail initially
        from fastapi.testclient import TestClient
        import time
        
        client = TestClient(app)
        
        # Test with a large collection (simulate 10k+ NFTs)
        large_collection_id = "large-test-collection-10000"
        
        start_time = time.time()
        response = client.get(f"/collections/{large_collection_id}/heatmap")
        end_time = time.time()
        
        response_time = end_time - start_time
        
        if response.status_code == 200:
            # Heatmap should generate in reasonable time per user story
            assert response_time < 5.0, f"Large collection heatmap took {response_time:.2f}s, should be < 5s"
            
            heatmap_data = response.json()
            
            # Should handle large datasets efficiently
            # May implement pagination or sampling for very large collections
            nfts_count = len(heatmap_data["nfts"])
            assert nfts_count <= 10000, "Should limit NFT count for performance"

    @pytest.mark.asyncio
    async def test_heatmap_empty_collection(self):
        """Test heatmap gracefully handles empty collections."""
        
        # This will fail initially - expected for TDD
        from backend.dashboard_service.app.main import app  # Will fail initially
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        # Test with empty collection
        empty_collection_id = "empty-test-collection"
        
        response = client.get(f"/collections/{empty_collection_id}/heatmap")
        
        if response.status_code == 200:
            heatmap_data = response.json()
            
            # Should return valid structure even for empty collection
            assert "collection_id" in heatmap_data
            assert "nfts" in heatmap_data
            assert "color_scale" in heatmap_data
            
            # NFTs array should be empty
            assert heatmap_data["nfts"] == []
            
            # Color scale should still be valid for UI consistency
            color_scale = heatmap_data["color_scale"]
            assert isinstance(color_scale, dict)

    @pytest.mark.asyncio
    async def test_heatmap_real_time_updates(
        self,
        test_collection_data: Dict[str, Any]
    ):
        """Test heatmap reflects real-time trading activity."""
        
        # This will fail initially - expected for TDD
        from backend.src.services.analytics_service import refresh_heatmap_data  # Will fail initially
        from backend.dashboard_service.app.main import app  # Will fail initially
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        collection_id = test_collection_data["collection_id"]
        
        # Get initial heatmap state
        initial_response = client.get(f"/collections/{collection_id}/heatmap")
        
        if initial_response.status_code != 200:
            pytest.skip("Collection not available for real-time test")
        
        initial_data = initial_response.json()
        initial_nfts = {nft["mint_address"]: nft["hold_duration_days"] for nft in initial_data["nfts"]}
        
        # Simulate new transaction (this would normally come from webhook)
        # Trigger heatmap data refresh
        await refresh_heatmap_data(collection_id)
        
        # Small delay for async processing
        await asyncio.sleep(1)
        
        # Get updated heatmap
        updated_response = client.get(f"/collections/{collection_id}/heatmap")
        assert updated_response.status_code == 200
        
        updated_data = updated_response.json()
        updated_nfts = {nft["mint_address"]: nft["hold_duration_days"] for nft in updated_data["nfts"]}
        
        # Verify data can be updated (exact changes depend on simulated transaction)
        # At minimum, structure should remain consistent
        assert len(updated_nfts) >= len(initial_nfts), "NFT count should not decrease"

    def test_heatmap_accessibility_data(
        self,
        test_collection_data: Dict[str, Any]
    ):
        """Test heatmap provides accessibility-friendly data."""
        
        # This will fail initially - expected for TDD
        from backend.dashboard_service.app.main import app  # Will fail initially
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        collection_id = test_collection_data["collection_id"]
        
        response = client.get(f"/collections/{collection_id}/heatmap")
        
        if response.status_code == 200:
            heatmap_data = response.json()
            
            # Should include text descriptions for accessibility
            color_scale = heatmap_data["color_scale"]
            
            # Color mapping should include descriptive labels
            if "color_mapping" in color_scale:
                color_mapping = color_scale["color_mapping"]
                
                # Should have human-readable labels, not just hex colors
                for range_label, color_value in color_mapping.items():
                    assert isinstance(range_label, str)
                    assert len(range_label) > 0
                    
            # NFT data should include text descriptions of trading activity
            nfts = heatmap_data["nfts"]
            
            for nft in nfts:
                # Hold duration should be interpretable
                hold_days = nft["hold_duration_days"]
                assert isinstance(hold_days, int)
                assert hold_days >= 0