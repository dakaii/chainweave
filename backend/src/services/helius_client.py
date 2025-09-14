"""Helius API client for ChainWeave.

Provides interface to Helius services for:
- NFT metadata retrieval
- Transaction history
- Real-time webhook processing
- Collection discovery
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List, AsyncGenerator
from datetime import datetime, timedelta
import httpx
import json
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class HeliusClient:
    """Client for Helius API services."""
    
    BASE_URL = "https://api.helius.xyz"
    
    def __init__(self, api_key: str, timeout: int = 30):
        """Initialize Helius client."""
        self.api_key = api_key
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
    
    async def test_connection(self) -> bool:
        """Test API connectivity."""
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/v0/addresses/11111111111111111111111111111112/balances",
                params={"api-key": self.api_key}
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    async def get_collection_metadata(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """Fetch collection metadata from Helius."""
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/v1/mintlists/{collection_id}",
                params={"api-key": self.api_key}
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch collection {collection_id}: {response.status_code}")
                return None
            
            data = response.json()
            
            # Transform Helius response to our Collection format
            return {
                "collection_id": collection_id,
                "collection_address": data.get("mint", ""),
                "name": data.get("content", {}).get("metadata", {}).get("name", "Unknown"),
                "symbol": data.get("content", {}).get("metadata", {}).get("symbol"),
                "description": data.get("content", {}).get("metadata", {}).get("description"),
                "image_url": data.get("content", {}).get("links", {}).get("image"),
                "creator_address": self._extract_creator_address(data),
                "total_supply": data.get("supply", {}).get("print_current_supply", 0),
                "verified": data.get("authorities", {}).get("verified", False),
                "external_url": data.get("content", {}).get("links", {}).get("external_url"),
                "status": "active",
                "is_whale_tracked": True,  # Default to tracking new collections
                "mint_date": self._parse_timestamp(data.get("content", {}).get("metadata", {}).get("created_at"))
            }
            
        except Exception as e:
            logger.error(f"Error fetching collection metadata: {e}")
            return None
    
    async def get_nft_metadata(self, mint_address: str) -> Optional[Dict[str, Any]]:
        """Fetch individual NFT metadata."""
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/v0/token-metadata",
                params={
                    "api-key": self.api_key,
                    "mint": mint_address
                }
            )
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch NFT {mint_address}: {response.status_code}")
                return None
            
            data = response.json()
            
            # Transform to our NFTMetadata format
            return {
                "mint_address": mint_address,
                "collection_id": self._extract_collection_id(data),
                "name": data.get("onChainMetadata", {}).get("metadata", {}).get("name", "Unknown"),
                "image_url": data.get("offChainMetadata", {}).get("image", ""),
                "description": data.get("offChainMetadata", {}).get("description"),
                "external_url": data.get("offChainMetadata", {}).get("external_url"),
                "animation_url": data.get("offChainMetadata", {}).get("animation_url"),
                "attributes": self._extract_attributes(data),
                "current_owner": data.get("account", ""),
                "mint_timestamp": self._parse_timestamp(data.get("onChainMetadata", {}).get("mint_time")),
                "last_transfer": datetime.now(),  # Would need transaction history for accurate value
                "rarity_rank": 0,  # Calculated separately
                "rarity_score": 0.0  # Calculated separately
            }
            
        except Exception as e:
            logger.error(f"Error fetching NFT metadata: {e}")
            return None
    
    async def get_transaction_history(
        self, 
        address: str, 
        start_date: datetime,
        end_date: datetime,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Fetch transaction history for an address."""
        try:
            transactions = []
            before = None
            
            while len(transactions) < limit:
                params = {
                    "api-key": self.api_key,
                    "address": address,
                    "limit": min(100, limit - len(transactions))  # Max 100 per request
                }
                
                if before:
                    params["before"] = before
                
                response = await self.client.get(
                    f"{self.BASE_URL}/v0/addresses/{address}/transactions",
                    params=params
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to fetch transactions: {response.status_code}")
                    break
                
                batch = response.json()
                if not batch:
                    break
                
                # Filter by date range and transform
                for tx in batch:
                    tx_time = self._parse_timestamp(tx.get("blockTime"))
                    if tx_time and start_date <= tx_time <= end_date:
                        transformed = self._transform_transaction(tx)
                        if transformed:
                            transactions.append(transformed)
                
                # Pagination
                if len(batch) < 100:  # No more results
                    break
                
                before = batch[-1].get("signature")
                
                # Rate limiting
                await asyncio.sleep(0.1)
            
            return transactions
            
        except Exception as e:
            logger.error(f"Error fetching transaction history: {e}")
            return []
    
    async def stream_transactions(
        self, 
        collection_ids: Optional[List[str]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream real-time transactions (mock implementation)."""
        # Note: This would typically connect to Helius webhooks or WebSocket
        # For now, implementing as periodic polling
        
        logger.info("Starting transaction stream...")
        
        last_check = datetime.now()
        
        while True:
            try:
                # Poll for new transactions every 10 seconds
                await asyncio.sleep(10)
                
                # In real implementation, this would be webhook-driven
                # For now, simulate by fetching recent transactions
                current_time = datetime.now()
                
                if collection_ids:
                    for collection_id in collection_ids:
                        # Fetch recent transactions for collection
                        transactions = await self._get_recent_collection_transactions(
                            collection_id, 
                            since=last_check
                        )
                        
                        for tx in transactions:
                            yield tx
                
                last_check = current_time
                
            except Exception as e:
                logger.error(f"Error in transaction stream: {e}")
                await asyncio.sleep(5)  # Brief pause before retrying
    
    async def _get_recent_collection_transactions(
        self,
        collection_id: str,
        since: datetime,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get recent transactions for a collection."""
        try:
            # This would use Helius's collection transaction endpoint
            # Mock implementation for now
            response = await self.client.get(
                f"{self.BASE_URL}/v1/mintlists/{collection_id}/transactions",
                params={
                    "api-key": self.api_key,
                    "limit": limit,
                    "since": int(since.timestamp())
                }
            )
            
            if response.status_code != 200:
                return []
            
            transactions = response.json()
            return [self._transform_transaction(tx) for tx in transactions]
            
        except Exception as e:
            logger.error(f"Error fetching recent transactions: {e}")
            return []
    
    def _transform_transaction(self, helius_tx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Transform Helius transaction format to our Transaction model."""
        try:
            # Extract NFT transfer information from transaction
            nft_transfers = helius_tx.get("tokenTransfers", [])
            if not nft_transfers:
                return None
            
            # Take the first NFT transfer (most transactions have one)
            transfer = nft_transfers[0]
            
            return {
                "transaction_signature": helius_tx.get("signature", ""),
                "mint_address": transfer.get("mint", ""),
                "event_type": self._determine_event_type(transfer),
                "from_address": transfer.get("fromUserAccount"),
                "to_address": transfer.get("toUserAccount"), 
                "price_sol": self._extract_price(helius_tx),
                "marketplace": self._extract_marketplace(helius_tx),
                "timestamp": self._parse_timestamp(helius_tx.get("blockTime")),
                "block_height": helius_tx.get("slot", 0),
                "instruction_index": 0,
                "status": "confirmed",
                "collection_id": self._extract_collection_from_tx(helius_tx)
            }
            
        except Exception as e:
            logger.error(f"Error transforming transaction: {e}")
            return None
    
    def _determine_event_type(self, transfer: Dict[str, Any]) -> str:
        """Determine transaction event type from transfer data."""
        if not transfer.get("fromUserAccount"):
            return "mint"
        elif not transfer.get("toUserAccount"):
            return "burn"
        elif transfer.get("tokenAmount", 0) > 0:
            return "sale"
        else:
            return "transfer"
    
    def _extract_price(self, tx: Dict[str, Any]) -> Optional[float]:
        """Extract sale price from transaction."""
        # Look for SOL transfers that might indicate payment
        native_transfers = tx.get("nativeTransfers", [])
        
        for transfer in native_transfers:
            amount = transfer.get("amount", 0)
            if amount > 0:
                return amount / 1e9  # Convert lamports to SOL
        
        return None
    
    def _extract_marketplace(self, tx: Dict[str, Any]) -> Optional[str]:
        """Extract marketplace from transaction instructions."""
        instructions = tx.get("instructions", [])
        
        # Known marketplace program IDs
        marketplace_programs = {
            "M2mx93ekt1fmXSVkTrUL9xVFHkmME8HTUi5Cyc5aF7K": "Magic Eden",
            "1BWutmTvYPwDtmw9abTkS4Ssr8no61spGAvW1X6NDix": "Magic Eden",
            "MEisE1HzehtrDpAAT8PnLHjpSSkRYakotTuJRPjTpo8": "Magic Eden V2",
            "A7p8451kBn8pUBCtKKz4oNwz7j1oUcFKZTmpCBjNWYBz": "OpenSea",
            "TSWAPaqyCSx2KABk68Shruf4rp7CxcNi8hAsbdwmHbN": "Tensor"
        }
        
        for instruction in instructions:
            program_id = instruction.get("programId", "")
            if program_id in marketplace_programs:
                return marketplace_programs[program_id]
        
        return None
    
    def _extract_collection_id(self, nft_data: Dict[str, Any]) -> str:
        """Extract collection ID from NFT metadata."""
        # Try to get from grouping or collection fields
        grouping = nft_data.get("grouping", [])
        for group in grouping:
            if group.get("group_key") == "collection":
                return group.get("group_value", "unknown")
        
        # Fallback to creator address or mint address
        creators = nft_data.get("onChainMetadata", {}).get("metadata", {}).get("data", {}).get("creators", [])
        if creators:
            return f"creator_{creators[0].get('address', 'unknown')}"
        
        return "unknown"
    
    def _extract_collection_from_tx(self, tx: Dict[str, Any]) -> Optional[str]:
        """Extract collection ID from transaction."""
        # Would need to look up mint address to get collection
        # For now, return None and let it be resolved later
        return None
    
    def _extract_creator_address(self, collection_data: Dict[str, Any]) -> str:
        """Extract creator address from collection data."""
        authorities = collection_data.get("authorities", {})
        if authorities.get("metadata"):
            return authorities["metadata"]
        
        # Fallback to update authority
        return authorities.get("metadata", "unknown")
    
    def _extract_attributes(self, nft_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and format NFT attributes."""
        attributes = {}
        
        off_chain = nft_data.get("offChainMetadata", {}).get("attributes", [])
        for attr in off_chain:
            trait_type = attr.get("trait_type")
            value = attr.get("value")
            if trait_type and value is not None:
                attributes[trait_type] = value
        
        return attributes
    
    def _parse_timestamp(self, timestamp: Any) -> Optional[datetime]:
        """Parse timestamp from various formats."""
        if not timestamp:
            return None
        
        try:
            if isinstance(timestamp, (int, float)):
                return datetime.fromtimestamp(timestamp)
            elif isinstance(timestamp, str):
                # Try common formats
                for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"]:
                    try:
                        return datetime.strptime(timestamp, fmt)
                    except ValueError:
                        continue
            return None
        except Exception:
            return None