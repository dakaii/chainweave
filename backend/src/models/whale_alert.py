"""Whale Alert data model for ChainWeave.

This model represents significant trading events that meet predefined criteria for tracking.
Implements validation rules from data-model.md specifications.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from enum import Enum
from uuid import uuid4
import re

from pydantic import BaseModel, Field, field_validator


class WhaleAlertType(str, Enum):
    """Types of whale alerts."""
    LARGE_PURCHASE = "large_purchase"          # Single high-value buy
    LARGE_SALE = "large_sale"                  # Single high-value sale
    WHALE_MINT = "whale_mint"                  # Whale minting NFTs
    COLLECTION_SWEEP = "collection_sweep"       # Buying multiple NFTs from collection
    VOLUME_SPIKE = "volume_spike"              # Unusual trading volume
    NEW_WHALE = "new_whale"                    # Wallet reaching whale status
    WHALE_DUMP = "whale_dump"                  # Large-scale selling
    FLOOR_MANIPULATION = "floor_manipulation"   # Potential floor price manipulation
    CROSS_COLLECTION = "cross_collection"       # Activity across multiple collections


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    LOW = "low"           # Minor whale activity
    MEDIUM = "medium"     # Notable activity
    HIGH = "high"         # Significant market impact
    CRITICAL = "critical" # Major market event


class AlertStatus(str, Enum):
    """Alert processing status."""
    PENDING = "pending"         # Alert created, not processed
    ACTIVE = "active"          # Alert active and visible
    ACKNOWLEDGED = "acknowledged" # Seen by users
    EXPIRED = "expired"        # Too old to be relevant
    SUPPRESSED = "suppressed"   # Hidden due to spam/false positive


class WhaleAlert(BaseModel):
    """Significant trading events that meet predefined criteria for tracking."""
    
    alert_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Generated UUID for alert"
    )
    
    transaction_signature: str = Field(
        ...,
        description="Related transaction hash",
        min_length=87,
        max_length=88
    )
    
    wallet_address: str = Field(
        ...,
        description="Wallet triggering alert",
        min_length=32,
        max_length=44
    )
    
    alert_type: WhaleAlertType = Field(
        ...,
        description="Type of whale alert"
    )
    
    nft_count: int = Field(
        ...,
        description="Number of NFTs in transaction",
        gt=0
    )
    
    total_value_sol: float = Field(
        ...,
        description="Combined value in SOL",
        gt=0.0
    )
    
    collection_id: str = Field(
        ...,
        description="Affected collection",
        min_length=1,
        max_length=100
    )
    
    triggered_at: datetime = Field(
        ...,
        description="When alert criteria were met"
    )
    
    notification_sent: bool = Field(
        default=False,
        description="Whether alert was distributed"
    )
    
    # Enhanced alert metadata
    severity: AlertSeverity = Field(
        default=AlertSeverity.MEDIUM,
        description="Alert severity level"
    )
    
    status: AlertStatus = Field(
        default=AlertStatus.PENDING,
        description="Alert processing status"
    )
    
    title: str = Field(
        ...,
        description="Human-readable alert title",
        min_length=1,
        max_length=200
    )
    
    description: str = Field(
        ...,
        description="Detailed alert description",
        min_length=1,
        max_length=1000
    )
    
    # Transaction details
    from_address: Optional[str] = Field(
        default=None,
        description="Transaction sender (if applicable)"
    )
    
    to_address: Optional[str] = Field(
        default=None,
        description="Transaction recipient (if applicable)"
    )
    
    marketplace: Optional[str] = Field(
        default=None,
        description="Marketplace where transaction occurred"
    )
    
    # Price analysis
    floor_price_at_time: Optional[float] = Field(
        default=None,
        description="Collection floor price when alert triggered",
        ge=0.0
    )
    
    price_premium_percentage: Optional[float] = Field(
        default=None,
        description="Premium over floor price as percentage",
        ge=-100.0  # Allow negative for below-floor sales
    )
    
    average_sale_price_7d: Optional[float] = Field(
        default=None,
        description="7-day average sale price for comparison",
        ge=0.0
    )
    
    # Whale context
    whale_total_volume: Optional[float] = Field(
        default=None,
        description="Whale's total trading volume",
        ge=0.0
    )
    
    whale_nft_count: Optional[int] = Field(
        default=None,
        description="Whale's total NFT count",
        ge=0
    )
    
    whale_collections_active: Optional[int] = Field(
        default=None,
        description="Number of collections whale trades",
        ge=0
    )
    
    # Market impact metrics
    collection_volume_24h: Optional[float] = Field(
        default=None,
        description="Collection 24h volume before alert",
        ge=0.0
    )
    
    volume_impact_percentage: Optional[float] = Field(
        default=None,
        description="Alert transaction as % of daily volume",
        ge=0.0
    )
    
    holders_count_before: Optional[int] = Field(
        default=None,
        description="Collection holders before transaction",
        ge=0
    )
    
    # Cooldown tracking
    last_alert_same_wallet: Optional[datetime] = Field(
        default=None,
        description="Last alert from same wallet"
    )
    
    cooldown_hours: int = Field(
        default=6,
        description="Cooldown period for same wallet alerts",
        ge=0,
        le=168  # Max 1 week
    )
    
    # Social metrics
    mentions_count: int = Field(
        default=0,
        description="Social media mentions of this alert",
        ge=0
    )
    
    engagement_score: Optional[float] = Field(
        default=None,
        description="User engagement score with alert",
        ge=0.0
    )
    
    # Alert lifecycle
    expires_at: Optional[datetime] = Field(
        default=None,
        description="When alert becomes irrelevant"
    )
    
    acknowledged_at: Optional[datetime] = Field(
        default=None,
        description="When alert was first viewed"
    )
    
    suppressed_at: Optional[datetime] = Field(
        default=None,
        description="When alert was suppressed"
    )
    
    # Metadata for analysis
    alert_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional alert-specific data"
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
    
    @field_validator('wallet_address', 'from_address', 'to_address')
    @classmethod
    def validate_solana_address(cls, v: Optional[str]) -> Optional[str]:
        """Validate Solana address format if provided."""
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
    
    @field_validator('total_value_sol')
    @classmethod
    def validate_meets_alert_threshold(cls, v: float, info) -> float:
        """Validate transaction value meets alert threshold."""
        # Basic threshold validation - would be configurable in production
        min_alert_threshold = 1.0  # Minimum 1 SOL for alerts
        
        if v < min_alert_threshold:
            raise ValueError(f"Transaction value {v} SOL below alert threshold {min_alert_threshold}")
        
        return v
    
    @field_validator('triggered_at')
    @classmethod
    def validate_triggered_time_realistic(cls, v: datetime) -> datetime:
        """Validate alert trigger time is realistic."""
        # Alert should not be from far future or too far in past
        max_past_hours = 24  # Max 24 hours old
        max_future_minutes = 5  # Allow 5 minutes for clock skew
        
        now = datetime.now()
        min_time = now - timedelta(hours=max_past_hours)
        max_time = now + timedelta(minutes=max_future_minutes)
        
        if v < min_time:
            raise ValueError(f"Alert triggered time {v} is too far in the past")
        
        if v > max_time:
            raise ValueError(f"Alert triggered time {v} is in the future")
        
        return v
    
    @field_validator('expires_at')
    @classmethod
    def validate_expiry_after_trigger(cls, v: Optional[datetime], info) -> Optional[datetime]:
        """Validate expiry time is after trigger time."""
        if v is None:
            return v
        
        if 'triggered_at' in info.data and v <= info.data['triggered_at']:
            raise ValueError("Alert expiry time must be after trigger time")
        
        return v
    
    def is_in_cooldown(self) -> bool:
        """Check if alert is within cooldown period for same wallet."""
        if self.last_alert_same_wallet is None:
            return False
        
        cooldown_end = self.last_alert_same_wallet + timedelta(hours=self.cooldown_hours)
        return datetime.now() < cooldown_end
    
    def calculate_severity(self) -> AlertSeverity:
        """Calculate alert severity based on transaction characteristics."""
        # Base severity on transaction value
        if self.total_value_sol >= 100.0:
            severity = AlertSeverity.CRITICAL
        elif self.total_value_sol >= 50.0:
            severity = AlertSeverity.HIGH
        elif self.total_value_sol >= 20.0:
            severity = AlertSeverity.MEDIUM
        else:
            severity = AlertSeverity.LOW
        
        # Increase severity for collection sweeps
        if self.alert_type == WhaleAlertType.COLLECTION_SWEEP and self.nft_count >= 10:
            if severity == AlertSeverity.LOW:
                severity = AlertSeverity.MEDIUM
            elif severity == AlertSeverity.MEDIUM:
                severity = AlertSeverity.HIGH
        
        # Increase severity for volume impact
        if self.volume_impact_percentage and self.volume_impact_percentage >= 20.0:
            if severity in [AlertSeverity.LOW, AlertSeverity.MEDIUM]:
                severity = AlertSeverity.HIGH
        
        return severity
    
    def get_display_title(self) -> str:
        """Generate user-friendly display title."""
        if self.title:
            return self.title
        
        # Generate based on alert type
        value_str = f"{self.total_value_sol:.1f} SOL"
        
        if self.alert_type == WhaleAlertType.LARGE_PURCHASE:
            return f"🐋 Whale purchased {self.nft_count} NFT{'s' if self.nft_count > 1 else ''} for {value_str}"
        elif self.alert_type == WhaleAlertType.LARGE_SALE:
            return f"🐋 Whale sold {self.nft_count} NFT{'s' if self.nft_count > 1 else ''} for {value_str}"
        elif self.alert_type == WhaleAlertType.COLLECTION_SWEEP:
            return f"🧹 Collection sweep: {self.nft_count} NFTs for {value_str}"
        elif self.alert_type == WhaleAlertType.NEW_WHALE:
            return f"🆕 New whale detected with {value_str} purchase"
        else:
            return f"🐋 Whale activity: {value_str}"
    
    def get_premium_description(self) -> Optional[str]:
        """Get description of price premium/discount."""
        if self.price_premium_percentage is None:
            return None
        
        if self.price_premium_percentage > 0:
            return f"+{self.price_premium_percentage:.1f}% above floor"
        elif self.price_premium_percentage < 0:
            return f"{self.price_premium_percentage:.1f}% below floor"
        else:
            return "At floor price"
    
    def should_notify(self) -> bool:
        """Check if alert should trigger notifications."""
        # Don't notify if already sent
        if self.notification_sent:
            return False
        
        # Don't notify if suppressed or expired
        if self.status in [AlertStatus.SUPPRESSED, AlertStatus.EXPIRED]:
            return False
        
        # Don't notify if in cooldown
        if self.is_in_cooldown():
            return False
        
        # Only notify for medium+ severity
        return self.severity in [AlertSeverity.MEDIUM, AlertSeverity.HIGH, AlertSeverity.CRITICAL]
    
    def get_age_minutes(self) -> int:
        """Get alert age in minutes."""
        return int((datetime.now() - self.triggered_at).total_seconds() / 60)
    
    def is_recent(self, minutes: int = 60) -> bool:
        """Check if alert is recent (within specified minutes)."""
        return self.get_age_minutes() <= minutes

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "alert_id": "550e8400-e29b-41d4-a716-446655440000",
                "transaction_signature": "5KJp9QjRgFryfbTTv8RtWGGCaYJJ7xBqQGY7FoXbpzSFwWrVvH3K7JX8QgGH1AjSBUL6Vh6Y8N3xAhVkCJ9wGxRr",
                "wallet_address": "ByXB7zV4TKa3xxC6PJxEQgm7cZxvXHU9C5qhHdKQN4R4",
                "alert_type": "large_purchase",
                "nft_count": 3,
                "total_value_sol": 45.5,
                "collection_id": "mad-lads-collection",
                "triggered_at": "2023-04-20T16:45:30Z",
                "notification_sent": True,
                "severity": "high",
                "title": "🐋 Whale purchased 3 NFTs for 45.5 SOL",
                "description": "Large purchase detected: whale acquired 3 Mad Lads NFTs in single transaction",
                "marketplace": "Magic Eden",
                "floor_price_at_time": 12.0,
                "price_premium_percentage": 26.4,
                "whale_total_volume": 342.5,
                "volume_impact_percentage": 8.2
            }
        }


# Response models for API endpoints
class WhaleAlertSummary(BaseModel):
    """Simplified alert model for lists."""
    
    alert_id: str
    alert_type: str
    wallet_address: str
    total_value_sol: float
    nft_count: int
    collection_id: str
    triggered_at: datetime
    severity: str
    title: str


class WhaleActivityFeed(BaseModel):
    """Feed item for whale activity streams."""
    
    alert_id: str
    alert_type: str
    wallet_address: str
    collection_name: str
    action_description: str  # Human readable action
    value_sol: float
    nft_count: int
    timestamp: datetime
    marketplace: Optional[str] = None
    premium_percentage: Optional[float] = None


# Database models
class WhaleAlertTable(BaseModel):
    """BigQuery table model for whale alerts."""
    
    alert_id: str
    transaction_signature: str
    wallet_address: str
    alert_type: str
    nft_count: int
    total_value_sol: float
    collection_id: str
    triggered_at: datetime
    notification_sent: bool
    severity: str
    status: str
    title: str
    description: str
    marketplace: Optional[str] = None
    floor_price_at_time: Optional[float] = None
    price_premium_percentage: Optional[float] = None
    whale_total_volume: Optional[float] = None
    volume_impact_percentage: Optional[float] = None
    cooldown_hours: int
    expires_at: Optional[datetime] = None
    
    # BigQuery specific fields
    ingested_at: datetime = Field(default_factory=datetime.now)
    partition_date: str = Field(
        default_factory=lambda: datetime.now().strftime('%Y-%m-%d')
    )


# Configuration models
class WhaleAlertThresholds(BaseModel):
    """Configurable thresholds for whale alert generation."""
    
    min_transaction_value_sol: float = Field(default=10.0, ge=0.0)
    large_purchase_threshold_sol: float = Field(default=25.0, ge=0.0)
    large_sale_threshold_sol: float = Field(default=25.0, ge=0.0)
    collection_sweep_min_nfts: int = Field(default=5, ge=1)
    volume_spike_multiplier: float = Field(default=3.0, ge=1.0)
    new_whale_volume_threshold: float = Field(default=100.0, ge=0.0)
    new_whale_nft_threshold: int = Field(default=50, ge=1)
    default_cooldown_hours: int = Field(default=6, ge=0, le=168)
    
    # Severity thresholds
    critical_threshold_sol: float = Field(default=100.0, ge=0.0)
    high_threshold_sol: float = Field(default=50.0, ge=0.0)
    medium_threshold_sol: float = Field(default=20.0, ge=0.0)


# Analytics models
class WhaleAlertStats(BaseModel):
    """Statistics about whale alerts for dashboard."""
    
    total_alerts_24h: int = 0
    total_alerts_7d: int = 0
    total_value_24h: float = 0.0
    total_value_7d: float = 0.0
    top_alert_types: List[Dict[str, Any]] = Field(default_factory=list)
    most_active_whales: List[Dict[str, Any]] = Field(default_factory=list)
    average_alert_value: float = 0.0
    alerts_by_severity: Dict[str, int] = Field(default_factory=dict)