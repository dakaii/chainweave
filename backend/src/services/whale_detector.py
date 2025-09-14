"""Whale detection service for ChainWeave.

Advanced whale detection and alert generation:
- Large volume transactions
- Unusual accumulation patterns
- Market manipulation indicators
- Smart alert filtering and cooldowns
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from google.cloud import bigquery
import uuid

from models.whale_alert import WhaleAlert, AlertType, AlertSeverity
from models.transaction import Transaction

logger = logging.getLogger(__name__)


class WhaleDetector:
    """Detects whale activity and generates intelligent alerts."""
    
    def __init__(self, project_id: str, dataset_id: str):
        """Initialize whale detector."""
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.client = bigquery.Client(project=project_id)
        
        # Configuration thresholds (could be made configurable)
        self.thresholds = {
            'large_purchase_sol': 50.0,
            'large_sale_sol': 50.0,
            'rapid_accumulation_count': 10,
            'rapid_accumulation_hours': 24,
            'whale_volume_sol': 100.0,
            'market_impact_threshold': 0.1,  # 10% price impact
            'bulk_listing_count': 20,
            'flash_loan_detection_minutes': 5
        }
        
        # Cooldown periods to prevent spam
        self.cooldown_periods = {
            AlertType.LARGE_PURCHASE: timedelta(hours=6),
            AlertType.LARGE_SALE: timedelta(hours=6),
            AlertType.RAPID_ACCUMULATION: timedelta(hours=12),
            AlertType.BULK_LISTING: timedelta(hours=8),
            AlertType.WHALE_MOVEMENT: timedelta(hours=4),
            AlertType.UNUSUAL_PATTERN: timedelta(hours=24),
            AlertType.MARKET_MANIPULATION: timedelta(hours=48)
        }
    
    async def scan_recent_activity(self, since: datetime) -> List[WhaleAlert]:
        """Scan all recent transactions for whale activity."""
        
        logger.info(f"Scanning for whale activity since {since}")
        
        alerts = []
        
        try:
            # Get recent high-value transactions
            recent_transactions = await self._get_recent_transactions(since)
            
            logger.info(f"Analyzing {len(recent_transactions)} recent transactions")
            
            # Process transactions in batches for different alert types
            large_transaction_alerts = await self._detect_large_transactions(recent_transactions)
            alerts.extend(large_transaction_alerts)
            
            rapid_accumulation_alerts = await self._detect_rapid_accumulation(since)
            alerts.extend(rapid_accumulation_alerts)
            
            bulk_listing_alerts = await self._detect_bulk_listings(since)
            alerts.extend(bulk_listing_alerts)
            
            unusual_pattern_alerts = await self._detect_unusual_patterns(since)
            alerts.extend(unusual_pattern_alerts)
            
            market_manipulation_alerts = await self._detect_market_manipulation(since)
            alerts.extend(market_manipulation_alerts)
            
            # Filter out alerts that are in cooldown
            filtered_alerts = await self._filter_cooldown_alerts(alerts)
            
            logger.info(f"Generated {len(filtered_alerts)} whale alerts ({len(alerts) - len(filtered_alerts)} filtered by cooldown)")
            
            return filtered_alerts
            
        except Exception as e:
            logger.error(f"Failed to scan whale activity: {e}")
            return []
    
    async def scan_collection_activity(
        self, collection_id: str, since: datetime
    ) -> List[WhaleAlert]:
        """Scan whale activity for a specific collection."""
        
        logger.info(f"Scanning collection {collection_id} for whale activity since {since}")
        
        try:
            # Get collection-specific transactions
            query = f"""
            SELECT *
            FROM `{self.project_id}.{self.dataset_id}.transactions`
            WHERE collection_id = @collection_id
              AND timestamp >= @since
              AND (
                  price_sol >= @large_transaction_threshold
                  OR event_type = 'sale'
              )
            ORDER BY timestamp DESC
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("collection_id", "STRING", collection_id),
                    bigquery.ScalarQueryParameter("since", "TIMESTAMP", since),
                    bigquery.ScalarQueryParameter("large_transaction_threshold", "FLOAT", self.thresholds['large_purchase_sol'])
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            transactions = [dict(row) for row in query_job]
            
            # Apply whale detection algorithms
            alerts = []
            
            large_tx_alerts = await self._detect_large_transactions(transactions)
            alerts.extend(large_tx_alerts)
            
            # Collection-specific patterns
            floor_manipulation_alerts = await self._detect_floor_manipulation(collection_id, since)
            alerts.extend(floor_manipulation_alerts)
            
            wash_trading_alerts = await self._detect_wash_trading(collection_id, since)
            alerts.extend(wash_trading_alerts)
            
            # Filter cooldowns
            filtered_alerts = await self._filter_cooldown_alerts(alerts)
            
            return filtered_alerts
            
        except Exception as e:
            logger.error(f"Failed to scan collection whale activity: {e}")
            return []
    
    async def _get_recent_transactions(self, since: datetime) -> List[Dict[str, Any]]:
        """Get recent high-value transactions."""
        
        query = f"""
        SELECT 
            transaction_signature,
            mint_address,
            event_type,
            from_address,
            to_address,
            price_sol,
            marketplace,
            timestamp,
            collection_id
        FROM `{self.project_id}.{self.dataset_id}.transactions`
        WHERE timestamp >= @since
          AND (
              price_sol >= @min_value_threshold
              OR event_type IN ('sale', 'transfer')
          )
        ORDER BY timestamp DESC
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("since", "TIMESTAMP", since),
                bigquery.ScalarQueryParameter("min_value_threshold", "FLOAT", 10.0)  # Min 10 SOL
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        return [dict(row) for row in query_job]
    
    async def _detect_large_transactions(
        self, transactions: List[Dict[str, Any]]
    ) -> List[WhaleAlert]:
        """Detect individual large purchase/sale transactions."""
        
        alerts = []
        
        for tx in transactions:
            if not tx.get('price_sol'):
                continue
            
            price_sol = float(tx['price_sol'])
            
            # Large purchase detection
            if (tx['event_type'] == 'sale' and 
                tx['to_address'] and 
                price_sol >= self.thresholds['large_purchase_sol']):
                
                alert = WhaleAlert(
                    alert_id=str(uuid.uuid4()),
                    wallet_address=tx['to_address'],
                    alert_type=AlertType.LARGE_PURCHASE,
                    transaction_signature=tx['transaction_signature'],
                    collection_id=tx['collection_id'],
                    mint_address=tx['mint_address'],
                    amount_sol=price_sol,
                    severity=self._calculate_severity_for_amount(price_sol),
                    triggered_at=tx['timestamp'],
                    details={
                        'marketplace': tx['marketplace'],
                        'seller': tx['from_address'],
                        'nft_name': tx.get('mint_address', 'Unknown')[:8] + '...'
                    }
                )
                
                alerts.append(alert)
            
            # Large sale detection
            elif (tx['event_type'] == 'sale' and 
                  tx['from_address'] and 
                  price_sol >= self.thresholds['large_sale_sol']):
                
                alert = WhaleAlert(
                    alert_id=str(uuid.uuid4()),
                    wallet_address=tx['from_address'],
                    alert_type=AlertType.LARGE_SALE,
                    transaction_signature=tx['transaction_signature'],
                    collection_id=tx['collection_id'],
                    mint_address=tx['mint_address'],
                    amount_sol=price_sol,
                    severity=self._calculate_severity_for_amount(price_sol),
                    triggered_at=tx['timestamp'],
                    details={
                        'marketplace': tx['marketplace'],
                        'buyer': tx['to_address'],
                        'nft_name': tx.get('mint_address', 'Unknown')[:8] + '...'
                    }
                )
                
                alerts.append(alert)
        
        return alerts
    
    async def _detect_rapid_accumulation(self, since: datetime) -> List[WhaleAlert]:
        """Detect wallets rapidly accumulating NFTs."""
        
        query = f"""
        WITH recent_acquisitions AS (
            SELECT 
                to_address as wallet,
                collection_id,
                COUNT(*) as nft_count,
                SUM(price_sol) as total_spent,
                MIN(timestamp) as first_acquisition,
                MAX(timestamp) as last_acquisition,
                TIMESTAMP_DIFF(MAX(timestamp), MIN(timestamp), HOUR) as accumulation_hours
            FROM `{self.project_id}.{self.dataset_id}.transactions`
            WHERE timestamp >= @since
              AND event_type = 'sale'
              AND to_address IS NOT NULL
            GROUP BY to_address, collection_id
        )
        SELECT *
        FROM recent_acquisitions
        WHERE nft_count >= @rapid_count_threshold
          AND accumulation_hours <= @rapid_hours_threshold
        ORDER BY nft_count DESC
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("since", "TIMESTAMP", since),
                bigquery.ScalarQueryParameter("rapid_count_threshold", "INT64", self.thresholds['rapid_accumulation_count']),
                bigquery.ScalarQueryParameter("rapid_hours_threshold", "INT64", self.thresholds['rapid_accumulation_hours'])
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        
        alerts = []
        for row in query_job:
            alert = WhaleAlert(
                alert_id=str(uuid.uuid4()),
                wallet_address=row.wallet,
                alert_type=AlertType.RAPID_ACCUMULATION,
                collection_id=row.collection_id,
                amount_sol=float(row.total_spent) if row.total_spent else 0.0,
                severity=self._calculate_severity_for_accumulation(row.nft_count, row.accumulation_hours),
                triggered_at=row.last_acquisition,
                details={
                    'nft_count': row.nft_count,
                    'time_span_hours': row.accumulation_hours,
                    'first_acquisition': row.first_acquisition.isoformat(),
                    'avg_price': (float(row.total_spent) / row.nft_count) if row.total_spent and row.nft_count > 0 else 0.0
                }
            )
            
            alerts.append(alert)
        
        return alerts
    
    async def _detect_bulk_listings(self, since: datetime) -> List[WhaleAlert]:
        """Detect bulk listing activities."""
        
        query = f"""
        WITH bulk_listings AS (
            SELECT 
                current_owner as wallet,
                collection_id,
                COUNT(*) as listings_count,
                AVG(listing_price) as avg_listing_price,
                MIN(listing_price) as min_listing_price
            FROM `{self.project_id}.{self.dataset_id}.nft_metadata`
            WHERE is_listed = true
              AND partition_date >= DATE(@since)
            GROUP BY current_owner, collection_id
            HAVING COUNT(*) >= @bulk_threshold
        )
        SELECT * FROM bulk_listings
        ORDER BY listings_count DESC
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("since", "TIMESTAMP", since),
                bigquery.ScalarQueryParameter("bulk_threshold", "INT64", self.thresholds['bulk_listing_count'])
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        
        alerts = []
        for row in query_job:
            alert = WhaleAlert(
                alert_id=str(uuid.uuid4()),
                wallet_address=row.wallet,
                alert_type=AlertType.BULK_LISTING,
                collection_id=row.collection_id,
                amount_sol=float(row.avg_listing_price * row.listings_count),
                severity=self._calculate_severity_for_bulk_listing(row.listings_count),
                triggered_at=datetime.now(),
                details={
                    'listings_count': row.listings_count,
                    'avg_listing_price': float(row.avg_listing_price),
                    'min_listing_price': float(row.min_listing_price),
                    'total_value': float(row.avg_listing_price * row.listings_count)
                }
            )
            
            alerts.append(alert)
        
        return alerts
    
    async def _detect_unusual_patterns(self, since: datetime) -> List[WhaleAlert]:
        """Detect unusual trading patterns."""
        
        # Detect accounts with unusual velocity
        query = f"""
        WITH trading_velocity AS (
            SELECT 
                COALESCE(from_address, to_address) as wallet,
                COUNT(*) as transaction_count,
                COUNT(DISTINCT collection_id) as collections_traded,
                SUM(price_sol) as total_volume,
                TIMESTAMP_DIFF(MAX(timestamp), MIN(timestamp), MINUTE) as active_minutes
            FROM `{self.project_id}.{self.dataset_id}.transactions`
            WHERE timestamp >= @since
              AND event_type = 'sale'
            GROUP BY COALESCE(from_address, to_address)
            HAVING COUNT(*) >= 20  -- High transaction count
        )
        SELECT *
        FROM trading_velocity
        WHERE (transaction_count / GREATEST(active_minutes, 1)) > 0.5  -- > 0.5 tx/minute
           OR total_volume >= @whale_volume_threshold
        ORDER BY transaction_count DESC
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("since", "TIMESTAMP", since),
                bigquery.ScalarQueryParameter("whale_volume_threshold", "FLOAT", self.thresholds['whale_volume_sol'])
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        
        alerts = []
        for row in query_job:
            if row.wallet:  # Ensure wallet address is not null
                velocity = row.transaction_count / max(row.active_minutes, 1)
                
                alert = WhaleAlert(
                    alert_id=str(uuid.uuid4()),
                    wallet_address=row.wallet,
                    alert_type=AlertType.UNUSUAL_PATTERN,
                    amount_sol=float(row.total_volume) if row.total_volume else 0.0,
                    severity=AlertSeverity.MEDIUM,
                    triggered_at=datetime.now(),
                    details={
                        'transaction_count': row.transaction_count,
                        'collections_traded': row.collections_traded,
                        'active_minutes': row.active_minutes,
                        'velocity_tx_per_minute': round(velocity, 3),
                        'pattern_type': 'high_velocity_trading'
                    }
                )
                
                alerts.append(alert)
        
        return alerts
    
    async def _detect_market_manipulation(self, since: datetime) -> List[WhaleAlert]:
        """Detect potential market manipulation patterns."""
        
        # Detect wash trading patterns
        query = f"""
        WITH potential_wash_trades AS (
            SELECT 
                s1.from_address as seller,
                s1.to_address as buyer,
                s1.mint_address,
                s1.collection_id,
                COUNT(*) as trade_count,
                AVG(s1.price_sol) as avg_price,
                MIN(s1.timestamp) as first_trade,
                MAX(s1.timestamp) as last_trade
            FROM `{self.project_id}.{self.dataset_id}.transactions` s1
            JOIN `{self.project_id}.{self.dataset_id}.transactions` s2
              ON s1.mint_address = s2.mint_address
              AND s1.from_address = s2.to_address
              AND s1.to_address = s2.from_address
              AND s1.timestamp != s2.timestamp
              AND ABS(TIMESTAMP_DIFF(s1.timestamp, s2.timestamp, HOUR)) <= 24
            WHERE s1.timestamp >= @since
              AND s1.event_type = 'sale'
              AND s2.event_type = 'sale'
            GROUP BY s1.from_address, s1.to_address, s1.mint_address, s1.collection_id
            HAVING COUNT(*) >= 3  -- Multiple back-and-forth trades
        )
        SELECT * FROM potential_wash_trades
        ORDER BY trade_count DESC
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("since", "TIMESTAMP", since)
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        
        alerts = []
        for row in query_job:
            alert = WhaleAlert(
                alert_id=str(uuid.uuid4()),
                wallet_address=row.seller,
                alert_type=AlertType.MARKET_MANIPULATION,
                collection_id=row.collection_id,
                mint_address=row.mint_address,
                amount_sol=float(row.avg_price * row.trade_count),
                severity=AlertSeverity.HIGH,
                triggered_at=row.last_trade,
                details={
                    'manipulation_type': 'potential_wash_trading',
                    'counterparty': row.buyer,
                    'trade_count': row.trade_count,
                    'avg_price': float(row.avg_price),
                    'time_span_hours': (row.last_trade - row.first_trade).total_seconds() / 3600
                }
            )
            
            alerts.append(alert)
        
        return alerts
    
    async def _detect_floor_manipulation(self, collection_id: str, since: datetime) -> List[WhaleAlert]:
        """Detect floor price manipulation attempts."""
        # Implementation for floor manipulation detection
        return []
    
    async def _detect_wash_trading(self, collection_id: str, since: datetime) -> List[WhaleAlert]:
        """Detect wash trading in specific collection."""
        # Implementation for wash trading detection
        return []
    
    async def _filter_cooldown_alerts(self, alerts: List[WhaleAlert]) -> List[WhaleAlert]:
        """Filter out alerts that are in cooldown period."""
        
        if not alerts:
            return []
        
        # Get recent alerts for cooldown checking
        wallet_addresses = list(set(alert.wallet_address for alert in alerts))
        
        query = f"""
        SELECT 
            wallet_address,
            alert_type,
            MAX(triggered_at) as last_alert
        FROM `{self.project_id}.{self.dataset_id}.whale_alerts`
        WHERE wallet_address IN UNNEST(@wallet_addresses)
          AND triggered_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
        GROUP BY wallet_address, alert_type
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("wallet_addresses", "STRING", wallet_addresses)
            ]
        )
        
        query_job = self.client.query(query, job_config=job_config)
        
        # Build cooldown lookup
        cooldown_lookup = {}
        for row in query_job:
            key = f"{row.wallet_address}_{row.alert_type}"
            cooldown_lookup[key] = row.last_alert
        
        # Filter alerts
        filtered_alerts = []
        current_time = datetime.now()
        
        for alert in alerts:
            key = f"{alert.wallet_address}_{alert.alert_type.value}"
            
            if key in cooldown_lookup:
                last_alert_time = cooldown_lookup[key]
                cooldown_period = self.cooldown_periods.get(alert.alert_type, timedelta(hours=6))
                
                if current_time - last_alert_time < cooldown_period:
                    logger.debug(f"Filtering alert {alert.alert_id} - still in cooldown")
                    continue
            
            # Set cooldown for future alerts
            alert.cooldown_until = current_time + self.cooldown_periods.get(
                alert.alert_type, timedelta(hours=6)
            )
            
            filtered_alerts.append(alert)
        
        return filtered_alerts
    
    def _calculate_severity_for_amount(self, amount_sol: float) -> AlertSeverity:
        """Calculate alert severity based on transaction amount."""
        if amount_sol >= 500.0:
            return AlertSeverity.CRITICAL
        elif amount_sol >= 200.0:
            return AlertSeverity.HIGH
        elif amount_sol >= 100.0:
            return AlertSeverity.MEDIUM
        else:
            return AlertSeverity.LOW
    
    def _calculate_severity_for_accumulation(self, nft_count: int, hours: float) -> AlertSeverity:
        """Calculate severity for rapid accumulation."""
        velocity = nft_count / max(hours, 1)
        
        if velocity >= 10.0:  # 10+ NFTs per hour
            return AlertSeverity.CRITICAL
        elif velocity >= 5.0:
            return AlertSeverity.HIGH
        elif velocity >= 2.0:
            return AlertSeverity.MEDIUM
        else:
            return AlertSeverity.LOW
    
    def _calculate_severity_for_bulk_listing(self, listing_count: int) -> AlertSeverity:
        """Calculate severity for bulk listing."""
        if listing_count >= 100:
            return AlertSeverity.CRITICAL
        elif listing_count >= 50:
            return AlertSeverity.HIGH
        elif listing_count >= 25:
            return AlertSeverity.MEDIUM
        else:
            return AlertSeverity.LOW