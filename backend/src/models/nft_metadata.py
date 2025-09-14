"""NFT Metadata data model for ChainWeave.

This model represents individual NFT characteristics and current ownership information.
Implements validation rules from data-model.md specifications.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
import json
import re

from pydantic import BaseModel, Field, field_validator


class NFTMetadata(BaseModel):
    """Individual NFT characteristics and current ownership information."""
    
    mint_address: str = Field(
        ...,
        description="Unique NFT identifier (Solana mint address)",
        min_length=32,
        max_length=44
    )
    
    collection_id: str = Field(
        ...,
        description="Links to NFTCollection",
        min_length=1,
        max_length=100
    )
    
    name: str = Field(
        ...,
        description="Individual NFT name",
        min_length=1,
        max_length=200
    )
    
    image_url: str = Field(
        ...,
        description="IPFS or HTTP link to artwork",
        min_length=1,
        max_length=500
    )
    
    attributes: Dict[str, Any] = Field(
        ...,
        description="Trait/rarity data as key-value pairs"
    )
    
    rarity_rank: int = Field(
        ...,
        description="Rank within collection (1 = rarest)",
        ge=1
    )
    
    rarity_score: float = Field(
        ...,
        description="Calculated rarity score",
        ge=0.0
    )
    
    current_owner: str = Field(
        ...,
        description="Current holder wallet address",
        min_length=32,
        max_length=44
    )
    
    mint_timestamp: datetime = Field(
        ...,
        description="When NFT was first created"
    )
    
    last_transfer: datetime = Field(
        ...,
        description="Most recent ownership change"
    )
    
    # Optional metadata fields
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="NFT description"
    )
    
    external_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="External link for this NFT"
    )
    
    animation_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Animation or video URL"
    )
    
    # Calculated fields
    hold_duration_days: Optional[int] = Field(
        default=None,
        ge=0,
        description="Days since last transfer"
    )
    
    estimated_value: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Estimated current value in SOL"
    )
    
    last_sale_price: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Last known sale price in SOL"
    )
    
    listing_price: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Current listing price in SOL (if listed)"
    )
    
    is_listed: bool = Field(
        default=False,
        description="Whether NFT is currently listed for sale"
    )
    
    marketplace: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Marketplace where NFT is listed"
    )

    @field_validator('mint_address', 'current_owner')
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
    
    @field_validator('attributes')
    @classmethod
    def validate_attributes_format(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate attributes JSON is properly formatted."""
        if not isinstance(v, dict):
            raise ValueError("Attributes must be a dictionary")
        
        # Ensure all keys are strings and values are serializable
        validated_attrs = {}
        for key, value in v.items():
            if not isinstance(key, str):
                raise ValueError(f"Attribute key must be string, got {type(key)}")
            
            # Ensure value is JSON serializable
            try:
                json.dumps(value)
                validated_attrs[key] = value
            except (TypeError, ValueError):
                raise ValueError(f"Attribute value for '{key}' is not JSON serializable")
        
        return validated_attrs
    
    @field_validator('last_transfer')
    @classmethod
    def validate_last_transfer_after_mint(cls, v: datetime, info) -> datetime:
        """Ensure last_transfer is not before mint_timestamp."""
        if 'mint_timestamp' in info.data and v < info.data['mint_timestamp']:
            raise ValueError("last_transfer cannot be before mint_timestamp")
        return v
    
    @field_validator('image_url', 'external_url', 'animation_url')
    @classmethod
    def validate_url_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate URL format."""
        if v is None:
            return v
        
        # Basic URL validation
        url_pattern = r'^https?:\/\/[^\s/$.?#].[^\s]*$|^ipfs:\/\/[a-zA-Z0-9]+$'
        if not re.match(url_pattern, v, re.IGNORECASE):
            raise ValueError(f"Invalid URL format: {v}")
        
        return v
    
    @field_validator('marketplace')
    @classmethod
    def validate_marketplace(cls, v: Optional[str]) -> Optional[str]:
        """Validate marketplace name."""
        if v is None:
            return v
        
        # Known marketplaces
        valid_marketplaces = {
            'Magic Eden', 'OpenSea', 'Tensor', 'Hadeswap', 'SolSea',
            'DigitalEyes', 'Holaplex', 'Solanart', 'Alpha Art'
        }
        
        # Allow unknown marketplaces but validate format
        if not re.match(r'^[A-Za-z0-9\s\-_.]+$', v):
            raise ValueError(f"Invalid marketplace name format: {v}")
        
        return v
    
    def calculate_hold_duration(self) -> int:
        """Calculate current hold duration in days."""
        return (datetime.now() - self.last_transfer).days
    
    def get_trait_value(self, trait_type: str) -> Any:
        """Get value for specific trait type."""
        return self.attributes.get(trait_type)
    
    def has_trait(self, trait_type: str, trait_value: Any = None) -> bool:
        """Check if NFT has specific trait (optionally with specific value)."""
        if trait_type not in self.attributes:
            return False
        
        if trait_value is None:
            return True
        
        return self.attributes[trait_type] == trait_value
    
    def get_rarity_tier(self) -> str:
        """Get rarity tier based on rarity rank percentile."""
        # This would typically use collection size to calculate percentile
        # For now, provide basic tiers
        if self.rarity_rank <= 10:
            return "Mythic"
        elif self.rarity_rank <= 100:
            return "Legendary"
        elif self.rarity_rank <= 500:
            return "Epic"
        elif self.rarity_rank <= 2000:
            return "Rare"
        else:
            return "Common"
    
    def is_diamond_hands(self, threshold_days: int = 30) -> bool:
        """Check if current owner is diamond hands (holding > threshold days)."""
        hold_duration = self.calculate_hold_duration()
        return hold_duration >= threshold_days
    
    def get_profit_loss(self, current_price: float) -> Optional[float]:
        """Calculate unrealized profit/loss if last sale price known."""
        if self.last_sale_price is None:
            return None
        
        return current_price - self.last_sale_price

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "mint_address": "7eUgpyKmK5z1Gs9k1rvnJh1C2Fm8v6eGzPjKKdq3sA2R",
                "collection_id": "mad-lads-collection",
                "name": "Mad Lad #1234",
                "image_url": "https://arweave.net/abc123.png",
                "attributes": {
                    "background": "Golden",
                    "rarity": "Legendary",
                    "eyes": "Diamond",
                    "accessory": "Crown"
                },
                "rarity_rank": 15,
                "rarity_score": 245.7,
                "current_owner": "ByXB7zV4TKa3xxC6PJxEQgm7cZxvXHU9C5qhHdKQN4R4",
                "mint_timestamp": "2023-04-01T10:30:00Z",
                "last_transfer": "2023-04-15T14:22:00Z",
                "description": "A rare Mad Lad with golden background",
                "hold_duration_days": 25,
                "estimated_value": 15.5,
                "last_sale_price": 12.3,
                "is_listed": False
            }
        }


# Response models for heatmap visualization
class NFTHeatmapPoint(BaseModel):
    """NFT data point for heatmap visualization."""
    
    mint_address: str
    name: str
    current_owner: str
    hold_duration_days: int
    last_sale_price: float
    rarity_rank: int
    
    # Heatmap-specific fields
    heat_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Normalized heat score for color mapping"
    )
    
    activity_level: Optional[str] = Field(
        default=None,
        description="Categorical activity level (hot, warm, cool, cold)"
    )


# Response models for attribute analysis
class AttributeMetadata(BaseModel):
    """Metadata about NFT attributes for analysis."""
    
    trait_type: str
    trait_value: Any
    frequency: float = Field(ge=0.0, le=1.0, description="Frequency in collection")
    rarity_score: float = Field(ge=0.0, description="Rarity score for this trait")
    floor_multiplier: Optional[float] = Field(
        default=None,
        description="Price multiplier relative to collection floor"
    )


# Database models
class NFTMetadataTable(BaseModel):
    """BigQuery table model for NFT metadata."""
    
    mint_address: str
    collection_id: str
    name: str
    image_url: str
    attributes: str  # JSON string in BigQuery
    rarity_rank: int
    rarity_score: float
    current_owner: str
    mint_timestamp: datetime
    last_transfer: datetime
    description: Optional[str] = None
    external_url: Optional[str] = None
    hold_duration_days: Optional[int] = None
    last_sale_price: Optional[float] = None
    is_listed: bool = False
    listing_price: Optional[float] = None
    marketplace: Optional[str] = None
    
    # BigQuery specific fields
    ingested_at: datetime = Field(default_factory=datetime.now)
    partition_date: str = Field(
        default_factory=lambda: datetime.now().strftime('%Y-%m-%d')
    )
    
    @field_validator('attributes', mode='before')
    @classmethod
    def serialize_attributes(cls, v):
        """Convert attributes dict to JSON string for BigQuery."""
        if isinstance(v, dict):
            return json.dumps(v)
        return v


# Ownership tracking models
class OwnershipHistory(BaseModel):
    """Track ownership changes for NFTs."""
    
    mint_address: str
    from_owner: Optional[str]  # None for mint events
    to_owner: str
    transfer_timestamp: datetime
    transaction_signature: str
    price_sol: Optional[float] = None  # None for transfers without price
    marketplace: Optional[str] = None
    
    @field_validator('from_owner', 'to_owner', mode='before')
    @classmethod
    def validate_owner_addresses(cls, v):
        """Validate owner addresses if provided."""
        if v is None:
            return v
        
        # Use same validation as other Solana addresses
        if not (32 <= len(v) <= 44):
            raise ValueError(f"Invalid owner address length: {len(v)}")
        
        base58_pattern = r'^[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]+$'
        if not re.match(base58_pattern, v):
            raise ValueError("Invalid owner address format: must be valid base58")
        
        return v