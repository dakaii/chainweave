"""Market Analytics data model for ChainWeave.

This model represents pre-calculated aggregations for dashboard performance optimization.
Implements validation rules from data-model.md specifications.
"""

from datetime import datetime, date
from typing import Optional, Dict, Any, List, Union
from enum import Enum
import json

from pydantic import BaseModel, Field, field_validator


class MetricType(str, Enum):
    """Types of market analytics metrics."""
    DAILY_VOLUME = "daily_volume"
    UNIQUE_TRADERS = "unique_traders"
    AVG_PRICE = "avg_price"
    HOLDERS_COUNT = "holders_count"
    FLOOR_PRICE = "floor_price"
    TOTAL_SALES = "total_sales"
    VOLUME_CHANGE_PCT = "volume_change_pct"
    PRICE_VOLATILITY = "price_volatility"
    LIQUIDITY_SCORE = "liquidity_score"
    WHALE_ACTIVITY = "whale_activity"
    NEW_HOLDERS = "new_holders"
    LOST_HOLDERS = "lost_holders"


class TimeGranularity(str, Enum):
    """Time granularity for metrics."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class MarketAnalytics(BaseModel):
    """Pre-calculated aggregations for dashboard performance optimization."""
    
    metric_id: str = Field(
        ...,
        description="Composite key: {collection_id}_{date}_{metric_type}",
        min_length=1,
        max_length=200
    )
    
    collection_id: Optional[str] = Field(
        default=None,
        description="Collection being measured (null for global metrics)",
        max_length=100
    )
    
    date: date = Field(
        ...,
        description="Aggregation date"
    )
    
    metric_type: MetricType = Field(
        ...,
        description="Type of metric being measured"
    )
    
    metric_value: float = Field(
        ...,
        description="Calculated metric value",
        ge=0.0
    )
    
    created_at: datetime = Field(
        ...,
        description="When aggregation was computed"
    )
    
    # Enhanced analytics fields
    granularity: TimeGranularity = Field(
        default=TimeGranularity.DAILY,
        description="Time granularity of the metric"
    )
    
    previous_value: Optional[float] = Field(
        default=None,
        description="Previous period value for comparison",
        ge=0.0
    )
    
    change_percentage: Optional[float] = Field(
        default=None,
        description="Percentage change from previous period"
    )
    
    sample_size: Optional[int] = Field(
        default=None,
        description="Number of data points used in calculation",
        ge=0
    )
    
    confidence_score: Optional[float] = Field(
        default=None,
        description="Statistical confidence in metric (0-1)",
        ge=0.0,
        le=1.0
    )
    
    # Metadata for complex metrics
    metric_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for metric calculation"
    )
    
    # Data quality indicators
    data_completeness: Optional[float] = Field(
        default=None,
        description="Completeness of underlying data (0-1)",
        ge=0.0,
        le=1.0
    )
    
    outliers_detected: bool = Field(
        default=False,
        description="Whether outliers were detected and handled"
    )
    
    calculation_method: Optional[str] = Field(
        default=None,
        description="Method used for calculation",
        max_length=100
    )

    @field_validator('metric_id')
    @classmethod
    def validate_metric_id_format(cls, v: str) -> str:
        """Validate metric ID follows expected format."""
        if not v:
            raise ValueError("Metric ID cannot be empty")
        
        # Should follow pattern: collection_date_metric or global_date_metric
        parts = v.split('_')
        if len(parts) < 3:
            raise ValueError("Metric ID must have format: {collection}_{date}_{metric_type}")
        
        return v
    
    @field_validator('metric_value')
    @classmethod
    def validate_metric_value_reasonable(cls, v: float, info) -> float:
        """Validate metric value is reasonable for its type."""
        if 'metric_type' not in info.data:
            return v
        
        metric_type = info.data['metric_type']
        
        # Type-specific validations
        if metric_type == MetricType.VOLUME_CHANGE_PCT:
            # Volume change percentage should be within reasonable bounds
            if v < -100.0 or v > 10000.0:  # Allow up to 10000% increase
                raise ValueError(f"Volume change {v}% seems unrealistic")
        
        elif metric_type == MetricType.UNIQUE_TRADERS:
            # Should be whole number for trader counts
            if v != int(v):
                raise ValueError("Unique traders count should be whole number")
        
        elif metric_type == MetricType.HOLDERS_COUNT:
            # Should be whole number for holder counts
            if v != int(v):
                raise ValueError("Holders count should be whole number")
        
        return v
    
    @field_validator('change_percentage')
    @classmethod
    def validate_change_percentage(cls, v: Optional[float]) -> Optional[float]:
        """Validate change percentage is reasonable."""
        if v is None:
            return v
        
        # Allow large changes but flag extreme values
        if abs(v) > 10000.0:  # 10000% change
            raise ValueError(f"Change percentage {v}% seems unrealistic")
        
        return v
    
    @field_validator('created_at')
    @classmethod
    def validate_created_at_not_future(cls, v: datetime) -> datetime:
        """Validate creation timestamp is not in future."""
        if v > datetime.now():
            raise ValueError("Created timestamp cannot be in the future")
        
        return v
    
    def calculate_change_from_previous(self) -> Optional[float]:
        """Calculate percentage change from previous value."""
        if self.previous_value is None or self.previous_value == 0:
            return None
        
        return ((self.metric_value - self.previous_value) / self.previous_value) * 100.0
    
    def get_trend_direction(self) -> str:
        """Get trend direction as string."""
        if self.change_percentage is None:
            return "unknown"
        elif self.change_percentage > 5.0:
            return "up"
        elif self.change_percentage < -5.0:
            return "down"
        else:
            return "stable"
    
    def is_significant_change(self, threshold_pct: float = 10.0) -> bool:
        """Check if change is statistically significant."""
        if self.change_percentage is None:
            return False
        
        return abs(self.change_percentage) >= threshold_pct
    
    def get_display_value(self) -> str:
        """Get formatted value for display."""
        if self.metric_type in [MetricType.UNIQUE_TRADERS, MetricType.HOLDERS_COUNT, MetricType.TOTAL_SALES]:
            return f"{int(self.metric_value):,}"
        elif self.metric_type in [MetricType.DAILY_VOLUME, MetricType.AVG_PRICE, MetricType.FLOOR_PRICE]:
            return f"{self.metric_value:.2f} SOL"
        elif self.metric_type == MetricType.VOLUME_CHANGE_PCT:
            return f"{self.metric_value:+.1f}%"
        else:
            return f"{self.metric_value:.2f}"
    
    def is_fresh(self, max_age_hours: int = 24) -> bool:
        """Check if metric is fresh (recently calculated)."""
        age_hours = (datetime.now() - self.created_at).total_seconds() / 3600
        return age_hours <= max_age_hours

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }
        schema_extra = {
            "example": {
                "metric_id": "mad-lads-collection_2023-04-20_daily_volume",
                "collection_id": "mad-lads-collection",
                "date": "2023-04-20",
                "metric_type": "daily_volume",
                "metric_value": 1250.75,
                "created_at": "2023-04-21T02:00:00Z",
                "granularity": "daily",
                "previous_value": 987.50,
                "change_percentage": 26.7,
                "sample_size": 156,
                "confidence_score": 0.95,
                "data_completeness": 0.98,
                "calculation_method": "sum_aggregation"
            }
        }


# Specialized analytics models
class PricePoint(BaseModel):
    """Price history data point for charts."""
    
    date: date
    floor_price: float = Field(ge=0.0)
    avg_price: float = Field(ge=0.0)
    volume: float = Field(ge=0.0)
    high_price: Optional[float] = Field(default=None, ge=0.0)
    low_price: Optional[float] = Field(default=None, ge=0.0)
    transactions_count: Optional[int] = Field(default=None, ge=0)


class VolumeAnalysis(BaseModel):
    """Volume analysis for collections."""
    
    collection_id: str
    date_range_start: date
    date_range_end: date
    total_volume: float = Field(ge=0.0)
    avg_daily_volume: float = Field(ge=0.0)
    peak_volume: float = Field(ge=0.0)
    peak_volume_date: date
    volume_volatility: float = Field(ge=0.0)
    trend_direction: str  # "increasing", "decreasing", "stable"


class TradingPairAnalysis(BaseModel):
    """Analysis of trading pairs and liquidity."""
    
    collection_id: str
    marketplace: str
    total_volume: float = Field(ge=0.0)
    unique_traders: int = Field(ge=0)
    avg_spread_percentage: float = Field(ge=0.0)
    liquidity_score: float = Field(ge=0.0, le=1.0)
    market_dominance: float = Field(ge=0.0, le=100.0)


class WhaleImpactAnalysis(BaseModel):
    """Analysis of whale impact on collection metrics."""
    
    collection_id: str
    date: date
    whale_volume_sol: float = Field(ge=0.0)
    whale_volume_percentage: float = Field(ge=0.0, le=100.0)
    whale_transactions: int = Field(ge=0)
    non_whale_volume: float = Field(ge=0.0)
    whale_impact_score: float = Field(ge=0.0, le=1.0)
    price_correlation: Optional[float] = Field(default=None, ge=-1.0, le=1.0)


# Response models for API endpoints
class CollectionMetricsSummary(BaseModel):
    """Summary of key metrics for collection dashboard."""
    
    collection_id: str
    collection_name: str
    current_floor: float
    volume_24h: float
    volume_7d: float
    holders_count: int
    unique_traders_24h: int
    avg_price_24h: float
    price_change_24h_pct: float
    volume_change_24h_pct: float
    liquidity_score: float
    last_updated: datetime


class GlobalMarketSummary(BaseModel):
    """Global market summary across all collections."""
    
    total_collections: int
    total_volume_24h: float
    total_transactions_24h: int
    unique_wallets_24h: int
    avg_transaction_size: float
    whale_activity_score: float
    market_trend: str  # "bullish", "bearish", "neutral"
    top_collections_by_volume: List[Dict[str, Any]]
    most_active_whales: List[Dict[str, Any]]


# Database models
class MarketAnalyticsTable(BaseModel):
    """BigQuery table model for market analytics."""
    
    metric_id: str
    collection_id: Optional[str] = None
    date: date
    metric_type: str
    metric_value: float
    created_at: datetime
    granularity: str
    previous_value: Optional[float] = None
    change_percentage: Optional[float] = None
    sample_size: Optional[int] = None
    confidence_score: Optional[float] = None
    metric_metadata: str = Field(default="{}")  # JSON string in BigQuery
    data_completeness: Optional[float] = None
    outliers_detected: bool = False
    calculation_method: Optional[str] = None
    
    # BigQuery specific fields
    partition_date: str = Field(
        default_factory=lambda: date.today().strftime('%Y-%m-%d')
    )
    
    @field_validator('metric_metadata', mode='before')
    @classmethod
    def serialize_metadata(cls, v):
        """Convert metadata dict to JSON string for BigQuery."""
        if isinstance(v, dict):
            return json.dumps(v)
        return v


# Aggregation configuration models
class MetricCalculationConfig(BaseModel):
    """Configuration for metric calculations."""
    
    metric_type: MetricType
    calculation_method: str  # "sum", "avg", "count", "median", etc.
    window_size_hours: int = Field(default=24, ge=1)
    outlier_threshold_std: float = Field(default=3.0, ge=0.0)
    min_sample_size: int = Field(default=5, ge=1)
    confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    update_frequency_hours: int = Field(default=1, ge=1)


class DashboardMetricsConfig(BaseModel):
    """Configuration for dashboard metrics display."""
    
    refresh_interval_minutes: int = Field(default=15, ge=1)
    cache_duration_hours: int = Field(default=1, ge=1)
    max_historical_days: int = Field(default=365, ge=7)
    significant_change_threshold: float = Field(default=10.0, ge=0.0)
    trending_window_hours: int = Field(default=24, ge=1)


# Time series models
class MetricTimeSeries(BaseModel):
    """Time series data for metric visualization."""
    
    collection_id: Optional[str]
    metric_type: MetricType
    granularity: TimeGranularity
    data_points: List[PricePoint] = Field(default_factory=list)
    start_date: date
    end_date: date
    total_points: int = Field(ge=0)
    
    def get_latest_value(self) -> Optional[float]:
        """Get most recent metric value."""
        if not self.data_points:
            return None
        
        # Assuming data_points are sorted by date
        latest_point = max(self.data_points, key=lambda p: p.date)
        return latest_point.avg_price  # Or appropriate field based on metric type
    
    def calculate_trend(self) -> str:
        """Calculate overall trend direction."""
        if len(self.data_points) < 2:
            return "insufficient_data"
        
        # Simple trend calculation using first and last points
        first_value = self.data_points[0].avg_price
        last_value = self.data_points[-1].avg_price
        
        if first_value == 0:
            return "undefined"
        
        change_pct = ((last_value - first_value) / first_value) * 100
        
        if change_pct > 5.0:
            return "increasing"
        elif change_pct < -5.0:
            return "decreasing"
        else:
            return "stable"