"""Webhook receiver service for ChainWeave.

FastAPI-based service for receiving and processing Helius NFT transaction webhooks:
- Real-time transaction ingestion
- Webhook validation and authentication
- Queue management for high throughput
- Health monitoring and metrics
"""

import asyncio
import logging
import json
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import uuid

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
import uvicorn

# Queue management
try:
    import aioredis
    from redis.exceptions import RedisError
    REDIS_AVAILABLE = True
except ImportError:
    aioredis = None
    REDIS_AVAILABLE = False

from models.transaction import Transaction, EventType
from models.whale_alert import WhaleAlert
from services.bigquery_writer import BigQueryWriter
from services.whale_detector import WhaleDetector
from services.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class WebhookPayload(BaseModel):
    """Helius webhook payload structure."""
    accountData: List[Dict[str, Any]]
    blockchain: str
    description: str
    events: Dict[str, Any]
    fee: int
    feePayer: str
    instructions: List[Dict[str, Any]]
    nativeTransfers: List[Dict[str, Any]]
    signature: str
    slot: int
    source: str
    timestamp: int
    tokenTransfers: List[Dict[str, Any]]
    transactionError: Optional[str] = None
    type: str


class WebhookStats(BaseModel):
    """Webhook processing statistics."""
    total_received: int = 0
    total_processed: int = 0
    total_errors: int = 0
    queue_size: int = 0
    last_processed: Optional[datetime] = None
    processing_rate_per_minute: float = 0.0
    error_rate_percentage: float = 0.0


class WebhookReceiver:
    """Main webhook receiver service."""
    
    def __init__(
        self,
        project_id: str,
        dataset_id: str,
        webhook_secret: Optional[str] = None,
        redis_url: Optional[str] = None,
        queue_name: str = "chainweave_webhook_queue",
        max_queue_size: int = 10000
    ):
        """Initialize webhook receiver."""
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.webhook_secret = webhook_secret
        self.queue_name = queue_name
        self.max_queue_size = max_queue_size
        
        # Initialize services
        self.bq_writer = BigQueryWriter(project_id, dataset_id)
        self.whale_detector = WhaleDetector(project_id, dataset_id)
        self.cache_manager = CacheManager()
        
        # Redis queue (optional)
        self.redis_client = None
        if REDIS_AVAILABLE and redis_url:
            self.redis_client = aioredis.from_url(redis_url)
        
        # In-memory queue fallback
        self.memory_queue = asyncio.Queue(maxsize=max_queue_size)
        
        # Statistics tracking
        self.stats = WebhookStats()
        self.processing_times = []
        
        # FastAPI app
        self.app = FastAPI(
            title="ChainWeave Webhook Receiver",
            description="Real-time NFT transaction webhook processing",
            version="1.0.0"
        )
        
        self._setup_routes()
        self._setup_middleware()
        
        # Background processor task
        self.processor_task = None
        self.is_processing = False
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.post("/webhook/helius")
        async def receive_helius_webhook(
            request: Request,
            background_tasks: BackgroundTasks
        ):
            """Receive and validate Helius webhook."""
            try:
                # Get raw body for signature verification
                body = await request.body()
                headers = dict(request.headers)
                
                # Verify webhook signature if secret is configured
                if self.webhook_secret:
                    if not self._verify_webhook_signature(body, headers):
                        raise HTTPException(status_code=401, detail="Invalid webhook signature")
                
                # Parse JSON payload
                try:
                    payload_data = json.loads(body)
                    webhook_payload = WebhookPayload(**payload_data)
                except (json.JSONDecodeError, ValidationError) as e:
                    logger.error(f"Invalid webhook payload: {e}")
                    raise HTTPException(status_code=400, detail="Invalid payload format")
                
                # Queue for processing
                queue_success = await self._queue_webhook(webhook_payload)
                if not queue_success:
                    raise HTTPException(status_code=503, detail="Queue full, try again later")
                
                # Update stats
                self.stats.total_received += 1
                
                # Start background processing if not already running
                if not self.is_processing:
                    background_tasks.add_task(self._start_processing)
                
                return {"status": "received", "queued": True}
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Webhook processing error: {e}")
                self.stats.total_errors += 1
                raise HTTPException(status_code=500, detail="Internal processing error")
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            try:
                # Test BigQuery connection
                bq_healthy = True
                try:
                    # Simple query to test connection
                    from google.cloud import bigquery
                    client = bigquery.Client(project=self.project_id)
                    query = f"SELECT 1 as test FROM `{self.project_id}.{self.dataset_id}.nft_collections` LIMIT 1"
                    list(client.query(query))
                except Exception as e:
                    logger.warning(f"BigQuery health check failed: {e}")
                    bq_healthy = False
                
                # Test Redis connection
                redis_healthy = True
                if self.redis_client:
                    try:
                        await self.redis_client.ping()
                    except Exception as e:
                        logger.warning(f"Redis health check failed: {e}")
                        redis_healthy = False
                
                # Calculate queue size
                queue_size = await self._get_queue_size()
                
                health_status = {
                    "status": "healthy" if bq_healthy else "degraded",
                    "timestamp": datetime.now().isoformat(),
                    "services": {
                        "bigquery": "healthy" if bq_healthy else "unhealthy",
                        "redis": "healthy" if redis_healthy else "unhealthy" if self.redis_client else "disabled",
                        "queue": "healthy" if queue_size < self.max_queue_size * 0.8 else "high_load"
                    },
                    "queue_size": queue_size,
                    "processing": self.is_processing
                }
                
                status_code = 200 if bq_healthy else 503
                return JSONResponse(content=health_status, status_code=status_code)
                
            except Exception as e:
                logger.error(f"Health check error: {e}")
                return JSONResponse(
                    content={"status": "error", "message": str(e)},
                    status_code=500
                )
        
        @self.app.get("/stats")
        async def get_stats():
            """Get webhook processing statistics."""
            try:
                # Calculate processing rate
                if self.processing_times:
                    recent_times = [t for t in self.processing_times if t > datetime.now() - timedelta(minutes=5)]
                    self.stats.processing_rate_per_minute = len(recent_times) * 12  # 5-min windows in hour
                
                # Calculate error rate
                if self.stats.total_received > 0:
                    self.stats.error_rate_percentage = (self.stats.total_errors / self.stats.total_received) * 100
                
                # Get current queue size
                self.stats.queue_size = await self._get_queue_size()
                
                return self.stats.dict()
                
            except Exception as e:
                logger.error(f"Stats error: {e}")
                raise HTTPException(status_code=500, detail="Failed to get stats")
        
        @self.app.post("/process/trigger")
        async def trigger_processing(background_tasks: BackgroundTasks):
            """Manually trigger webhook processing."""
            if not self.is_processing:
                background_tasks.add_task(self._start_processing)
                return {"status": "processing_started"}
            else:
                return {"status": "already_processing"}
        
        @self.app.get("/queue/size")
        async def get_queue_size():
            """Get current queue size."""
            size = await self._get_queue_size()
            return {"queue_size": size}
        
        @self.app.delete("/queue/clear")
        async def clear_queue():
            """Clear the processing queue (admin endpoint)."""
            try:
                cleared_count = 0
                
                # Clear Redis queue
                if self.redis_client:
                    cleared_count = await self.redis_client.llen(self.queue_name)
                    await self.redis_client.delete(self.queue_name)
                
                # Clear memory queue
                memory_cleared = 0
                try:
                    while True:
                        self.memory_queue.get_nowait()
                        memory_cleared += 1
                except asyncio.QueueEmpty:
                    pass
                
                total_cleared = cleared_count + memory_cleared
                return {"cleared_items": total_cleared}
                
            except Exception as e:
                logger.error(f"Queue clear error: {e}")
                raise HTTPException(status_code=500, detail="Failed to clear queue")
    
    def _setup_middleware(self):
        """Setup FastAPI middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _verify_webhook_signature(self, body: bytes, headers: Dict[str, str]) -> bool:
        """Verify Helius webhook signature."""
        if not self.webhook_secret:
            return True
        
        signature = headers.get("x-helius-signature") or headers.get("X-Helius-Signature")
        if not signature:
            logger.warning("Missing webhook signature")
            return False
        
        # Calculate expected signature
        expected_signature = hmac.new(
            self.webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        return hmac.compare_digest(signature, expected_signature)
    
    async def _queue_webhook(self, payload: WebhookPayload) -> bool:
        """Queue webhook for processing."""
        try:
            # Try Redis first
            if self.redis_client:
                try:
                    queue_size = await self.redis_client.llen(self.queue_name)
                    if queue_size >= self.max_queue_size:
                        logger.warning("Redis queue is full")
                        return False
                    
                    await self.redis_client.lpush(self.queue_name, payload.json())
                    return True
                    
                except RedisError as e:
                    logger.warning(f"Redis queue failed, using memory: {e}")
            
            # Fallback to memory queue
            try:
                self.memory_queue.put_nowait(payload)
                return True
            except asyncio.QueueFull:
                logger.warning("Memory queue is full")
                return False
                
        except Exception as e:
            logger.error(f"Failed to queue webhook: {e}")
            return False
    
    async def _get_queue_size(self) -> int:
        """Get current queue size."""
        size = 0
        
        # Redis queue size
        if self.redis_client:
            try:
                size += await self.redis_client.llen(self.queue_name)
            except RedisError:
                pass
        
        # Memory queue size
        size += self.memory_queue.qsize()
        
        return size
    
    async def _start_processing(self):
        """Start background webhook processing."""
        if self.is_processing:
            return
        
        self.is_processing = True
        logger.info("Starting webhook processing")
        
        try:
            while True:
                # Get webhook from queue
                webhook_payload = await self._dequeue_webhook()
                if not webhook_payload:
                    break  # No more items to process
                
                # Process the webhook
                await self._process_webhook(webhook_payload)
                
                # Track processing time
                self.processing_times.append(datetime.now())
                
                # Keep only recent processing times
                cutoff = datetime.now() - timedelta(hours=1)
                self.processing_times = [t for t in self.processing_times if t > cutoff]
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(0.01)
                
        except Exception as e:
            logger.error(f"Processing error: {e}")
        finally:
            self.is_processing = False
            logger.info("Webhook processing stopped")
    
    async def _dequeue_webhook(self) -> Optional[WebhookPayload]:
        """Get next webhook from queue."""
        try:
            # Try Redis first
            if self.redis_client:
                try:
                    payload_json = await self.redis_client.rpop(self.queue_name)
                    if payload_json:
                        return WebhookPayload.parse_raw(payload_json)
                except RedisError:
                    pass
            
            # Try memory queue
            try:
                return self.memory_queue.get_nowait()
            except asyncio.QueueEmpty:
                return None
                
        except Exception as e:
            logger.error(f"Failed to dequeue webhook: {e}")
            return None
    
    async def _process_webhook(self, payload: WebhookPayload):
        """Process individual webhook payload."""
        start_time = datetime.now()
        
        try:
            # Extract NFT transactions from payload
            transactions = self._extract_transactions(payload)
            
            if not transactions:
                return  # No NFT transactions to process
            
            # Process each transaction
            processed_count = 0
            whale_alerts = []
            
            for transaction_data in transactions:
                try:
                    # Create transaction model
                    transaction = Transaction(**transaction_data)
                    
                    # Write to BigQuery
                    success = await self.bq_writer.write_transaction(transaction)
                    if success:
                        processed_count += 1
                        
                        # Check for whale activity
                        if transaction.price_sol and transaction.price_sol >= 50.0:  # Whale threshold
                            alerts = await self.whale_detector.scan_recent_activity(
                                since=datetime.now() - timedelta(minutes=5)
                            )
                            whale_alerts.extend(alerts)
                    
                except ValidationError as e:
                    logger.warning(f"Invalid transaction data: {e}")
                    self.stats.total_errors += 1
                except Exception as e:
                    logger.error(f"Failed to process transaction: {e}")
                    self.stats.total_errors += 1
            
            # Save whale alerts
            for alert in whale_alerts:
                await self.bq_writer.write_whale_alert(alert)
            
            # Update stats
            self.stats.total_processed += processed_count
            self.stats.last_processed = datetime.now()
            
            # Invalidate related cache
            if processed_count > 0:
                collection_ids = set(t.get('collection_id') for t in transactions if t.get('collection_id'))
                for collection_id in collection_ids:
                    await self.cache_manager.invalidate_related([collection_id])
            
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.debug(f"Processed {processed_count} transactions in {processing_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Webhook processing failed: {e}")
            self.stats.total_errors += 1
    
    def _extract_transactions(self, payload: WebhookPayload) -> List[Dict[str, Any]]:
        """Extract NFT transactions from webhook payload."""
        transactions = []
        
        try:
            # Process token transfers (NFT transactions)
            for transfer in payload.tokenTransfers:
                # Only process NFT transfers (amount = 1 typically)
                if transfer.get('tokenAmount', 0) == 1:
                    
                    # Determine event type
                    if not transfer.get('fromUserAccount'):
                        event_type = EventType.MINT
                    elif not transfer.get('toUserAccount'):
                        event_type = EventType.BURN
                    else:
                        # Check if there's a corresponding SOL transfer (sale)
                        price_sol = self._find_corresponding_price(payload.nativeTransfers, transfer)
                        event_type = EventType.SALE if price_sol else EventType.TRANSFER
                    
                    # Extract marketplace from instructions
                    marketplace = self._extract_marketplace(payload.instructions)
                    
                    # Build transaction data
                    transaction_data = {
                        'transaction_signature': payload.signature,
                        'mint_address': transfer.get('mint', ''),
                        'event_type': event_type,
                        'from_address': transfer.get('fromUserAccount'),
                        'to_address': transfer.get('toUserAccount'),
                        'price_sol': self._find_corresponding_price(payload.nativeTransfers, transfer),
                        'marketplace': marketplace,
                        'timestamp': datetime.fromtimestamp(payload.timestamp),
                        'block_height': payload.slot,
                        'status': 'confirmed',
                        'webhook_timestamp': datetime.now(),
                        'slot_number': payload.slot
                    }
                    
                    transactions.append(transaction_data)
            
        except Exception as e:
            logger.error(f"Failed to extract transactions: {e}")
        
        return transactions
    
    def _find_corresponding_price(self, native_transfers: List[Dict], token_transfer: Dict) -> Optional[float]:
        """Find SOL transfer amount corresponding to NFT transfer."""
        try:
            # Look for SOL transfers between same parties
            from_user = token_transfer.get('fromUserAccount')
            to_user = token_transfer.get('toUserAccount')
            
            for sol_transfer in native_transfers:
                if (sol_transfer.get('fromUserAccount') == from_user and 
                    sol_transfer.get('toUserAccount') == to_user):
                    amount_lamports = sol_transfer.get('amount', 0)
                    return amount_lamports / 1e9  # Convert lamports to SOL
            
            return None
            
        except Exception:
            return None
    
    def _extract_marketplace(self, instructions: List[Dict]) -> Optional[str]:
        """Extract marketplace from transaction instructions."""
        try:
            # Known marketplace program IDs
            marketplace_programs = {
                "M2mx93ekt1fmXSVkTrUL9xVFHkmME8HTUi5Cyc5aF7K": "Magic Eden",
                "1BWutmTvYPwDtmw9abTkS4Ssr8no61spGAvW1X6NDix": "Magic Eden",
                "MEisE1HzehtrDpAAT8PnLHjpSSkRYakotTuJRPjTpo8": "Magic Eden V2",
                "A7p8451kBn8pUBCtKKz4oNwz7j1oUcFKZTmpCBjNWYBz": "OpenSea",
                "TSWAPaqyCSx2KABk68Shruf4rp7CxcNi8hAsbdwmHbN": "Tensor"
            }
            
            for instruction in instructions:
                program_id = instruction.get('programId', '')
                if program_id in marketplace_programs:
                    return marketplace_programs[program_id]
            
            return None
            
        except Exception:
            return None
    
    async def start_server(self, host: str = "0.0.0.0", port: int = 8000):
        """Start the webhook receiver server."""
        logger.info(f"Starting webhook receiver on {host}:{port}")
        
        config = uvicorn.Config(
            app=self.app,
            host=host,
            port=port,
            log_level="info",
            access_log=True
        )
        
        server = uvicorn.Server(config)
        await server.serve()
    
    async def shutdown(self):
        """Graceful shutdown."""
        logger.info("Shutting down webhook receiver")
        
        # Stop processing
        self.is_processing = False
        
        # Close connections
        if self.redis_client:
            await self.redis_client.close()
        
        await self.cache_manager.close()


# Factory function for creating webhook receiver
def create_webhook_receiver(
    project_id: str,
    dataset_id: str,
    webhook_secret: Optional[str] = None,
    redis_url: Optional[str] = None
) -> WebhookReceiver:
    """Create and configure webhook receiver."""
    return WebhookReceiver(
        project_id=project_id,
        dataset_id=dataset_id,
        webhook_secret=webhook_secret,
        redis_url=redis_url
    )