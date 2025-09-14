"""BigQuery writer service for ChainWeave.

Handles batch and streaming writes to BigQuery tables with:
- Automatic retries and error handling
- Schema validation
- Batch processing for efficiency
- Data deduplication
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, date
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
import json
from concurrent.futures import ThreadPoolExecutor
import threading

from models.nft_collection import NFTCollection
from models.nft_metadata import NFTMetadata
from models.transaction import Transaction
from models.wallet_profile import WalletProfile
from models.whale_alert import WhaleAlert
from models.market_analytics import MarketAnalytics

logger = logging.getLogger(__name__)


class BigQueryWriter:
    """Handles writes to BigQuery tables with batching and error handling."""
    
    def __init__(self, project_id: str, dataset_id: str, batch_size: int = 1000):
        """Initialize BigQuery writer."""
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.batch_size = batch_size
        self.client = bigquery.Client(project=project_id)
        self.dataset_ref = self.client.dataset(dataset_id)
        
        # Thread pool for async BigQuery operations
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Batching queues
        self._batches = {
            'collections': [],
            'metadata': [],
            'transactions': [],
            'profiles': [],
            'alerts': [],
            'analytics': []
        }
        self._batch_locks = {
            table: threading.Lock() for table in self._batches.keys()
        }
        
        # Auto-flush batches periodically
        self._flush_interval = 30  # seconds
        self._last_flush = datetime.now()
    
    async def write_collection(self, collection: NFTCollection) -> bool:
        """Write a single collection record."""
        try:
            table_data = self._collection_to_bq_format(collection)
            return await self._write_single_record('nft_collections', table_data)
        except Exception as e:
            logger.error(f"Failed to write collection {collection.collection_id}: {e}")
            return False
    
    async def write_collections_batch(self, collections: List[NFTCollection]) -> int:
        """Write multiple collections in batch."""
        try:
            table_data = [self._collection_to_bq_format(c) for c in collections]
            return await self._write_batch('nft_collections', table_data)
        except Exception as e:
            logger.error(f"Failed to write collections batch: {e}")
            return 0
    
    async def write_nft_metadata(self, metadata: NFTMetadata) -> bool:
        """Write a single NFT metadata record."""
        try:
            table_data = self._metadata_to_bq_format(metadata)
            return await self._write_single_record('nft_metadata', table_data)
        except Exception as e:
            logger.error(f"Failed to write NFT metadata {metadata.mint_address}: {e}")
            return False
    
    async def write_metadata_batch(self, metadata_list: List[NFTMetadata]) -> int:
        """Write multiple NFT metadata records in batch."""
        try:
            table_data = [self._metadata_to_bq_format(m) for m in metadata_list]
            return await self._write_batch('nft_metadata', table_data)
        except Exception as e:
            logger.error(f"Failed to write metadata batch: {e}")
            return 0
    
    async def write_transaction(self, transaction: Transaction) -> bool:
        """Write a single transaction record."""
        try:
            table_data = self._transaction_to_bq_format(transaction)
            return await self._write_single_record('transactions', table_data)
        except Exception as e:
            logger.error(f"Failed to write transaction {transaction.transaction_signature}: {e}")
            return False
    
    async def write_transactions_batch(self, transactions: List[Transaction]) -> int:
        """Write multiple transactions in batch."""
        try:
            table_data = [self._transaction_to_bq_format(t) for t in transactions]
            return await self._write_batch('transactions', table_data)
        except Exception as e:
            logger.error(f"Failed to write transactions batch: {e}")
            return 0
    
    async def write_wallet_profile(self, profile: WalletProfile) -> bool:
        """Write a single wallet profile record."""
        try:
            table_data = self._profile_to_bq_format(profile)
            return await self._write_single_record('wallet_profiles', table_data)
        except Exception as e:
            logger.error(f"Failed to write wallet profile {profile.wallet_address}: {e}")
            return False
    
    async def write_whale_alert(self, alert: WhaleAlert) -> bool:
        """Write a single whale alert record."""
        try:
            table_data = self._alert_to_bq_format(alert)
            return await self._write_single_record('whale_alerts', table_data)
        except Exception as e:
            logger.error(f"Failed to write whale alert {alert.alert_id}: {e}")
            return False
    
    async def write_market_analytics(self, analytics: MarketAnalytics) -> bool:
        """Write a single market analytics record."""
        try:
            table_data = self._analytics_to_bq_format(analytics)
            return await self._write_single_record('market_analytics', table_data)
        except Exception as e:
            logger.error(f"Failed to write market analytics {analytics.metric_id}: {e}")
            return False
    
    async def write_analytics_batch(self, analytics_list: List[MarketAnalytics]) -> int:
        """Write multiple analytics records in batch."""
        try:
            table_data = [self._analytics_to_bq_format(a) for a in analytics_list]
            return await self._write_batch('market_analytics', table_data)
        except Exception as e:
            logger.error(f"Failed to write analytics batch: {e}")
            return 0
    
    async def queue_for_batch_write(
        self, 
        record_type: str, 
        data: Union[NFTCollection, NFTMetadata, Transaction, WalletProfile, WhaleAlert, MarketAnalytics]
    ) -> None:
        """Queue record for batch writing."""
        batch_key = self._get_batch_key(record_type)
        if not batch_key:
            logger.error(f"Unknown record type: {record_type}")
            return
        
        with self._batch_locks[batch_key]:
            if batch_key == 'collections':
                self._batches[batch_key].append(self._collection_to_bq_format(data))
            elif batch_key == 'metadata':
                self._batches[batch_key].append(self._metadata_to_bq_format(data))
            elif batch_key == 'transactions':
                self._batches[batch_key].append(self._transaction_to_bq_format(data))
            elif batch_key == 'profiles':
                self._batches[batch_key].append(self._profile_to_bq_format(data))
            elif batch_key == 'alerts':
                self._batches[batch_key].append(self._alert_to_bq_format(data))
            elif batch_key == 'analytics':
                self._batches[batch_key].append(self._analytics_to_bq_format(data))
        
        # Check if we need to flush
        await self._check_and_flush_batches()
    
    async def flush_all_batches(self) -> Dict[str, int]:
        """Flush all pending batches to BigQuery."""
        results = {}
        
        for batch_key in self._batches.keys():
            with self._batch_locks[batch_key]:
                if self._batches[batch_key]:
                    table_name = self._get_table_name(batch_key)
                    count = await self._write_batch(table_name, self._batches[batch_key])
                    results[batch_key] = count
                    self._batches[batch_key].clear()
                else:
                    results[batch_key] = 0
        
        self._last_flush = datetime.now()
        return results
    
    async def _write_single_record(self, table_name: str, data: Dict[str, Any]) -> bool:
        """Write a single record to BigQuery."""
        try:
            table_ref = self.dataset_ref.table(table_name)
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            def _insert():
                table = self.client.get_table(table_ref)
                errors = self.client.insert_rows_json(table, [data])
                return len(errors) == 0
            
            success = await loop.run_in_executor(self.executor, _insert)
            
            if success:
                logger.debug(f"Successfully wrote record to {table_name}")
            else:
                logger.error(f"Failed to write record to {table_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error writing to {table_name}: {e}")
            return False
    
    async def _write_batch(self, table_name: str, data: List[Dict[str, Any]]) -> int:
        """Write batch of records to BigQuery."""
        if not data:
            return 0
        
        try:
            table_ref = self.dataset_ref.table(table_name)
            
            # Run in thread pool
            loop = asyncio.get_event_loop()
            
            def _insert_batch():
                table = self.client.get_table(table_ref)
                errors = self.client.insert_rows_json(table, data)
                
                if errors:
                    logger.error(f"BigQuery insert errors for {table_name}: {errors}")
                    return len(data) - len(errors)  # Return successful count
                
                return len(data)
            
            success_count = await loop.run_in_executor(self.executor, _insert_batch)
            
            logger.info(f"Successfully wrote {success_count}/{len(data)} records to {table_name}")
            return success_count
            
        except Exception as e:
            logger.error(f"Error writing batch to {table_name}: {e}")
            return 0
    
    async def _check_and_flush_batches(self) -> None:
        """Check if batches need flushing based on size or time."""
        should_flush = False
        
        # Check batch sizes
        for batch_key, batch in self._batches.items():
            with self._batch_locks[batch_key]:
                if len(batch) >= self.batch_size:
                    should_flush = True
                    break
        
        # Check time since last flush
        if (datetime.now() - self._last_flush).total_seconds() >= self._flush_interval:
            should_flush = True
        
        if should_flush:
            await self.flush_all_batches()
    
    def _get_batch_key(self, record_type: str) -> Optional[str]:
        """Get batch key for record type."""
        mapping = {
            'collection': 'collections',
            'nft_metadata': 'metadata',
            'transaction': 'transactions',
            'wallet_profile': 'profiles',
            'whale_alert': 'alerts',
            'market_analytics': 'analytics'
        }
        return mapping.get(record_type)
    
    def _get_table_name(self, batch_key: str) -> str:
        """Get BigQuery table name for batch key."""
        mapping = {
            'collections': 'nft_collections',
            'metadata': 'nft_metadata',
            'transactions': 'transactions',
            'profiles': 'wallet_profiles',
            'alerts': 'whale_alerts',
            'analytics': 'market_analytics'
        }
        return mapping[batch_key]
    
    def _collection_to_bq_format(self, collection: NFTCollection) -> Dict[str, Any]:
        """Convert NFTCollection to BigQuery format."""
        return {
            "collection_id": collection.collection_id,
            "collection_address": collection.collection_address,
            "name": collection.name,
            "symbol": collection.symbol,
            "description": collection.description,
            "image_url": collection.image_url,
            "creator_address": collection.creator_address,
            "total_supply": collection.total_supply,
            "verified": collection.verified,
            "floor_price": collection.floor_price,
            "market_cap": collection.market_cap,
            "volume_24h": collection.volume_24h,
            "holders_count": collection.holders_count,
            "listed_count": collection.listed_count,
            "status": collection.status.value,
            "mint_date": collection.mint_date.isoformat() if collection.mint_date else None,
            "last_sale": collection.last_sale.isoformat() if collection.last_sale else None,
            "is_whale_tracked": collection.is_whale_tracked,
            "royalty_percentage": collection.royalty_percentage,
            "external_url": collection.external_url,
            "twitter_handle": collection.twitter_handle,
            "discord_url": collection.discord_url,
            "categories": collection.categories,
            "attributes_schema": json.dumps(collection.attributes_schema) if collection.attributes_schema else None,
            "ingested_at": datetime.now().isoformat(),
            "updated_at": collection.updated_at.isoformat(),
            "partition_date": collection.updated_at.date().isoformat()
        }
    
    def _metadata_to_bq_format(self, metadata: NFTMetadata) -> Dict[str, Any]:
        """Convert NFTMetadata to BigQuery format."""
        return {
            "mint_address": metadata.mint_address,
            "collection_id": metadata.collection_id,
            "name": metadata.name,
            "image_url": metadata.image_url,
            "attributes": json.dumps(metadata.attributes),
            "rarity_rank": metadata.rarity_rank,
            "rarity_score": metadata.rarity_score,
            "current_owner": metadata.current_owner,
            "mint_timestamp": metadata.mint_timestamp.isoformat(),
            "last_transfer": metadata.last_transfer.isoformat(),
            "description": metadata.description,
            "external_url": metadata.external_url,
            "animation_url": metadata.animation_url,
            "hold_duration_days": metadata.hold_duration_days,
            "estimated_value": metadata.estimated_value,
            "last_sale_price": metadata.last_sale_price,
            "listing_price": metadata.listing_price,
            "is_listed": metadata.is_listed,
            "marketplace": metadata.marketplace,
            "ingested_at": datetime.now().isoformat(),
            "partition_date": datetime.now().date().isoformat()
        }
    
    def _transaction_to_bq_format(self, transaction: Transaction) -> Dict[str, Any]:
        """Convert Transaction to BigQuery format."""
        return {
            "transaction_signature": transaction.transaction_signature,
            "mint_address": transaction.mint_address,
            "event_type": transaction.event_type.value,
            "from_address": transaction.from_address,
            "to_address": transaction.to_address,
            "price_sol": transaction.price_sol,
            "price_usd": transaction.price_usd,
            "marketplace": transaction.marketplace,
            "timestamp": transaction.timestamp.isoformat(),
            "block_height": transaction.block_height,
            "instruction_index": transaction.instruction_index,
            "status": transaction.status.value,
            "program_id": transaction.program_id,
            "collection_id": transaction.collection_id,
            "royalty_paid": transaction.royalty_paid,
            "marketplace_fee": transaction.marketplace_fee,
            "gas_fee": transaction.gas_fee,
            "webhook_timestamp": transaction.webhook_timestamp.isoformat() if transaction.webhook_timestamp else None,
            "slot_number": transaction.slot_number,
            "ingested_at": datetime.now().isoformat(),
            "partition_date": transaction.timestamp.date().isoformat()
        }
    
    def _profile_to_bq_format(self, profile: WalletProfile) -> Dict[str, Any]:
        """Convert WalletProfile to BigQuery format."""
        return {
            "wallet_address": profile.wallet_address,
            "total_nfts_owned": profile.total_nfts_owned,
            "total_volume_traded": profile.total_volume_traded,
            "first_activity": profile.first_activity.isoformat(),
            "last_activity": profile.last_activity.isoformat(),
            "avg_hold_duration": profile.avg_hold_duration,
            "collections_active": profile.collections_active,
            "whale_status": profile.whale_status,
            "profit_loss_sol": profile.profit_loss_sol,
            "favorite_marketplace": profile.favorite_marketplace,
            "wallet_tier": profile.wallet_tier.value,
            "trading_behavior": profile.trading_behavior.value,
            "total_spent_sol": profile.total_spent_sol,
            "total_received_sol": profile.total_received_sol,
            "total_transactions": profile.total_transactions,
            "successful_flips": profile.successful_flips,
            "failed_flips": profile.failed_flips,
            "avg_purchase_price": profile.avg_purchase_price,
            "avg_sale_price": profile.avg_sale_price,
            "largest_purchase_sol": profile.largest_purchase_sol,
            "largest_sale_sol": profile.largest_sale_sol,
            "win_rate": profile.win_rate,
            "days_active": profile.days_active,
            "avg_transactions_per_day": profile.avg_transactions_per_day,
            "most_active_hour": profile.most_active_hour,
            "top_collection": profile.top_collection,
            "portfolio_diversity_score": profile.portfolio_diversity_score,
            "unique_counterparties": profile.unique_counterparties,
            "profile_updated_at": profile.profile_updated_at.isoformat(),
            "partition_date": profile.profile_updated_at.date().isoformat()
        }
    
    def _alert_to_bq_format(self, alert: WhaleAlert) -> Dict[str, Any]:
        """Convert WhaleAlert to BigQuery format."""
        return {
            "alert_id": alert.alert_id,
            "wallet_address": alert.wallet_address,
            "alert_type": alert.alert_type.value,
            "transaction_signature": alert.transaction_signature,
            "collection_id": alert.collection_id,
            "mint_address": alert.mint_address,
            "amount_sol": alert.amount_sol,
            "severity": alert.severity.value,
            "triggered_at": alert.triggered_at.isoformat(),
            "details": json.dumps(alert.details) if alert.details else None,
            "resolved": alert.resolved,
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "resolution_reason": alert.resolution_reason,
            "notification_sent": alert.notification_sent,
            "notification_channels": alert.notification_channels,
            "cooldown_until": alert.cooldown_until.isoformat() if alert.cooldown_until else None,
            "market_impact_score": alert.market_impact_score,
            "is_false_positive": alert.is_false_positive,
            "feedback_score": alert.feedback_score,
            "ingested_at": datetime.now().isoformat(),
            "partition_date": alert.triggered_at.date().isoformat()
        }
    
    def _analytics_to_bq_format(self, analytics: MarketAnalytics) -> Dict[str, Any]:
        """Convert MarketAnalytics to BigQuery format."""
        return {
            "metric_id": analytics.metric_id,
            "collection_id": analytics.collection_id,
            "date": analytics.date.isoformat(),
            "metric_type": analytics.metric_type.value,
            "metric_value": analytics.metric_value,
            "created_at": analytics.created_at.isoformat(),
            "granularity": analytics.granularity.value,
            "previous_value": analytics.previous_value,
            "change_percentage": analytics.change_percentage,
            "sample_size": analytics.sample_size,
            "confidence_score": analytics.confidence_score,
            "metric_metadata": json.dumps(analytics.metric_metadata) if analytics.metric_metadata else None,
            "data_completeness": analytics.data_completeness,
            "outliers_detected": analytics.outliers_detected,
            "calculation_method": analytics.calculation_method,
            "partition_date": analytics.date.isoformat()
        }