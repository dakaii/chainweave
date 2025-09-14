"""Transaction data model for ChainWeave.

This model represents individual NFT transfer, sale, or mint events from blockchain.
Implements validation rules from data-model.md specifications.
"""

from datetime import datetime
from typing import Optional
from enum import Enum
import re

from pydantic import BaseModel, Field, field_validator


class EventType(str, Enum):
    """Transaction event types."""
    MINT = "mint"
    TRANSFER = "transfer"
    SALE = "sale"
    BURN = "burn"
    LIST = "list"
    DELIST = "delist"


class TransactionStatus(str, Enum):
    """Transaction processing status."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class Transaction(BaseModel):
    """Individual NFT transfer, sale, or mint events from blockchain."""
    
    transaction_signature: str = Field(
        ...,
        description="Solana transaction hash (unique identifier)",
        min_length=87,
        max_length=88
    )
    
    mint_address: str = Field(
        ...,
        description="NFT being transferred",
        min_length=32,
        max_length=44
    )
    
    event_type: EventType = Field(
        ...,
        description="Type of blockchain event"
    )
    
    from_address: Optional[str] = Field(
        default=None,
        description="Sender wallet (null for mint events)",
        min_length=32,
        max_length=44
    )
    
    to_address: Optional[str] = Field(
        default=None,
        description="Recipient wallet (null for burn events)",
        min_length=32,
        max_length=44
    )
    
    price_sol: Optional[float] = Field(
        default=None,
        description="Sale price in SOL (null for non-sale events)",
        ge=0.0
    )
    
    price_usd: Optional[float] = Field(
        default=None,
        description="USD equivalent at transaction time",
        ge=0.0
    )
    
    marketplace: Optional[str] = Field(
        default=None,
        description="Platform facilitating sale",
        max_length=50
    )
    
    timestamp: datetime = Field(
        ...,
        description="Block timestamp"
    )
    
    block_height: int = Field(
        ...,
        description="Solana block number",
        ge=1
    )
    
    instruction_index: Optional[int] = Field(
        default=None,
        description="Position within transaction",
        ge=0
    )
    
    status: TransactionStatus = Field(
        default=TransactionStatus.CONFIRMED,
        description="Transaction processing status"
    )
    
    # Optional metadata fields
    program_id: Optional[str] = Field(
        default=None,
        description="Solana program that executed the transaction",
        min_length=32,
        max_length=44
    )
    
    collection_id: Optional[str] = Field(
        default=None,
        description="Associated collection identifier"
    )
    
    royalty_paid: Optional[float] = Field(
        default=None,
        description="Creator royalty amount in SOL",
        ge=0.0
    )
    
    marketplace_fee: Optional[float] = Field(
        default=None,
        description="Marketplace fee in SOL",
        ge=0.0
    )
    
    gas_fee: Optional[float] = Field(
        default=None,
        description="Transaction fee in SOL",
        ge=0.0
    )
    
    # Helius webhook metadata
    webhook_timestamp: Optional[datetime] = Field(
        default=None,
        description="When webhook was received"
    )
    
    slot_number: Optional[int] = Field(
        default=None,
        description="Solana slot number",
        ge=1
    )

    @field_validator('transaction_signature')
    @classmethod
    def validate_transaction_signature(cls, v: str) -> str:
        """Validate Solana transaction signature format."""
        if not v:
            raise ValueError("Transaction signature cannot be empty")
        
        # Solana transaction signatures are base58 encoded and 87-88 characters
        if not (87 <= len(v) <= 88):
            raise ValueError(f"Invalid signature length: {len(v)}, expected 87-88 characters")
        
        # Base58 alphabet (no 0, O, I, l)
        base58_pattern = r'^[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]+$'
        if not re.match(base58_pattern, v):
            raise ValueError("Invalid signature format: must be valid base58")
        
        return v
    
    @field_validator('mint_address', 'from_address', 'to_address', 'program_id')
    @classmethod
    def validate_solana_address(cls, v: Optional[str]) -> Optional[str]:
        """Validate Solana address format (base58) if provided."""
        if v is None:
            return v
        
        if not v:
            raise ValueError("Address cannot be empty string")
        
        # Solana addresses are base58 encoded and typically 32-44 characters
        if not (32 <= len(v) <= 44):
            raise ValueError(f"Invalid address length: {len(v)}, expected 32-44 characters")
        
        # Base58 alphabet (no 0, O, I, l)
        base58_pattern = r'^[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]+$'
        if not re.match(base58_pattern, v):
            raise ValueError("Invalid address format: must be valid base58")
        
        return v
    
    @field_validator('marketplace')
    @classmethod
    def validate_marketplace_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate marketplace name format."""
        if v is None:
            return v
        
        # Known Solana NFT marketplaces
        known_marketplaces = {
            'Magic Eden', 'OpenSea', 'Tensor', 'Hadeswap', 'SolSea',
            'DigitalEyes', 'Holaplex', 'Solanart', 'Alpha Art', 'Hyperspace',
            'CoralCube', 'Exchange.art', 'Formfunction', 'Direct Transfer'
        }
        
        # Allow known marketplaces or validate format for unknown ones
        if v not in known_marketplaces:
            if not re.match(r'^[A-Za-z0-9\s\-_.]+$', v):
                raise ValueError(f"Invalid marketplace name format: {v}")
        
        return v
    
    @field_validator('timestamp')
    @classmethod
    def validate_timestamp_realistic(cls, v: datetime) -> datetime:
        """Validate timestamp is realistic (after Solana launch, not future)."""
        # Solana mainnet launched in March 2020
        min_timestamp = datetime(2020, 3, 1)
        max_timestamp = datetime.now()
        
        if v < min_timestamp:
            raise ValueError(f"Timestamp {v} is before Solana mainnet launch")
        
        if v > max_timestamp:
            raise ValueError(f"Timestamp {v} is in the future")
        
        return v
    
    @field_validator('price_sol')
    @classmethod
    def validate_price_for_event_type(cls, v: Optional[float], info) -> Optional[float]:
        """Validate price is provided for sale events and null for others appropriately."""
        if 'event_type' not in info.data:
            return v
        
        event_type = info.data['event_type']
        
        # Sales must have price
        if event_type == EventType.SALE and v is None:
            raise ValueError("Sale events must have price_sol")
        
        # Sales must have positive price
        if event_type == EventType.SALE and (v is None or v <= 0):
            raise ValueError("Sale price must be positive")
        
        # Non-sale events should not have price (except list events)
        if event_type in [EventType.MINT, EventType.TRANSFER, EventType.BURN] and v is not None:
            raise ValueError(f"{event_type.value} events should not have price")
        
        return v
    
    @field_validator('from_address', 'to_address')
    @classmethod
    def validate_addresses_for_event_type(cls, v: Optional[str], info) -> Optional[str]:
        """Validate from/to addresses are appropriate for event type."""
        if 'event_type' not in info.data:
            return v
        
        event_type = info.data['event_type']
        field_name = info.field_name
        
        # Mint events: from_address should be None, to_address required
        if event_type == EventType.MINT:
            if field_name == 'from_address' and v is not None:
                raise ValueError("Mint events should not have from_address")
            if field_name == 'to_address' and v is None:
                raise ValueError("Mint events must have to_address")
        
        # Burn events: to_address should be None, from_address required
        elif event_type == EventType.BURN:
            if field_name == 'to_address' and v is not None:
                raise ValueError("Burn events should not have to_address")
            if field_name == 'from_address' and v is None:
                raise ValueError("Burn events must have from_address")
        
        # Transfer/Sale events: both addresses required
        elif event_type in [EventType.TRANSFER, EventType.SALE]:
            if v is None:
                raise ValueError(f"{event_type.value} events must have both from_address and to_address")
        
        return v
    
    def get_total_fees(self) -> float:
        """Calculate total fees paid for this transaction."""
        total = 0.0
        
        if self.royalty_paid:
            total += self.royalty_paid
        
        if self.marketplace_fee:
            total += self.marketplace_fee
        
        if self.gas_fee:
            total += self.gas_fee
        
        return total
    
    def get_net_price(self) -> Optional[float]:
        """Get net price after deducting fees."""
        if self.price_sol is None:
            return None
        
        return self.price_sol - self.get_total_fees()
    
    def is_high_value(self, threshold_sol: float = 10.0) -> bool:
        """Check if transaction is high value (above threshold)."""
        if self.price_sol is None:
            return False
        
        return self.price_sol >= threshold_sol
    
    def involves_wallet(self, wallet_address: str) -> bool:
        """Check if transaction involves specific wallet address."""
        return (self.from_address == wallet_address or 
                self.to_address == wallet_address)
    
    def get_counterparty(self, wallet_address: str) -> Optional[str]:
        """Get the counterparty address for a given wallet."""
        if self.from_address == wallet_address:
            return self.to_address
        elif self.to_address == wallet_address:
            return self.from_address
        else:
            return None
    
    def days_since_transaction(self) -> int:
        """Calculate days since transaction occurred."""
        return (datetime.now() - self.timestamp).days

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "transaction_signature": "5KJp9QjRgFryfbTTv8RtWGGCaYJJ7xBqQGY7FoXbpzSFwWrVvH3K7JX8QgGH1AjSBUL6Vh6Y8N3xAhVkCJ9wGxRr",
                "mint_address": "7eUgpyKmK5z1Gs9k1rvnJh1C2Fm8v6eGzPjKKdq3sA2R",
                "event_type": "sale",
                "from_address": "ByXB7zV4TKa3xxC6PJxEQgm7cZxvXHU9C5qhHdKQN4R4",
                "to_address": "9CwD5fX7JHs8RqVbGhTyE3nH4P2vZmKaL6tQsYuMxNpF",
                "price_sol": 15.5,
                "price_usd": 325.50,
                "marketplace": "Magic Eden",
                "timestamp": "2023-04-15T14:22:30Z",
                "block_height": 259841234,
                "instruction_index": 0,
                "status": "confirmed",
                "collection_id": "mad-lads-collection",
                "royalty_paid": 0.775,
                "marketplace_fee": 0.31,
                "gas_fee": 0.000005
            }
        }


# Response models for API endpoints
class RecentTransaction(BaseModel):
    """Simplified transaction model for recent activity."""
    
    transaction_signature: str
    event_type: str
    mint_address: str
    collection_name: Optional[str] = None
    price_sol: Optional[float] = None
    timestamp: datetime


class RecentSale(BaseModel):
    """Sale transaction model for collection details."""
    
    mint_address: str
    name: str
    price_sol: float
    buyer: str
    seller: str
    marketplace: str
    timestamp: datetime


# Database models
class TransactionTable(BaseModel):
    """BigQuery table model for transactions."""
    
    transaction_signature: str
    mint_address: str
    event_type: str
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    price_sol: Optional[float] = None
    price_usd: Optional[float] = None
    marketplace: Optional[str] = None
    timestamp: datetime
    block_height: int
    instruction_index: Optional[int] = None
    status: str
    program_id: Optional[str] = None
    collection_id: Optional[str] = None
    royalty_paid: Optional[float] = None
    marketplace_fee: Optional[float] = None
    gas_fee: Optional[float] = None
    
    # BigQuery specific fields
    ingested_at: datetime = Field(default_factory=datetime.now)
    partition_date: str = Field(
        default_factory=lambda: datetime.now().strftime('%Y-%m-%d')
    )


# Aggregation models for analytics
class DailyTransactionSummary(BaseModel):
    """Daily transaction summary for analytics."""
    
    date: str  # YYYY-MM-DD format
    collection_id: Optional[str] = None
    total_transactions: int = 0
    total_volume_sol: float = 0.0
    avg_price_sol: Optional[float] = None
    unique_traders: int = 0
    mints: int = 0
    sales: int = 0
    transfers: int = 0
    high_value_transactions: int = 0  # Above threshold


class WalletTransactionSummary(BaseModel):
    """Wallet transaction summary for profiles."""
    
    wallet_address: str
    total_transactions: int = 0
    total_volume_sol: float = 0.0
    total_spent_sol: float = 0.0
    total_received_sol: float = 0.0
    unique_collections: int = 0
    first_transaction: Optional[datetime] = None
    last_transaction: Optional[datetime] = None
    most_active_marketplace: Optional[str] = None