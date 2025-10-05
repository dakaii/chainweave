"""Data Processor Service Main Entry Point.

Pub/Sub subscriber that processes NFT transaction events from Helius webhooks
and loads them into BigQuery for analytics.
"""

import asyncio
import json
import logging
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from google.cloud import pubsub_v1, bigquery
from google.api_core import retry
import structlog

# Add parent directory to path for imports
sys.path.append('../..')
from src.config import config
from src.models.transaction import NFTTransaction, TransactionTable
from src.models.nft_metadata import NFTMetadata, NFTMetadataTable
from src.models.nft_collection import NFTCollection, CollectionTable
from src.models.wallet_profile import WalletProfile, WalletProfileTable
from src.models.whale_alert import WhaleAlert, WhaleAlertTable
from src.services.data_enrichment import DataEnrichmentService
from src.services.whale_detector import WhaleDetectorService
from src.services.collection_analyzer import CollectionAnalyzerService

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class DataProcessor:
    """Main data processing service for NFT events."""

    def __init__(self):
        """Initialize the data processor."""
        self.project_id = config.gcp.project_id
        self.subscription_path = f"projects/{self.project_id}/subscriptions/{config.pubsub.subscription}"

        # Initialize clients
        self.subscriber_client = pubsub_v1.SubscriberClient()
        self.bigquery_client = bigquery.Client(project=self.project_id)

        # Initialize services
        self.enrichment_service = DataEnrichmentService()
        self.whale_detector = WhaleDetectorService()
        self.collection_analyzer = CollectionAnalyzerService()

        # Thread pool for concurrent processing
        self.executor = ThreadPoolExecutor(max_workers=10)

        # Processing statistics
        self.stats = {
            'messages_processed': 0,
            'messages_failed': 0,
            'transactions_created': 0,
            'whale_alerts_created': 0,
            'collections_updated': 0,
            'start_time': datetime.now(timezone.utc)
        }

        # Graceful shutdown flag
        self.shutdown_requested = False

        logger.info("Data processor initialized", project_id=self.project_id)

    async def start(self):
        """Start the data processor."""
        logger.info("Starting data processor service")

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        try:
            # Start the main processing loop
            await self._process_messages()
        except Exception as e:
            logger.error("Fatal error in data processor", error=str(e))
            raise
        finally:
            logger.info("Data processor shutting down", stats=self.stats)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("Shutdown signal received", signal=signum)
        self.shutdown_requested = True

    async def _process_messages(self):
        """Main message processing loop."""

        flow_control = pubsub_v1.types.FlowControl(max_messages=100)

        def callback(message):
            """Process a single Pub/Sub message."""
            try:
                # Parse message data
                try:
                    payload = json.loads(message.data.decode('utf-8'))
                except json.JSONDecodeError as e:
                    logger.error("Failed to parse message JSON", error=str(e))
                    message.nack()
                    self.stats['messages_failed'] += 1
                    return

                # Process the payload
                success = asyncio.run(self._process_webhook_payload(payload))

                if success:
                    message.ack()
                    self.stats['messages_processed'] += 1
                    logger.debug("Message processed successfully")
                else:
                    message.nack()
                    self.stats['messages_failed'] += 1
                    logger.warning("Message processing failed, will retry")

            except Exception as e:
                logger.error("Exception in message callback", error=str(e))
                message.nack()
                self.stats['messages_failed'] += 1

        # Start pulling messages
        streaming_pull_future = self.subscriber_client.subscribe(
            self.subscription_path,
            callback=callback,
            flow_control=flow_control
        )

        logger.info("Listening for messages", subscription=self.subscription_path)

        try:
            # Keep the main thread alive
            while not self.shutdown_requested:
                await asyncio.sleep(1)

                # Log stats periodically
                if self.stats['messages_processed'] % 100 == 0 and self.stats['messages_processed'] > 0:
                    self._log_processing_stats()

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            streaming_pull_future.cancel()
            streaming_pull_future.result()  # Block until the shutdown is complete

    async def _process_webhook_payload(self, payload: Dict[str, Any]) -> bool:
        """Process a single webhook payload."""

        try:
            # Extract transaction information
            transaction_data = await self._extract_transaction_data(payload)
            if not transaction_data:
                return True  # Skip non-transaction events

            # Create transaction record
            transaction = await self._create_transaction_record(transaction_data)
            if not transaction:
                return False

            # Enrich with metadata
            enriched_data = await self.enrichment_service.enrich_transaction(transaction_data)

            # Update NFT metadata if available
            if enriched_data.get('nft_metadata'):
                await self._update_nft_metadata(enriched_data['nft_metadata'])

            # Update collection information
            if enriched_data.get('collection_data'):
                await self._update_collection_data(enriched_data['collection_data'])
                self.stats['collections_updated'] += 1

            # Update wallet profiles
            await self._update_wallet_profiles(transaction_data)

            # Check for whale activity
            whale_alert = await self.whale_detector.analyze_transaction(transaction_data)
            if whale_alert:
                await self._create_whale_alert(whale_alert)
                self.stats['whale_alerts_created'] += 1

            # Update collection analytics
            await self.collection_analyzer.update_collection_metrics(
                transaction_data['collection_id'],
                transaction_data
            )

            self.stats['transactions_created'] += 1
            return True

        except Exception as e:
            logger.error("Failed to process webhook payload", error=str(e), payload=payload)
            return False

    async def _extract_transaction_data(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract transaction data from webhook payload."""

        try:
            # Validate required fields
            if not all(key in payload for key in ['type', 'signature', 'timestamp', 'events']):
                logger.warning("Missing required fields in payload")
                return None

            events = payload.get('events', {})
            nft_event = events.get('nft', {})

            # Check if this is an NFT transaction
            if not nft_event:
                return None

            # Extract transaction details
            transaction_data = {
                'transaction_signature': payload['signature'],
                'slot': payload.get('slot'),
                'timestamp': datetime.fromisoformat(payload['timestamp'].replace('Z', '+00:00')),
                'event_type': nft_event.get('type', 'unknown'),
                'mint_address': nft_event.get('nftMint'),
                'collection_id': nft_event.get('collection'),
                'from_address': nft_event.get('seller'),
                'to_address': nft_event.get('buyer'),
                'price_sol': float(nft_event.get('amount', 0)) / 1_000_000_000,  # Convert lamports to SOL
                'marketplace': nft_event.get('marketplace'),
                'raw_payload': json.dumps(payload)
            }

            # Validate critical fields
            if not transaction_data['mint_address']:
                logger.warning("No mint address in transaction")
                return None

            return transaction_data

        except Exception as e:
            logger.error("Failed to extract transaction data", error=str(e))
            return None

    async def _create_transaction_record(self, transaction_data: Dict[str, Any]) -> Optional[NFTTransaction]:
        """Create and store transaction record in BigQuery."""

        try:
            # Create transaction model
            transaction = NFTTransaction(
                transaction_signature=transaction_data['transaction_signature'],
                mint_address=transaction_data['mint_address'],
                collection_id=transaction_data.get('collection_id'),
                event_type=transaction_data['event_type'],
                from_address=transaction_data.get('from_address'),
                to_address=transaction_data.get('to_address'),
                price_sol=transaction_data['price_sol'],
                timestamp=transaction_data['timestamp'],
                slot=transaction_data.get('slot'),
                marketplace=transaction_data.get('marketplace'),
                fees_sol=0.0,  # TODO: Extract from transaction data
                is_verified=True,  # TODO: Add verification logic
                metadata={}
            )

            # Convert to BigQuery table model
            table_record = TransactionTable(
                **transaction.model_dump(),
                ingested_at=datetime.now(timezone.utc),
                partition_date=transaction_data['timestamp'].strftime('%Y-%m-%d')
            )

            # Insert into BigQuery
            table_id = f"{self.project_id}.{config.bigquery.dataset}.transactions"
            rows_to_insert = [table_record.model_dump()]

            errors = self.bigquery_client.insert_rows_json(table_id, rows_to_insert)
            if errors:
                logger.error("BigQuery insert failed", errors=errors)
                return None

            logger.debug("Transaction record created", signature=transaction.transaction_signature)
            return transaction

        except Exception as e:
            logger.error("Failed to create transaction record", error=str(e))
            return None

    async def _update_nft_metadata(self, metadata: Dict[str, Any]):
        """Update NFT metadata in BigQuery."""

        try:
            # Create metadata model
            nft_metadata = NFTMetadata(
                mint_address=metadata['mint_address'],
                collection_id=metadata.get('collection_id'),
                name=metadata.get('name', 'Unknown'),
                description=metadata.get('description'),
                image_url=metadata.get('image'),
                attributes=metadata.get('attributes', []),
                current_owner=metadata.get('current_owner'),
                is_verified=metadata.get('verified', False),
                rarity_rank=metadata.get('rarity_rank'),
                estimated_value=metadata.get('estimated_value', 0.0),
                last_updated=datetime.now(timezone.utc)
            )

            # Convert to table model
            table_record = NFTMetadataTable(
                **nft_metadata.model_dump(),
                ingested_at=datetime.now(timezone.utc),
                partition_date=datetime.now().strftime('%Y-%m-%d')
            )

            # Upsert into BigQuery (replace if exists)
            table_id = f"{self.project_id}.{config.bigquery.dataset}.nft_metadata"
            rows_to_insert = [table_record.model_dump()]

            errors = self.bigquery_client.insert_rows_json(table_id, rows_to_insert)
            if errors:
                logger.error("Failed to update NFT metadata", errors=errors)
            else:
                logger.debug("NFT metadata updated", mint_address=metadata['mint_address'])

        except Exception as e:
            logger.error("Exception updating NFT metadata", error=str(e))

    async def _update_collection_data(self, collection_data: Dict[str, Any]):
        """Update collection information in BigQuery."""

        try:
            # Check if collection already exists
            existing = await self._get_existing_collection(collection_data['collection_id'])

            if existing:
                # Update existing collection
                updated_collection = existing.copy()
                updated_collection.update({
                    'floor_price': collection_data.get('floor_price', existing.get('floor_price', 0.0)),
                    'total_volume': collection_data.get('total_volume', existing.get('total_volume', 0.0)),
                    'holder_count': collection_data.get('holder_count', existing.get('holder_count')),
                    'updated_at': datetime.now(timezone.utc)
                })
                collection = NFTCollection(**updated_collection)
            else:
                # Create new collection
                collection = NFTCollection(
                    collection_id=collection_data['collection_id'],
                    collection_address=collection_data.get('collection_address', collection_data['collection_id']),
                    name=collection_data.get('name', 'Unknown Collection'),
                    symbol=collection_data.get('symbol', 'UNK'),
                    creator_address=collection_data.get('creator', 'Unknown'),
                    total_supply=collection_data.get('total_supply', 10000),
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    floor_price=collection_data.get('floor_price', 0.0),
                    total_volume=collection_data.get('total_volume', 0.0),
                    description=collection_data.get('description'),
                    image_url=collection_data.get('image')
                )

            # Convert to table model
            table_record = CollectionTable(
                **collection.model_dump(),
                ingested_at=datetime.now(timezone.utc),
                partition_date=datetime.now().strftime('%Y-%m-%d')
            )

            # Upsert into BigQuery
            table_id = f"{self.project_id}.{config.bigquery.dataset}.nft_collections"
            rows_to_insert = [table_record.model_dump()]

            errors = self.bigquery_client.insert_rows_json(table_id, rows_to_insert)
            if errors:
                logger.error("Failed to update collection", errors=errors)
            else:
                logger.debug("Collection updated", collection_id=collection_data['collection_id'])

        except Exception as e:
            logger.error("Exception updating collection", error=str(e))

    async def _get_existing_collection(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """Get existing collection data from BigQuery."""

        try:
            query = f"""
            SELECT *
            FROM `{self.project_id}.{config.bigquery.dataset}.nft_collections`
            WHERE collection_id = @collection_id
              AND partition_date = CURRENT_DATE()
            LIMIT 1
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id)
                ]
            )

            query_job = self.bigquery_client.query(query, job_config=job_config)
            results = list(query_job)

            if results:
                return dict(results[0])
            return None

        except Exception as e:
            logger.error("Failed to get existing collection", error=str(e), collection_id=collection_id)
            return None

    async def _update_wallet_profiles(self, transaction_data: Dict[str, Any]):
        """Update wallet profiles for transaction participants."""

        addresses = [transaction_data.get('from_address'), transaction_data.get('to_address')]

        for address in addresses:
            if not address:
                continue

            try:
                # Get or create wallet profile
                profile_data = await self._get_or_create_wallet_profile(address)

                # Update with transaction data
                profile_data['total_transactions'] += 1
                profile_data['total_volume_traded'] += transaction_data['price_sol']
                profile_data['last_activity'] = transaction_data['timestamp']

                # Determine whale status
                if profile_data['total_volume_traded'] > config.whale.volume_threshold_sol:
                    profile_data['whale_status'] = 'whale'
                elif profile_data['total_volume_traded'] > config.whale.volume_threshold_sol * 0.5:
                    profile_data['whale_status'] = 'potential_whale'
                else:
                    profile_data['whale_status'] = 'regular'

                # Create profile model
                profile = WalletProfile(**profile_data)

                # Convert to table model
                table_record = WalletProfileTable(
                    **profile.model_dump(),
                    ingested_at=datetime.now(timezone.utc),
                    partition_date=datetime.now().strftime('%Y-%m-%d')
                )

                # Upsert into BigQuery
                table_id = f"{self.project_id}.{config.bigquery.dataset}.wallet_profiles"
                rows_to_insert = [table_record.model_dump()]

                errors = self.bigquery_client.insert_rows_json(table_id, rows_to_insert)
                if errors:
                    logger.error("Failed to update wallet profile", errors=errors)

            except Exception as e:
                logger.error("Exception updating wallet profile", error=str(e), address=address)

    async def _get_or_create_wallet_profile(self, wallet_address: str) -> Dict[str, Any]:
        """Get existing wallet profile or create default."""

        try:
            query = f"""
            SELECT *
            FROM `{self.project_id}.{config.bigquery.dataset}.wallet_profiles`
            WHERE wallet_address = @wallet_address
              AND partition_date = CURRENT_DATE()
            LIMIT 1
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("wallet_address", "STRING", wallet_address)
                ]
            )

            query_job = self.bigquery_client.query(query, job_config=job_config)
            results = list(query_job)

            if results:
                return dict(results[0])

            # Create new profile
            return {
                'wallet_address': wallet_address,
                'first_seen': datetime.now(timezone.utc),
                'last_activity': datetime.now(timezone.utc),
                'total_transactions': 0,
                'total_volume_traded': 0.0,
                'total_nfts_owned': 0,
                'whale_status': 'regular',
                'trading_behavior': 'unknown',
                'verified': False
            }

        except Exception as e:
            logger.error("Failed to get wallet profile", error=str(e))
            return {
                'wallet_address': wallet_address,
                'first_seen': datetime.now(timezone.utc),
                'last_activity': datetime.now(timezone.utc),
                'total_transactions': 0,
                'total_volume_traded': 0.0,
                'total_nfts_owned': 0,
                'whale_status': 'regular',
                'trading_behavior': 'unknown',
                'verified': False
            }

    async def _create_whale_alert(self, whale_alert: Dict[str, Any]):
        """Create whale alert in BigQuery."""

        try:
            # Create whale alert model
            alert = WhaleAlert(
                alert_id=whale_alert['alert_id'],
                wallet_address=whale_alert['wallet_address'],
                alert_type=whale_alert['alert_type'],
                collection_id=whale_alert.get('collection_id'),
                amount_sol=whale_alert['amount_sol'],
                threshold_sol=whale_alert['threshold_sol'],
                severity=whale_alert['severity'],
                triggered_at=whale_alert['triggered_at'],
                resolved=False,
                details=whale_alert.get('details', {}),
                market_impact_score=whale_alert.get('market_impact_score', 0.0)
            )

            # Convert to table model
            table_record = WhaleAlertTable(
                **alert.model_dump(),
                ingested_at=datetime.now(timezone.utc),
                partition_date=whale_alert['triggered_at'].strftime('%Y-%m-%d')
            )

            # Insert into BigQuery
            table_id = f"{self.project_id}.{config.bigquery.dataset}.whale_alerts"
            rows_to_insert = [table_record.model_dump()]

            errors = self.bigquery_client.insert_rows_json(table_id, rows_to_insert)
            if errors:
                logger.error("Failed to create whale alert", errors=errors)
            else:
                logger.info("Whale alert created",
                           alert_id=alert.alert_id,
                           severity=alert.severity,
                           amount=alert.amount_sol)

        except Exception as e:
            logger.error("Exception creating whale alert", error=str(e))

    def _log_processing_stats(self):
        """Log current processing statistics."""

        uptime = datetime.now(timezone.utc) - self.stats['start_time']
        rate = self.stats['messages_processed'] / max(uptime.total_seconds(), 1) * 60  # per minute

        logger.info("Processing statistics",
                   messages_processed=self.stats['messages_processed'],
                   messages_failed=self.stats['messages_failed'],
                   transactions_created=self.stats['transactions_created'],
                   whale_alerts_created=self.stats['whale_alerts_created'],
                   collections_updated=self.stats['collections_updated'],
                   uptime_seconds=int(uptime.total_seconds()),
                   processing_rate_per_minute=round(rate, 2))


async def main():
    """Main entry point."""

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format='%(message)s'
    )

    logger.info("Starting ChainWeave Data Processor",
               environment=config.environment,
               log_level=config.log_level)

    # Create and start data processor
    processor = DataProcessor()
    await processor.start()


if __name__ == "__main__":
    asyncio.run(main())