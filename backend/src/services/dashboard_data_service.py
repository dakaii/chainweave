"""Dashboard data service for ChainWeave.

Provides optimized data aggregation and preparation for dashboard views:
- Real-time market summaries
- Collection performance metrics
- Whale activity feeds
- Historical trend analysis
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, date
from google.cloud import bigquery
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class DashboardDataService:
    """Optimized data service for dashboard consumption."""
    
    def __init__(self, project_id: str, dataset_id: str):
        """Initialize dashboard data service."""
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.client = bigquery.Client(project=project_id)
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def get_global_market_summary(self) -> Dict[str, Any]:
        """Get global market overview with key metrics."""
        
        try:
            query = f"""
            WITH recent_activity AS (
                SELECT 
                    COUNT(*) as total_transactions_24h,
                    COUNT(DISTINCT collection_id) as active_collections_24h,
                    COUNT(DISTINCT COALESCE(from_address, to_address)) as unique_wallets_24h,
                    SUM(price_sol) as total_volume_24h,
                    AVG(price_sol) as avg_transaction_size
                FROM `{self.project_id}.{self.dataset_id}.transactions`
                WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
                  AND event_type = 'sale'
                  AND price_sol > 0
            ),
            collection_stats AS (
                SELECT COUNT(*) as total_collections
                FROM `{self.project_id}.{self.dataset_id}.nft_collections`
                WHERE status = 'active'
                  AND partition_date = CURRENT_DATE()
            ),
            whale_activity AS (
                SELECT 
                    COUNT(*) as whale_alerts_24h,
                    AVG(market_impact_score) as avg_whale_impact
                FROM `{self.project_id}.{self.dataset_id}.whale_alerts`
                WHERE triggered_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
                  AND severity IN ('high', 'critical')
            ),
            volume_comparison AS (
                SELECT 
                    SUM(CASE WHEN DATE(timestamp) = CURRENT_DATE() THEN price_sol ELSE 0 END) as today_volume,
                    SUM(CASE WHEN DATE(timestamp) = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY) THEN price_sol ELSE 0 END) as yesterday_volume
                FROM `{self.project_id}.{self.dataset_id}.transactions`
                WHERE DATE(timestamp) IN (CURRENT_DATE(), DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY))
                  AND event_type = 'sale'
                  AND price_sol > 0
            )
            SELECT 
                ra.*,
                cs.total_collections,
                wa.whale_alerts_24h,
                wa.avg_whale_impact,
                vc.today_volume,
                vc.yesterday_volume,
                CASE 
                    WHEN vc.yesterday_volume > 0 THEN 
                        ((vc.today_volume - vc.yesterday_volume) / vc.yesterday_volume) * 100
                    ELSE NULL 
                END as volume_change_24h_pct
            FROM recent_activity ra
            CROSS JOIN collection_stats cs
            CROSS JOIN whale_activity wa
            CROSS JOIN volume_comparison vc
            """
            
            loop = asyncio.get_event_loop()
            query_job = await loop.run_in_executor(self.executor, self.client.query, query)
            results = list(query_job)
            
            if not results:
                return {}
            
            row = results[0]
            
            # Determine market trend
            volume_change = row.volume_change_24h_pct or 0
            whale_impact = row.avg_whale_impact or 0
            
            if volume_change > 20 and whale_impact < 0.5:
                market_trend = "bullish"
            elif volume_change < -20 or whale_impact > 0.8:
                market_trend = "bearish"
            else:
                market_trend = "neutral"
            
            return {
                'timestamp': datetime.now().isoformat(),
                'total_collections': row.total_collections or 0,
                'total_volume_24h': float(row.total_volume_24h) if row.total_volume_24h else 0.0,
                'volume_change_24h_pct': float(volume_change),
                'total_transactions_24h': row.total_transactions_24h or 0,
                'unique_wallets_24h': row.unique_wallets_24h or 0,
                'avg_transaction_size': float(row.avg_transaction_size) if row.avg_transaction_size else 0.0,
                'whale_alerts_24h': row.whale_alerts_24h or 0,
                'whale_activity_score': float(whale_impact),
                'market_trend': market_trend,
                'active_collections_24h': row.active_collections_24h or 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get global market summary: {e}")
            return {}
    
    async def get_top_collections_by_volume(
        self, days: int = 1, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get top collections ranked by trading volume."""
        
        try:
            query = f"""
            WITH collection_volume AS (
                SELECT 
                    t.collection_id,
                    c.name,
                    c.floor_price,
                    COUNT(*) as transaction_count,
                    SUM(t.price_sol) as volume,
                    AVG(t.price_sol) as avg_price,
                    COUNT(DISTINCT COALESCE(t.from_address, t.to_address)) as unique_traders,
                    MAX(t.timestamp) as last_transaction
                FROM `{self.project_id}.{self.dataset_id}.transactions` t
                JOIN `{self.project_id}.{self.dataset_id}.nft_collections` c
                  ON t.collection_id = c.collection_id
                WHERE DATE(t.timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
                  AND t.event_type = 'sale'
                  AND t.price_sol > 0
                  AND c.partition_date = CURRENT_DATE()
                GROUP BY t.collection_id, c.name, c.floor_price
            ),
            volume_comparison AS (
                SELECT 
                    cv.*,
                    LAG(cv.volume) OVER (PARTITION BY cv.collection_id ORDER BY CURRENT_DATE()) as previous_volume
                FROM collection_volume cv
            )
            SELECT 
                collection_id,
                name,
                floor_price,
                transaction_count,
                volume,
                avg_price,
                unique_traders,
                last_transaction,
                CASE 
                    WHEN previous_volume > 0 THEN 
                        ((volume - previous_volume) / previous_volume) * 100
                    ELSE NULL 
                END as volume_change_pct
            FROM volume_comparison
            ORDER BY volume DESC
            LIMIT @limit
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("days", "INT64", days),
                    bigquery.ScalarQueryParameter("limit", "INT64", limit)
                ]
            )
            
            loop = asyncio.get_event_loop()
            query_job = await loop.run_in_executor(
                self.executor, self.client.query, query, job_config
            )
            
            results = []
            for row in query_job:
                results.append({
                    'collection_id': row.collection_id,
                    'name': row.name,
                    'floor_price': float(row.floor_price) if row.floor_price else 0.0,
                    'volume': float(row.volume),
                    'transaction_count': row.transaction_count,
                    'avg_price': float(row.avg_price),
                    'unique_traders': row.unique_traders,
                    'volume_change_pct': float(row.volume_change_pct) if row.volume_change_pct else 0.0,
                    'last_transaction': row.last_transaction.isoformat() if row.last_transaction else None
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get top collections: {e}")
            return []
    
    async def get_recent_whale_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent whale activity alerts."""
        
        try:
            query = f"""
            SELECT 
                wa.alert_id,
                wa.wallet_address,
                wa.alert_type,
                wa.collection_id,
                wa.amount_sol,
                wa.severity,
                wa.triggered_at,
                wa.details,
                c.name as collection_name
            FROM `{self.project_id}.{self.dataset_id}.whale_alerts` wa
            LEFT JOIN `{self.project_id}.{self.dataset_id}.nft_collections` c
              ON wa.collection_id = c.collection_id
              AND c.partition_date = CURRENT_DATE()
            WHERE wa.triggered_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
              AND wa.resolved = false
            ORDER BY wa.triggered_at DESC
            LIMIT @limit
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("limit", "INT64", limit)
                ]
            )
            
            loop = asyncio.get_event_loop()
            query_job = await loop.run_in_executor(
                self.executor, self.client.query, query, job_config
            )
            
            results = []
            for row in query_job:
                # Parse details JSON if it exists
                details = {}
                if row.details:
                    try:
                        import json
                        details = json.loads(row.details)
                    except json.JSONDecodeError:
                        details = {}
                
                results.append({
                    'alert_id': row.alert_id,
                    'wallet_address': row.wallet_address,
                    'alert_type': row.alert_type,
                    'collection_id': row.collection_id,
                    'collection_name': row.collection_name or 'Unknown',
                    'amount_sol': float(row.amount_sol) if row.amount_sol else 0.0,
                    'severity': row.severity,
                    'triggered_at': row.triggered_at.isoformat(),
                    'details': details
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get whale alerts: {e}")
            return []
    
    async def get_collection_summary(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive summary for a specific collection."""
        
        try:
            query = f"""
            WITH collection_base AS (
                SELECT 
                    collection_id,
                    name,
                    total_supply,
                    floor_price,
                    market_cap,
                    volume_24h,
                    holders_count,
                    listed_count,
                    verified,
                    image_url,
                    description
                FROM `{self.project_id}.{self.dataset_id}.nft_collections`
                WHERE collection_id = @collection_id
                  AND partition_date = CURRENT_DATE()
            ),
            recent_activity AS (
                SELECT 
                    COUNT(*) as transactions_24h,
                    SUM(price_sol) as volume_24h_actual,
                    COUNT(DISTINCT COALESCE(from_address, to_address)) as unique_traders_24h,
                    AVG(price_sol) as avg_price_24h,
                    MIN(price_sol) as min_price_24h,
                    MAX(price_sol) as max_price_24h
                FROM `{self.project_id}.{self.dataset_id}.transactions`
                WHERE collection_id = @collection_id
                  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
                  AND event_type = 'sale'
                  AND price_sol > 0
            ),
            price_change AS (
                SELECT 
                    AVG(CASE WHEN DATE(timestamp) = CURRENT_DATE() THEN price_sol END) as today_avg,
                    AVG(CASE WHEN DATE(timestamp) = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY) THEN price_sol END) as yesterday_avg
                FROM `{self.project_id}.{self.dataset_id}.transactions`
                WHERE collection_id = @collection_id
                  AND DATE(timestamp) IN (CURRENT_DATE(), DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY))
                  AND event_type = 'sale'
                  AND price_sol > 0
            )
            SELECT 
                cb.*,
                ra.transactions_24h,
                ra.volume_24h_actual,
                ra.unique_traders_24h,
                ra.avg_price_24h,
                ra.min_price_24h,
                ra.max_price_24h,
                pc.today_avg,
                pc.yesterday_avg,
                CASE 
                    WHEN pc.yesterday_avg > 0 THEN 
                        ((pc.today_avg - pc.yesterday_avg) / pc.yesterday_avg) * 100
                    ELSE NULL 
                END as price_change_24h_pct
            FROM collection_base cb
            CROSS JOIN recent_activity ra
            CROSS JOIN price_change pc
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id)
                ]
            )
            
            loop = asyncio.get_event_loop()
            query_job = await loop.run_in_executor(
                self.executor, self.client.query, query, job_config
            )
            results = list(query_job)
            
            if not results:
                return None
            
            row = results[0]
            
            return {
                'collection_id': row.collection_id,
                'name': row.name,
                'total_supply': row.total_supply,
                'floor_price': float(row.floor_price) if row.floor_price else 0.0,
                'market_cap': float(row.market_cap) if row.market_cap else 0.0,
                'volume_24h': float(row.volume_24h_actual) if row.volume_24h_actual else 0.0,
                'transactions_24h': row.transactions_24h or 0,
                'holders_count': row.holders_count or 0,
                'listed_count': row.listed_count or 0,
                'unique_traders_24h': row.unique_traders_24h or 0,
                'verified': row.verified,
                'image_url': row.image_url,
                'description': row.description,
                'price_stats_24h': {
                    'avg': float(row.avg_price_24h) if row.avg_price_24h else 0.0,
                    'min': float(row.min_price_24h) if row.min_price_24h else 0.0,
                    'max': float(row.max_price_24h) if row.max_price_24h else 0.0,
                    'change_pct': float(row.price_change_24h_pct) if row.price_change_24h_pct else 0.0
                },
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection summary for {collection_id}: {e}")
            return None
    
    async def get_recent_transactions(
        self, collection_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get recent transactions for a collection."""
        
        try:
            query = f"""
            SELECT 
                t.transaction_signature,
                t.mint_address,
                t.event_type,
                t.from_address,
                t.to_address,
                t.price_sol,
                t.marketplace,
                t.timestamp,
                n.name as nft_name,
                n.image_url
            FROM `{self.project_id}.{self.dataset_id}.transactions` t
            LEFT JOIN `{self.project_id}.{self.dataset_id}.nft_metadata` n
              ON t.mint_address = n.mint_address
              AND n.partition_date = CURRENT_DATE()
            WHERE t.collection_id = @collection_id
              AND t.timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
            ORDER BY t.timestamp DESC
            LIMIT @limit
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
                    bigquery.ScalarQueryParameter("limit", "INT64", limit)
                ]
            )
            
            loop = asyncio.get_event_loop()
            query_job = await loop.run_in_executor(
                self.executor, self.client.query, query, job_config
            )
            
            results = []
            for row in query_job:
                results.append({
                    'transaction_signature': row.transaction_signature,
                    'mint_address': row.mint_address,
                    'nft_name': row.nft_name or 'Unknown',
                    'event_type': row.event_type,
                    'from_address': row.from_address,
                    'to_address': row.to_address,
                    'price_sol': float(row.price_sol) if row.price_sol else 0.0,
                    'marketplace': row.marketplace,
                    'timestamp': row.timestamp.isoformat(),
                    'image_url': row.image_url
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get recent transactions: {e}")
            return []
    
    async def get_top_holders(
        self, collection_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get top holders for a collection."""
        
        try:
            query = f"""
            WITH holder_stats AS (
                SELECT 
                    current_owner as wallet_address,
                    COUNT(*) as nft_count,
                    AVG(estimated_value) as avg_nft_value,
                    SUM(estimated_value) as total_estimated_value
                FROM `{self.project_id}.{self.dataset_id}.nft_metadata`
                WHERE collection_id = @collection_id
                  AND partition_date = CURRENT_DATE()
                  AND current_owner IS NOT NULL
                GROUP BY current_owner
            ),
            holder_profiles AS (
                SELECT 
                    hs.*,
                    wp.whale_status,
                    wp.trading_behavior,
                    wp.total_volume_traded,
                    wp.last_activity
                FROM holder_stats hs
                LEFT JOIN `{self.project_id}.{self.dataset_id}.wallet_profiles` wp
                  ON hs.wallet_address = wp.wallet_address
                  AND wp.partition_date = CURRENT_DATE()
            )
            SELECT *
            FROM holder_profiles
            ORDER BY nft_count DESC
            LIMIT @limit
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
                    bigquery.ScalarQueryParameter("limit", "INT64", limit)
                ]
            )
            
            loop = asyncio.get_event_loop()
            query_job = await loop.run_in_executor(
                self.executor, self.client.query, query, job_config
            )
            
            results = []
            for row in query_job:
                results.append({
                    'wallet_address': row.wallet_address,
                    'nft_count': row.nft_count,
                    'avg_nft_value': float(row.avg_nft_value) if row.avg_nft_value else 0.0,
                    'total_estimated_value': float(row.total_estimated_value) if row.total_estimated_value else 0.0,
                    'whale_status': row.whale_status,
                    'trading_behavior': row.trading_behavior,
                    'total_volume_traded': float(row.total_volume_traded) if row.total_volume_traded else 0.0,
                    'last_activity': row.last_activity.isoformat() if row.last_activity else None
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get top holders: {e}")
            return []
    
    async def get_price_history(
        self, collection_id: str, days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get price history for a collection."""
        
        try:
            query = f"""
            SELECT 
                date,
                AVG(CASE WHEN metric_type = 'floor_price' THEN metric_value END) as floor_price,
                AVG(CASE WHEN metric_type = 'avg_price' THEN metric_value END) as avg_price,
                SUM(CASE WHEN metric_type = 'daily_volume' THEN metric_value END) as volume,
                SUM(CASE WHEN metric_type = 'total_sales' THEN metric_value END) as sales_count
            FROM `{self.project_id}.{self.dataset_id}.market_analytics`
            WHERE collection_id = @collection_id
              AND date >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
              AND metric_type IN ('floor_price', 'avg_price', 'daily_volume', 'total_sales')
            GROUP BY date
            ORDER BY date DESC
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
                    bigquery.ScalarQueryParameter("days", "INT64", days)
                ]
            )
            
            loop = asyncio.get_event_loop()
            query_job = await loop.run_in_executor(
                self.executor, self.client.query, query, job_config
            )
            
            results = []
            for row in query_job:
                results.append({
                    'date': row.date.isoformat(),
                    'floor_price': float(row.floor_price) if row.floor_price else 0.0,
                    'avg_price': float(row.avg_price) if row.avg_price else 0.0,
                    'volume': float(row.volume) if row.volume else 0.0,
                    'sales_count': int(row.sales_count) if row.sales_count else 0
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get price history: {e}")
            return []
    
    async def get_market_trends(self, days: int = 7) -> Dict[str, Any]:
        """Get overall market trends and sentiment."""
        
        try:
            # This would analyze various trend indicators
            # For now, return basic trend data
            
            query = f"""
            WITH daily_metrics AS (
                SELECT 
                    date,
                    SUM(CASE WHEN metric_type = 'daily_volume' THEN metric_value END) as total_volume,
                    COUNT(DISTINCT collection_id) as active_collections,
                    AVG(CASE WHEN metric_type = 'avg_price' THEN metric_value END) as market_avg_price
                FROM `{self.project_id}.{self.dataset_id}.market_analytics`
                WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
                  AND metric_type IN ('daily_volume', 'avg_price')
                GROUP BY date
                ORDER BY date
            )
            SELECT 
                date,
                total_volume,
                active_collections,
                market_avg_price,
                LAG(total_volume) OVER (ORDER BY date) as prev_volume,
                LAG(market_avg_price) OVER (ORDER BY date) as prev_avg_price
            FROM daily_metrics
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("days", "INT64", days)
                ]
            )
            
            loop = asyncio.get_event_loop()
            query_job = await loop.run_in_executor(
                self.executor, self.client.query, query, job_config
            )
            
            daily_data = []
            for row in query_job:
                volume_change = 0.0
                price_change = 0.0
                
                if row.prev_volume and row.prev_volume > 0:
                    volume_change = ((row.total_volume - row.prev_volume) / row.prev_volume) * 100
                
                if row.prev_avg_price and row.prev_avg_price > 0:
                    price_change = ((row.market_avg_price - row.prev_avg_price) / row.prev_avg_price) * 100
                
                daily_data.append({
                    'date': row.date.isoformat(),
                    'total_volume': float(row.total_volume) if row.total_volume else 0.0,
                    'active_collections': row.active_collections,
                    'market_avg_price': float(row.market_avg_price) if row.market_avg_price else 0.0,
                    'volume_change_pct': volume_change,
                    'price_change_pct': price_change
                })
            
            # Calculate overall trends
            if len(daily_data) >= 2:
                recent_volume_trend = sum(d['volume_change_pct'] for d in daily_data[-3:]) / min(3, len(daily_data))
                recent_price_trend = sum(d['price_change_pct'] for d in daily_data[-3:]) / min(3, len(daily_data))
            else:
                recent_volume_trend = 0.0
                recent_price_trend = 0.0
            
            return {
                'period_days': days,
                'daily_data': daily_data,
                'summary': {
                    'volume_trend': 'increasing' if recent_volume_trend > 5 else 'decreasing' if recent_volume_trend < -5 else 'stable',
                    'price_trend': 'increasing' if recent_price_trend > 5 else 'decreasing' if recent_price_trend < -5 else 'stable',
                    'avg_volume_change_pct': recent_volume_trend,
                    'avg_price_change_pct': recent_price_trend
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get market trends: {e}")
            return {}
    
    # Helper methods
    async def get_active_collection_ids(self) -> List[str]:
        """Get list of active collection IDs."""
        
        try:
            query = f"""
            SELECT collection_id
            FROM `{self.project_id}.{self.dataset_id}.nft_collections`
            WHERE status = 'active'
              AND partition_date = CURRENT_DATE()
            ORDER BY volume_24h DESC NULLS LAST
            """
            
            loop = asyncio.get_event_loop()
            query_job = await loop.run_in_executor(self.executor, self.client.query, query)
            
            return [row.collection_id for row in query_job]
            
        except Exception as e:
            logger.error(f"Failed to get active collection IDs: {e}")
            return []
    
    async def get_total_collections_count(self) -> int:
        """Get total number of collections."""
        
        try:
            query = f"""
            SELECT COUNT(*) as total
            FROM `{self.project_id}.{self.dataset_id}.nft_collections`
            WHERE partition_date = CURRENT_DATE()
            """
            
            loop = asyncio.get_event_loop()
            query_job = await loop.run_in_executor(self.executor, self.client.query, query)
            results = list(query_job)
            
            return results[0].total if results else 0
            
        except Exception as e:
            logger.error(f"Failed to get total collections count: {e}")
            return 0
    
    async def get_biggest_movers(
        self, days: int = 7, min_volume: float = 10.0
    ) -> List[Dict[str, Any]]:
        """Get collections with biggest volume changes."""
        
        try:
            query = f"""
            WITH current_volume AS (
                SELECT 
                    collection_id,
                    SUM(price_sol) as current_volume
                FROM `{self.project_id}.{self.dataset_id}.transactions`
                WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
                  AND event_type = 'sale'
                  AND price_sol > 0
                GROUP BY collection_id
            ),
            previous_volume AS (
                SELECT 
                    collection_id,
                    SUM(price_sol) as previous_volume
                FROM `{self.project_id}.{self.dataset_id}.transactions`
                WHERE DATE(timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days * 2 DAY)
                  AND DATE(timestamp) < DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
                  AND event_type = 'sale'
                  AND price_sol > 0
                GROUP BY collection_id
            )
            SELECT 
                cv.collection_id,
                c.name,
                cv.current_volume,
                pv.previous_volume,
                CASE 
                    WHEN pv.previous_volume > 0 THEN 
                        ((cv.current_volume - pv.previous_volume) / pv.previous_volume) * 100
                    ELSE NULL 
                END as volume_change_pct
            FROM current_volume cv
            LEFT JOIN previous_volume pv ON cv.collection_id = pv.collection_id
            LEFT JOIN `{self.project_id}.{self.dataset_id}.nft_collections` c
              ON cv.collection_id = c.collection_id
              AND c.partition_date = CURRENT_DATE()
            WHERE cv.current_volume >= @min_volume
            ORDER BY volume_change_pct DESC NULLS LAST
            LIMIT 20
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("days", "INT64", days),
                    bigquery.ScalarQueryParameter("min_volume", "FLOAT64", min_volume)
                ]
            )
            
            loop = asyncio.get_event_loop()
            query_job = await loop.run_in_executor(
                self.executor, self.client.query, query, job_config
            )
            
            results = []
            for row in query_job:
                results.append({
                    'collection_id': row.collection_id,
                    'name': row.name or 'Unknown',
                    'current_volume': float(row.current_volume),
                    'previous_volume': float(row.previous_volume) if row.previous_volume else 0.0,
                    'volume_change_pct': float(row.volume_change_pct) if row.volume_change_pct else 0.0
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get biggest movers: {e}")
            return []
    
    async def get_collection_whale_alerts(
        self, collection_id: str, days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get whale alerts for a specific collection."""
        
        try:
            query = f"""
            SELECT 
                alert_id,
                wallet_address,
                alert_type,
                amount_sol,
                severity,
                triggered_at,
                details
            FROM `{self.project_id}.{self.dataset_id}.whale_alerts`
            WHERE collection_id = @collection_id
              AND triggered_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
            ORDER BY triggered_at DESC
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
                    bigquery.ScalarQueryParameter("days", "INT64", days)
                ]
            )
            
            loop = asyncio.get_event_loop()
            query_job = await loop.run_in_executor(
                self.executor, self.client.query, query, job_config
            )
            
            results = []
            for row in query_job:
                results.append({
                    'alert_id': row.alert_id,
                    'wallet_address': row.wallet_address,
                    'alert_type': row.alert_type,
                    'amount_sol': float(row.amount_sol) if row.amount_sol else 0.0,
                    'severity': row.severity,
                    'triggered_at': row.triggered_at.isoformat()
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get collection whale alerts: {e}")
            return []
    
    async def get_historical_metrics(
        self, collection_id: str, days: int = 90
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get historical metrics for advanced analytics."""
        
        try:
            query = f"""
            SELECT 
                date,
                metric_type,
                metric_value,
                change_percentage,
                confidence_score
            FROM `{self.project_id}.{self.dataset_id}.market_analytics`
            WHERE collection_id = @collection_id
              AND date >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
            ORDER BY date DESC, metric_type
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
                    bigquery.ScalarQueryParameter("days", "INT64", days)
                ]
            )
            
            loop = asyncio.get_event_loop()
            query_job = await loop.run_in_executor(
                self.executor, self.client.query, query, job_config
            )
            
            # Group by metric type
            metrics_by_type = {}
            for row in query_job:
                metric_type = row.metric_type
                if metric_type not in metrics_by_type:
                    metrics_by_type[metric_type] = []
                
                metrics_by_type[metric_type].append({
                    'date': row.date.isoformat(),
                    'value': float(row.metric_value),
                    'change_pct': float(row.change_percentage) if row.change_percentage else 0.0,
                    'confidence': float(row.confidence_score) if row.confidence_score else 0.0
                })
            
            return metrics_by_type
            
        except Exception as e:
            logger.error(f"Failed to get historical metrics: {e}")
            return {}