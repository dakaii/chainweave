"""NFT Collection data model for ChainWeave.

This model represents collections of related NFTs, typically from the same creator or project.
Implements validation rules from data-model.md specifications.
"""

from datetime import datetime
from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field, field_validator
import re


class CollectionStatus(str, Enum):
    """Collection lifecycle status."""
    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    INACTIVE = "inactive"


class NFTCollection(BaseModel):
    """Primary grouping entity for related NFTs."""
    
    collection_id: str = Field(
        ...,
        description="Unique identifier for the collection",
        min_length=1,
        max_length=100
    )
    
    collection_address: str = Field(
        ...,
        description="On-chain collection address",
        min_length=32,
        max_length=44
    )
    
    name: str = Field(
        ...,
        description="Human-readable collection name",
        min_length=1,
        max_length=200
    )
    
    symbol: str = Field(
        ...,
        description="Trading symbol/ticker",
        min_length=1,
        max_length=20
    )
    
    creator_address: str = Field(
        ...,
        description="Original creator wallet address",
        min_length=32,
        max_length=44
    )
    
    total_supply: int = Field(
        ...,
        description="Maximum possible NFTs in collection",
        gt=0,
        le=1_000_000  # Reasonable upper bound
    )
    
    created_at: datetime = Field(
        ...,
        description="First mint timestamp"
    )
    
    updated_at: datetime = Field(
        ...,
        description="Last metadata update timestamp"
    )
    
    floor_price: float = Field(
        ...,
        description="Current lowest listing price in SOL",
        ge=0.0
    )
    
    total_volume: float = Field(
        ...,
        description="All-time trading volume in SOL",
        ge=0.0
    )
    
    status: CollectionStatus = Field(
        default=CollectionStatus.CREATED,
        description="Current collection lifecycle status"
    )
    
    # Optional metadata fields
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Collection description"
    )
    
    image_url: Optional[str] = Field(
        default=None,
        description="Collection cover image URL"
    )
    
    website_url: Optional[str] = Field(
        default=None,
        description="Official collection website"
    )
    
    twitter_handle: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Twitter handle without @ symbol"
    )
    
    discord_url: Optional[str] = Field(
        default=None,
        description="Discord server invite URL"
    )
    
    # Calculated fields (updated by analytics services)
    holder_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of unique holders"
    )
    
    listed_count: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of NFTs currently listed for sale"
    )
    
    average_hold_duration_days: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Average holding period in days"
    )
    
    royalty_percentage: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Creator royalty percentage"
    )

    @field_validator('collection_address', 'creator_address')
    @classmethod
    def validate_solana_address(cls, v: str) -> str:
        """Validate Solana address format (base58)."""
        if not v:
            raise ValueError("Address cannot be empty")
        
        # Solana addresses are base58 encoded and typically 32-44 characters
        if not (32 <= len(v) <= 44):
            raise ValueError(f"Invalid address length: {len(v)}, expected 32-44 characters")
        
        # Base58 alphabet (no 0, O, I, l)
        base58_pattern = r'^[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]+$'
        if not re.match(base58_pattern, v):
            raise ValueError("Invalid address format: must be valid base58")
        
        return v
    
    @field_validator('updated_at')
    @classmethod
    def validate_updated_after_created(cls, v: datetime, info) -> datetime:
        """Ensure updated_at is not before created_at."""
        if 'created_at' in info.data and v < info.data['created_at']:
            raise ValueError("updated_at cannot be before created_at")
        return v
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol_format(cls, v: str) -> str:
        """Validate symbol format (alphanumeric, uppercase preferred)."""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError("Symbol must be alphanumeric (with optional _ or -)")
        return v.upper()
    
    @field_validator('twitter_handle')
    @classmethod
    def validate_twitter_handle(cls, v: Optional[str]) -> Optional[str]:
        """Validate Twitter handle format."""
        if v is None:
            return v
        
        # Remove @ if present
        handle = v.lstrip('@')
        
        # Twitter handle validation
        if not re.match(r'^[A-Za-z0-9_]{1,15}$', handle):
            raise ValueError("Invalid Twitter handle format")
        
        return handle
    
    def get_listing_percentage(self) -> float:
        """Calculate percentage of collection listed for sale."""
        if self.listed_count is None or self.total_supply == 0:
            return 0.0
        return (self.listed_count / self.total_supply) * 100
    
    def get_holder_ratio(self) -> float:
        """Calculate holders per NFT ratio (indicates distribution)."""
        if self.holder_count is None or self.total_supply == 0:
            return 0.0
        return self.holder_count / self.total_supply
    
    def is_fully_minted(self) -> bool:
        """Check if collection has reached total supply."""
        return self.status == CollectionStatus.COMPLETED
    
    def days_since_creation(self) -> int:
        """Calculate days since collection was created."""
        return (datetime.now() - self.created_at).days

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "collection_id": "mad-lads-collection",
                "collection_address": "J1S9H3QjnRtBbbuD4HjPV6RpRhwuk4zKbxsnCHuTgh9w",
                "name": "Mad Lads",
                "symbol": "MADLADS",
                "creator_address": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
                "total_supply": 10000,
                "created_at": "2023-04-01T00:00:00Z",
                "updated_at": "2023-04-01T12:00:00Z",
                "floor_price": 12.5,
                "total_volume": 125000.0,
                "status": "active",
                "description": "Mad Lads NFT Collection on Solana",
                "holder_count": 7500,
                "listed_count": 250,
                "royalty_percentage": 5.0
            }
        }


# Response models for API endpoints
class CollectionSummary(BaseModel):
    """Lightweight collection model for list endpoints."""
    
    collection_id: str
    name: str
    symbol: str
    total_supply: int
    floor_price: float
    total_volume: float
    holder_count: int
    avg_price_24h: float = Field(description="24-hour average price")
    volume_24h: float = Field(description="24-hour trading volume")


class CollectionDetails(NFTCollection):
    """Extended collection model with analytics data."""
    
    price_history: list = Field(
        default_factory=list,
        description="Historical price data points"
    )
    
    top_holders: list = Field(
        default_factory=list,
        description="Top NFT holders in this collection"
    )
    
    recent_sales: list = Field(
        default_factory=list,
        description="Recent sale transactions"
    )
    
    trait_distribution: Optional[dict] = Field(
        default=None,
        description="Distribution of traits within collection"
    )


# Database models (for BigQuery schema)
class CollectionTable(BaseModel):
    """BigQuery table model for collections."""
    
    collection_id: str
    collection_address: str
    name: str
    symbol: str
    creator_address: str
    total_supply: int
    created_at: datetime
    updated_at: datetime
    floor_price: float
    total_volume: float
    status: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    website_url: Optional[str] = None
    holder_count: Optional[int] = None
    listed_count: Optional[int] = None
    royalty_percentage: Optional[float] = None
    
    # BigQuery specific fields
    ingested_at: datetime = Field(default_factory=datetime.now)
    partition_date: str = Field(
        default_factory=lambda: datetime.now().strftime('%Y-%m-%d')
    )