"""ChainWeave Analytics CLI.

Command-line interface for analytics processing and calculations:
- Market metrics computation
- Whale detection and alerts
- Wallet profile analysis
- Rarity calculations
- Data quality checks
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
import click
from google.cloud import bigquery
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from models.market_analytics import MarketAnalytics, MetricType, TimeGranularity
from models.whale_alert import WhaleAlert, AlertType, AlertSeverity
from models.wallet_profile import WalletProfile, WalletTier, TradingBehavior
from services.analytics_engine import AnalyticsEngine
from services.whale_detector import WhaleDetector
from services.rarity_calculator import RarityCalculator
from services.bigquery_writer import BigQueryWriter
from schemas.migrations import BigQueryMigrationManager

logger = logging.getLogger(__name__)


class AnalyticsConfig:
    """Configuration for analytics operations."""
    
    def __init__(
        self,
        project_id: str,
        dataset_id: str,
        batch_size: int = 1000,
        lookback_days: int = 30
    ):
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.batch_size = batch_size
        self.lookback_days = lookback_days


@click.group()
@click.option('--project-id', required=True, help='Google Cloud project ID')
@click.option('--dataset-id', default='chainweave', help='BigQuery dataset ID')
@click.option('--batch-size', default=1000, help='Batch size for processing')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.pass_context
def analytics(ctx, project_id: str, dataset_id: str, batch_size: int, verbose: bool):
    """ChainWeave analytics processing utilities."""
    # Setup logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Store config in context
    ctx.ensure_object(dict)
    ctx.obj['config'] = AnalyticsConfig(
        project_id=project_id,
        dataset_id=dataset_id,
        batch_size=batch_size
    )


@analytics.command()
@click.option('--date', help='Specific date to calculate (YYYY-MM-DD), defaults to yesterday')
@click.option('--collection-id', help='Specific collection to process (optional)')
@click.option('--metrics', default='all', help='Comma-separated metric types (or "all")')
@click.pass_context
def calculate_metrics(ctx, date: Optional[str], collection_id: Optional[str], metrics: str):
    """Calculate daily market metrics."""
    config = ctx.obj['config']
    
    async def _calculate_metrics():
        try:
            # Parse target date
            if date:
                target_date = datetime.strptime(date, '%Y-%m-%d').date()
            else:
                target_date = (datetime.now() - timedelta(days=1)).date()
            
            click.echo(f"Calculating metrics for {target_date}")
            
            # Parse metric types
            if metrics == 'all':
                metric_types = list(MetricType)
            else:
                metric_types = [MetricType(m.strip()) for m in metrics.split(',')]
            
            click.echo(f"Metrics to calculate: {[m.value for m in metric_types]}")
            
            # Initialize services
            bq_writer = BigQueryWriter(config.project_id, config.dataset_id)
            analytics_engine = AnalyticsEngine(config.project_id, config.dataset_id)
            
            if collection_id:
                # Calculate metrics for specific collection
                click.echo(f"Processing collection: {collection_id}")
                
                results = await analytics_engine.calculate_collection_metrics(
                    collection_id=collection_id,
                    target_date=target_date,
                    metric_types=metric_types
                )
                
                click.echo(f"✓ Calculated {len(results)} metrics for {collection_id}")
                
                # Write results
                if results:
                    written_count = await bq_writer.write_analytics_batch(results)
                    click.echo(f"✓ Saved {written_count} analytics records")
            else:
                # Calculate metrics for all collections
                collections = await analytics_engine.get_active_collections()
                click.echo(f"Processing {len(collections)} collections...")
                
                total_metrics = 0
                
                for collection in collections:
                    try:
                        results = await analytics_engine.calculate_collection_metrics(
                            collection_id=collection['collection_id'],
                            target_date=target_date,
                            metric_types=metric_types
                        )
                        
                        if results:
                            written_count = await bq_writer.write_analytics_batch(results)
                            total_metrics += written_count
                            click.echo(f"  ✓ {collection['name']}: {written_count} metrics")
                        
                        # Rate limiting
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        logger.error(f"Failed to process {collection['collection_id']}: {e}")
                        click.echo(f"  ✗ {collection['name']}: {e}")
                
                click.echo(f"✓ Total: {total_metrics} metrics calculated")
            
        except Exception as e:
            logger.error(f"Metrics calculation failed: {e}")
            click.echo(f"Error: {e}")
    
    asyncio.run(_calculate_metrics())


@analytics.command()
@click.option('--lookback-hours', default=24, help='Hours to look back for whale activity')
@click.option('--collection-id', help='Specific collection to monitor (optional)')
@click.option('--dry-run', is_flag=True, help='Show detected whales without saving alerts')
@click.pass_context
def detect_whales(ctx, lookback_hours: int, collection_id: Optional[str], dry_run: bool):
    """Detect whale activity and generate alerts."""
    config = ctx.obj['config']
    
    async def _detect_whales():
        try:
            lookback_time = datetime.now() - timedelta(hours=lookback_hours)
            click.echo(f"Detecting whale activity since {lookback_time}")
            
            # Initialize services
            bq_writer = BigQueryWriter(config.project_id, config.dataset_id)
            whale_detector = WhaleDetector(config.project_id, config.dataset_id)
            
            if collection_id:
                # Detect whales for specific collection
                alerts = await whale_detector.scan_collection_activity(
                    collection_id=collection_id,
                    since=lookback_time
                )
                
                click.echo(f"Detected {len(alerts)} whale activities for {collection_id}")
            else:
                # Scan all recent transactions
                alerts = await whale_detector.scan_recent_activity(since=lookback_time)
                click.echo(f"Detected {len(alerts)} whale activities across all collections")
            
            if not alerts:
                click.echo("No whale activity detected")
                return
            
            # Group alerts by severity
            alert_counts = {}
            for alert in alerts:
                severity = alert.severity.value
                alert_counts[severity] = alert_counts.get(severity, 0) + 1
            
            click.echo("Alert summary:")
            for severity, count in alert_counts.items():
                click.echo(f"  {severity}: {count} alerts")
            
            if dry_run:
                click.echo("\nDry run - showing sample alerts:")
                for alert in alerts[:5]:  # Show first 5
                    click.echo(f"  {alert.severity.value}: {alert.alert_type.value} - "
                             f"{alert.wallet_address[:8]}... - {alert.amount_sol:.2f} SOL")
                return
            
            # Save alerts to BigQuery
            success_count = 0
            for alert in alerts:
                success = await bq_writer.write_whale_alert(alert)
                if success:
                    success_count += 1
            
            click.echo(f"✓ Saved {success_count}/{len(alerts)} alerts")
            
        except Exception as e:
            logger.error(f"Whale detection failed: {e}")
            click.echo(f"Error: {e}")
    
    asyncio.run(_detect_whales())


@analytics.command()
@click.option('--date', help='Specific date to update (YYYY-MM-DD), defaults to yesterday')
@click.option('--wallet-address', help='Specific wallet to update (optional)')
@click.option('--min-activity-threshold', default=1, help='Minimum transactions to create profile')
@click.pass_context
def update_profiles(ctx, date: Optional[str], wallet_address: Optional[str], min_activity_threshold: int):
    """Update wallet profiles with latest activity."""
    config = ctx.obj['config']
    
    async def _update_profiles():
        try:
            # Parse target date
            if date:
                target_date = datetime.strptime(date, '%Y-%m-%d').date()
            else:
                target_date = (datetime.now() - timedelta(days=1)).date()
            
            click.echo(f"Updating wallet profiles for {target_date}")
            
            # Initialize services
            bq_writer = BigQueryWriter(config.project_id, config.dataset_id)
            analytics_engine = AnalyticsEngine(config.project_id, config.dataset_id)
            
            if wallet_address:
                # Update specific wallet profile
                click.echo(f"Updating profile for wallet: {wallet_address}")
                
                profile = await analytics_engine.calculate_wallet_profile(
                    wallet_address=wallet_address,
                    as_of_date=target_date
                )
                
                if profile:
                    success = await bq_writer.write_wallet_profile(profile)
                    if success:
                        click.echo(f"✓ Updated profile for {wallet_address}")
                    else:
                        click.echo(f"✗ Failed to save profile for {wallet_address}")
                else:
                    click.echo(f"No activity found for {wallet_address}")
            else:
                # Update profiles for all active wallets
                active_wallets = await analytics_engine.get_active_wallets(
                    target_date=target_date,
                    min_transactions=min_activity_threshold
                )
                
                click.echo(f"Updating profiles for {len(active_wallets)} active wallets...")
                
                updated_count = 0
                error_count = 0
                
                # Process in batches
                batch_size = config.batch_size // 10  # Smaller batches for profiles
                batches = [
                    active_wallets[i:i + batch_size]
                    for i in range(0, len(active_wallets), batch_size)
                ]
                
                for batch_idx, batch in enumerate(batches):
                    click.echo(f"Processing batch {batch_idx + 1}/{len(batches)}")
                    
                    # Calculate profiles for batch
                    profile_tasks = [
                        analytics_engine.calculate_wallet_profile(wallet, target_date)
                        for wallet in batch
                    ]
                    
                    profile_results = await asyncio.gather(*profile_tasks, return_exceptions=True)
                    
                    # Save successful profiles
                    for wallet, profile_result in zip(batch, profile_results):
                        if isinstance(profile_result, WalletProfile):
                            success = await bq_writer.write_wallet_profile(profile_result)
                            if success:
                                updated_count += 1
                            else:
                                error_count += 1
                        else:
                            error_count += 1
                            logger.warning(f"Failed to calculate profile for {wallet}: {profile_result}")
                    
                    # Progress update
                    if (batch_idx + 1) % 10 == 0:
                        click.echo(f"  Progress: {updated_count} updated, {error_count} errors")
                    
                    # Rate limiting
                    await asyncio.sleep(0.5)
                
                click.echo(f"✓ Updated {updated_count} profiles, {error_count} errors")
            
        except Exception as e:
            logger.error(f"Profile update failed: {e}")
            click.echo(f"Error: {e}")
    
    asyncio.run(_update_profiles())


@analytics.command()
@click.option('--collection-id', required=True, help='Collection to calculate rarity for')
@click.option('--force', is_flag=True, help='Recalculate even if recently updated')
@click.pass_context
def calculate_rarity(ctx, collection_id: str, force: bool):
    """Calculate rarity ranks and scores for NFT collection."""
    config = ctx.obj['config']
    
    async def _calculate_rarity():
        try:
            click.echo(f"Calculating rarity for collection: {collection_id}")
            
            # Initialize services
            bq_writer = BigQueryWriter(config.project_id, config.dataset_id)
            rarity_calculator = RarityCalculator(config.project_id, config.dataset_id)
            
            # Check if calculation is needed
            if not force:
                last_update = await rarity_calculator.get_last_rarity_update(collection_id)
                if last_update and (datetime.now() - last_update).total_seconds() < 86400:  # 24 hours
                    click.echo("Rarity recently calculated. Use --force to recalculate.")
                    return
            
            # Get all NFTs in collection
            nfts = await rarity_calculator.get_collection_nfts(collection_id)
            if not nfts:
                click.echo(f"No NFTs found for collection {collection_id}")
                return
            
            click.echo(f"Found {len(nfts)} NFTs in collection")
            
            # Calculate rarity scores
            click.echo("Calculating rarity scores...")
            rarity_results = await rarity_calculator.calculate_collection_rarity(collection_id, nfts)
            
            if not rarity_results:
                click.echo("Failed to calculate rarity scores")
                return
            
            # Update NFT metadata with new rarity information
            click.echo("Updating NFT metadata with rarity scores...")
            
            updated_count = 0
            for mint_address, rarity_data in rarity_results.items():
                try:
                    success = await rarity_calculator.update_nft_rarity(
                        mint_address=mint_address,
                        rarity_rank=rarity_data['rank'],
                        rarity_score=rarity_data['score']
                    )
                    if success:
                        updated_count += 1
                except Exception as e:
                    logger.warning(f"Failed to update rarity for {mint_address}: {e}")
            
            click.echo(f"✓ Updated rarity for {updated_count}/{len(rarity_results)} NFTs")
            
            # Calculate collection-level rarity statistics
            stats = await rarity_calculator.calculate_rarity_stats(collection_id)
            click.echo(f"\nCollection Rarity Statistics:")
            click.echo(f"  Unique traits: {stats.get('unique_traits', 0)}")
            click.echo(f"  Avg rarity score: {stats.get('avg_score', 0):.2f}")
            click.echo(f"  Rarity distribution:")
            for tier, count in stats.get('tier_distribution', {}).items():
                percentage = (count / len(nfts)) * 100
                click.echo(f"    {tier}: {count} ({percentage:.1f}%)")
            
        except Exception as e:
            logger.error(f"Rarity calculation failed: {e}")
            click.echo(f"Error: {e}")
    
    asyncio.run(_calculate_rarity())


@analytics.command()
@click.option('--date', help='Specific date to check (YYYY-MM-DD), defaults to yesterday')
@click.option('--fix-issues', is_flag=True, help='Attempt to fix detected issues')
@click.pass_context
def check_data_quality(ctx, date: Optional[str], fix_issues: bool):
    """Run data quality checks and report issues."""
    config = ctx.obj['config']
    
    async def _check_data_quality():
        try:
            # Parse target date
            if date:
                target_date = datetime.strptime(date, '%Y-%m-%d').date()
            else:
                target_date = (datetime.now() - timedelta(days=1)).date()
            
            click.echo(f"Running data quality checks for {target_date}")
            
            # Initialize services
            analytics_engine = AnalyticsEngine(config.project_id, config.dataset_id)
            mgr = BigQueryMigrationManager(config.project_id, config.dataset_id)
            
            # Run comprehensive data quality checks
            issues = []
            
            # Check 1: Missing transactions for active collections
            click.echo("Checking for missing transaction data...")
            missing_tx = await analytics_engine.find_missing_transaction_data(target_date)
            if missing_tx:
                issues.extend(missing_tx)
                click.echo(f"  Found {len(missing_tx)} collections with missing transactions")
            
            # Check 2: Orphaned NFT metadata
            click.echo("Checking for orphaned NFT metadata...")
            orphaned_nfts = await analytics_engine.find_orphaned_nfts()
            if orphaned_nfts:
                issues.extend(orphaned_nfts)
                click.echo(f"  Found {len(orphaned_nfts)} orphaned NFTs")
            
            # Check 3: Inconsistent wallet profiles
            click.echo("Checking wallet profile consistency...")
            inconsistent_profiles = await analytics_engine.find_inconsistent_profiles(target_date)
            if inconsistent_profiles:
                issues.extend(inconsistent_profiles)
                click.echo(f"  Found {len(inconsistent_profiles)} inconsistent profiles")
            
            # Check 4: Missing market analytics
            click.echo("Checking for missing market analytics...")
            missing_analytics = await analytics_engine.find_missing_analytics(target_date)
            if missing_analytics:
                issues.extend(missing_analytics)
                click.echo(f"  Found {len(missing_analytics)} missing analytics")
            
            # Check 5: Data integrity across tables
            click.echo("Running table integrity checks...")
            for table_name in ['nft_collections', 'nft_metadata', 'transactions', 'wallet_profiles']:
                integrity_result = mgr.validate_data_integrity(table_name)
                if integrity_result.get('issues'):
                    issues.extend(integrity_result['issues'])
                    click.echo(f"  {table_name}: {len(integrity_result['issues'])} issues")
            
            # Summary
            if not issues:
                click.echo("\n✓ No data quality issues detected")
                return
            
            click.echo(f"\n⚠ Found {len(issues)} data quality issues:")
            for issue in issues[:10]:  # Show first 10 issues
                click.echo(f"  - {issue}")
            
            if len(issues) > 10:
                click.echo(f"  ... and {len(issues) - 10} more issues")
            
            if fix_issues:
                click.echo("\nAttempting to fix issues...")
                fixed_count = await analytics_engine.fix_data_quality_issues(issues)
                click.echo(f"✓ Fixed {fixed_count}/{len(issues)} issues")
            else:
                click.echo("\nUse --fix-issues to attempt automatic repairs")
            
        except Exception as e:
            logger.error(f"Data quality check failed: {e}")
            click.echo(f"Error: {e}")
    
    asyncio.run(_check_data_quality())


@analytics.command()
@click.pass_context
def status(ctx):
    """Show analytics system status and health."""
    config = ctx.obj['config']
    
    async def _status():
        try:
            click.echo("=== ChainWeave Analytics Status ===\n")
            
            # Initialize services
            analytics_engine = AnalyticsEngine(config.project_id, config.dataset_id)
            client = bigquery.Client(project=config.project_id)
            
            # Check recent analytics activity
            query = f"""
            SELECT 
                metric_type,
                DATE(partition_date) as date,
                COUNT(*) as records,
                COUNT(DISTINCT collection_id) as collections
            FROM `{config.project_id}.{config.dataset_id}.market_analytics`
            WHERE partition_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
            GROUP BY metric_type, DATE(partition_date)
            ORDER BY date DESC, metric_type
            LIMIT 20
            """
            
            query_job = client.query(query)
            results = list(query_job)
            
            if results:
                click.echo("Recent analytics activity:")
                current_date = None
                for row in results:
                    if current_date != row.date:
                        current_date = row.date
                        click.echo(f"\n  {row.date}:")
                    click.echo(f"    {row.metric_type}: {row.records:,} records, {row.collections} collections")
            
            # Check whale alert activity
            click.echo(f"\n=== Whale Alert Activity ===")
            
            whale_query = f"""
            SELECT 
                DATE(partition_date) as date,
                alert_type,
                severity,
                COUNT(*) as alerts
            FROM `{config.project_id}.{config.dataset_id}.whale_alerts`
            WHERE partition_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
            GROUP BY DATE(partition_date), alert_type, severity
            ORDER BY date DESC, alerts DESC
            LIMIT 15
            """
            
            whale_job = client.query(whale_query)
            whale_results = list(whale_job)
            
            if whale_results:
                for row in whale_results:
                    click.echo(f"  {row.date}: {row.alert_type} ({row.severity}) - {row.alerts} alerts")
            else:
                click.echo("  No recent whale alerts")
            
            # Check data freshness
            click.echo(f"\n=== Data Freshness ===")
            
            freshness_checks = {
                'market_analytics': 'partition_date',
                'wallet_profiles': 'partition_date', 
                'whale_alerts': 'partition_date',
                'transactions': 'partition_date'
            }
            
            for table, date_field in freshness_checks.items():
                query = f"""
                SELECT MAX({date_field}) as latest_date
                FROM `{config.project_id}.{config.dataset_id}.{table}`
                """
                
                job = client.query(query)
                result = list(job)
                
                if result and result[0].latest_date:
                    latest = result[0].latest_date
                    days_old = (datetime.now().date() - latest).days
                    status_indicator = "✓" if days_old <= 1 else "⚠" if days_old <= 3 else "✗"
                    click.echo(f"  {table}: {latest} ({days_old} days old) {status_indicator}")
                else:
                    click.echo(f"  {table}: No data found ✗")
            
            # Processing performance stats
            click.echo(f"\n=== Processing Performance ===")
            
            perf_query = f"""
            SELECT 
                'Daily Analytics' as process,
                COUNT(DISTINCT DATE(created_at)) as days_processed,
                COUNT(*) as total_metrics,
                AVG(confidence_score) as avg_confidence
            FROM `{config.project_id}.{config.dataset_id}.market_analytics`
            WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
            """
            
            perf_job = client.query(perf_query)
            perf_results = list(perf_job)
            
            for row in perf_results:
                click.echo(f"  {row.process}: {row.total_metrics:,} metrics over {row.days_processed} days")
                if row.avg_confidence:
                    click.echo(f"    Average confidence: {row.avg_confidence:.2%}")
            
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            click.echo(f"Error: {e}")
    
    asyncio.run(_status())


if __name__ == '__main__':
    analytics()