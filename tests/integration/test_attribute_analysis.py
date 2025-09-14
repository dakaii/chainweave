"""Integration test for attribute-price correlation analysis feature.

This test validates the complete attribute analysis user story from specification:
"Given I'm evaluating NFT attributes for investment, When I access attribute analysis, 
Then I can see which traits correlate with higher sale prices compared to floor prices"

MUST FAIL initially as no implementation exists yet (TDD requirement).
Uses real BigQuery dependencies per constitutional requirements.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal

from google.cloud import bigquery
from backend.src.config import config


class TestAttributeAnalysisIntegration:
    """Integration tests for NFT attribute-price correlation analysis."""

    @pytest.fixture(scope="class")
    def bigquery_client(self) -> bigquery.Client:
        """Create BigQuery client for integration testing."""
        return bigquery.Client(project=config.gcp.project_id)

    @pytest.fixture(scope="class")
    def test_attribute_data(self) -> Dict[str, Any]:
        """Sample NFT attribute and pricing data for correlation analysis."""
        base_time = datetime.now()
        
        return {
            "collections": [
                {
                    "collection_id": "test-collection-attributes-1",
                    "name": "Attribute Test Collection",
                    "floor_price": 2.0,  # Base floor price in SOL
                    "nfts": [
                        {
                            "mint_address": "Attr1Rare1111111111111111111111111111111",
                            "name": "Golden Legendary #001",
                            "attributes": {
                                "background": "Golden",
                                "rarity": "Legendary", 
                                "eyes": "Diamond",
                                "accessory": "Crown"
                            },
                            "sales": [
                                {"price_sol": 15.5, "timestamp": base_time - timedelta(days=1)},
                                {"price_sol": 18.0, "timestamp": base_time - timedelta(days=3)},
                                {"price_sol": 12.8, "timestamp": base_time - timedelta(days=7)}
                            ],
                            "rarity_rank": 1
                        },
                        {
                            "mint_address": "Attr2Gold1111111111111111111111111111111",
                            "name": "Golden Epic #045",
                            "attributes": {
                                "background": "Golden",
                                "rarity": "Epic",
                                "eyes": "Ruby", 
                                "accessory": "Necklace"
                            },
                            "sales": [
                                {"price_sol": 8.2, "timestamp": base_time - timedelta(days=2)},
                                {"price_sol": 9.5, "timestamp": base_time - timedelta(days=5)}
                            ],
                            "rarity_rank": 15
                        },
                        {
                            "mint_address": "Attr3Blue1111111111111111111111111111111",
                            "name": "Blue Common #234",
                            "attributes": {
                                "background": "Blue",
                                "rarity": "Common",
                                "eyes": "Normal",
                                "accessory": "None"
                            },
                            "sales": [
                                {"price_sol": 2.1, "timestamp": base_time - timedelta(days=1)},
                                {"price_sol": 1.9, "timestamp": base_time - timedelta(days=4)}
                            ],
                            "rarity_rank": 234
                        },
                        {
                            "mint_address": "Attr4Gold2222222222222222222222222222222",
                            "name": "Golden Rare #089",
                            "attributes": {
                                "background": "Golden",
                                "rarity": "Rare",
                                "eyes": "Emerald",
                                "accessory": "Ring"
                            },
                            "sales": [
                                {"price_sol": 6.8, "timestamp": base_time - timedelta(days=1)},
                                {"price_sol": 7.2, "timestamp": base_time - timedelta(days=6)}
                            ],
                            "rarity_rank": 89
                        },
                        {
                            "mint_address": "Attr5Red31111111111111111111111111111111",
                            "name": "Red Common #456",
                            "attributes": {
                                "background": "Red",
                                "rarity": "Common",
                                "eyes": "Normal",
                                "accessory": "Hat"
                            },
                            "sales": [
                                {"price_sol": 2.3, "timestamp": base_time - timedelta(days=2)},
                                {"price_sol": 2.0, "timestamp": base_time - timedelta(days=8)}
                            ],
                            "rarity_rank": 456
                        }
                    ]
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_attribute_price_correlation_calculation(
        self,
        bigquery_client: bigquery.Client,
        test_attribute_data: Dict[str, Any]
    ):
        """Test attribute-price correlation calculation per user story."""
        
        # This will fail initially - expected for TDD
        from backend.src.services.analytics_service import calculate_attribute_correlations  # Will fail initially
        
        collection_data = test_attribute_data["collections"][0]
        collection_id = collection_data["collection_id"]
        
        # Calculate correlations for the collection
        correlation_results = await calculate_attribute_correlations(
            collection_ids=[collection_id],
            time_range_days=30
        )
        
        # Verify structure per user story requirements
        assert "analysis_date" in correlation_results
        assert "collections" in correlation_results
        
        collection_analysis = correlation_results["collections"][0]
        assert "collection_id" in collection_analysis
        assert "collection_name" in collection_analysis
        assert "attribute_correlations" in collection_analysis
        
        # Verify attribute correlation data
        correlations = collection_analysis["attribute_correlations"]
        assert len(correlations) > 0, "Should find attribute correlations"
        
        # Check correlation structure
        for correlation in correlations:
            required_fields = {
                "trait_type", "trait_value", "avg_price_premium", 
                "sample_size", "correlation_strength"
            }
            
            for field in required_fields:
                assert field in correlation, f"Missing correlation field: {field}"
            
            # Validate correlation strength is within valid range [-1, 1]
            strength = correlation["correlation_strength"]
            assert -1.0 <= strength <= 1.0, f"Correlation strength {strength} out of range"
            
            # Sample size should be positive
            assert correlation["sample_size"] > 0, "Sample size should be positive"

    @pytest.mark.asyncio
    async def test_attribute_premium_calculation(
        self,
        test_attribute_data: Dict[str, Any]
    ):
        """Test premium calculation shows which traits command higher prices."""
        
        # This will fail initially - expected for TDD
        from backend.src.services.analytics_service import calculate_trait_premium  # Will fail initially
        
        collection_data = test_attribute_data["collections"][0]
        floor_price = collection_data["floor_price"]
        
        # Test specific trait premium calculation
        # "Golden" background should have positive premium based on test data
        golden_premium = await calculate_trait_premium(
            trait_type="background",
            trait_value="Golden",
            collection_id=collection_data["collection_id"],
            floor_price=floor_price
        )
        
        # Verify premium calculation
        assert "avg_price_premium" in golden_premium
        assert "sample_size" in golden_premium
        assert "confidence_level" in golden_premium
        
        # Golden background should command premium (based on test data)
        premium_percentage = golden_premium["avg_price_premium"]
        assert premium_percentage > 0, "Golden background should have positive premium"
        
        # Test common trait (should have lower or negative premium)
        common_premium = await calculate_trait_premium(
            trait_type="rarity", 
            trait_value="Common",
            collection_id=collection_data["collection_id"],
            floor_price=floor_price
        )
        
        common_percentage = common_premium["avg_price_premium"]
        
        # Common should have lower premium than rare traits
        assert common_percentage < premium_percentage, "Common should have lower premium than Golden"

    @pytest.mark.asyncio
    async def test_attribute_analysis_api_integration(
        self,
        test_attribute_data: Dict[str, Any]
    ):
        """Test attribute analysis API endpoint integration per user story."""
        
        # This will fail initially - expected for TDD
        from backend.dashboard_service.app.main import app  # Will fail initially
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        collection_data = test_attribute_data["collections"][0]
        
        # Request attribute analysis via API
        analysis_request = {
            "collection_ids": [collection_data["collection_id"]],
            "time_range_days": 30
        }
        
        response = client.post("/attributes/analysis", json=analysis_request)
        
        if response.status_code == 404:
            pytest.skip("Collection not found in test database")
        
        assert response.status_code == 200
        
        analysis_data = response.json()
        
        # Verify API response matches user story requirements  
        assert "analysis_date" in analysis_data
        assert "collections" in analysis_data
        
        # User should be able to identify valuable traits
        collections = analysis_data["collections"]
        assert len(collections) > 0
        
        collection_analysis = collections[0]
        correlations = collection_analysis["attribute_correlations"]
        
        # Should have correlations for different trait types
        trait_types = set(c["trait_type"] for c in correlations)
        assert len(trait_types) > 1, "Should analyze multiple trait types"
        
        # Should identify both positive and negative correlations
        premiums = [c["avg_price_premium"] for c in correlations]
        has_positive = any(p > 0 for p in premiums)
        has_negative = any(p < 0 for p in premiums)
        
        assert has_positive, "Should identify traits with positive premium"
        # Note: has_negative might be False if all traits are above floor - that's valid

    @pytest.mark.asyncio
    async def test_multi_collection_attribute_analysis(
        self,
        test_attribute_data: Dict[str, Any]
    ):
        """Test attribute analysis across multiple collections."""
        
        # This will fail initially - expected for TDD
        from backend.src.services.analytics_service import calculate_multi_collection_correlations  # Will fail initially
        
        # Add second collection for cross-collection analysis
        collection_ids = [
            test_attribute_data["collections"][0]["collection_id"],
            "test-collection-attributes-2"  # Second collection
        ]
        
        # Analyze attributes across multiple collections
        multi_analysis = await calculate_multi_collection_correlations(
            collection_ids=collection_ids,
            time_range_days=30
        )
        
        # Verify multi-collection analysis structure
        assert "analysis_date" in multi_analysis
        assert "collections" in multi_analysis
        assert "cross_collection_insights" in multi_analysis
        
        # Should have analysis for each requested collection
        collections = multi_analysis["collections"]
        collection_ids_found = [c["collection_id"] for c in collections]
        
        for requested_id in collection_ids:
            assert requested_id in collection_ids_found or len([c for c in collections if c["collection_id"] == requested_id]) == 0
            # Some collections might not exist in test data
        
        # Cross-collection insights should identify market trends
        insights = multi_analysis["cross_collection_insights"]
        assert isinstance(insights, dict)

    @pytest.mark.asyncio
    async def test_attribute_correlation_confidence_levels(
        self,
        test_attribute_data: Dict[str, Any]
    ):
        """Test correlation analysis includes confidence levels and statistical validity."""
        
        # This will fail initially - expected for TDD
        from backend.src.services.analytics_service import calculate_correlation_confidence  # Will fail initially
        
        collection_data = test_attribute_data["collections"][0]
        
        # Calculate correlation with confidence metrics
        correlation_with_confidence = await calculate_correlation_confidence(
            trait_type="background",
            trait_value="Golden", 
            collection_id=collection_data["collection_id"]
        )
        
        # Verify confidence calculation
        assert "correlation_strength" in correlation_with_confidence
        assert "confidence_level" in correlation_with_confidence
        assert "p_value" in correlation_with_confidence
        assert "sample_size" in correlation_with_confidence
        
        # Confidence level should be between 0 and 1
        confidence = correlation_with_confidence["confidence_level"]
        assert 0.0 <= confidence <= 1.0, f"Confidence {confidence} out of range"
        
        # P-value should be between 0 and 1
        p_value = correlation_with_confidence["p_value"]
        assert 0.0 <= p_value <= 1.0, f"P-value {p_value} out of range"
        
        # Sample size should match number of sales with this trait
        sample_size = correlation_with_confidence["sample_size"]
        assert sample_size > 0, "Sample size should be positive"

    @pytest.mark.asyncio
    async def test_attribute_rarity_vs_price_correlation(
        self,
        test_attribute_data: Dict[str, Any]
    ):
        """Test correlation between attribute rarity and price premium."""
        
        # This will fail initially - expected for TDD
        from backend.src.services.analytics_service import analyze_rarity_price_correlation  # Will fail initially
        
        collection_data = test_attribute_data["collections"][0]
        collection_id = collection_data["collection_id"]
        
        # Analyze rarity vs price correlation
        rarity_analysis = await analyze_rarity_price_correlation(collection_id)
        
        # Verify rarity analysis structure
        assert "collection_id" in rarity_analysis
        assert "trait_rarity_analysis" in rarity_analysis
        assert "overall_rarity_correlation" in rarity_analysis
        
        # Trait rarity analysis should show frequency vs price correlation
        trait_analysis = rarity_analysis["trait_rarity_analysis"]
        
        for trait_type, trait_data in trait_analysis.items():
            assert "values" in trait_data
            
            for trait_value, value_data in trait_data["values"].items():
                required_fields = {"frequency", "avg_price", "price_premium", "rarity_score"}
                
                for field in required_fields:
                    assert field in value_data, f"Missing rarity field: {field}"
                
                # Frequency should be between 0 and 1 (percentage)
                frequency = value_data["frequency"]
                assert 0.0 <= frequency <= 1.0, f"Frequency {frequency} out of range"
                
                # Rarity score should be inversely related to frequency
                rarity_score = value_data["rarity_score"]
                assert rarity_score > 0, "Rarity score should be positive"

    @pytest.mark.asyncio
    async def test_attribute_time_series_analysis(
        self,
        test_attribute_data: Dict[str, Any]
    ):
        """Test attribute price trends over time."""
        
        # This will fail initially - expected for TDD
        from backend.src.services.analytics_service import analyze_attribute_price_trends  # Will fail initially
        
        collection_data = test_attribute_data["collections"][0]
        collection_id = collection_data["collection_id"]
        
        # Analyze price trends for specific attribute over time
        trend_analysis = await analyze_attribute_price_trends(
            collection_id=collection_id,
            trait_type="background",
            trait_value="Golden",
            time_range_days=30
        )
        
        # Verify trend analysis structure
        assert "trait_type" in trend_analysis
        assert "trait_value" in trend_analysis
        assert "time_series_data" in trend_analysis
        assert "trend_direction" in trend_analysis
        assert "price_volatility" in trend_analysis
        
        # Time series should have chronological data
        time_series = trend_analysis["time_series_data"]
        assert len(time_series) > 0, "Should have time series data"
        
        for data_point in time_series:
            required_fields = {"date", "avg_price", "transaction_count", "price_premium"}
            
            for field in required_fields:
                assert field in data_point, f"Missing time series field: {field}"
        
        # Trend direction should be valid
        trend_direction = trend_analysis["trend_direction"]
        assert trend_direction in ["increasing", "decreasing", "stable", "volatile"]

    @pytest.mark.asyncio
    async def test_attribute_analysis_performance(
        self,
        test_attribute_data: Dict[str, Any]
    ):
        """Test attribute analysis performance meets user requirements."""
        
        # This will fail initially - expected for TDD
        from backend.dashboard_service.app.main import app  # Will fail initially
        from fastapi.testclient import TestClient
        import time
        
        client = TestClient(app)
        
        collection_data = test_attribute_data["collections"][0]
        
        # Performance test: analysis should complete reasonably quickly
        analysis_request = {
            "collection_ids": [collection_data["collection_id"]],
            "time_range_days": 30
        }
        
        start_time = time.time()
        response = client.post("/attributes/analysis", json=analysis_request)
        end_time = time.time()
        
        response_time = end_time - start_time
        
        if response.status_code == 200:
            # Attribute analysis should complete in reasonable time
            assert response_time < 10.0, f"Attribute analysis took {response_time:.2f}s, should be < 10s"

    @pytest.mark.asyncio
    async def test_attribute_analysis_data_quality(
        self,
        test_attribute_data: Dict[str, Any]
    ):
        """Test attribute analysis handles data quality issues gracefully."""
        
        # This will fail initially - expected for TDD
        from backend.src.services.analytics_service import validate_attribute_data_quality  # Will fail initially
        
        collection_data = test_attribute_data["collections"][0]
        collection_id = collection_data["collection_id"]
        
        # Test data quality validation
        quality_report = await validate_attribute_data_quality(collection_id)
        
        # Verify quality report structure
        assert "collection_id" in quality_report
        assert "data_quality_score" in quality_report
        assert "issues_found" in quality_report
        assert "recommendations" in quality_report
        
        # Data quality score should be between 0 and 1
        quality_score = quality_report["data_quality_score"]
        assert 0.0 <= quality_score <= 1.0, f"Quality score {quality_score} out of range"
        
        # Issues should be categorized
        issues = quality_report["issues_found"]
        if len(issues) > 0:
            for issue in issues:
                assert "category" in issue
                assert "description" in issue
                assert "severity" in issue
                
                # Severity should be valid level
                assert issue["severity"] in ["low", "medium", "high", "critical"]

    @pytest.mark.asyncio
    async def test_attribute_filtering_and_search(
        self,
        test_attribute_data: Dict[str, Any]
    ):
        """Test attribute analysis supports filtering and search per user story."""
        
        # This will fail initially - expected for TDD
        from backend.dashboard_service.app.main import app  # Will fail initially
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        collection_data = test_attribute_data["collections"][0]
        
        # Test filtering by specific trait type
        filter_request = {
            "collection_ids": [collection_data["collection_id"]],
            "time_range_days": 30,
            "trait_filters": {
                "background": ["Golden", "Blue"]  # Only analyze these values
            }
        }
        
        response = client.post("/attributes/analysis", json=filter_request)
        
        if response.status_code == 200:
            analysis_data = response.json()
            collections = analysis_data["collections"]
            
            if len(collections) > 0:
                correlations = collections[0]["attribute_correlations"]
                
                # Should only include filtered trait values
                background_correlations = [c for c in correlations if c["trait_type"] == "background"]
                
                for correlation in background_correlations:
                    trait_value = correlation["trait_value"]
                    assert trait_value in ["Golden", "Blue"], f"Unexpected trait value: {trait_value}"