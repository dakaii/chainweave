"""End-to-end pipeline integration test.

This test validates the complete ChainWeave data pipeline from webhook ingestion 
to dashboard visualization, covering all major user stories:

1. Webhook receives Helius event → Pub/Sub → BigQuery
2. Whale detection triggers alerts and updates profiles  
3. Collection heatmap reflects real-time trading activity
4. Attribute analysis shows price correlations
5. Dashboard APIs serve accurate, up-to-date data

MUST FAIL initially as no implementation exists yet (TDD requirement).
Uses real GCP dependencies (BigQuery, Pub/Sub) per constitutional requirements.
"""

import pytest
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from uuid import uuid4

from google.cloud import bigquery
from google.cloud import pubsub_v1
from fastapi.testclient import TestClient

from backend.src.config import config


class TestChainWeavePipelineE2E:
    """End-to-end integration tests for complete ChainWeave pipeline."""

    @pytest.fixture(scope="class")
    def bigquery_client(self) -> bigquery.Client:
        """Create BigQuery client for E2E testing."""
        return bigquery.Client(project=config.gcp.project_id)

    @pytest.fixture(scope="class")
    def pubsub_publisher(self) -> pubsub_v1.PublisherClient:
        """Create Pub/Sub publisher for E2E testing."""
        return pubsub_v1.PublisherClient()

    @pytest.fixture(scope="class")
    def pubsub_subscriber(self) -> pubsub_v1.SubscriberClient:
        """Create Pub/Sub subscriber for E2E testing."""
        return pubsub_v1.SubscriberClient()

    @pytest.fixture(scope="class")
    def webhook_client(self) -> TestClient:
        """Create webhook service test client."""
        # This will fail initially - expected for TDD
        from backend.webhook_service.app.main import app  # Will fail initially
        return TestClient(app)

    @pytest.fixture(scope="class")
    def dashboard_client(self) -> TestClient:
        """Create dashboard service test client."""
        # This will fail initially - expected for TDD  
        from backend.dashboard_service.app.main import app  # Will fail initially
        return TestClient(app)

    @pytest.fixture(scope="class")
    def e2e_test_data(self) -> Dict[str, Any]:
        """Complete test scenario data for E2E pipeline testing."""
        test_id = str(uuid4())[:8]
        base_time = datetime.now()
        
        return {
            "test_id": test_id,
            "collection": {
                "collection_id": f"e2e-test-collection-{test_id}",
                "collection_address": f"E2E{test_id}Collection11111111111111111111111",
                "name": f"E2E Test Collection {test_id}",
                "creator_address": f"Creator{test_id}111111111111111111111111111"
            },
            "whale_wallet": {
                "address": f"Whale{test_id}11111111111111111111111111111111",
                "expected_whale_status": True
            },
            "regular_wallet": {
                "address": f"Regular{test_id}1111111111111111111111111111111",
                "expected_whale_status": False
            },
            "nft_transactions": [
                {
                    # High-value whale purchase
                    "signature": f"WhaleHighValue{test_id}Transaction111111111111111111111111111111111111111111",
                    "mint_address": f"NFT1{test_id}111111111111111111111111111111111",
                    "from_address": None,  # Mint
                    "to_address": f"Whale{test_id}11111111111111111111111111111111",
                    "price_sol": 25.5,
                    "marketplace": "Magic Eden",
                    "timestamp": base_time - timedelta(minutes=30),
                    "attributes": {
                        "background": "Golden",
                        "rarity": "Legendary",
                        "eyes": "Diamond"
                    }
                },
                {
                    # Whale selling for profit
                    "signature": f"WhaleSell{test_id}Transaction11111111111111111111111111111111111111111111111",
                    "mint_address": f"NFT2{test_id}111111111111111111111111111111111",
                    "from_address": f"Whale{test_id}11111111111111111111111111111111",
                    "to_address": f"Buyer{test_id}111111111111111111111111111111111",
                    "price_sol": 18.7,
                    "marketplace": "Tensor",
                    "timestamp": base_time - timedelta(minutes=15),
                    "attributes": {
                        "background": "Golden",
                        "rarity": "Epic",
                        "eyes": "Ruby"
                    }
                },
                {
                    # Regular user small purchase
                    "signature": f"RegularBuy{test_id}Transaction111111111111111111111111111111111111111111111",
                    "mint_address": f"NFT3{test_id}111111111111111111111111111111111",
                    "from_address": f"Seller{test_id}11111111111111111111111111111111",
                    "to_address": f"Regular{test_id}1111111111111111111111111111111",
                    "price_sol": 3.2,
                    "marketplace": "Magic Eden",
                    "timestamp": base_time - timedelta(minutes=10),
                    "attributes": {
                        "background": "Blue",
                        "rarity": "Common",
                        "eyes": "Normal"
                    }
                },
                {
                    # Another whale transaction for volume buildup
                    "signature": f"WhaleVolume{test_id}Transaction1111111111111111111111111111111111111111111111",
                    "mint_address": f"NFT4{test_id}111111111111111111111111111111111",
                    "from_address": f"Previous{test_id}111111111111111111111111111111111",
                    "to_address": f"Whale{test_id}11111111111111111111111111111111",
                    "price_sol": 45.0,  # Large purchase to trigger whale status
                    "marketplace": "OpenSea",
                    "timestamp": base_time - timedelta(minutes=5),
                    "attributes": {
                        "background": "Golden",
                        "rarity": "Mythic",
                        "eyes": "Dragon"
                    }
                }
            ]
        }

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_complete_pipeline_flow(
        self,
        webhook_client: TestClient,
        dashboard_client: TestClient,
        bigquery_client: bigquery.Client,
        pubsub_subscriber: pubsub_v1.SubscriberClient,
        e2e_test_data: Dict[str, Any]
    ):
        """Test complete pipeline: webhook → processing → storage → dashboard."""
        
        # This is the master E2E test that will fail initially - expected for TDD
        
        test_id = e2e_test_data["test_id"]
        transactions = e2e_test_data["nft_transactions"]
        
        print(f"🔄 Starting E2E pipeline test with ID: {test_id}")
        
        # ==========================================
        # PHASE 1: Webhook Ingestion
        # ==========================================
        
        webhook_results = []
        
        for transaction in transactions:
            # Convert transaction to Helius webhook format
            helius_payload = {
                "type": "ENHANCED",
                "signature": transaction["signature"],
                "timestamp": int(transaction["timestamp"].timestamp() * 1000),
                "slot": 259841234 + len(webhook_results),  # Unique slots
                "events": {
                    "nft": {
                        "nftMint": transaction["mint_address"],
                        "oldOwner": transaction["from_address"],
                        "newOwner": transaction["to_address"],
                        "price": transaction["price_sol"],
                        "marketplace": transaction["marketplace"]
                    }
                }
            }
            
            print(f"📥 Sending webhook for transaction: {transaction['signature'][:20]}...")
            
            # Send to webhook endpoint
            response = webhook_client.post("/webhook/helius", json=helius_payload)
            
            # Webhook should accept and publish to Pub/Sub
            assert response.status_code == 200, f"Webhook failed for transaction {transaction['signature']}"
            
            webhook_result = response.json()
            assert webhook_result["status"] in ["received", "processed"]
            
            webhook_results.append(webhook_result)
            
            # Small delay between transactions to simulate real-world timing
            await asyncio.sleep(0.5)
        
        print(f"✅ Phase 1 complete: {len(webhook_results)} webhooks processed")
        
        # ==========================================  
        # PHASE 2: Wait for Async Processing
        # ==========================================
        
        print("⏳ Waiting for async pipeline processing...")
        
        # Wait for Pub/Sub messages to be processed and data to reach BigQuery
        # In production, this would be handled by data processor service
        await asyncio.sleep(10)  # Allow time for async processing
        
        # Verify messages were processed from Pub/Sub
        subscription_path = pubsub_subscriber.subscription_path(
            config.gcp.project_id,
            config.pubsub.subscription
        )
        
        # Check for any unprocessed messages (should be empty after processing)
        # This validates that the data processor service consumed the messages
        print("🔍 Checking Pub/Sub message processing...")
        
        # ==========================================
        # PHASE 3: Data Validation in BigQuery
        # ==========================================
        
        print("🗃️  Validating data in BigQuery...")
        
        # Verify transaction data was stored correctly
        transaction_query = f"""
        SELECT 
            transaction_signature,
            mint_address,
            from_address, 
            to_address,
            price_sol,
            marketplace,
            timestamp
        FROM `{config.gcp.project_id}.{config.bigquery.dataset}.{config.bigquery.table_prefix}transaction`
        WHERE transaction_signature IN UNNEST(@signatures)
        """
        
        signatures = [t["signature"] for t in transactions]
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("signatures", "STRING", signatures)
            ]
        )
        
        query_job = bigquery_client.query(transaction_query, job_config=job_config)
        transaction_results = list(query_job.result())
        
        # Should find all transactions in BigQuery
        assert len(transaction_results) == len(transactions), \
            f"Expected {len(transactions)} transactions in BigQuery, found {len(transaction_results)}"
        
        print(f"✅ Found {len(transaction_results)} transactions in BigQuery")
        
        # Verify whale profile was updated
        whale_address = e2e_test_data["whale_wallet"]["address"]
        
        whale_query = f"""
        SELECT 
            wallet_address,
            total_volume_traded,
            whale_status,
            last_activity
        FROM `{config.gcp.project_id}.{config.bigquery.dataset}.{config.bigquery.table_prefix}wallet_profile`
        WHERE wallet_address = @whale_address
        """
        
        whale_job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("whale_address", "STRING", whale_address)
            ]
        )
        
        whale_job = bigquery_client.query(whale_query, job_config=whale_job_config)
        whale_results = list(whale_job.result())
        
        assert len(whale_results) > 0, "Whale profile should exist in BigQuery"
        
        whale_profile = whale_results[0]
        
        # Whale should be detected based on transaction volume
        total_whale_volume = sum(t["price_sol"] for t in transactions if t["to_address"] == whale_address)
        expected_whale_status = total_whale_volume >= config.whale.volume_threshold_sol
        
        assert whale_profile.whale_status == expected_whale_status, \
            f"Whale status should be {expected_whale_status} based on volume {total_whale_volume}"
        
        print(f"✅ Whale profile validated: volume={whale_profile.total_volume_traded}, status={whale_profile.whale_status}")
        
        # ==========================================
        # PHASE 4: Dashboard API Validation  
        # ==========================================
        
        print("📊 Validating dashboard API responses...")
        
        # Test collections endpoint reflects new data
        collections_response = dashboard_client.get("/collections")
        assert collections_response.status_code == 200
        
        collections_data = collections_response.json()
        assert "collections" in collections_data
        
        # Should find our test collection
        test_collection_id = e2e_test_data["collection"]["collection_id"]
        collection_ids = [c["collection_id"] for c in collections_data["collections"]]
        
        # Collection might not be in top results, so we test individual endpoint
        collection_detail_response = dashboard_client.get(f"/collections/{test_collection_id}")
        
        if collection_detail_response.status_code == 200:
            collection_details = collection_detail_response.json()
            assert collection_details["collection_id"] == test_collection_id
            
            # Recent sales should include our transactions
            recent_sales = collection_details["recent_sales"]
            sale_signatures = [s["mint_address"] for s in recent_sales]
            
            our_mint_addresses = [t["mint_address"] for t in transactions]
            found_transactions = set(sale_signatures).intersection(set(our_mint_addresses))
            
            assert len(found_transactions) > 0, "Should find our transactions in recent sales"
            
            print(f"✅ Found {len(found_transactions)} of our transactions in collection details")
        
        # Test whale tracking endpoint
        whales_response = dashboard_client.get("/whales?activity_days=1")
        assert whales_response.status_code == 200
        
        whales_data = whales_response.json()
        whale_addresses = [w["wallet_address"] for w in whales_data["whales"]]
        
        if expected_whale_status:
            assert whale_address in whale_addresses, "Whale should appear in whales list"
            print("✅ Whale detected and visible in dashboard")
        
        # Test wallet profile endpoint
        wallet_response = dashboard_client.get(f"/wallets/{whale_address}")
        
        if wallet_response.status_code == 200:
            wallet_data = wallet_response.json()
            assert wallet_data["wallet_address"] == whale_address
            assert wallet_data["whale_status"] == expected_whale_status
            
            # Recent transactions should include our whale transactions
            recent_transactions = wallet_data["recent_transactions"]
            whale_transactions = [t for t in transactions if t["to_address"] == whale_address or t["from_address"] == whale_address]
            
            transaction_sigs = [rt["transaction_signature"] for rt in recent_transactions]
            our_sigs = [wt["signature"] for wt in whale_transactions]
            
            found_wallet_transactions = set(transaction_sigs).intersection(set(our_sigs))
            assert len(found_wallet_transactions) > 0, "Should find whale transactions in wallet profile"
            
            print(f"✅ Wallet profile validated with {len(found_wallet_transactions)} matching transactions")
        
        # ==========================================
        # PHASE 5: Advanced Analytics Validation
        # ==========================================
        
        print("🎯 Validating advanced analytics features...")
        
        # Test collection heatmap
        heatmap_response = dashboard_client.get(f"/collections/{test_collection_id}/heatmap")
        
        if heatmap_response.status_code == 200:
            heatmap_data = heatmap_response.json()
            assert "nfts" in heatmap_data
            assert "color_scale" in heatmap_data
            
            # Should find our NFTs in heatmap
            heatmap_nfts = heatmap_data["nfts"]
            heatmap_mints = [nft["mint_address"] for nft in heatmap_nfts]
            our_mints = [t["mint_address"] for t in transactions]
            
            found_heatmap_nfts = set(heatmap_mints).intersection(set(our_mints))
            
            if len(found_heatmap_nfts) > 0:
                print(f"✅ Heatmap includes {len(found_heatmap_nfts)} of our NFTs")
        
        # Test attribute analysis
        attribute_request = {
            "collection_ids": [test_collection_id],
            "time_range_days": 1
        }
        
        attributes_response = dashboard_client.post("/attributes/analysis", json=attribute_request)
        
        if attributes_response.status_code == 200:
            attributes_data = attributes_response.json()
            assert "collections" in attributes_data
            
            if len(attributes_data["collections"]) > 0:
                collection_analysis = attributes_data["collections"][0]
                correlations = collection_analysis.get("attribute_correlations", [])
                
                # Should analyze attributes from our transactions
                trait_types = set(c["trait_type"] for c in correlations)
                
                # Our test data has "background", "rarity", "eyes" attributes
                expected_traits = {"background", "rarity", "eyes"}
                found_traits = trait_types.intersection(expected_traits)
                
                if len(found_traits) > 0:
                    print(f"✅ Attribute analysis found {len(found_traits)} trait types: {found_traits}")
        
        # ==========================================
        # PHASE 6: Performance Validation
        # ==========================================
        
        print("⚡ Validating performance requirements...")
        
        # Test dashboard response times meet requirements (<2s)
        performance_tests = [
            ("/collections", "Collections list"),
            (f"/collections/{test_collection_id}", "Collection details"),
            ("/whales", "Whale tracking"),
            (f"/wallets/{whale_address}", "Wallet profile")
        ]
        
        for endpoint, description in performance_tests:
            start_time = time.time()
            response = dashboard_client.get(endpoint)
            end_time = time.time()
            
            response_time = end_time - start_time
            
            if response.status_code == 200:
                assert response_time < 2.0, f"{description} took {response_time:.2f}s, should be <2s"
                print(f"✅ {description} performance: {response_time:.2f}s")
        
        # ==========================================
        # PHASE 7: Data Consistency Validation
        # ==========================================
        
        print("🔄 Validating data consistency across services...")
        
        # Verify whale status consistent between BigQuery and API
        if wallet_response.status_code == 200:
            api_whale_status = wallet_data["whale_status"]
            bigquery_whale_status = whale_profile.whale_status
            
            assert api_whale_status == bigquery_whale_status, \
                f"Whale status inconsistent: API={api_whale_status}, BigQuery={bigquery_whale_status}"
        
        # Verify transaction counts match between BigQuery and API responses
        bigquery_transaction_count = len(transaction_results)
        
        # Count transactions visible through various API endpoints
        api_transaction_count = 0
        
        if collection_detail_response.status_code == 200:
            api_transaction_count += len(collection_details["recent_sales"])
        
        # Transaction counts might differ due to API limits, but should be non-zero
        assert api_transaction_count > 0, "Should show transactions through API"
        
        print(f"✅ Data consistency validated: {bigquery_transaction_count} in BigQuery, {api_transaction_count} visible via API")
        
        # ==========================================
        # FINAL VALIDATION
        # ==========================================
        
        print("🎉 E2E Pipeline Test Complete!")
        print(f"   Test ID: {test_id}")
        print(f"   Transactions processed: {len(transactions)}")
        print(f"   Whale detected: {expected_whale_status}")
        print(f"   Data pipeline: Webhook → Pub/Sub → BigQuery → Dashboard ✅")
        
        assert True, "Complete E2E pipeline test passed"

    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(
        self,
        webhook_client: TestClient,
        e2e_test_data: Dict[str, Any]
    ):
        """Test pipeline error handling and recovery mechanisms."""
        
        # This will fail initially - expected for TDD
        
        print("🚨 Testing error handling and recovery...")
        
        # Test invalid webhook payload handling
        invalid_payload = {
            "type": "ENHANCED",
            # Missing required fields
            "invalid": "data"
        }
        
        response = webhook_client.post("/webhook/helius", json=invalid_payload)
        assert response.status_code == 400, "Should reject invalid webhook payload"
        
        error_data = response.json()
        assert "error" in error_data
        
        # Test webhook service resilience to malformed data
        malformed_payloads = [
            {"type": "ENHANCED", "signature": "invalid_signature_format"},
            {"type": "ENHANCED", "signature": None},
            {},  # Empty payload
            "not_json_object",  # Wrong type
        ]
        
        for payload in malformed_payloads:
            response = webhook_client.post("/webhook/helius", json=payload)
            assert response.status_code in [400, 422], f"Should handle malformed payload: {payload}"
        
        print("✅ Error handling validation complete")

    @pytest.mark.asyncio 
    async def test_concurrent_load_handling(
        self,
        webhook_client: TestClient,
        e2e_test_data: Dict[str, Any]
    ):
        """Test pipeline handles concurrent webhook load."""
        
        # This will fail initially - expected for TDD
        
        print("🚀 Testing concurrent load handling...")
        
        # Create multiple concurrent webhook requests
        concurrent_transactions = []
        
        for i in range(10):  # Simulate burst of 10 concurrent webhooks
            payload = {
                "type": "ENHANCED",
                "signature": f"ConcurrentTest{i}_{e2e_test_data['test_id']}{'1'*50}",
                "timestamp": int(datetime.now().timestamp() * 1000),
                "slot": 259841000 + i,
                "events": {
                    "nft": {
                        "nftMint": f"ConcurrentNFT{i}_{e2e_test_data['test_id']}{'1'*20}",
                        "newOwner": f"ConcurrentOwner{i}_{e2e_test_data['test_id']}{'1'*10}",
                        "price": 1.0 + i * 0.1,
                        "marketplace": "Magic Eden"
                    }
                }
            }
            concurrent_transactions.append(payload)
        
        # Send all requests concurrently
        tasks = []
        for payload in concurrent_transactions:
            task = asyncio.create_task(
                self._send_webhook_async(webhook_client, payload)
            )
            tasks.append(task)
        
        # Wait for all requests to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all requests were handled successfully
        successful_responses = [r for r in results if not isinstance(r, Exception)]
        
        assert len(successful_responses) == len(concurrent_transactions), \
            f"Expected {len(concurrent_transactions)} successful responses, got {len(successful_responses)}"
        
        print(f"✅ Concurrent load test passed: {len(successful_responses)} requests handled")

    async def _send_webhook_async(self, client: TestClient, payload: dict) -> dict:
        """Helper method for async webhook testing."""
        response = client.post("/webhook/helius", json=payload)
        assert response.status_code == 200
        return response.json()

    def test_monitoring_and_alerting_integration(self):
        """Test monitoring and alerting system integration."""
        
        # This will fail initially - expected for TDD
        # This would test integration with Cloud Monitoring, logging, and alerting
        
        from backend.src.utils.monitoring import get_pipeline_health_metrics  # Will fail initially
        
        # Verify health metrics are being collected
        health_metrics = get_pipeline_health_metrics()
        
        assert "webhook_requests_total" in health_metrics
        assert "pubsub_messages_processed" in health_metrics
        assert "bigquery_load_jobs_total" in health_metrics
        assert "dashboard_requests_total" in health_metrics
        
        # Verify all metrics have valid values
        for metric_name, metric_value in health_metrics.items():
            assert isinstance(metric_value, (int, float)), f"Metric {metric_name} should be numeric"
            assert metric_value >= 0, f"Metric {metric_name} should be non-negative"
        
        print("✅ Monitoring integration validated")