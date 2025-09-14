"""Collection tracking service for ChainWeave.

Manages NFT collection discovery, monitoring, and data synchronization:
- Collection metadata updates
- Historical data backfill
- Real-time tracking coordination
- Data quality monitoring
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from google.cloud import bigquery

from models.nft_collection import NFTCollection
from models.nft_metadata import NFTMetadata
from models.transaction import Transaction
from services.helius_client import HeliusClient
from services.bigquery_writer import BigQueryWriter

logger = logging.getLogger(__name__)


class CollectionTracker:
    """Manages NFT collection tracking and data synchronization."""
    
    def __init__(
        self, 
        helius_client: HeliusClient, 
        bigquery_writer: BigQueryWriter,
        batch_size: int = 100
    ):
        """Initialize collection tracker."""
        self.helius = helius_client
        self.bq_writer = bigquery_writer
        self.batch_size = batch_size
        self.bq_client = bigquery.Client(project=bigquery_writer.project_id)
        
        # Cache for collection metadata to avoid repeated API calls
        self._collection_cache = {}
        self._cache_ttl = timedelta(hours=6)
        self._cache_timestamps = {}
    
    async def add_collection(self, collection_id: str, backfill_days: int = 0) -> bool:
        """Add a new collection for tracking."""
        try:
            # Fetch collection metadata
            collection_data = await self.helius.get_collection_metadata(collection_id)
            if not collection_data:
                logger.error(f"Could not fetch metadata for collection {collection_id}")
                return False
            
            # Create collection model
            collection = NFTCollection(**collection_data)
            
            # Save to BigQuery
            success = await self.bq_writer.write_collection(collection)
            if not success:
                logger.error(f"Failed to save collection {collection_id} to BigQuery")
                return False
            
            logger.info(f"Added collection {collection.name} ({collection_id})")
            
            # Perform backfill if requested
            if backfill_days > 0:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=backfill_days)
                
                await self.backfill_collection_data(collection_id, start_date, end_date)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to add collection {collection_id}: {e}")
            return False
    
    async def get_tracked_collections(self) -> List[Dict[str, Any]]:
        """Get list of all tracked collections."""
        try:
            query = f"""
            SELECT 
                collection_id,
                name,
                status,
                total_supply,
                is_whale_tracked,
                updated_at
            FROM `{self.bq_writer.project_id}.{self.bq_writer.dataset_id}.nft_collections`
            WHERE partition_date = (
                SELECT MAX(partition_date) 
                FROM `{self.bq_writer.project_id}.{self.bq_writer.dataset_id}.nft_collections`
            )
            ORDER BY name
            """
            
            query_job = self.bq_client.query(query)
            results = []
            
            for row in query_job:
                results.append({
                    "collection_id": row.collection_id,
                    "name": row.name,
                    "status": row.status,
                    "total_supply": row.total_supply,
                    "is_whale_tracked": row.is_whale_tracked,
                    "updated_at": row.updated_at
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get tracked collections: {e}")
            return []
    
    async def backfill_collection_data(
        self, 
        collection_id: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, int]:
        """Backfill historical data for a collection."""
        logger.info(f"Starting backfill for {collection_id} from {start_date} to {end_date}")
        
        result = {"transactions": 0, "nfts": 0, "errors": 0}
        
        try:
            # Get collection metadata to find all NFTs
            collection_data = await self._get_cached_collection_metadata(collection_id)
            if not collection_data:
                logger.error(f"Could not fetch collection metadata for {collection_id}")
                return result
            
            # Get all NFT mint addresses for this collection
            mint_addresses = await self._get_collection_mint_addresses(collection_id)
            if not mint_addresses:
                logger.warning(f"No mint addresses found for collection {collection_id}")
                return result
            
            logger.info(f"Found {len(mint_addresses)} NFTs in collection {collection_id}")
            
            # Process NFTs in batches
            nft_batches = [
                mint_addresses[i:i + self.batch_size] 
                for i in range(0, len(mint_addresses), self.batch_size)
            ]
            
            for batch_idx, mint_batch in enumerate(nft_batches):
                logger.info(f"Processing NFT batch {batch_idx + 1}/{len(nft_batches)}")
                
                # Fetch metadata for NFTs in batch
                metadata_tasks = [
                    self.helius.get_nft_metadata(mint_address)
                    for mint_address in mint_batch
                ]
                
                metadata_results = await asyncio.gather(*metadata_tasks, return_exceptions=True)
                
                # Process successful metadata fetches
                valid_metadata = []
                for mint_address, metadata_result in zip(mint_batch, metadata_results):
                    if isinstance(metadata_result, dict):
                        try:
                            metadata = NFTMetadata(**metadata_result)
                            valid_metadata.append(metadata)
                        except Exception as e:
                            logger.warning(f"Invalid metadata for {mint_address}: {e}")
                            result["errors"] += 1
                    else:
                        logger.warning(f"Failed to fetch metadata for {mint_address}")
                        result["errors"] += 1
                
                # Write metadata batch
                if valid_metadata:
                    written_count = await self.bq_writer.write_metadata_batch(valid_metadata)
                    result["nfts"] += written_count
                
                # Fetch transaction history for each NFT
                for mint_address in mint_batch:
                    try:
                        transactions = await self.helius.get_transaction_history(
                            mint_address, start_date, end_date
                        )
                        
                        if transactions:
                            # Convert to Transaction models
                            tx_models = []
                            for tx_data in transactions:
                                try:
                                    # Ensure collection_id is set
                                    tx_data["collection_id"] = collection_id
                                    transaction = Transaction(**tx_data)
                                    tx_models.append(transaction)
                                except Exception as e:
                                    logger.warning(f"Invalid transaction data: {e}")
                                    result["errors"] += 1
                            
                            # Write transaction batch
                            if tx_models:
                                written_count = await self.bq_writer.write_transactions_batch(tx_models)
                                result["transactions"] += written_count
                    
                    except Exception as e:
                        logger.warning(f"Failed to fetch transactions for {mint_address}: {e}")
                        result["errors"] += 1
                
                # Rate limiting between batches
                await asyncio.sleep(1)
            
            logger.info(f"Backfill completed for {collection_id}: {result}")
            
        except Exception as e:
            logger.error(f"Backfill failed for {collection_id}: {e}")
            result["errors"] += 1
        
        return result
    
    async def update_collection_metadata(
        self, 
        collection_id: str, 
        force: bool = False
    ) -> Dict[str, int]:
        """Update metadata for all NFTs in a collection."""
        logger.info(f"Updating metadata for collection {collection_id}")
        
        result = {"nfts_updated": 0, "errors": 0}
        
        try:
            # Check if update is needed (unless forced)
            if not force:
                last_update = await self._get_last_metadata_update(collection_id)
                if last_update and (datetime.now() - last_update).total_seconds() < 3600:
                    logger.info(f"Collection {collection_id} metadata recently updated, skipping")
                    return result
            
            # Get all NFT mint addresses for collection
            mint_addresses = await self._get_collection_mint_addresses(collection_id)
            if not mint_addresses:
                logger.warning(f"No NFTs found for collection {collection_id}")
                return result
            
            logger.info(f"Updating metadata for {len(mint_addresses)} NFTs")
            
            # Process in batches
            batches = [
                mint_addresses[i:i + self.batch_size]
                for i in range(0, len(mint_addresses), self.batch_size)
            ]
            
            for batch_idx, batch in enumerate(batches):
                logger.info(f"Processing metadata batch {batch_idx + 1}/{len(batches)}")
                
                # Fetch metadata for batch
                metadata_tasks = [
                    self.helius.get_nft_metadata(mint_address)
                    for mint_address in batch
                ]
                
                metadata_results = await asyncio.gather(*metadata_tasks, return_exceptions=True)
                
                # Process results
                valid_metadata = []
                for mint_address, metadata_result in zip(batch, metadata_results):
                    if isinstance(metadata_result, dict):
                        try:
                            # Ensure collection_id is set
                            metadata_result["collection_id"] = collection_id
                            metadata = NFTMetadata(**metadata_result)
                            valid_metadata.append(metadata)
                        except Exception as e:
                            logger.warning(f"Invalid metadata for {mint_address}: {e}")
                            result["errors"] += 1
                    else:
                        logger.warning(f"Failed to fetch metadata for {mint_address}")
                        result["errors"] += 1
                
                # Write metadata batch
                if valid_metadata:
                    written_count = await self.bq_writer.write_metadata_batch(valid_metadata)
                    result["nfts_updated"] += written_count
                
                # Rate limiting
                await asyncio.sleep(0.5)
            
            logger.info(f"Metadata update completed for {collection_id}: {result}")
            
        except Exception as e:
            logger.error(f"Metadata update failed for {collection_id}: {e}")
            result["errors"] += 1
        
        return result
    
    async def _get_cached_collection_metadata(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """Get collection metadata with caching."""
        now = datetime.now()
        
        # Check cache
        if collection_id in self._collection_cache:
            cached_time = self._cache_timestamps.get(collection_id, now)
            if now - cached_time < self._cache_ttl:
                return self._collection_cache[collection_id]
        
        # Fetch fresh data
        metadata = await self.helius.get_collection_metadata(collection_id)
        if metadata:
            self._collection_cache[collection_id] = metadata
            self._cache_timestamps[collection_id] = now
        
        return metadata
    
    async def _get_collection_mint_addresses(self, collection_id: str) -> List[str]:
        """Get all mint addresses for a collection from BigQuery."""
        try:
            query = f"""
            SELECT DISTINCT mint_address
            FROM `{self.bq_writer.project_id}.{self.bq_writer.dataset_id}.nft_metadata`
            WHERE collection_id = @collection_id
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id)
                ]
            )
            
            query_job = self.bq_client.query(query, job_config=job_config)
            results = [row.mint_address for row in query_job]
            
            # If no results in BigQuery, try to fetch from Helius
            if not results:
                logger.info(f"No mint addresses in BigQuery for {collection_id}, fetching from Helius")
                results = await self._fetch_mint_addresses_from_helius(collection_id)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get mint addresses for {collection_id}: {e}")
            return []
    
    async def _fetch_mint_addresses_from_helius(self, collection_id: str) -> List[str]:
        """Fetch mint addresses for collection from Helius API."""
        try:
            # This would use Helius's collection NFT listing endpoint
            # For now, return empty list as we need the actual API endpoint
            logger.warning(f"Helius mint address fetching not implemented for {collection_id}")
            return []
            
        except Exception as e:
            logger.error(f"Failed to fetch mint addresses from Helius: {e}")
            return []
    
    async def _get_last_metadata_update(self, collection_id: str) -> Optional[datetime]:
        """Get timestamp of last metadata update for collection."""
        try:
            query = f"""
            SELECT MAX(ingested_at) as last_update
            FROM `{self.bq_writer.project_id}.{self.bq_writer.dataset_id}.nft_metadata`
            WHERE collection_id = @collection_id
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id)
                ]
            )
            
            query_job = self.bq_client.query(query, job_config=job_config)
            results = list(query_job)
            
            if results and results[0].last_update:
                return results[0].last_update
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get last update time: {e}")
            return None
    
    async def get_collection_stats(self, collection_id: str) -> Dict[str, Any]:
        """Get current statistics for a collection."""
        try:
            query = f"""
            WITH collection_stats AS (
                SELECT 
                    COUNT(DISTINCT mint_address) as total_nfts,
                    COUNT(DISTINCT current_owner) as unique_holders,
                    AVG(last_sale_price) as avg_price,
                    MIN(last_sale_price) as floor_price,
                    COUNT(*) FILTER (WHERE is_listed = true) as listed_count
                FROM `{self.bq_writer.project_id}.{self.bq_writer.dataset_id}.nft_metadata`
                WHERE collection_id = @collection_id
                  AND partition_date = CURRENT_DATE()
            ),
            recent_volume AS (
                SELECT 
                    COUNT(*) as transactions_24h,
                    SUM(price_sol) as volume_24h,
                    COUNT(DISTINCT from_address) + COUNT(DISTINCT to_address) as active_wallets_24h
                FROM `{self.bq_writer.project_id}.{self.bq_writer.dataset_id}.transactions`
                WHERE collection_id = @collection_id
                  AND event_type = 'sale'
                  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
            )
            SELECT * FROM collection_stats CROSS JOIN recent_volume
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id)
                ]
            )
            
            query_job = self.bq_client.query(query, job_config=job_config)
            results = list(query_job)
            
            if results:
                row = results[0]
                return {
                    "collection_id": collection_id,
                    "total_nfts": row.total_nfts or 0,
                    "unique_holders": row.unique_holders or 0,
                    "avg_price": float(row.avg_price) if row.avg_price else 0.0,
                    "floor_price": float(row.floor_price) if row.floor_price else 0.0,
                    "listed_count": row.listed_count or 0,
                    "transactions_24h": row.transactions_24h or 0,
                    "volume_24h": float(row.volume_24h) if row.volume_24h else 0.0,
                    "active_wallets_24h": row.active_wallets_24h or 0
                }
            
            return {
                "collection_id": collection_id,
                "error": "No data found"
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {
                "collection_id": collection_id,
                "error": str(e)
            }