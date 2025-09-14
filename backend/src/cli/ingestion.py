"""ChainWeave Ingestion CLI.

Command-line interface for managing NFT data ingestion from various sources:
- Helius webhook processing
- On-chain data backfill
- Collection metadata updates
- Real-time transaction streaming
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import click
from google.cloud import bigquery
import httpx
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from models.nft_collection import NFTCollection
from models.nft_metadata import NFTMetadata
from models.transaction import Transaction, EventType
from models.wallet_profile import WalletProfile
from schemas.migrations import BigQueryMigrationManager
from services.helius_client import HeliusClient
from services.bigquery_writer import BigQueryWriter
from services.collection_tracker import CollectionTracker

logger = logging.getLogger(__name__)


class IngestionConfig:
    """Configuration for ingestion operations."""
    
    def __init__(
        self,
        project_id: str,
        dataset_id: str,
        helius_api_key: str,
        webhook_secret: Optional[str] = None,
        batch_size: int = 1000,
        max_retries: int = 3
    ):
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.helius_api_key = helius_api_key
        self.webhook_secret = webhook_secret
        self.batch_size = batch_size
        self.max_retries = max_retries


@click.group()
@click.option('--project-id', required=True, help='Google Cloud project ID')
@click.option('--dataset-id', default='chainweave', help='BigQuery dataset ID')
@click.option('--helius-api-key', required=True, help='Helius API key')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.pass_context
def ingestion(ctx, project_id: str, dataset_id: str, helius_api_key: str, verbose: bool):
    """ChainWeave data ingestion utilities."""
    # Setup logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Store config in context
    ctx.ensure_object(dict)
    ctx.obj['config'] = IngestionConfig(
        project_id=project_id,
        dataset_id=dataset_id,
        helius_api_key=helius_api_key
    )


@ingestion.command()
@click.option('--collection-id', required=True, help='Collection ID to track')
@click.option('--backfill-days', default=7, help='Days of historical data to backfill')
@click.pass_context
def add_collection(ctx, collection_id: str, backfill_days: int):
    """Add a new NFT collection for tracking."""
    config = ctx.obj['config']
    
    async def _add_collection():
        try:
            # Initialize services
            helius = HeliusClient(config.helius_api_key)
            bq_writer = BigQueryWriter(config.project_id, config.dataset_id)
            tracker = CollectionTracker(helius, bq_writer)
            
            click.echo(f"Adding collection {collection_id} for tracking...")
            
            # Fetch collection metadata from on-chain
            collection_data = await helius.get_collection_metadata(collection_id)
            if not collection_data:
                click.echo(f"Error: Could not fetch metadata for collection {collection_id}")
                return
            
            # Create collection record
            collection = NFTCollection(**collection_data)
            
            # Save to BigQuery
            success = await bq_writer.write_collection(collection)
            if not success:
                click.echo(f"Error: Failed to save collection {collection_id} to BigQuery")
                return
            
            click.echo(f"✓ Collection {collection.name} added successfully")
            
            # Start backfill if requested
            if backfill_days > 0:
                click.echo(f"Starting {backfill_days}-day historical backfill...")
                
                end_date = datetime.now()
                start_date = end_date - timedelta(days=backfill_days)
                
                await tracker.backfill_collection_data(
                    collection_id=collection_id,
                    start_date=start_date,
                    end_date=end_date
                )
                
                click.echo("✓ Historical backfill completed")
            
        except Exception as e:
            logger.error(f"Failed to add collection: {e}")
            click.echo(f"Error: {e}")
    
    asyncio.run(_add_collection())


@ingestion.command()
@click.option('--webhook-url', required=True, help='Webhook payload URL or file path')
@click.option('--validate-only', is_flag=True, help='Only validate webhook, do not process')
@click.pass_context
def process_webhook(ctx, webhook_url: str, validate_only: bool):
    """Process a Helius webhook payload."""
    config = ctx.obj['config']
    
    async def _process_webhook():
        try:
            # Load webhook data
            if webhook_url.startswith('http'):
                # Fetch from URL
                async with httpx.AsyncClient() as client:
                    response = await client.get(webhook_url)
                    webhook_data = response.json()
            else:
                # Load from file
                import json
                with open(webhook_url, 'r') as f:
                    webhook_data = json.load(f)
            
            click.echo(f"Processing webhook with {len(webhook_data)} transactions...")
            
            if validate_only:
                # Just validate the data
                valid_count = 0
                for tx_data in webhook_data:
                    try:
                        transaction = Transaction(**tx_data)
                        valid_count += 1
                    except Exception as e:
                        logger.warning(f"Invalid transaction: {e}")
                
                click.echo(f"✓ {valid_count}/{len(webhook_data)} transactions are valid")
                return
            
            # Process transactions
            bq_writer = BigQueryWriter(config.project_id, config.dataset_id)
            
            processed_count = 0
            for tx_data in webhook_data:
                try:
                    transaction = Transaction(**tx_data)
                    success = await bq_writer.write_transaction(transaction)
                    if success:
                        processed_count += 1
                except Exception as e:
                    logger.warning(f"Failed to process transaction: {e}")
            
            click.echo(f"✓ Processed {processed_count}/{len(webhook_data)} transactions")
            
        except Exception as e:
            logger.error(f"Failed to process webhook: {e}")
            click.echo(f"Error: {e}")
    
    asyncio.run(_process_webhook())


@ingestion.command()
@click.option('--collection-id', help='Specific collection to backfill (optional)')
@click.option('--start-date', required=True, help='Start date (YYYY-MM-DD)')
@click.option('--end-date', help='End date (YYYY-MM-DD, defaults to today)')
@click.option('--batch-size', default=1000, help='Batch size for processing')
@click.pass_context
def backfill(ctx, collection_id: Optional[str], start_date: str, end_date: Optional[str], batch_size: int):
    """Backfill historical NFT transaction data."""
    config = ctx.obj['config']
    config.batch_size = batch_size
    
    async def _backfill():
        try:
            # Parse dates
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') if end_date else datetime.now()
            
            if start_dt >= end_dt:
                click.echo("Error: Start date must be before end date")
                return
            
            days = (end_dt - start_dt).days
            click.echo(f"Starting {days}-day backfill from {start_date} to {end_dt.strftime('%Y-%m-%d')}")
            
            # Initialize services
            helius = HeliusClient(config.helius_api_key)
            bq_writer = BigQueryWriter(config.project_id, config.dataset_id)
            tracker = CollectionTracker(helius, bq_writer)
            
            if collection_id:
                # Backfill specific collection
                click.echo(f"Backfilling collection: {collection_id}")
                result = await tracker.backfill_collection_data(collection_id, start_dt, end_dt)
                click.echo(f"✓ Processed {result['transactions']} transactions, {result['nfts']} NFTs")
            else:
                # Backfill all tracked collections
                collections = await tracker.get_tracked_collections()
                click.echo(f"Backfilling {len(collections)} collections...")
                
                total_transactions = 0
                total_nfts = 0
                
                for collection in collections:
                    click.echo(f"Processing {collection['name']}...")
                    result = await tracker.backfill_collection_data(
                        collection['collection_id'], start_dt, end_dt
                    )
                    total_transactions += result['transactions']
                    total_nfts += result['nfts']
                    click.echo(f"  ✓ {result['transactions']} transactions, {result['nfts']} NFTs")
                
                click.echo(f"✓ Total: {total_transactions} transactions, {total_nfts} NFTs")
            
        except Exception as e:
            logger.error(f"Backfill failed: {e}")
            click.echo(f"Error: {e}")
    
    asyncio.run(_backfill())


@ingestion.command()
@click.option('--duration', default=3600, help='Duration to stream in seconds')
@click.option('--collections', help='Comma-separated collection IDs to track')
@click.pass_context
def stream(ctx, duration: int, collections: Optional[str]):
    """Stream real-time NFT transactions."""
    config = ctx.obj['config']
    
    async def _stream():
        try:
            collection_ids = collections.split(',') if collections else None
            
            # Initialize services
            helius = HeliusClient(config.helius_api_key)
            bq_writer = BigQueryWriter(config.project_id, config.dataset_id)
            
            click.echo(f"Starting real-time stream for {duration} seconds...")
            if collection_ids:
                click.echo(f"Tracking collections: {', '.join(collection_ids)}")
            
            processed_count = 0
            start_time = datetime.now()
            
            async for transaction_data in helius.stream_transactions(collection_ids):
                try:
                    transaction = Transaction(**transaction_data)
                    success = await bq_writer.write_transaction(transaction)
                    
                    if success:
                        processed_count += 1
                        if processed_count % 100 == 0:
                            elapsed = (datetime.now() - start_time).total_seconds()
                            rate = processed_count / elapsed
                            click.echo(f"Processed {processed_count} transactions ({rate:.1f}/sec)")
                    
                    # Check duration
                    if (datetime.now() - start_time).total_seconds() >= duration:
                        break
                        
                except Exception as e:
                    logger.warning(f"Failed to process transaction: {e}")
            
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = processed_count / elapsed if elapsed > 0 else 0
            click.echo(f"✓ Streamed {processed_count} transactions in {elapsed:.1f}s ({rate:.1f}/sec)")
            
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            click.echo(f"Error: {e}")
    
    asyncio.run(_stream())


@ingestion.command()
@click.option('--collection-id', help='Specific collection to update (optional)')
@click.option('--force', is_flag=True, help='Force update even if recently updated')
@click.pass_context
def update_metadata(ctx, collection_id: Optional[str], force: bool):
    """Update NFT and collection metadata."""
    config = ctx.obj['config']
    
    async def _update_metadata():
        try:
            # Initialize services
            helius = HeliusClient(config.helius_api_key)
            bq_writer = BigQueryWriter(config.project_id, config.dataset_id)
            tracker = CollectionTracker(helius, bq_writer)
            
            if collection_id:
                # Update specific collection
                click.echo(f"Updating metadata for collection: {collection_id}")
                result = await tracker.update_collection_metadata(collection_id, force=force)
                click.echo(f"✓ Updated {result['nfts_updated']} NFTs")
            else:
                # Update all collections
                collections = await tracker.get_tracked_collections()
                click.echo(f"Updating metadata for {len(collections)} collections...")
                
                total_updated = 0
                for collection in collections:
                    click.echo(f"Processing {collection['name']}...")
                    result = await tracker.update_collection_metadata(
                        collection['collection_id'], force=force
                    )
                    total_updated += result['nfts_updated']
                    click.echo(f"  ✓ {result['nfts_updated']} NFTs updated")
                
                click.echo(f"✓ Total: {total_updated} NFTs updated")
            
        except Exception as e:
            logger.error(f"Metadata update failed: {e}")
            click.echo(f"Error: {e}")
    
    asyncio.run(_update_metadata())


@ingestion.command()
@click.pass_context
def status(ctx):
    """Show ingestion system status."""
    config = ctx.obj['config']
    
    async def _status():
        try:
            # Get BigQuery status
            mgr = BigQueryMigrationManager(config.project_id, config.dataset_id)
            
            click.echo("=== ChainWeave Ingestion Status ===\n")
            
            # Check table status
            tables = ['nft_collections', 'nft_metadata', 'transactions', 'wallet_profiles']
            for table_name in tables:
                info = mgr.get_table_info(table_name)
                if 'error' not in info:
                    click.echo(f"✓ {table_name}: {info['num_rows']:,} rows, {info['num_bytes']//1024//1024}MB")
                else:
                    click.echo(f"✗ {table_name}: {info['error']}")
            
            click.echo()
            
            # Check recent ingestion activity
            client = bigquery.Client(project=config.project_id)
            
            # Recent transactions
            query = f"""
            SELECT 
                DATE(partition_date) as date,
                COUNT(*) as transactions,
                COUNT(DISTINCT collection_id) as collections
            FROM `{config.project_id}.{config.dataset_id}.transactions`
            WHERE partition_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
            GROUP BY DATE(partition_date)
            ORDER BY date DESC
            LIMIT 7
            """
            
            query_job = client.query(query)
            results = list(query_job)
            
            if results:
                click.echo("Recent transaction activity:")
                for row in results:
                    click.echo(f"  {row.date}: {row.transactions:,} transactions, {row.collections} collections")
            else:
                click.echo("No recent transaction data found")
            
            # Test Helius connectivity
            click.echo("\n=== API Connectivity ===")
            helius = HeliusClient(config.helius_api_key)
            
            try:
                # Test API call
                test_result = await helius.test_connection()
                if test_result:
                    click.echo("✓ Helius API: Connected")
                else:
                    click.echo("✗ Helius API: Connection failed")
            except Exception as e:
                click.echo(f"✗ Helius API: {e}")
            
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            click.echo(f"Error: {e}")
    
    asyncio.run(_status())


if __name__ == '__main__':
    ingestion()