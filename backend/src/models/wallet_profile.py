"""Wallet Profile data model for ChainWeave.

This model represents aggregated analytics and behavior patterns for individual wallets.
Implements validation rules from data-model.md specifications.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
import re

from pydantic import BaseModel, Field, field_validator


class WalletTier(str, Enum):
    """Wallet classification tiers."""
    WHALE = "whale"           # High volume/count traders
    DOLPHIN = "dolphin"       # Mid-tier active traders  
    FISH = "fish"            # Regular users
    SHRIMP = "shrimp"        # Small/new users


class TradingBehavior(str, Enum):
    """Trading behavior patterns."""
    DIAMOND_HANDS = "diamond_hands"    # Long-term holders
    PAPER_HANDS = "paper_hands"        # Quick flippers
    ACTIVE_TRADER = "active_trader"    # Regular buying/selling
    COLLECTOR = "collector"            # Accumulates, rarely sells
    FLIPPER = "flipper"               # Quick profit taking


class WalletProfile(BaseModel):
    """Aggregated analytics and behavior patterns for individual wallets."""
    
    wallet_address: str = Field(
        ...,
        description="Solana wallet address (primary key)",
        min_length=32,
        max_length=44
    )
    
    total_nfts_owned: int = Field(
        ...,
        description="Current NFT count across all collections",
        ge=0
    )
    
    total_volume_traded: float = Field(
        ...,
        description="Lifetime trading volume in SOL",
        ge=0.0
    )
    
    first_activity: datetime = Field(
        ...,
        description="First recorded transaction"
    )
    
    last_activity: datetime = Field(
        ...,
        description="Most recent transaction"
    )
    
    avg_hold_duration: int = Field(
        ...,
        description="Average days holding NFTs before sale",
        ge=0
    )
    
    collections_active: int = Field(
        ...,
        description="Number of different collections traded",
        ge=0
    )
    
    whale_status: bool = Field(
        ...,
        description="Meets high-volume trader criteria"
    )
    
    profit_loss_sol: float = Field(
        ...,
        description="Estimated P&L from completed trades"
    )
    
    favorite_marketplace: Optional[str] = Field(
        default=None,
        description="Most frequently used trading platform"
    )
    
    # Enhanced analytics fields
    wallet_tier: WalletTier = Field(
        default=WalletTier.FISH,
        description="Wallet classification tier"
    )
    
    trading_behavior: TradingBehavior = Field(
        default=TradingBehavior.COLLECTOR,
        description="Primary trading behavior pattern"
    )
    
    total_spent_sol: float = Field(
        default=0.0,
        description="Total SOL spent on purchases",
        ge=0.0
    )
    
    total_received_sol: float = Field(
        default=0.0,
        description="Total SOL received from sales",
        ge=0.0
    )
    
    total_transactions: int = Field(
        default=0,
        description="Total number of NFT transactions",
        ge=0
    )
    
    successful_flips: int = Field(
        default=0,
        description="Number of profitable sales",
        ge=0
    )
    
    failed_flips: int = Field(
        default=0,
        description="Number of unprofitable sales",
        ge=0
    )
    
    avg_purchase_price: Optional[float] = Field(
        default=None,
        description="Average purchase price in SOL",
        ge=0.0
    )
    
    avg_sale_price: Optional[float] = Field(
        default=None,
        description="Average sale price in SOL", 
        ge=0.0
    )
    
    largest_purchase_sol: Optional[float] = Field(
        default=None,
        description="Largest single purchase in SOL",
        ge=0.0
    )
    
    largest_sale_sol: Optional[float] = Field(
        default=None,
        description="Largest single sale in SOL",
        ge=0.0
    )
    
    win_rate: Optional[float] = Field(
        default=None,
        description="Percentage of profitable sales",
        ge=0.0,
        le=100.0
    )
    
    # Time-based metrics
    days_active: Optional[int] = Field(
        default=None,
        description="Total days with NFT activity",
        ge=0
    )
    
    avg_transactions_per_day: Optional[float] = Field(
        default=None,
        description="Average transactions per active day",
        ge=0.0
    )
    
    most_active_hour: Optional[int] = Field(
        default=None,
        description="Hour of day (0-23) with most activity",
        ge=0,
        le=23
    )
    
    # Portfolio composition
    top_collection: Optional[str] = Field(
        default=None,
        description="Collection with most NFTs owned"
    )
    
    portfolio_diversity_score: Optional[float] = Field(
        default=None,
        description="Portfolio diversification score (0-1)",
        ge=0.0,
        le=1.0
    )
    
    # Social/network metrics
    unique_counterparties: Optional[int] = Field(
        default=None,
        description="Number of unique trading partners",
        ge=0
    )
    
    # Updated timestamps
    profile_updated_at: datetime = Field(
        default_factory=datetime.now,
        description="Last profile calculation timestamp"
    )
    
    metrics_calculated_at: Optional[datetime] = Field(
        default=None,
        description="When advanced metrics were last calculated"
    )

    @field_validator('wallet_address')
    @classmethod
    def validate_solana_address(cls, v: str) -> str:
        """Validate Solana address format (base58)."""
        if not v:
            raise ValueError("Wallet address cannot be empty")
        
        # Solana addresses are base58 encoded and typically 32-44 characters
        if not (32 <= len(v) <= 44):
            raise ValueError(f"Invalid address length: {len(v)}, expected 32-44 characters")
        
        # Base58 alphabet (no 0, O, I, l)
        base58_pattern = r'^[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]+$'
        if not re.match(base58_pattern, v):
            raise ValueError("Invalid address format: must be valid base58")
        
        return v
    
    @field_validator('last_activity')
    @classmethod
    def validate_last_activity_after_first(cls, v: datetime, info) -> datetime:
        """Ensure last_activity is not before first_activity."""
        if 'first_activity' in info.data and v < info.data['first_activity']:
            raise ValueError("last_activity cannot be before first_activity")
        return v
    
    @field_validator('favorite_marketplace')
    @classmethod
    def validate_marketplace(cls, v: Optional[str]) -> Optional[str]:
        """Validate marketplace name format."""
        if v is None:
            return v
        
        # Known Solana marketplaces
        known_marketplaces = {
            'Magic Eden', 'OpenSea', 'Tensor', 'Hadeswap', 'SolSea',
            'DigitalEyes', 'Holaplex', 'Solanart', 'Alpha Art', 'Hyperspace'
        }
        
        # Allow unknown marketplaces but validate format
        if v not in known_marketplaces:
            if not re.match(r'^[A-Za-z0-9\s\-_.]+$', v):
                raise ValueError(f"Invalid marketplace name format: {v}")
        
        return v
    
    @field_validator('profit_loss_sol')
    @classmethod
    def validate_pnl_matches_trades(cls, v: float, info) -> float:
        """Basic validation of P&L against trading volumes."""
        # P&L should be reasonable relative to trading volume
        if 'total_volume_traded' in info.data:
            volume = info.data['total_volume_traded']
            if volume > 0 and abs(v) > volume:
                # Allow some flexibility for fees and market movements
                pass  # Just a warning, don't fail validation
        
        return v
    
    def calculate_activity_days(self) -> int:
        """Calculate total days between first and last activity."""
        return (self.last_activity - self.first_activity).days + 1
    
    def calculate_win_rate(self) -> float:
        """Calculate win rate as percentage of profitable sales."""
        total_sales = self.successful_flips + self.failed_flips
        if total_sales == 0:
            return 0.0
        
        return (self.successful_flips / total_sales) * 100.0
    
    def get_roi_percentage(self) -> float:
        """Calculate return on investment as percentage."""
        if self.total_spent_sol == 0:
            return 0.0
        
        return (self.profit_loss_sol / self.total_spent_sol) * 100.0
    
    def is_active_in_period(self, days: int = 30) -> bool:
        """Check if wallet was active in the last N days."""
        cutoff = datetime.now() - timedelta(days=days)
        return self.last_activity >= cutoff
    
    def get_trading_frequency(self) -> str:
        """Get descriptive trading frequency category."""
        if self.avg_transactions_per_day is None or self.avg_transactions_per_day == 0:
            return "Inactive"
        elif self.avg_transactions_per_day >= 5:
            return "Very High"
        elif self.avg_transactions_per_day >= 2:
            return "High"
        elif self.avg_transactions_per_day >= 0.5:
            return "Moderate"
        else:
            return "Low"
    
    def get_portfolio_size_category(self) -> str:
        """Get portfolio size category."""
        if self.total_nfts_owned >= 1000:
            return "Mega Collection"
        elif self.total_nfts_owned >= 100:
            return "Large Collection"
        elif self.total_nfts_owned >= 10:
            return "Medium Collection"
        elif self.total_nfts_owned >= 1:
            return "Small Collection"
        else:
            return "No NFTs"
    
    def get_experience_level(self) -> str:
        """Get experience level based on activity duration and volume."""
        activity_days = self.calculate_activity_days()
        
        if activity_days >= 365 and self.total_volume_traded >= 100:
            return "Veteran"
        elif activity_days >= 180 and self.total_volume_traded >= 50:
            return "Experienced"
        elif activity_days >= 30 and self.total_volume_traded >= 10:
            return "Intermediate"
        else:
            return "Beginner"
    
    def should_update_tier(self) -> bool:
        """Check if wallet tier should be recalculated based on current metrics."""
        # Whale thresholds (these would be configurable)
        whale_volume_threshold = 500.0  # SOL
        whale_nft_threshold = 100
        
        # Determine expected tier
        if (self.total_volume_traded >= whale_volume_threshold or 
            self.total_nfts_owned >= whale_nft_threshold):
            expected_tier = WalletTier.WHALE
        elif (self.total_volume_traded >= 100.0 or 
              self.total_nfts_owned >= 50):
            expected_tier = WalletTier.DOLPHIN
        elif (self.total_volume_traded >= 10.0 or 
              self.total_nfts_owned >= 5):
            expected_tier = WalletTier.FISH
        else:
            expected_tier = WalletTier.SHRIMP
        
        return self.wallet_tier != expected_tier

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "wallet_address": "ByXB7zV4TKa3xxC6PJxEQgm7cZxvXHU9C5qhHdKQN4R4",
                "total_nfts_owned": 75,
                "total_volume_traded": 342.5,
                "first_activity": "2023-01-15T10:30:00Z",
                "last_activity": "2023-04-20T16:45:00Z",
                "avg_hold_duration": 45,
                "collections_active": 12,
                "whale_status": True,
                "profit_loss_sol": 67.8,
                "favorite_marketplace": "Magic Eden",
                "wallet_tier": "whale",
                "trading_behavior": "active_trader",
                "total_spent_sol": 1250.0,
                "total_received_sol": 1317.8,
                "successful_flips": 28,
                "failed_flips": 12,
                "win_rate": 70.0,
                "largest_purchase_sol": 45.0,
                "portfolio_diversity_score": 0.75
            }
        }


# Response models for API endpoints
class WalletSummary(BaseModel):
    """Simplified wallet model for whale lists."""
    
    wallet_address: str
    total_volume_traded: float
    total_nfts_owned: int
    whale_status: bool
    last_activity: datetime
    recent_activity_count: int


class TopHolder(BaseModel):
    """Top holder model for collection details."""
    
    wallet_address: str
    nft_count: int
    estimated_value: float
    whale_status: bool
    hold_duration_days: Optional[int] = None


class WalletHolding(BaseModel):
    """Individual NFT holding for wallet profiles."""
    
    mint_address: str
    name: str
    collection_name: str
    acquired_date: datetime
    acquisition_price: Optional[float] = None
    current_floor_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    hold_duration_days: int


# Database models
class WalletProfileTable(BaseModel):
    """BigQuery table model for wallet profiles."""
    
    wallet_address: str
    total_nfts_owned: int
    total_volume_traded: float
    first_activity: datetime
    last_activity: datetime
    avg_hold_duration: int
    collections_active: int
    whale_status: bool
    profit_loss_sol: float
    favorite_marketplace: Optional[str] = None
    wallet_tier: str
    trading_behavior: str
    total_spent_sol: float
    total_received_sol: float
    total_transactions: int
    successful_flips: int
    failed_flips: int
    win_rate: Optional[float] = None
    largest_purchase_sol: Optional[float] = None
    largest_sale_sol: Optional[float] = None
    portfolio_diversity_score: Optional[float] = None
    unique_counterparties: Optional[int] = None
    
    # BigQuery specific fields
    profile_updated_at: datetime
    partition_date: str = Field(
        default_factory=lambda: datetime.now().strftime('%Y-%m-%d')
    )


# Analytics aggregation models
class WalletActivitySummary(BaseModel):
    """Daily/weekly wallet activity summary."""
    
    wallet_address: str
    date: str  # YYYY-MM-DD format
    transactions_count: int = 0
    volume_traded_sol: float = 0.0
    nfts_acquired: int = 0
    nfts_sold: int = 0
    profit_loss_sol: float = 0.0
    unique_collections: int = 0
    active_hours: List[int] = Field(default_factory=list)


class WalletRankings(BaseModel):
    """Wallet rankings for leaderboards."""
    
    wallet_address: str
    rank_by_volume: Optional[int] = None
    rank_by_nfts: Optional[int] = None
    rank_by_profit: Optional[int] = None
    rank_by_activity: Optional[int] = None
    total_wallets: int
    percentile: float  # 0-100


from datetime import timedelta  # Import needed for is_active_in_period method