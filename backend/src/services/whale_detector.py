"""Whale detection service for identifying significant NFT transactions."""

import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class WhaleDetectorService:
    """Service for detecting whale activity in NFT transactions."""

    def __init__(self):
        """Initialize the whale detector."""
        self.volume_threshold = 100.0  # SOL
        self.nft_count_threshold = 50
        self.cooldown_hours = 6
        self.recent_alerts = {}

    async def analyze_transaction(self, transaction_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze a transaction for whale activity."""

        try:
            price_sol = transaction_data.get('price_sol', 0.0)
            wallet_address = transaction_data.get('to_address') or transaction_data.get('from_address')

            if not wallet_address:
                return None

            # Check if transaction meets whale criteria
            alert_type = self._determine_alert_type(transaction_data)
            if not alert_type:
                return None

            # Check cooldown period
            if self._is_in_cooldown(wallet_address, alert_type):
                return None

            # Calculate severity
            severity = self._calculate_severity(transaction_data)

            # Calculate market impact score
            market_impact = await self._calculate_market_impact(transaction_data)

            # Create whale alert
            alert = {
                'alert_id': str(uuid.uuid4()),
                'wallet_address': wallet_address,
                'alert_type': alert_type,
                'collection_id': transaction_data.get('collection_id'),
                'amount_sol': price_sol,
                'threshold_sol': self.volume_threshold,
                'severity': severity,
                'triggered_at': transaction_data.get('timestamp', datetime.now(timezone.utc)),
                'market_impact_score': market_impact,
                'details': {
                    'transaction_signature': transaction_data.get('transaction_signature'),
                    'mint_address': transaction_data.get('mint_address'),
                    'event_type': transaction_data.get('event_type'),
                    'marketplace': transaction_data.get('marketplace'),
                    'analysis_timestamp': datetime.now(timezone.utc).isoformat()
                }
            }

            # Update cooldown cache
            self._update_cooldown_cache(wallet_address, alert_type)

            logger.info(f"Whale alert generated: {alert_type} for {wallet_address} - {price_sol} SOL")
            return alert

        except Exception as e:
            logger.error(f"Exception in whale analysis: {e}")
            return None

    def _determine_alert_type(self, transaction_data: Dict[str, Any]) -> Optional[str]:
        """Determine the type of whale alert based on transaction data."""

        price_sol = transaction_data.get('price_sol', 0.0)
        event_type = transaction_data.get('event_type', '')

        if event_type in ['sale', 'purchase'] and price_sol >= self.volume_threshold:
            return 'large_purchase'
        elif event_type in ['sale', 'purchase'] and price_sol >= self.volume_threshold * 0.5:
            return 'significant_purchase'
        elif event_type in ['listing', 'delist'] and price_sol >= self.volume_threshold:
            return 'large_listing'

        return None

    def _calculate_severity(self, transaction_data: Dict[str, Any]) -> str:
        """Calculate the severity of the whale activity."""

        price_sol = transaction_data.get('price_sol', 0.0)

        if price_sol >= self.volume_threshold * 5:
            return 'critical'
        elif price_sol >= self.volume_threshold * 2:
            return 'high'
        elif price_sol >= self.volume_threshold:
            return 'medium'
        else:
            return 'low'

    async def _calculate_market_impact(self, transaction_data: Dict[str, Any]) -> float:
        """Calculate the potential market impact of the transaction."""

        try:
            price_sol = transaction_data.get('price_sol', 0.0)
            base_impact = min(price_sol / (self.volume_threshold * 10), 1.0)
            return base_impact

        except Exception as e:
            logger.error(f"Exception calculating market impact: {e}")
            return 0.0

    def _is_in_cooldown(self, wallet_address: str, alert_type: str) -> bool:
        """Check if wallet is in cooldown period for this alert type."""

        key = f"{wallet_address}_{alert_type}"
        last_alert = self.recent_alerts.get(key)

        if not last_alert:
            return False

        cooldown_period = timedelta(hours=self.cooldown_hours)
        return datetime.now(timezone.utc) - last_alert < cooldown_period

    def _update_cooldown_cache(self, wallet_address: str, alert_type: str):
        """Update the cooldown cache."""

        key = f"{wallet_address}_{alert_type}"
        self.recent_alerts[key] = datetime.now(timezone.utc)