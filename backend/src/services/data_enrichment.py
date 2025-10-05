"""Data enrichment service for NFT transactions.

Enriches raw transaction data with additional metadata from various sources.
"""

import aiohttp
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from ..config import config

logger = logging.getLogger(__name__)


class DataEnrichmentService:
    """Service for enriching transaction data with metadata."""

    def __init__(self):
        """Initialize the enrichment service."""
        self.helius_api_key = config.helius.api_key
        self.rpc_url = config.helius.rpc_url
        self.session = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def enrich_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich transaction with additional metadata."""

        enriched_data = {
            'nft_metadata': None,
            'collection_data': None,
            'price_analysis': None
        }

        try:
            # Create session if not exists
            if not self.session:
                self.session = aiohttp.ClientSession()

            # Enrich NFT metadata
            if transaction_data.get('mint_address'):
                nft_metadata = await self._get_nft_metadata(transaction_data['mint_address'])
                if nft_metadata:
                    enriched_data['nft_metadata'] = nft_metadata

            # Enrich collection data
            if transaction_data.get('collection_id'):
                collection_data = await self._get_collection_metadata(transaction_data['collection_id'])
                if collection_data:
                    enriched_data['collection_data'] = collection_data

            # Add price analysis
            enriched_data['price_analysis'] = await self._analyze_price(transaction_data)

            return enriched_data

        except Exception as e:
            logger.error(f"Failed to enrich transaction data: {e}")
            return enriched_data

    async def _get_nft_metadata(self, mint_address: str) -> Optional[Dict[str, Any]]:
        """Get NFT metadata from Helius API."""

        if not self.helius_api_key:
            logger.warning("No Helius API key configured")
            return None

        try:
            url = f"{self.rpc_url}/v0/token-metadata"
            params = {
                'mint-accounts': [mint_address]
            }
            headers = {
                'Authorization': f'Bearer {self.helius_api_key}'
            }

            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 0:
                        metadata = data[0]
                        return {
                            'mint_address': mint_address,
                            'name': metadata.get('onchain_metadata', {}).get('metadata', {}).get('name'),
                            'description': metadata.get('onchain_metadata', {}).get('metadata', {}).get('description'),
                            'image': metadata.get('offchain_metadata', {}).get('metadata', {}).get('image'),
                            'attributes': metadata.get('offchain_metadata', {}).get('metadata', {}).get('attributes', []),
                            'collection_id': metadata.get('grouping', [{}])[0].get('group_value'),
                            'verified': metadata.get('onchain_metadata', {}).get('metadata', {}).get('verified_collection'),
                            'current_owner': metadata.get('ownership', {}).get('owner'),
                            'supply': metadata.get('onchain_metadata', {}).get('metadata', {}).get('supply'),
                            'creators': metadata.get('onchain_metadata', {}).get('metadata', {}).get('creators', [])
                        }
                else:
                    logger.warning(f"Failed to get NFT metadata: {response.status}")

        except Exception as e:
            logger.error(f"Exception getting NFT metadata: {e}")

        return None

    async def _get_collection_metadata(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """Get collection metadata from various sources."""

        try:
            # Try to get from Helius first
            helius_data = await self._get_helius_collection_data(collection_id)
            if helius_data:
                return helius_data

            # Fallback to other sources or create minimal data
            return {
                'collection_id': collection_id,
                'name': f'Collection {collection_id[:8]}...',
                'symbol': 'UNK',
                'total_supply': 10000,  # Default estimate
                'floor_price': 0.0,
                'total_volume': 0.0,
                'creator': 'Unknown',
                'description': 'Collection metadata not available',
                'verified': False
            }

        except Exception as e:
            logger.error(f"Exception getting collection metadata: {e}")
            return None

    async def _get_helius_collection_data(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """Get collection data from Helius API."""

        if not self.helius_api_key:
            return None

        try:
            # This would use Helius collection endpoints when available
            # For now, return None to use fallback
            return None

        except Exception as e:
            logger.error(f"Exception getting Helius collection data: {e}")
            return None

    async def _analyze_price(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze transaction price context."""

        price_sol = transaction_data.get('price_sol', 0.0)

        try:
            # Basic price analysis
            analysis = {
                'price_sol': price_sol,
                'price_category': self._categorize_price(price_sol),
                'is_significant': price_sol > 10.0,  # Above 10 SOL
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            # Add more sophisticated analysis here
            # - Historical price comparison
            # - Floor price ratio
            # - Market trend correlation

            return analysis

        except Exception as e:
            logger.error(f"Exception analyzing price: {e}")
            return {'price_sol': price_sol, 'analysis_failed': True}

    def _categorize_price(self, price_sol: float) -> str:
        """Categorize transaction price."""

        if price_sol >= 100:
            return 'very_high'
        elif price_sol >= 10:
            return 'high'
        elif price_sol >= 1:
            return 'medium'
        elif price_sol >= 0.1:
            return 'low'
        else:
            return 'very_low'

    async def get_historical_floor_price(self, collection_id: str, days: int = 7) -> Optional[float]:
        """Get historical floor price for comparison."""

        try:
            # This would query BigQuery for historical data
            # For now, return None
            return None

        except Exception as e:
            logger.error(f"Exception getting historical floor price: {e}")
            return None

    async def enrich_batch(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich multiple transactions in batch."""

        tasks = [self.enrich_transaction(tx) for tx in transactions]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        enriched = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to enrich transaction {i}: {result}")
                enriched.append({})
            else:
                enriched.append(result)

        return enriched

    async def close(self):
        """Close the enrichment service."""
        if self.session:
            await self.session.close()
            self.session = None