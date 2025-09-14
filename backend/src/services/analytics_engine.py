"""Analytics engine for ChainWeave.

Core analytics processing engine that handles:
- Market metrics calculation
- Collection performance analysis
- Wallet behavior analysis
- Data aggregation and time series
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, date
from google.cloud import bigquery
import statistics
from concurrent.futures import ThreadPoolExecutor

from models.market_analytics import MarketAnalytics, MetricType, TimeGranularity
from models.wallet_profile import WalletProfile, WalletTier, TradingBehavior
from models.nft_collection import NFTCollection

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """Core analytics processing engine for market metrics and analysis."""
    
    def __init__(self, project_id: str, dataset_id: str):
        """Initialize analytics engine."""
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.client = bigquery.Client(project=project_id)
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def calculate_collection_metrics(
        self,
        collection_id: str,
        target_date: date,
        metric_types: List[MetricType],
        granularity: TimeGranularity = TimeGranularity.DAILY
    ) -> List[MarketAnalytics]:
        """Calculate specified metrics for a collection on target date."""
        results = []
        
        try:
            # Get previous day's data for comparison
            previous_date = target_date - timedelta(days=1)
            
            for metric_type in metric_types:
                try:
                    metric = await self._calculate_single_metric(
                        collection_id=collection_id,
                        metric_type=metric_type,
                        target_date=target_date,
                        previous_date=previous_date,
                        granularity=granularity
                    )
                    
                    if metric:
                        results.append(metric)
                        
                except Exception as e:
                    logger.error(f"Failed to calculate {metric_type.value} for {collection_id}: {e}")
            
        except Exception as e:
            logger.error(f"Failed to calculate metrics for {collection_id}: {e}")
        
        return results
    
    async def _calculate_single_metric(
        self,
        collection_id: str,
        metric_type: MetricType,
        target_date: date,
        previous_date: date,
        granularity: TimeGranularity
    ) -> Optional[MarketAnalytics]:
        """Calculate a single metric for a collection."""
        
        # Metric-specific calculation logic
        if metric_type == MetricType.DAILY_VOLUME:
            return await self._calculate_daily_volume(collection_id, target_date, previous_date)
        elif metric_type == MetricType.UNIQUE_TRADERS:
            return await self._calculate_unique_traders(collection_id, target_date, previous_date)
        elif metric_type == MetricType.AVG_PRICE:
            return await self._calculate_avg_price(collection_id, target_date, previous_date)
        elif metric_type == MetricType.FLOOR_PRICE:
            return await self._calculate_floor_price(collection_id, target_date, previous_date)
        elif metric_type == MetricType.TOTAL_SALES:
            return await self._calculate_total_sales(collection_id, target_date, previous_date)
        elif metric_type == MetricType.HOLDERS_COUNT:
            return await self._calculate_holders_count(collection_id, target_date, previous_date)
        elif metric_type == MetricType.VOLUME_CHANGE_PCT:
            return await self._calculate_volume_change(collection_id, target_date, previous_date)
        elif metric_type == MetricType.PRICE_VOLATILITY:
            return await self._calculate_price_volatility(collection_id, target_date, previous_date)
        elif metric_type == MetricType.LIQUIDITY_SCORE:
            return await self._calculate_liquidity_score(collection_id, target_date, previous_date)
        elif metric_type == MetricType.WHALE_ACTIVITY:
            return await self._calculate_whale_activity(collection_id, target_date, previous_date)
        else:
            logger.warning(f"Unknown metric type: {metric_type}")
            return None
    
    async def _calculate_daily_volume(
        self, collection_id: str, target_date: date, previous_date: date
    ) -> Optional[MarketAnalytics]:
        """Calculate daily trading volume."""
        
        query = f"""
        WITH daily_volume AS (
            SELECT 
                DATE(timestamp) as date,
                SUM(price_sol) as volume
            FROM `{self.project_id}.{self.dataset_id}.transactions`
            WHERE collection_id = @collection_id
              AND event_type = 'sale'
              AND DATE(timestamp) IN (@target_date, @previous_date)
            GROUP BY DATE(timestamp)
        )
        SELECT 
            MAX(CASE WHEN date = @target_date THEN volume END) as current_volume,
            MAX(CASE WHEN date = @previous_date THEN volume END) as previous_volume,
            COUNT(CASE WHEN date = @target_date THEN 1 END) as sample_size
        FROM daily_volume
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
                bigquery.ScalarQueryParameter("target_date", "DATE", target_date),
                bigquery.ScalarQueryParameter("previous_date", "DATE", previous_date)
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        results = list(query_job)
        
        if not results:
            return None
        
        row = results[0]
        current_volume = float(row.current_volume) if row.current_volume else 0.0
        previous_volume = float(row.previous_volume) if row.previous_volume else 0.0
        
        # Calculate percentage change
        change_pct = None
        if previous_volume > 0:
            change_pct = ((current_volume - previous_volume) / previous_volume) * 100
        
        return MarketAnalytics(
            metric_id=f"{collection_id}_{target_date}_{MetricType.DAILY_VOLUME.value}",
            collection_id=collection_id,
            date=target_date,
            metric_type=MetricType.DAILY_VOLUME,
            metric_value=current_volume,
            created_at=datetime.now(),
            granularity=TimeGranularity.DAILY,
            previous_value=previous_volume if previous_volume > 0 else None,
            change_percentage=change_pct,
            sample_size=row.sample_size,
            confidence_score=1.0 if current_volume > 0 else 0.5,
            calculation_method="sum_aggregation"
        )
    
    async def _calculate_unique_traders(
        self, collection_id: str, target_date: date, previous_date: date
    ) -> Optional[MarketAnalytics]:
        """Calculate unique traders count."""
        
        query = f"""
        WITH daily_traders AS (
            SELECT 
                DATE(timestamp) as date,
                COUNT(DISTINCT from_address) + COUNT(DISTINCT to_address) as traders
            FROM `{self.project_id}.{self.dataset_id}.transactions`
            WHERE collection_id = @collection_id
              AND event_type = 'sale'
              AND DATE(timestamp) IN (@target_date, @previous_date)
            GROUP BY DATE(timestamp)
        )
        SELECT 
            MAX(CASE WHEN date = @target_date THEN traders END) as current_traders,
            MAX(CASE WHEN date = @previous_date THEN traders END) as previous_traders
        FROM daily_traders
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
                bigquery.ScalarQueryParameter("target_date", "DATE", target_date),
                bigquery.ScalarQueryParameter("previous_date", "DATE", previous_date)
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        results = list(query_job)
        
        if not results:
            return None
        
        row = results[0]
        current_traders = int(row.current_traders) if row.current_traders else 0
        previous_traders = int(row.previous_traders) if row.previous_traders else 0
        
        change_pct = None
        if previous_traders > 0:
            change_pct = ((current_traders - previous_traders) / previous_traders) * 100
        
        return MarketAnalytics(
            metric_id=f"{collection_id}_{target_date}_{MetricType.UNIQUE_TRADERS.value}",
            collection_id=collection_id,
            date=target_date,
            metric_type=MetricType.UNIQUE_TRADERS,
            metric_value=float(current_traders),
            created_at=datetime.now(),
            granularity=TimeGranularity.DAILY,
            previous_value=float(previous_traders) if previous_traders > 0 else None,
            change_percentage=change_pct,
            confidence_score=1.0 if current_traders > 0 else 0.5,
            calculation_method="count_distinct"
        )
    
    async def _calculate_avg_price(
        self, collection_id: str, target_date: date, previous_date: date
    ) -> Optional[MarketAnalytics]:
        """Calculate average sale price."""
        
        query = f"""
        WITH daily_prices AS (
            SELECT 
                DATE(timestamp) as date,
                AVG(price_sol) as avg_price,
                COUNT(*) as sample_size
            FROM `{self.project_id}.{self.dataset_id}.transactions`
            WHERE collection_id = @collection_id
              AND event_type = 'sale'
              AND price_sol > 0
              AND DATE(timestamp) IN (@target_date, @previous_date)
            GROUP BY DATE(timestamp)
        )
        SELECT 
            MAX(CASE WHEN date = @target_date THEN avg_price END) as current_avg,
            MAX(CASE WHEN date = @previous_date THEN avg_price END) as previous_avg,
            MAX(CASE WHEN date = @target_date THEN sample_size END) as sample_size
        FROM daily_prices
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
                bigquery.ScalarQueryParameter("target_date", "DATE", target_date),
                bigquery.ScalarQueryParameter("previous_date", "DATE", previous_date)
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        results = list(query_job)
        
        if not results or not results[0].current_avg:
            return None
        
        row = results[0]
        current_avg = float(row.current_avg)
        previous_avg = float(row.previous_avg) if row.previous_avg else 0.0
        
        change_pct = None
        if previous_avg > 0:
            change_pct = ((current_avg - previous_avg) / previous_avg) * 100
        
        return MarketAnalytics(
            metric_id=f"{collection_id}_{target_date}_{MetricType.AVG_PRICE.value}",
            collection_id=collection_id,
            date=target_date,
            metric_type=MetricType.AVG_PRICE,
            metric_value=current_avg,
            created_at=datetime.now(),
            granularity=TimeGranularity.DAILY,
            previous_value=previous_avg if previous_avg > 0 else None,
            change_percentage=change_pct,
            sample_size=row.sample_size,
            confidence_score=min(1.0, (row.sample_size or 0) / 10),  # Higher confidence with more samples
            calculation_method="average"
        )
    
    async def _calculate_floor_price(
        self, collection_id: str, target_date: date, previous_date: date
    ) -> Optional[MarketAnalytics]:
        """Calculate floor price (lowest active listing or recent sale)."""
        
        # Check current listings first
        listing_query = f"""
        SELECT MIN(listing_price) as floor_price
        FROM `{self.project_id}.{self.dataset_id}.nft_metadata`
        WHERE collection_id = @collection_id
          AND is_listed = true
          AND listing_price > 0
          AND partition_date = @target_date
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
                bigquery.ScalarQueryParameter("target_date", "DATE", target_date)
            ]
        )
        
        query_job = self.client.query(listing_query, job_config=job_config)
        listing_results = list(query_job)
        
        floor_price = None
        confidence_score = 0.5
        
        if listing_results and listing_results[0].floor_price:
            floor_price = float(listing_results[0].floor_price)
            confidence_score = 1.0  # High confidence from active listings
        else:
            # Fallback to recent sales minimum
            sales_query = f"""
            SELECT MIN(price_sol) as min_sale_price
            FROM `{self.project_id}.{self.dataset_id}.transactions`
            WHERE collection_id = @collection_id
              AND event_type = 'sale'
              AND price_sol > 0
              AND DATE(timestamp) >= DATE_SUB(@target_date, INTERVAL 7 DAY)
            """
            
            sales_job = self.client.query(sales_query, job_config=job_config)
            sales_results = list(sales_job)
            
            if sales_results and sales_results[0].min_sale_price:
                floor_price = float(sales_results[0].min_sale_price)
                confidence_score = 0.7  # Medium confidence from recent sales
        
        if not floor_price:
            return None
        
        # Get previous floor price for comparison
        prev_query = f"""
        SELECT metric_value
        FROM `{self.project_id}.{self.dataset_id}.market_analytics`
        WHERE collection_id = @collection_id
          AND metric_type = @metric_type
          AND date = @previous_date
        ORDER BY created_at DESC
        LIMIT 1
        """
        
        prev_job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
                bigquery.ScalarQueryParameter("metric_type", "STRING", MetricType.FLOOR_PRICE.value),
                bigquery.ScalarQueryParameter("previous_date", "DATE", previous_date)
            ]
        )
        
        prev_job = self.client.query(prev_query, job_config=prev_job_config)
        prev_results = list(prev_job)
        
        previous_floor = None
        change_pct = None
        
        if prev_results and prev_results[0].metric_value:
            previous_floor = float(prev_results[0].metric_value)
            change_pct = ((floor_price - previous_floor) / previous_floor) * 100
        
        return MarketAnalytics(
            metric_id=f"{collection_id}_{target_date}_{MetricType.FLOOR_PRICE.value}",
            collection_id=collection_id,
            date=target_date,
            metric_type=MetricType.FLOOR_PRICE,
            metric_value=floor_price,
            created_at=datetime.now(),
            granularity=TimeGranularity.DAILY,
            previous_value=previous_floor,
            change_percentage=change_pct,
            confidence_score=confidence_score,
            calculation_method="minimum_active_listing"
        )
    
    async def calculate_wallet_profile(
        self, wallet_address: str, as_of_date: date
    ) -> Optional[WalletProfile]:
        """Calculate comprehensive wallet profile."""
        
        try:
            # Get wallet transaction history
            query = f"""
            WITH wallet_stats AS (
                SELECT 
                    COUNT(*) as total_transactions,
                    SUM(CASE WHEN from_address = @wallet_address THEN price_sol ELSE 0 END) as total_received,
                    SUM(CASE WHEN to_address = @wallet_address THEN price_sol ELSE 0 END) as total_spent,
                    COUNT(DISTINCT collection_id) as collections_active,
                    MIN(timestamp) as first_activity,
                    MAX(timestamp) as last_activity,
                    COUNT(DISTINCT DATE(timestamp)) as days_active,
                    EXTRACT(HOUR FROM timestamp) as most_active_hour
                FROM `{self.project_id}.{self.dataset_id}.transactions`
                WHERE (from_address = @wallet_address OR to_address = @wallet_address)
                  AND DATE(timestamp) <= @as_of_date
                  AND event_type IN ('sale', 'transfer')
            ),
            current_holdings AS (
                SELECT COUNT(*) as total_nfts_owned
                FROM `{self.project_id}.{self.dataset_id}.nft_metadata`
                WHERE current_owner = @wallet_address
                  AND partition_date = @as_of_date
            ),
            trading_performance AS (
                SELECT 
                    COUNT(CASE WHEN s.price_sol > b.price_sol THEN 1 END) as successful_flips,
                    COUNT(CASE WHEN s.price_sol <= b.price_sol THEN 1 END) as failed_flips,
                    AVG(CASE WHEN to_address = @wallet_address THEN price_sol END) as avg_purchase_price,
                    AVG(CASE WHEN from_address = @wallet_address THEN price_sol END) as avg_sale_price
                FROM `{self.project_id}.{self.dataset_id}.transactions` s
                LEFT JOIN `{self.project_id}.{self.dataset_id}.transactions` b
                  ON s.mint_address = b.mint_address 
                  AND b.to_address = @wallet_address
                  AND b.timestamp < s.timestamp
                WHERE s.from_address = @wallet_address
                  AND s.event_type = 'sale'
                  AND DATE(s.timestamp) <= @as_of_date
            )
            SELECT * FROM wallet_stats CROSS JOIN current_holdings CROSS JOIN trading_performance
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("wallet_address", "STRING", wallet_address),
                    bigquery.ScalarQueryParameter("as_of_date", "DATE", as_of_date)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job)
            
            if not results or results[0].total_transactions == 0:
                return None
            
            row = results[0]
            
            # Calculate derived metrics
            total_volume = (row.total_spent or 0) + (row.total_received or 0)
            profit_loss = (row.total_received or 0) - (row.total_spent or 0)
            
            # Determine wallet tier
            wallet_tier = self._determine_wallet_tier(
                total_volume=total_volume,
                total_nfts=row.total_nfts_owned or 0
            )
            
            # Determine trading behavior
            trading_behavior = self._determine_trading_behavior(
                successful_flips=row.successful_flips or 0,
                failed_flips=row.failed_flips or 0,
                avg_hold_duration=30,  # Would calculate from actual data
                total_transactions=row.total_transactions
            )
            
            # Calculate win rate
            total_flips = (row.successful_flips or 0) + (row.failed_flips or 0)
            win_rate = None
            if total_flips > 0:
                win_rate = (row.successful_flips / total_flips) * 100
            
            return WalletProfile(
                wallet_address=wallet_address,
                total_nfts_owned=row.total_nfts_owned or 0,
                total_volume_traded=total_volume,
                first_activity=row.first_activity,
                last_activity=row.last_activity,
                avg_hold_duration=30,  # Placeholder - would calculate from data
                collections_active=row.collections_active or 0,
                whale_status=wallet_tier == WalletTier.WHALE,
                profit_loss_sol=profit_loss,
                wallet_tier=wallet_tier,
                trading_behavior=trading_behavior,
                total_spent_sol=row.total_spent or 0.0,
                total_received_sol=row.total_received or 0.0,
                total_transactions=row.total_transactions,
                successful_flips=row.successful_flips or 0,
                failed_flips=row.failed_flips or 0,
                avg_purchase_price=row.avg_purchase_price,
                avg_sale_price=row.avg_sale_price,
                win_rate=win_rate,
                days_active=row.days_active,
                avg_transactions_per_day=(row.total_transactions / max(row.days_active, 1)) if row.days_active else None
            )
            
        except Exception as e:
            logger.error(f"Failed to calculate wallet profile for {wallet_address}: {e}")
            return None
    
    def _determine_wallet_tier(self, total_volume: float, total_nfts: int) -> WalletTier:
        """Determine wallet tier based on activity."""
        if total_volume >= 500.0 or total_nfts >= 100:
            return WalletTier.WHALE
        elif total_volume >= 100.0 or total_nfts >= 50:
            return WalletTier.DOLPHIN
        elif total_volume >= 10.0 or total_nfts >= 5:
            return WalletTier.FISH
        else:
            return WalletTier.SHRIMP
    
    def _determine_trading_behavior(
        self, 
        successful_flips: int, 
        failed_flips: int, 
        avg_hold_duration: int,
        total_transactions: int
    ) -> TradingBehavior:
        """Determine primary trading behavior pattern."""
        
        if total_transactions < 5:
            return TradingBehavior.COLLECTOR
        
        total_flips = successful_flips + failed_flips
        flip_ratio = total_flips / total_transactions if total_transactions > 0 else 0
        
        if avg_hold_duration > 90:
            return TradingBehavior.DIAMOND_HANDS
        elif flip_ratio > 0.7 and avg_hold_duration < 7:
            return TradingBehavior.FLIPPER
        elif flip_ratio > 0.3:
            return TradingBehavior.ACTIVE_TRADER
        elif avg_hold_duration < 3:
            return TradingBehavior.PAPER_HANDS
        else:
            return TradingBehavior.COLLECTOR
    
    async def get_active_collections(self) -> List[Dict[str, Any]]:
        """Get list of active collections for processing."""
        
        query = f"""
        SELECT 
            collection_id,
            name,
            status,
            is_whale_tracked
        FROM `{self.project_id}.{self.dataset_id}.nft_collections`
        WHERE status = 'active'
          AND partition_date = (
              SELECT MAX(partition_date) 
              FROM `{self.project_id}.{self.dataset_id}.nft_collections`
          )
        ORDER BY name
        """
        
        query_job = self.client.query(query)
        
        results = []
        for row in query_job:
            results.append({
                "collection_id": row.collection_id,
                "name": row.name,
                "status": row.status,
                "is_whale_tracked": row.is_whale_tracked
            })
        
        return results
    
    async def get_active_wallets(
        self, target_date: date, min_transactions: int = 1
    ) -> List[str]:
        """Get wallets with recent activity."""
        
        query = f"""
        SELECT DISTINCT 
            COALESCE(from_address, to_address) as wallet_address
        FROM `{self.project_id}.{self.dataset_id}.transactions`
        WHERE DATE(timestamp) = @target_date
          AND (from_address IS NOT NULL OR to_address IS NOT NULL)
        GROUP BY COALESCE(from_address, to_address)
        HAVING COUNT(*) >= @min_transactions
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("target_date", "DATE", target_date),
                bigquery.ScalarQueryParameter("min_transactions", "INT64", min_transactions)
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        
        return [row.wallet_address for row in query_job if row.wallet_address]
    
    # Additional calculation methods would go here...
    async def _calculate_total_sales(self, collection_id: str, target_date: date, previous_date: date) -> Optional[MarketAnalytics]:
        """Calculate total number of sales."""
        # Implementation similar to other metrics
        pass
    
    async def _calculate_holders_count(self, collection_id: str, target_date: date, previous_date: date) -> Optional[MarketAnalytics]:
        """Calculate unique holders count."""
        # Implementation for holders count
        pass
    
    async def _calculate_volume_change(self, collection_id: str, target_date: date, previous_date: date) -> Optional[MarketAnalytics]:
        """Calculate volume change percentage."""
        # Implementation for volume change
        pass
    
    async def _calculate_price_volatility(self, collection_id: str, target_date: date, previous_date: date) -> Optional[MarketAnalytics]:
        """Calculate price volatility."""
        # Implementation for volatility calculation
        pass
    
    async def _calculate_liquidity_score(self, collection_id: str, target_date: date, previous_date: date) -> Optional[MarketAnalytics]:
        """Calculate liquidity score."""
        # Implementation for liquidity analysis
        pass
    
    async def _calculate_whale_activity(self, collection_id: str, target_date: date, previous_date: date) -> Optional[MarketAnalytics]:
        """Calculate whale activity score."""
        # Implementation for whale activity analysis
        pass
    
    # Data quality methods
    async def find_missing_transaction_data(self, target_date: date) -> List[str]:
        """Find collections missing transaction data."""
        # Implementation for data quality checks
        return []
    
    async def find_orphaned_nfts(self) -> List[str]:
        """Find NFTs without valid collection references."""
        return []
    
    async def find_inconsistent_profiles(self, target_date: date) -> List[str]:
        """Find wallet profiles with data inconsistencies."""
        return []
    
    async def find_missing_analytics(self, target_date: date) -> List[str]:
        """Find missing analytics records."""
        return []
    
    async def fix_data_quality_issues(self, issues: List[str]) -> int:
        """Attempt to fix data quality issues."""
        return 0