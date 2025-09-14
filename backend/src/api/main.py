"""ChainWeave FastAPI main application.

REST API endpoints for ChainWeave NFT analytics:
- Collection data and metrics
- Whale alerts and activity
- Wallet profiles and analysis
- Real-time market data
"""

from fastapi import FastAPI, HTTPException, Depends, Query, Path, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
import asyncio
import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
import uvicorn

# Import services
from services.dashboard_data_service import DashboardDataService
from services.analytics_engine import AnalyticsEngine
from services.whale_detector import WhaleDetector
from services.cache_manager import CacheManager
from services.collection_tracker import CollectionTracker
from services.helius_client import HeliusClient
from services.bigquery_writer import BigQueryWriter

# Import models for API responses
from models.nft_collection import NFTCollection
from models.whale_alert import WhaleAlert, AlertType, AlertSeverity
from models.market_analytics import MarketAnalytics, MetricType
from models.wallet_profile import WalletProfile

logger = logging.getLogger(__name__)

# API Response Models
class APIResponse(BaseModel):
    """Standard API response wrapper."""
    success: bool = True
    data: Any = None
    message: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Error response model."""
    success: bool = False
    error: str
    details: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class CollectionSummaryResponse(BaseModel):
    """Collection summary API response."""
    collection_id: str
    name: str
    floor_price: float
    volume_24h: float
    market_cap: float
    holders_count: int
    transactions_24h: int
    price_change_24h_pct: float
    verified: bool
    last_updated: datetime


class WhaleAlertResponse(BaseModel):
    """Whale alert API response."""
    alert_id: str
    wallet_address: str
    alert_type: str
    severity: str
    amount_sol: float
    collection_id: Optional[str]
    collection_name: Optional[str]
    triggered_at: datetime
    details: Dict[str, Any]


class MarketSummaryResponse(BaseModel):
    """Market summary API response."""
    total_volume_24h: float
    volume_change_24h_pct: float
    total_collections: int
    active_collections_24h: int
    unique_wallets_24h: int
    avg_transaction_size: float
    market_trend: str
    whale_alerts_24h: int
    last_updated: datetime


# API Configuration
class APIConfig:
    """API configuration."""
    def __init__(self):
        self.project_id = "chainweave-analytics"  # Configure from environment
        self.dataset_id = "chainweave"
        self.helius_api_key = "your-helius-api-key"  # Configure from environment
        self.redis_url = None  # Configure from environment
        self.cache_ttl_minutes = 5
        self.rate_limit_requests = 1000
        self.rate_limit_window = 3600  # 1 hour


# Initialize FastAPI app
def create_app(config: APIConfig = None) -> FastAPI:
    """Create and configure FastAPI application."""
    
    if config is None:
        config = APIConfig()
    
    app = FastAPI(
        title="ChainWeave NFT Analytics API",
        description="Real-time NFT analytics and whale tracking for Solana",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Initialize services
    dashboard_service = DashboardDataService(config.project_id, config.dataset_id)
    analytics_engine = AnalyticsEngine(config.project_id, config.dataset_id)
    whale_detector = WhaleDetector(config.project_id, config.dataset_id)
    cache_manager = CacheManager(redis_url=config.redis_url)
    
    if config.helius_api_key:
        helius_client = HeliusClient(config.helius_api_key)
        collection_tracker = CollectionTracker(helius_client, BigQueryWriter(config.project_id, config.dataset_id))
    else:
        helius_client = None
        collection_tracker = None
    
    # Dependency injection
    def get_dashboard_service() -> DashboardDataService:
        return dashboard_service
    
    def get_analytics_engine() -> AnalyticsEngine:
        return analytics_engine
    
    def get_whale_detector() -> WhaleDetector:
        return whale_detector
    
    def get_cache_manager() -> CacheManager:
        return cache_manager
    
    def get_collection_tracker() -> Optional[CollectionTracker]:
        return collection_tracker
    
    # Error handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=exc.detail,
                details=str(exc)
            ).dict()
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc):
        logger.error(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="Internal server error",
                details=str(exc)
            ).dict()
        )
    
    # Health check endpoint
    @app.get("/health", response_model=APIResponse)
    async def health_check():
        """Health check endpoint."""
        try:
            # Test database connectivity
            collections = await dashboard_service.get_active_collection_ids()
            
            health_status = {
                "status": "healthy",
                "services": {
                    "database": "connected",
                    "cache": "active" if cache_manager else "disabled",
                    "helius": "connected" if helius_client else "disabled"
                },
                "active_collections": len(collections)
            }
            
            return APIResponse(data=health_status, message="Service is healthy")
            
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")
    
    # Market data endpoints
    @app.get("/api/v1/market/summary", response_model=APIResponse)
    async def get_market_summary(
        dashboard: DashboardDataService = Depends(get_dashboard_service),
        cache: CacheManager = Depends(get_cache_manager)
    ):
        """Get global market summary."""
        try:
            cache_key = "api_market_summary"
            
            # Try cache first
            cached_data = await cache.get(cache_key)
            if cached_data:
                return APIResponse(data=cached_data, message="Data from cache")
            
            # Load fresh data
            summary = await dashboard.get_global_market_summary()
            if not summary:
                raise HTTPException(status_code=404, detail="Market summary not available")
            
            # Transform to response model
            response_data = MarketSummaryResponse(
                total_volume_24h=summary.get('total_volume_24h', 0),
                volume_change_24h_pct=summary.get('volume_change_24h_pct', 0),
                total_collections=summary.get('total_collections', 0),
                active_collections_24h=summary.get('active_collections_24h', 0),
                unique_wallets_24h=summary.get('unique_wallets_24h', 0),
                avg_transaction_size=summary.get('avg_transaction_size', 0),
                market_trend=summary.get('market_trend', 'neutral'),
                whale_alerts_24h=summary.get('whale_alerts_24h', 0),
                last_updated=datetime.now()
            )
            
            # Cache result
            await cache.set(cache_key, response_data.dict(), ttl_minutes=config.cache_ttl_minutes)
            
            return APIResponse(data=response_data, message="Market summary retrieved")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get market summary: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve market summary")
    
    @app.get("/api/v1/market/trending", response_model=APIResponse)
    async def get_trending_collections(
        limit: int = Query(20, ge=1, le=100, description="Number of collections to return"),
        days: int = Query(7, ge=1, le=30, description="Time range in days"),
        min_volume: float = Query(10.0, ge=0, description="Minimum volume filter"),
        dashboard: DashboardDataService = Depends(get_dashboard_service)
    ):
        """Get trending collections by volume."""
        try:
            collections = await dashboard.get_top_collections_by_volume(days=days, limit=limit)
            
            # Filter by minimum volume
            filtered_collections = [c for c in collections if c.get('volume', 0) >= min_volume]
            
            return APIResponse(
                data=filtered_collections,
                message=f"Retrieved {len(filtered_collections)} trending collections",
                metadata={"limit": limit, "days": days, "min_volume": min_volume}
            )
            
        except Exception as e:
            logger.error(f"Failed to get trending collections: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve trending collections")
    
    # Collection endpoints
    @app.get("/api/v1/collections", response_model=APIResponse)
    async def get_collections(
        limit: int = Query(50, ge=1, le=500, description="Number of collections to return"),
        offset: int = Query(0, ge=0, description="Pagination offset"),
        dashboard: DashboardDataService = Depends(get_dashboard_service)
    ):
        """Get list of collections."""
        try:
            # Get top collections by volume
            collections = await dashboard.get_top_collections_by_volume(limit=limit + offset)
            
            # Apply pagination
            paginated_collections = collections[offset:offset + limit]
            
            return APIResponse(
                data=paginated_collections,
                message=f"Retrieved {len(paginated_collections)} collections",
                metadata={"limit": limit, "offset": offset, "total_available": len(collections)}
            )
            
        except Exception as e:
            logger.error(f"Failed to get collections: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve collections")
    
    @app.get("/api/v1/collections/{collection_id}", response_model=APIResponse)
    async def get_collection_details(
        collection_id: str = Path(..., description="Collection ID"),
        dashboard: DashboardDataService = Depends(get_dashboard_service),
        cache: CacheManager = Depends(get_cache_manager)
    ):
        """Get detailed information about a specific collection."""
        try:
            cache_key = f"api_collection_{collection_id}"
            
            # Try cache first
            cached_data = await cache.get(cache_key)
            if cached_data:
                return APIResponse(data=cached_data, message="Data from cache")
            
            # Load collection summary
            summary = await dashboard.get_collection_summary(collection_id)
            if not summary:
                raise HTTPException(status_code=404, detail="Collection not found")
            
            # Load additional data
            recent_transactions = await dashboard.get_recent_transactions(collection_id, limit=10)
            top_holders = await dashboard.get_top_holders(collection_id, limit=10)
            price_history = await dashboard.get_price_history(collection_id, days=30)
            
            # Combine data
            collection_data = {
                **summary,
                "recent_transactions": recent_transactions,
                "top_holders": top_holders,
                "price_history": price_history
            }
            
            # Cache result
            await cache.set(cache_key, collection_data, ttl_minutes=config.cache_ttl_minutes)
            
            return APIResponse(data=collection_data, message="Collection details retrieved")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get collection details: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve collection details")
    
    @app.get("/api/v1/collections/{collection_id}/transactions", response_model=APIResponse)
    async def get_collection_transactions(
        collection_id: str = Path(..., description="Collection ID"),
        limit: int = Query(100, ge=1, le=1000, description="Number of transactions to return"),
        dashboard: DashboardDataService = Depends(get_dashboard_service)
    ):
        """Get recent transactions for a collection."""
        try:
            transactions = await dashboard.get_recent_transactions(collection_id, limit=limit)
            
            return APIResponse(
                data=transactions,
                message=f"Retrieved {len(transactions)} transactions",
                metadata={"collection_id": collection_id, "limit": limit}
            )
            
        except Exception as e:
            logger.error(f"Failed to get collection transactions: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve transactions")
    
    @app.get("/api/v1/collections/{collection_id}/holders", response_model=APIResponse)
    async def get_collection_holders(
        collection_id: str = Path(..., description="Collection ID"),
        limit: int = Query(50, ge=1, le=500, description="Number of holders to return"),
        dashboard: DashboardDataService = Depends(get_dashboard_service)
    ):
        """Get top holders for a collection."""
        try:
            holders = await dashboard.get_top_holders(collection_id, limit=limit)
            
            return APIResponse(
                data=holders,
                message=f"Retrieved {len(holders)} top holders",
                metadata={"collection_id": collection_id, "limit": limit}
            )
            
        except Exception as e:
            logger.error(f"Failed to get collection holders: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve holders")
    
    # Whale activity endpoints
    @app.get("/api/v1/whales/alerts", response_model=APIResponse)
    async def get_whale_alerts(
        limit: int = Query(100, ge=1, le=1000, description="Number of alerts to return"),
        severity: Optional[str] = Query(None, description="Filter by severity"),
        alert_type: Optional[str] = Query(None, description="Filter by alert type"),
        collection_id: Optional[str] = Query(None, description="Filter by collection"),
        dashboard: DashboardDataService = Depends(get_dashboard_service)
    ):
        """Get recent whale alerts."""
        try:
            # Get alerts
            alerts = await dashboard.get_recent_whale_alerts(limit=limit)
            
            # Apply filters
            if severity:
                alerts = [a for a in alerts if a.get('severity') == severity]
            
            if alert_type:
                alerts = [a for a in alerts if a.get('alert_type') == alert_type]
            
            if collection_id:
                alerts = [a for a in alerts if a.get('collection_id') == collection_id]
            
            # Transform to response format
            response_alerts = [
                WhaleAlertResponse(
                    alert_id=alert['alert_id'],
                    wallet_address=alert['wallet_address'],
                    alert_type=alert['alert_type'],
                    severity=alert['severity'],
                    amount_sol=alert['amount_sol'],
                    collection_id=alert.get('collection_id'),
                    collection_name=alert.get('collection_name'),
                    triggered_at=datetime.fromisoformat(alert['triggered_at'].replace('Z', '+00:00')),
                    details=alert.get('details', {})
                ) for alert in alerts
            ]
            
            return APIResponse(
                data=[alert.dict() for alert in response_alerts],
                message=f"Retrieved {len(response_alerts)} whale alerts",
                metadata={
                    "filters": {"severity": severity, "alert_type": alert_type, "collection_id": collection_id},
                    "total_before_filters": len(alerts) if not any([severity, alert_type, collection_id]) else None
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to get whale alerts: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve whale alerts")
    
    @app.get("/api/v1/whales/wallets/{wallet_address}", response_model=APIResponse)
    async def get_wallet_profile(
        wallet_address: str = Path(..., description="Wallet address"),
        analytics: AnalyticsEngine = Depends(get_analytics_engine)
    ):
        """Get wallet profile and analytics."""
        try:
            # Calculate wallet profile
            profile = await analytics.calculate_wallet_profile(
                wallet_address=wallet_address,
                as_of_date=datetime.now().date()
            )
            
            if not profile:
                raise HTTPException(status_code=404, detail="Wallet profile not found or insufficient activity")
            
            return APIResponse(
                data=profile.dict(),
                message="Wallet profile retrieved"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get wallet profile: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve wallet profile")
    
    # Analytics endpoints
    @app.get("/api/v1/analytics/metrics/{collection_id}", response_model=APIResponse)
    async def get_collection_metrics(
        collection_id: str = Path(..., description="Collection ID"),
        metric_type: Optional[str] = Query(None, description="Specific metric type"),
        days: int = Query(30, ge=1, le=365, description="Number of days of history"),
        dashboard: DashboardDataService = Depends(get_dashboard_service)
    ):
        """Get analytics metrics for a collection."""
        try:
            # Get historical metrics
            metrics = await dashboard.get_historical_metrics(collection_id, days=days)
            
            # Filter by metric type if specified
            if metric_type and metric_type in metrics:
                metrics = {metric_type: metrics[metric_type]}
            
            return APIResponse(
                data=metrics,
                message=f"Retrieved metrics for {collection_id}",
                metadata={"collection_id": collection_id, "days": days, "metric_type": metric_type}
            )
            
        except Exception as e:
            logger.error(f"Failed to get collection metrics: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve metrics")
    
    # Administrative endpoints
    @app.post("/api/v1/admin/collections/{collection_id}/track", response_model=APIResponse)
    async def add_collection_tracking(
        collection_id: str = Path(..., description="Collection ID to track"),
        backfill_days: int = Query(7, ge=0, le=365, description="Days of historical data to backfill"),
        background_tasks: BackgroundTasks,
        tracker: Optional[CollectionTracker] = Depends(get_collection_tracker)
    ):
        """Add a collection for tracking (admin endpoint)."""
        if not tracker:
            raise HTTPException(status_code=503, detail="Collection tracking service not available")
        
        try:
            # Add collection tracking in background
            background_tasks.add_task(
                tracker.add_collection,
                collection_id,
                backfill_days
            )
            
            return APIResponse(
                message=f"Collection {collection_id} queued for tracking",
                metadata={"collection_id": collection_id, "backfill_days": backfill_days}
            )
            
        except Exception as e:
            logger.error(f"Failed to add collection tracking: {e}")
            raise HTTPException(status_code=500, detail="Failed to add collection tracking")
    
    @app.get("/api/v1/admin/stats", response_model=APIResponse)
    async def get_system_stats(
        dashboard: DashboardDataService = Depends(get_dashboard_service),
        cache: CacheManager = Depends(get_cache_manager)
    ):
        """Get system statistics (admin endpoint)."""
        try:
            # Get cache info
            cache_info = await cache.get_cache_info()
            
            # Get database stats
            total_collections = await dashboard.get_total_collections_count()
            active_collections = len(await dashboard.get_active_collection_ids())
            
            stats = {
                "database": {
                    "total_collections": total_collections,
                    "active_collections": active_collections
                },
                "cache": cache_info,
                "system": {
                    "timestamp": datetime.now().isoformat(),
                    "uptime_seconds": None  # Would implement uptime tracking
                }
            }
            
            return APIResponse(data=stats, message="System statistics retrieved")
            
        except Exception as e:
            logger.error(f"Failed to get system stats: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve system statistics")
    
    return app


# Create app instance
app = create_app()

# Custom OpenAPI
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="ChainWeave NFT Analytics API",
        version="1.0.0",
        description="Real-time NFT analytics and whale tracking for Solana blockchain",
        routes=app.routes,
    )
    
    # Add API key security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key"
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Health check at root
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "ChainWeave NFT Analytics API",
        "version": "1.0.0",
        "description": "Real-time NFT analytics and whale tracking for Solana",
        "docs_url": "/docs",
        "health_url": "/health",
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )