"""Integration test for whale tracking feature.

This test validates the complete whale tracking user story from specification:
"Given I want to track influential traders, When I access the whale monitoring feature, 
Then I can see a list of high-volume wallets and their recent activity with transaction timelines"

MUST FAIL initially as no implementation exists yet (TDD requirement).
Uses real BigQuery and Pub/Sub dependencies per constitutional requirements.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any

from google.cloud import bigquery
from google.cloud import pubsub_v1

from backend.src.config import config


class TestWhaleTrackingIntegration:
    """Integration tests for whale tracking functionality."""

    @pytest.fixture(scope="class")
    def bigquery_client(self) -> bigquery.Client:
        """Create BigQuery client for integration testing."""
        return bigquery.Client(project=config.gcp.project_id)

    @pytest.fixture(scope="class")
    def pubsub_publisher(self) -> pubsub_v1.PublisherClient:
        """Create Pub/Sub publisher for integration testing."""
        return pubsub_v1.PublisherClient()

    @pytest.fixture(scope="class") 
    def test_whale_data(self) -> List[Dict[str, Any]]:
        """Sample whale transaction data for testing."""
        return [
            {
                "wallet_address": "ByXB7zV4TKa3xxC6PJxEQgm7cZxvXHU9C5qhHdKQN4R4",
                "total_volume_traded": 250.5,  # Above whale threshold
                "total_nfts_owned": 75,        # Above whale threshold
                "transactions": [
                    {
                        "signature": "5KJp9QjRgFryfbTTv8RtWGGCaYJJ7xBqQGY7FoXbpzSFwWrVvH3K7JX8QgGH1AjSBUL6Vh6Y8N3xAhVkCJ9wGxRr",
                        "mint_address": "8Gv8q3K9FjTb1cH4yWaJsyLxMhD4NnPvQcZg5T6eYfRx",
                        "event_type": "sale",
                        "price_sol": 15.5,
                        "timestamp": datetime.now() - timedelta(hours=2)
                    },
                    {
                        "signature": "3MJp8QjRgFryfbTTv8RtWGGCaYJJ7xBqQGY7FoXbpzSFwWrVvH3K7JX8QgGH1AjSBUL6Vh6Y8N3xAhVkCJ9wTxRr",
                        "mint_address": "9Gv8q3K9FjTb1cH4yWaJsyLxMhD4NnPvQcZg5T6eYfRx",
                        "event_type": "purchase", 
                        "price_sol": 12.0,
                        "timestamp": datetime.now() - timedelta(hours=1)
                    }
                ]
            },
            {
                "wallet_address": "9CwD5fX7JHs8RqVbGhTyE3nH4P2vZmKaL6tQsYuMxNpF",
                "total_volume_traded": 45.2,   # Below whale threshold
                "total_nfts_owned": 12,        # Below whale threshold
                "transactions": [
                    {
                        "signature": "4MJp8QjRgFryfbTTv8RtWGGCaYJJ7xBqQGY7FoXbpzSFwWrVvH3K7JX8QgGH1AjSBUL6Vh6Y8N3xAhVkCJ9wTxRr",
                        "mint_address": "7Gv8q3K9FjTb1cH4yWaJsyLxMhD4NnPvQcZg5T6eYfRx",
                        "event_type": "sale",
                        "price_sol": 2.1,
                        "timestamp": datetime.now() - timedelta(hours=3)
                    }
                ]
            }
        ]

    @pytest.mark.asyncio
    async def test_whale_detection_pipeline(
        self, 
        bigquery_client: bigquery.Client,
        pubsub_publisher: pubsub_v1.PublisherClient,
        test_whale_data: List[Dict[str, Any]]
    ):
        """Test complete whale detection pipeline: webhook → processing → detection → storage."""
        
        # This will fail initially - expected for TDD
        # When implementation exists, this tests the full pipeline
        
        # Step 1: Simulate webhook receiving transaction data
        # This would normally come from Helius webhook
        from backend.src.services.webhook_service import process_helius_webhook  # Will fail initially
        from backend.src.services.whale_service import detect_whale_activity     # Will fail initially
        
        whale_wallet = test_whale_data[0]
        non_whale_wallet = test_whale_data[1]
        
        # Step 2: Process transactions through pipeline
        for transaction in whale_wallet["transactions"]:
            # Simulate webhook payload
            webhook_payload = {
                "type": "ENHANCED",
                "signature": transaction["signature"],
                "timestamp": int(transaction["timestamp"].timestamp() * 1000),
                "slot": 259841234,
                "events": {
                    "nft": {
                        "nftMint": transaction["mint_address"],
                        "newOwner": whale_wallet["wallet_address"],
                        "price": transaction["price_sol"],
                        "marketplace": "Magic Eden"
                    }
                }
            }
            
            # Process webhook (should publish to Pub/Sub)
            result = await process_helius_webhook(webhook_payload)
            assert result["status"] == "received"
            
        # Step 3: Wait for async processing to complete
        await asyncio.sleep(2)  # Allow time for Pub/Sub message processing
        
        # Step 4: Verify whale detection
        whale_status = await detect_whale_activity(whale_wallet["wallet_address"])
        non_whale_status = await detect_whale_activity(non_whale_wallet["wallet_address"])
        
        # Assertions per user story requirements
        assert whale_status["is_whale"] == True, "High-volume wallet should be detected as whale"
        assert non_whale_status["is_whale"] == False, "Low-volume wallet should not be whale"
        
        # Step 5: Verify whale alert generation
        whale_alerts = whale_status.get("recent_alerts", [])
        assert len(whale_alerts) > 0, "Whale activity should generate alerts"
        
        # Step 6: Verify whale appears in dashboard API
        from backend.dashboard_service.app.main import app  # Will fail initially
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        response = client.get("/whales?activity_days=1")
        
        assert response.status_code == 200
        whales_data = response.json()
        
        # Whale should appear in list
        whale_addresses = [w["wallet_address"] for w in whales_data["whales"]]
        assert whale_wallet["wallet_address"] in whale_addresses
        
        # Non-whale should not appear
        assert non_whale_wallet["wallet_address"] not in whale_addresses

    @pytest.mark.asyncio 
    async def test_whale_activity_timeline(
        self,
        test_whale_data: List[Dict[str, Any]]
    ):
        """Test whale activity timeline display per user story."""
        
        # This will fail initially - expected for TDD
        from backend.src.services.analytics_service import get_whale_timeline  # Will fail initially
        
        whale_wallet = test_whale_data[0]
        
        # Get whale activity timeline
        timeline = await get_whale_timeline(
            wallet_address=whale_wallet["wallet_address"],
            days_back=7
        )
        
        # Verify timeline structure per user story
        assert "wallet_address" in timeline
        assert "activity_events" in timeline
        assert "summary_metrics" in timeline
        
        # Activity events should be chronologically ordered
        events = timeline["activity_events"]
        if len(events) > 1:
            for i in range(len(events) - 1):
                current_time = datetime.fromisoformat(events[i]["timestamp"])
                next_time = datetime.fromisoformat(events[i + 1]["timestamp"])
                assert current_time >= next_time, "Timeline should be in reverse chronological order"
        
        # Summary metrics should match user story requirements
        summary = timeline["summary_metrics"]
        required_metrics = {
            "total_transactions", "total_volume_sol", "unique_collections",
            "avg_transaction_size", "largest_transaction"
        }
        
        for metric in required_metrics:
            assert metric in summary, f"Missing timeline metric: {metric}"

    @pytest.mark.asyncio
    async def test_whale_threshold_configuration(self):
        """Test whale detection thresholds are configurable."""
        
        # This will fail initially - expected for TDD
        from backend.src.services.whale_service import update_whale_thresholds  # Will fail initially
        from backend.src.services.whale_service import get_whale_thresholds     # Will fail initially
        
        # Get current thresholds
        current_thresholds = await get_whale_thresholds()
        
        assert "volume_threshold_sol" in current_thresholds
        assert "nft_count_threshold" in current_thresholds
        assert "alert_cooldown_hours" in current_thresholds
        
        # Update thresholds
        new_thresholds = {
            "volume_threshold_sol": 200.0,
            "nft_count_threshold": 100,
            "alert_cooldown_hours": 12
        }
        
        result = await update_whale_thresholds(new_thresholds)
        assert result["success"] == True
        
        # Verify thresholds were updated
        updated_thresholds = await get_whale_thresholds()
        assert updated_thresholds["volume_threshold_sol"] == 200.0
        assert updated_thresholds["nft_count_threshold"] == 100
        assert updated_thresholds["alert_cooldown_hours"] == 12

    @pytest.mark.asyncio
    async def test_whale_data_persistence(
        self,
        bigquery_client: bigquery.Client,
        test_whale_data: List[Dict[str, Any]]
    ):
        """Test whale data is properly stored in BigQuery."""
        
        # This will fail initially - expected for TDD
        # Verify whale profile data exists in BigQuery
        
        whale_wallet = test_whale_data[0]
        
        query = f"""
        SELECT 
            wallet_address,
            total_volume_traded,
            total_nfts_owned,
            whale_status,
            last_activity
        FROM `{config.gcp.project_id}.{config.bigquery.dataset}.wallet_profile`
        WHERE wallet_address = @wallet_address
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("wallet_address", "STRING", whale_wallet["wallet_address"])
            ]
        )
        
        query_job = bigquery_client.query(query, job_config=job_config)
        results = list(query_job.result())
        
        # Should find the whale wallet
        assert len(results) > 0, "Whale wallet should exist in BigQuery"
        
        whale_record = results[0]
        assert whale_record.whale_status == True, "Wallet should be marked as whale in BigQuery"
        assert whale_record.total_volume_traded >= config.whale.volume_threshold_sol

    @pytest.mark.asyncio
    async def test_whale_alert_cooldown(
        self,
        test_whale_data: List[Dict[str, Any]]
    ):
        """Test whale alert cooldown mechanism prevents spam."""
        
        # This will fail initially - expected for TDD
        from backend.src.services.whale_service import generate_whale_alert  # Will fail initially
        
        whale_wallet = test_whale_data[0]
        
        # Generate first alert
        alert1 = await generate_whale_alert(
            wallet_address=whale_wallet["wallet_address"],
            alert_type="large_purchase",
            transaction_data={
                "signature": "test-signature-1",
                "amount_sol": 25.0,
                "nft_count": 1
            }
        )
        
        assert alert1["generated"] == True, "First alert should be generated"
        
        # Try to generate another alert immediately
        alert2 = await generate_whale_alert(
            wallet_address=whale_wallet["wallet_address"],
            alert_type="large_purchase", 
            transaction_data={
                "signature": "test-signature-2",
                "amount_sol": 30.0,
                "nft_count": 1
            }
        )
        
        assert alert2["generated"] == False, "Second alert should be blocked by cooldown"
        assert "cooldown" in alert2["reason"].lower()

    def test_whale_tracking_performance(self):
        """Test whale tracking performance meets requirements."""
        import time
        
        # This will fail initially - expected for TDD
        from backend.dashboard_service.app.main import app  # Will fail initially
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        # Performance test: whale list should load in < 2s per requirements
        start_time = time.time()
        response = client.get("/whales?limit=50")
        end_time = time.time()
        
        response_time = end_time - start_time
        
        if response.status_code == 200:
            assert response_time < 2.0, f"Whale tracking took {response_time:.2f}s, should be < 2s"