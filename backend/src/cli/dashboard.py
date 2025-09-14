"""ChainWeave Dashboard CLI.

Command-line interface for dashboard data preparation and management:
- Data aggregation for dashboard views
- Cache warming and management
- Dashboard health monitoring
- Export utilities for external tools
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
import click
import json
from pathlib import Path
import csv
from google.cloud import bigquery

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from services.dashboard_data_service import DashboardDataService
from services.cache_manager import CacheManager
from schemas.migrations import BigQueryMigrationManager

logger = logging.getLogger(__name__)


class DashboardConfig:
    """Configuration for dashboard operations."""
    
    def __init__(
        self,
        project_id: str,
        dataset_id: str,
        cache_ttl_minutes: int = 15,
        max_collections: int = 100
    ):
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.cache_ttl_minutes = cache_ttl_minutes
        self.max_collections = max_collections


@click.group()
@click.option('--project-id', required=True, help='Google Cloud project ID')
@click.option('--dataset-id', default='chainweave', help='BigQuery dataset ID')
@click.option('--cache-ttl', default=15, help='Cache TTL in minutes')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.pass_context
def dashboard(ctx, project_id: str, dataset_id: str, cache_ttl: int, verbose: bool):
    """ChainWeave dashboard utilities."""
    # Setup logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Store config in context
    ctx.ensure_object(dict)
    ctx.obj['config'] = DashboardConfig(
        project_id=project_id,
        dataset_id=dataset_id,
        cache_ttl_minutes=cache_ttl
    )


@dashboard.command()
@click.option('--collections', help='Comma-separated collection IDs (optional)')
@click.option('--force-refresh', is_flag=True, help='Force refresh cached data')
@click.pass_context
def warm_cache(ctx, collections: Optional[str], force_refresh: bool):
    """Warm dashboard cache with fresh data."""
    config = ctx.obj['config']
    
    async def _warm_cache():
        try:
            # Initialize services
            dashboard_service = DashboardDataService(config.project_id, config.dataset_id)
            cache_manager = CacheManager()
            
            collection_ids = collections.split(',') if collections else None
            
            if collection_ids:
                click.echo(f"Warming cache for {len(collection_ids)} collections...")
            else:
                click.echo("Warming cache for all active collections...")
                collection_ids = await dashboard_service.get_active_collection_ids()
                click.echo(f"Found {len(collection_ids)} active collections")
            
            # Warm different data types
            cache_operations = [
                ('Global Market Summary', dashboard_service.get_global_market_summary()),
                ('Top Collections', dashboard_service.get_top_collections_by_volume()),
                ('Recent Whale Alerts', dashboard_service.get_recent_whale_alerts()),
                ('Market Trends', dashboard_service.get_market_trends())
            ]
            
            for operation_name, operation_coro in cache_operations:
                try:
                    click.echo(f"Caching {operation_name}...")
                    data = await operation_coro
                    
                    if data:
                        cache_key = f"dashboard_{operation_name.lower().replace(' ', '_')}"
                        await cache_manager.set(cache_key, data, ttl_minutes=config.cache_ttl_minutes)
                        click.echo(f"  ✓ Cached {operation_name}")
                    else:
                        click.echo(f"  ⚠ No data for {operation_name}")
                        
                except Exception as e:
                    click.echo(f"  ✗ Failed to cache {operation_name}: {e}")
            
            # Cache collection-specific data
            cached_collections = 0
            for collection_id in collection_ids[:20]:  # Limit to prevent overload
                try:
                    click.echo(f"Caching data for {collection_id}...")
                    
                    # Collection summary
                    summary = await dashboard_service.get_collection_summary(collection_id)
                    if summary:
                        cache_key = f"collection_summary_{collection_id}"
                        await cache_manager.set(cache_key, summary, ttl_minutes=config.cache_ttl_minutes)
                    
                    # Recent transactions
                    transactions = await dashboard_service.get_recent_transactions(collection_id, limit=50)
                    if transactions:
                        cache_key = f"recent_transactions_{collection_id}"
                        await cache_manager.set(cache_key, transactions, ttl_minutes=config.cache_ttl_minutes)
                    
                    # Price history
                    price_history = await dashboard_service.get_price_history(collection_id, days=30)
                    if price_history:
                        cache_key = f"price_history_{collection_id}"
                        await cache_manager.set(cache_key, price_history, ttl_minutes=config.cache_ttl_minutes)
                    
                    cached_collections += 1
                    
                    # Rate limiting
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    click.echo(f"  ✗ Failed to cache {collection_id}: {e}")
            
            click.echo(f"✓ Cache warming completed: {cached_collections} collections cached")
            
        except Exception as e:
            logger.error(f"Cache warming failed: {e}")
            click.echo(f"Error: {e}")
    
    asyncio.run(_warm_cache())


@dashboard.command()
@click.option('--output-file', required=True, help='Output JSON file path')
@click.option('--collections', help='Comma-separated collection IDs (optional)')
@click.option('--include-historical', is_flag=True, help='Include historical data')
@click.pass_context
def export_data(ctx, output_file: str, collections: Optional[str], include_historical: bool):
    """Export dashboard data to JSON file."""
    config = ctx.obj['config']
    
    async def _export_data():
        try:
            dashboard_service = DashboardDataService(config.project_id, config.dataset_id)
            
            collection_ids = collections.split(',') if collections else None
            if not collection_ids:
                collection_ids = await dashboard_service.get_active_collection_ids()
            
            click.echo(f"Exporting data for {len(collection_ids)} collections...")
            
            # Build export data structure
            export_data = {
                'metadata': {
                    'export_timestamp': datetime.now().isoformat(),
                    'total_collections': len(collection_ids),
                    'includes_historical': include_historical
                },
                'global_summary': {},
                'collections': {},
                'whale_alerts': [],
                'market_trends': {}
            }
            
            # Global data
            click.echo("Exporting global market data...")
            export_data['global_summary'] = await dashboard_service.get_global_market_summary()
            export_data['whale_alerts'] = await dashboard_service.get_recent_whale_alerts(limit=100)
            export_data['market_trends'] = await dashboard_service.get_market_trends(days=30)
            
            # Collection data
            for collection_id in collection_ids:
                try:
                    click.echo(f"Exporting {collection_id}...")
                    
                    collection_data = {
                        'summary': await dashboard_service.get_collection_summary(collection_id),
                        'recent_transactions': await dashboard_service.get_recent_transactions(collection_id, limit=100),
                        'top_holders': await dashboard_service.get_top_holders(collection_id, limit=20),
                        'floor_price_history': await dashboard_service.get_price_history(collection_id, days=30)
                    }
                    
                    if include_historical:
                        collection_data['historical_metrics'] = await dashboard_service.get_historical_metrics(
                            collection_id, days=90
                        )
                    
                    export_data['collections'][collection_id] = collection_data
                    
                except Exception as e:
                    click.echo(f"  ✗ Failed to export {collection_id}: {e}")
            
            # Write to file
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            file_size = output_path.stat().st_size / (1024 * 1024)  # MB
            click.echo(f"✓ Exported {file_size:.1f}MB to {output_file}")
            
        except Exception as e:
            logger.error(f"Data export failed: {e}")
            click.echo(f"Error: {e}")
    
    asyncio.run(_export_data())


@dashboard.command()
@click.option('--collection-id', required=True, help='Collection to analyze')
@click.option('--output-csv', help='Output CSV file (optional)')
@click.pass_context
def analyze_collection(ctx, collection_id: str, output_csv: Optional[str]):
    """Perform detailed analysis of a specific collection."""
    config = ctx.obj['config']
    
    async def _analyze_collection():
        try:
            dashboard_service = DashboardDataService(config.project_id, config.dataset_id)
            
            click.echo(f"Analyzing collection: {collection_id}")
            
            # Get comprehensive collection data
            summary = await dashboard_service.get_collection_summary(collection_id)
            if not summary:
                click.echo(f"Collection {collection_id} not found")
                return
            
            click.echo(f"\n=== {summary['name']} ===")
            click.echo(f"Total Supply: {summary.get('total_supply', 0):,}")
            click.echo(f"Holders: {summary.get('holders_count', 0):,}")
            click.echo(f"Floor Price: {summary.get('floor_price', 0):.4f} SOL")
            click.echo(f"24h Volume: {summary.get('volume_24h', 0):.2f} SOL")
            click.echo(f"Market Cap: {summary.get('market_cap', 0):.2f} SOL")
            
            # Trading activity analysis
            click.echo(f"\n=== Trading Activity ===")
            recent_transactions = await dashboard_service.get_recent_transactions(collection_id, limit=100)
            
            if recent_transactions:
                total_volume = sum(tx.get('price_sol', 0) for tx in recent_transactions if tx.get('price_sol'))
                avg_price = total_volume / len(recent_transactions) if recent_transactions else 0
                unique_traders = len(set(
                    [tx.get('from_address'), tx.get('to_address')] 
                    for tx in recent_transactions
                ))
                
                click.echo(f"Recent Transactions: {len(recent_transactions)}")
                click.echo(f"Volume (Recent): {total_volume:.2f} SOL")
                click.echo(f"Average Price: {avg_price:.4f} SOL")
                click.echo(f"Unique Traders: {unique_traders}")
            
            # Holder analysis
            click.echo(f"\n=== Holder Analysis ===")
            top_holders = await dashboard_service.get_top_holders(collection_id, limit=10)
            
            if top_holders:
                total_held_by_top_10 = sum(holder.get('nft_count', 0) for holder in top_holders[:10])
                concentration_pct = (total_held_by_top_10 / summary.get('total_supply', 1)) * 100
                
                click.echo(f"Top 10 holders own: {total_held_by_top_10} NFTs ({concentration_pct:.1f}%)")
                click.echo(f"Top holder: {top_holders[0]['nft_count']} NFTs" if top_holders else "No holder data")
            
            # Whale activity
            click.echo(f"\n=== Whale Activity ===")
            whale_alerts = await dashboard_service.get_collection_whale_alerts(collection_id, days=7)
            
            if whale_alerts:
                alert_counts = {}
                for alert in whale_alerts:
                    alert_type = alert.get('alert_type', 'unknown')
                    alert_counts[alert_type] = alert_counts.get(alert_type, 0) + 1
                
                click.echo(f"Whale alerts (7 days): {len(whale_alerts)}")
                for alert_type, count in alert_counts.items():
                    click.echo(f"  {alert_type}: {count}")
            else:
                click.echo("No recent whale activity")
            
            # Price trends
            click.echo(f"\n=== Price Trends ===")
            price_history = await dashboard_service.get_price_history(collection_id, days=30)
            
            if price_history and len(price_history) >= 2:
                first_price = price_history[-1].get('floor_price', 0)
                latest_price = price_history[0].get('floor_price', 0)
                
                if first_price > 0:
                    price_change_pct = ((latest_price - first_price) / first_price) * 100
                    trend = "📈" if price_change_pct > 0 else "📉" if price_change_pct < 0 else "➡️"
                    click.echo(f"30-day price change: {price_change_pct:+.1f}% {trend}")
                    click.echo(f"Price range: {min(p.get('floor_price', 0) for p in price_history):.4f} - {max(p.get('floor_price', 0) for p in price_history):.4f} SOL")
            
            # Export to CSV if requested
            if output_csv and recent_transactions:
                click.echo(f"\n=== Exporting to CSV ===")
                
                csv_path = Path(output_csv)
                csv_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(csv_path, 'w', newline='') as csvfile:
                    if recent_transactions:
                        fieldnames = recent_transactions[0].keys()
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(recent_transactions)
                
                click.echo(f"✓ Exported transaction data to {output_csv}")
            
        except Exception as e:
            logger.error(f"Collection analysis failed: {e}")
            click.echo(f"Error: {e}")
    
    asyncio.run(_analyze_collection())


@dashboard.command()
@click.option('--days', default=7, help='Days to look back for trending analysis')
@click.option('--min-volume', default=10.0, help='Minimum volume threshold in SOL')
@click.pass_context
def trending(ctx, days: int, min_volume: float):
    """Show trending collections and market movements."""
    config = ctx.obj['config']
    
    async def _show_trending():
        try:
            dashboard_service = DashboardDataService(config.project_id, config.dataset_id)
            
            click.echo(f"=== Trending Analysis ({days} days) ===\n")
            
            # Top volume collections
            click.echo("🔥 Top Collections by Volume:")
            top_collections = await dashboard_service.get_top_collections_by_volume(days=days, limit=10)
            
            for i, collection in enumerate(top_collections, 1):
                volume = collection.get('volume', 0)
                change_pct = collection.get('volume_change_pct', 0)
                trend = "📈" if change_pct > 10 else "📉" if change_pct < -10 else "➡️"
                
                click.echo(f"{i:2d}. {collection.get('name', 'Unknown')[:30]:<30} "
                          f"{volume:>8.1f} SOL {change_pct:>+6.1f}% {trend}")
            
            # Biggest movers
            click.echo(f"\n🚀 Biggest Volume Movers:")
            movers = await dashboard_service.get_biggest_movers(days=days, min_volume=min_volume)
            
            for mover in movers[:10]:
                name = mover.get('name', 'Unknown')[:30]
                change_pct = mover.get('volume_change_pct', 0)
                current_volume = mover.get('current_volume', 0)
                trend = "🔥" if change_pct > 100 else "📈" if change_pct > 50 else "📊"
                
                click.echo(f"  {name:<30} {current_volume:>8.1f} SOL {change_pct:>+7.1f}% {trend}")
            
            # Recent whale activity
            click.echo(f"\n🐋 Recent Whale Activity:")
            whale_alerts = await dashboard_service.get_recent_whale_alerts(limit=10)
            
            for alert in whale_alerts:
                alert_type = alert.get('alert_type', 'unknown')
                amount = alert.get('amount_sol', 0)
                collection = alert.get('collection_name', 'Unknown')[:20]
                severity = alert.get('severity', 'unknown')
                
                severity_emoji = {'critical': '🚨', 'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(severity, '⚪')
                
                click.echo(f"  {severity_emoji} {alert_type:<20} {amount:>8.1f} SOL in {collection}")
            
            # Market overview
            click.echo(f"\n📊 Market Overview:")
            global_summary = await dashboard_service.get_global_market_summary()
            
            if global_summary:
                click.echo(f"Total Collections: {global_summary.get('total_collections', 0):,}")
                click.echo(f"24h Volume: {global_summary.get('total_volume_24h', 0):.1f} SOL")
                click.echo(f"Active Wallets: {global_summary.get('unique_wallets_24h', 0):,}")
                click.echo(f"Avg Transaction: {global_summary.get('avg_transaction_size', 0):.3f} SOL")
                
                market_trend = global_summary.get('market_trend', 'neutral')
                trend_emoji = {'bullish': '🐂', 'bearish': '🐻', 'neutral': '😐'}.get(market_trend, '❓')
                click.echo(f"Market Sentiment: {market_trend.title()} {trend_emoji}")
            
        except Exception as e:
            logger.error(f"Trending analysis failed: {e}")
            click.echo(f"Error: {e}")
    
    asyncio.run(_show_trending())


@dashboard.command()
@click.pass_context
def health_check(ctx):
    """Check dashboard data health and freshness."""
    config = ctx.obj['config']
    
    async def _health_check():
        try:
            click.echo("=== Dashboard Health Check ===\n")
            
            # Initialize services
            dashboard_service = DashboardDataService(config.project_id, config.dataset_id)
            cache_manager = CacheManager()
            mgr = BigQueryMigrationManager(config.project_id, config.dataset_id)
            
            # Check data freshness
            click.echo("📅 Data Freshness:")
            
            tables_to_check = {
                'transactions': 'Recent transaction data',
                'market_analytics': 'Market metrics',
                'whale_alerts': 'Whale alerts',
                'wallet_profiles': 'Wallet profiles'
            }
            
            client = bigquery.Client(project=config.project_id)
            
            for table_name, description in tables_to_check.items():
                query = f"""
                SELECT MAX(partition_date) as latest_date
                FROM `{config.project_id}.{config.dataset_id}.{table_name}`
                """
                
                query_job = client.query(query)
                results = list(query_job)
                
                if results and results[0].latest_date:
                    latest_date = results[0].latest_date
                    days_old = (datetime.now().date() - latest_date).days
                    
                    if days_old == 0:
                        status = "✅ Fresh"
                    elif days_old == 1:
                        status = "⚠️  1 day old"
                    else:
                        status = f"❌ {days_old} days old"
                    
                    click.echo(f"  {description:<20} {latest_date} {status}")
                else:
                    click.echo(f"  {description:<20} No data found ❌")
            
            # Check cache health
            click.echo(f"\n💾 Cache Status:")
            cache_keys = [
                'dashboard_global_market_summary',
                'dashboard_top_collections', 
                'dashboard_recent_whale_alerts'
            ]
            
            for cache_key in cache_keys:
                try:
                    cached_data = await cache_manager.get(cache_key)
                    if cached_data:
                        click.echo(f"  {cache_key:<35} ✅ Cached")
                    else:
                        click.echo(f"  {cache_key:<35} ❌ Empty")
                except Exception as e:
                    click.echo(f"  {cache_key:<35} ❌ Error: {e}")
            
            # Check collection coverage
            click.echo(f"\n📈 Collection Coverage:")
            
            total_collections = await dashboard_service.get_total_collections_count()
            active_collections = len(await dashboard_service.get_active_collection_ids())
            
            click.echo(f"  Total collections: {total_collections:,}")
            click.echo(f"  Active collections: {active_collections:,}")
            
            if total_collections > 0:
                coverage_pct = (active_collections / total_collections) * 100
                click.echo(f"  Active coverage: {coverage_pct:.1f}%")
            
            # Check recent activity levels
            click.echo(f"\n📊 Activity Levels (24h):")
            
            activity_query = f"""
            SELECT 
                COUNT(*) as total_transactions,
                COUNT(DISTINCT collection_id) as active_collections,
                COUNT(DISTINCT COALESCE(from_address, to_address)) as active_wallets,
                SUM(price_sol) as total_volume
            FROM `{config.project_id}.{config.dataset_id}.transactions`
            WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
              AND event_type = 'sale'
            """
            
            activity_job = client.query(activity_query)
            activity_results = list(activity_job)
            
            if activity_results:
                row = activity_results[0]
                click.echo(f"  Transactions: {row.total_transactions:,}")
                click.echo(f"  Active collections: {row.active_collections:,}")
                click.echo(f"  Active wallets: {row.active_wallets:,}")
                click.echo(f"  Volume: {row.total_volume:.1f} SOL" if row.total_volume else "  Volume: 0 SOL")
            
            click.echo(f"\n✅ Health check completed")
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            click.echo(f"Error: {e}")
    
    asyncio.run(_health_check())


@dashboard.command()
@click.option('--pattern', help='Clear cache keys matching pattern')
@click.option('--all', 'clear_all', is_flag=True, help='Clear all dashboard cache')
@click.pass_context
def clear_cache(ctx, pattern: Optional[str], clear_all: bool):
    """Clear dashboard cache."""
    config = ctx.obj['config']
    
    async def _clear_cache():
        try:
            cache_manager = CacheManager()
            
            if clear_all:
                click.echo("Clearing all dashboard cache...")
                cleared_count = await cache_manager.clear_pattern("dashboard_*")
                click.echo(f"✓ Cleared {cleared_count} cache entries")
            elif pattern:
                click.echo(f"Clearing cache matching pattern: {pattern}")
                cleared_count = await cache_manager.clear_pattern(pattern)
                click.echo(f"✓ Cleared {cleared_count} cache entries")
            else:
                click.echo("Specify --pattern or --all to clear cache")
            
        except Exception as e:
            logger.error(f"Cache clearing failed: {e}")
            click.echo(f"Error: {e}")
    
    asyncio.run(_clear_cache())


if __name__ == '__main__':
    dashboard()