"""Data processor service for ChainWeave.

Background service for scheduled analytics processing:
- Periodic metric calculations
- Whale detection scheduling
- Data quality monitoring
- Automated maintenance tasks
"""

import asyncio
import logging
import signal
from datetime import datetime, timedelta, time
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
import json
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

# Optional task queue support
try:
    import celery
    from celery import Celery
    from celery.schedules import crontab
    CELERY_AVAILABLE = True
except ImportError:
    celery = None
    CELERY_AVAILABLE = False

from services.analytics_engine import AnalyticsEngine
from services.whale_detector import WhaleDetector
from services.bigquery_writer import BigQueryWriter
from services.cache_manager import CacheManager
from services.dashboard_data_service import DashboardDataService
from models.market_analytics import MetricType, TimeGranularity
from schemas.migrations import BigQueryMigrationManager

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class TaskResult:
    """Result of task execution."""
    task_name: str
    status: TaskStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    records_processed: int = 0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass 
class ScheduledTask:
    """Configuration for a scheduled task."""
    name: str
    function: Callable
    schedule: str  # cron expression
    priority: TaskPriority = TaskPriority.NORMAL
    timeout_minutes: int = 60
    retry_count: int = 3
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None


class DataProcessor:
    """Main data processing service with scheduling and monitoring."""
    
    def __init__(
        self,
        project_id: str,
        dataset_id: str,
        redis_url: Optional[str] = None,
        enable_celery: bool = False
    ):
        """Initialize data processor."""
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.redis_url = redis_url
        
        # Initialize services
        self.analytics_engine = AnalyticsEngine(project_id, dataset_id)
        self.whale_detector = WhaleDetector(project_id, dataset_id)
        self.bq_writer = BigQueryWriter(project_id, dataset_id)
        self.cache_manager = CacheManager(redis_url=redis_url)
        self.dashboard_service = DashboardDataService(project_id, dataset_id)
        self.migration_manager = BigQueryMigrationManager(project_id, dataset_id)
        
        # Task management
        self.scheduled_tasks: Dict[str, ScheduledTask] = {}
        self.task_history: List[TaskResult] = []
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.max_history_items = 1000
        
        # Control flags
        self.is_running = False
        self.shutdown_event = asyncio.Event()
        
        # Thread pool for CPU-intensive tasks
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Celery app (optional)
        self.celery_app = None
        if CELERY_AVAILABLE and enable_celery:
            self._setup_celery()
        
        # Setup default scheduled tasks
        self._setup_default_tasks()
    
    def _setup_celery(self):
        """Setup Celery for distributed task processing."""
        self.celery_app = Celery(
            'chainweave_processor',
            broker=self.redis_url,
            backend=self.redis_url
        )
        
        # Celery configuration
        self.celery_app.conf.update(
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone='UTC',
            enable_utc=True,
            task_track_started=True,
            task_time_limit=3600,  # 1 hour
            worker_prefetch_multiplier=1,
        )
    
    def _setup_default_tasks(self):
        """Setup default scheduled tasks."""
        
        # Daily metrics calculation (every day at 2 AM)
        self.schedule_task(
            name="daily_metrics_calculation",
            function=self._calculate_daily_metrics,
            schedule="0 2 * * *",  # Daily at 2 AM
            priority=TaskPriority.HIGH,
            timeout_minutes=120
        )
        
        # Whale detection (every 15 minutes)
        self.schedule_task(
            name="whale_detection",
            function=self._detect_whale_activity,
            schedule="*/15 * * * *",  # Every 15 minutes
            priority=TaskPriority.HIGH,
            timeout_minutes=30
        )
        
        # Wallet profile updates (every 6 hours)
        self.schedule_task(
            name="wallet_profile_updates",
            function=self._update_wallet_profiles,
            schedule="0 */6 * * *",  # Every 6 hours
            priority=TaskPriority.NORMAL,
            timeout_minutes=180
        )
        
        # Cache warming (every hour)
        self.schedule_task(
            name="cache_warming",
            function=self._warm_dashboard_cache,
            schedule="0 * * * *",  # Every hour
            priority=TaskPriority.NORMAL,
            timeout_minutes=15
        )
        
        # Data quality checks (daily at 3 AM)
        self.schedule_task(
            name="data_quality_check",
            function=self._check_data_quality,
            schedule="0 3 * * *",  # Daily at 3 AM
            priority=TaskPriority.NORMAL,
            timeout_minutes=60
        )
        
        # Rarity calculations (weekly on Sunday at 4 AM)
        self.schedule_task(
            name="rarity_calculations",
            function=self._calculate_rarity_scores,
            schedule="0 4 * * 0",  # Weekly on Sunday at 4 AM
            priority=TaskPriority.LOW,
            timeout_minutes=240
        )
        
        # Database maintenance (daily at 1 AM)
        self.schedule_task(
            name="database_maintenance",
            function=self._database_maintenance,
            schedule="0 1 * * *",  # Daily at 1 AM
            priority=TaskPriority.LOW,
            timeout_minutes=60
        )
    
    def schedule_task(
        self,
        name: str,
        function: Callable,
        schedule: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout_minutes: int = 60,
        retry_count: int = 3,
        enabled: bool = True
    ):
        """Schedule a new task."""
        task = ScheduledTask(
            name=name,
            function=function,
            schedule=schedule,
            priority=priority,
            timeout_minutes=timeout_minutes,
            retry_count=retry_count,
            enabled=enabled
        )
        
        # Calculate next run time
        task.next_run = self._calculate_next_run(schedule)
        
        self.scheduled_tasks[name] = task
        logger.info(f"Scheduled task '{name}' with schedule '{schedule}'")
    
    def _calculate_next_run(self, cron_schedule: str) -> datetime:
        """Calculate next run time from cron expression."""
        try:
            # Simple cron parser for basic expressions
            # In production, use croniter or similar library
            parts = cron_schedule.split()
            if len(parts) != 5:
                logger.error(f"Invalid cron expression: {cron_schedule}")
                return datetime.now() + timedelta(hours=1)
            
            minute, hour, day, month, day_of_week = parts
            
            # For now, implement basic patterns
            now = datetime.now()
            
            # Every X minutes
            if minute.startswith("*/"):
                interval = int(minute[2:])
                next_run = now + timedelta(minutes=interval)
                return next_run.replace(second=0, microsecond=0)
            
            # Specific hour
            if minute == "0" and hour.isdigit():
                target_hour = int(hour)
                next_run = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(days=1)
                return next_run
            
            # Default: 1 hour from now
            return now + timedelta(hours=1)
            
        except Exception as e:
            logger.error(f"Failed to calculate next run for {cron_schedule}: {e}")
            return datetime.now() + timedelta(hours=1)
    
    async def start(self):
        """Start the data processor service."""
        logger.info("Starting ChainWeave Data Processor")
        self.is_running = True
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        # Start main processing loop
        try:
            await self._main_loop()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Processor error: {e}")
        finally:
            await self.shutdown()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}")
            self.shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def _main_loop(self):
        """Main processing loop."""
        logger.info("Data processor main loop started")
        
        while self.is_running and not self.shutdown_event.is_set():
            try:
                # Check for tasks ready to run
                await self._check_and_run_tasks()
                
                # Clean up completed tasks
                await self._cleanup_completed_tasks()
                
                # Update task history
                self._cleanup_task_history()
                
                # Sleep for 1 minute before next check
                try:
                    await asyncio.wait_for(
                        self.shutdown_event.wait(),
                        timeout=60.0
                    )
                    break  # Shutdown requested
                except asyncio.TimeoutError:
                    continue  # Normal timeout, continue loop
                
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                await asyncio.sleep(60)
    
    async def _check_and_run_tasks(self):
        """Check for tasks ready to run and execute them."""
        now = datetime.now()
        
        for task_name, task in self.scheduled_tasks.items():
            if not task.enabled:
                continue
            
            # Skip if task is already running
            if task_name in self.running_tasks:
                continue
            
            # Check if task is due
            if task.next_run and now >= task.next_run:
                logger.info(f"Starting scheduled task: {task_name}")
                
                # Create async task
                async_task = asyncio.create_task(
                    self._execute_task(task)
                )
                self.running_tasks[task_name] = async_task
                
                # Update next run time
                task.last_run = now
                task.next_run = self._calculate_next_run(task.schedule)
    
    async def _execute_task(self, task: ScheduledTask) -> TaskResult:
        """Execute a scheduled task with error handling and retries."""
        result = TaskResult(
            task_name=task.name,
            status=TaskStatus.RUNNING,
            start_time=datetime.now()
        )
        
        try:
            # Execute with timeout
            await asyncio.wait_for(
                task.function(),
                timeout=task.timeout_minutes * 60
            )
            
            result.status = TaskStatus.COMPLETED
            result.end_time = datetime.now()
            result.duration_seconds = (result.end_time - result.start_time).total_seconds()
            
            logger.info(f"Task '{task.name}' completed in {result.duration_seconds:.1f}s")
            
        except asyncio.TimeoutError:
            result.status = TaskStatus.FAILED
            result.error_message = f"Task timed out after {task.timeout_minutes} minutes"
            logger.error(f"Task '{task.name}' timed out")
            
        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error_message = str(e)
            logger.error(f"Task '{task.name}' failed: {e}")
        
        finally:
            if result.end_time is None:
                result.end_time = datetime.now()
                result.duration_seconds = (result.end_time - result.start_time).total_seconds()
        
        # Add to history
        self.task_history.append(result)
        
        return result
    
    async def _cleanup_completed_tasks(self):
        """Clean up completed async tasks."""
        completed_tasks = []
        
        for task_name, async_task in self.running_tasks.items():
            if async_task.done():
                completed_tasks.append(task_name)
                
                try:
                    result = await async_task
                except Exception as e:
                    logger.error(f"Task {task_name} raised exception: {e}")
        
        # Remove completed tasks
        for task_name in completed_tasks:
            del self.running_tasks[task_name]
    
    def _cleanup_task_history(self):
        """Clean up old task history entries."""
        if len(self.task_history) > self.max_history_items:
            self.task_history = self.task_history[-self.max_history_items:]
    
    # Task implementations
    async def _calculate_daily_metrics(self):
        """Calculate daily market metrics for all collections."""
        logger.info("Starting daily metrics calculation")
        
        try:
            # Get target date (yesterday)
            target_date = (datetime.now() - timedelta(days=1)).date()
            
            # Get active collections
            collections = await self.analytics_engine.get_active_collections()
            logger.info(f"Calculating metrics for {len(collections)} collections")
            
            total_metrics = 0
            
            # Calculate metrics for each collection
            for collection in collections:
                try:
                    collection_id = collection['collection_id']
                    
                    # Calculate all metric types
                    metric_types = list(MetricType)
                    results = await self.analytics_engine.calculate_collection_metrics(
                        collection_id=collection_id,
                        target_date=target_date,
                        metric_types=metric_types
                    )
                    
                    # Write results to BigQuery
                    if results:
                        written_count = await self.bq_writer.write_analytics_batch(results)
                        total_metrics += written_count
                        logger.debug(f"Calculated {written_count} metrics for {collection_id}")
                    
                    # Rate limiting
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Failed to calculate metrics for {collection['collection_id']}: {e}")
            
            logger.info(f"Daily metrics calculation completed: {total_metrics} metrics")
            
        except Exception as e:
            logger.error(f"Daily metrics calculation failed: {e}")
            raise
    
    async def _detect_whale_activity(self):
        """Detect recent whale activity and generate alerts."""
        logger.info("Starting whale detection")
        
        try:
            # Look for activity in the last 30 minutes
            since = datetime.now() - timedelta(minutes=30)
            
            # Scan for whale activity
            alerts = await self.whale_detector.scan_recent_activity(since=since)
            
            if alerts:
                logger.info(f"Detected {len(alerts)} whale activities")
                
                # Save alerts to BigQuery
                saved_count = 0
                for alert in alerts:
                    success = await self.bq_writer.write_whale_alert(alert)
                    if success:
                        saved_count += 1
                
                logger.info(f"Saved {saved_count}/{len(alerts)} whale alerts")
            else:
                logger.debug("No whale activity detected")
            
        except Exception as e:
            logger.error(f"Whale detection failed: {e}")
            raise
    
    async def _update_wallet_profiles(self):
        """Update wallet profiles for active wallets."""
        logger.info("Starting wallet profile updates")
        
        try:
            # Get target date
            target_date = (datetime.now() - timedelta(days=1)).date()
            
            # Get active wallets from recent transactions
            active_wallets = await self.analytics_engine.get_active_wallets(
                target_date=target_date,
                min_transactions=1
            )
            
            logger.info(f"Updating profiles for {len(active_wallets)} active wallets")
            
            updated_count = 0
            batch_size = 50
            
            # Process in batches
            for i in range(0, len(active_wallets), batch_size):
                batch = active_wallets[i:i + batch_size]
                
                # Calculate profiles for batch
                for wallet_address in batch:
                    try:
                        profile = await self.analytics_engine.calculate_wallet_profile(
                            wallet_address=wallet_address,
                            as_of_date=target_date
                        )
                        
                        if profile:
                            success = await self.bq_writer.write_wallet_profile(profile)
                            if success:
                                updated_count += 1
                    
                    except Exception as e:
                        logger.warning(f"Failed to update profile for {wallet_address}: {e}")
                
                # Rate limiting between batches
                await asyncio.sleep(1)
            
            logger.info(f"Wallet profile updates completed: {updated_count} profiles updated")
            
        except Exception as e:
            logger.error(f"Wallet profile updates failed: {e}")
            raise
    
    async def _warm_dashboard_cache(self):
        """Warm dashboard cache with fresh data."""
        logger.info("Starting cache warming")
        
        try:
            # Get active collections (top 20 by volume)
            collections = await self.dashboard_service.get_top_collections_by_volume(limit=20)
            
            # Cache global data
            global_summary = await self.dashboard_service.get_global_market_summary()
            if global_summary:
                await self.cache_manager.set("dashboard_global_summary", global_summary, ttl_minutes=15)
            
            # Cache whale alerts
            whale_alerts = await self.dashboard_service.get_recent_whale_alerts(limit=50)
            if whale_alerts:
                await self.cache_manager.set("dashboard_whale_alerts", whale_alerts, ttl_minutes=10)
            
            # Cache collection data
            cached_collections = 0
            for collection in collections[:10]:  # Limit to top 10
                collection_id = collection['collection_id']
                
                # Collection summary
                summary = await self.dashboard_service.get_collection_summary(collection_id)
                if summary:
                    await self.cache_manager.set(f"collection_summary_{collection_id}", summary, ttl_minutes=15)
                    cached_collections += 1
                
                await asyncio.sleep(0.1)
            
            logger.info(f"Cache warming completed: {cached_collections} collections cached")
            
        except Exception as e:
            logger.error(f"Cache warming failed: {e}")
            raise
    
    async def _check_data_quality(self):
        """Check data quality and integrity."""
        logger.info("Starting data quality check")
        
        try:
            target_date = (datetime.now() - timedelta(days=1)).date()
            
            # Check for missing data
            issues = await self.analytics_engine.find_missing_transaction_data(target_date)
            issues.extend(await self.analytics_engine.find_orphaned_nfts())
            issues.extend(await self.analytics_engine.find_inconsistent_profiles(target_date))
            
            if issues:
                logger.warning(f"Found {len(issues)} data quality issues")
                
                # Attempt to fix issues
                fixed_count = await self.analytics_engine.fix_data_quality_issues(issues)
                logger.info(f"Fixed {fixed_count}/{len(issues)} data quality issues")
            else:
                logger.info("No data quality issues found")
            
        except Exception as e:
            logger.error(f"Data quality check failed: {e}")
            raise
    
    async def _calculate_rarity_scores(self):
        """Calculate rarity scores for collections (weekly task)."""
        logger.info("Starting weekly rarity calculations")
        
        try:
            from services.rarity_calculator import RarityCalculator
            rarity_calculator = RarityCalculator(self.project_id, self.dataset_id)
            
            # Get collections that need rarity updates
            collections = await self.analytics_engine.get_active_collections()
            
            updated_collections = 0
            for collection in collections[:10]:  # Limit to prevent overload
                collection_id = collection['collection_id']
                
                try:
                    # Check if update is needed
                    last_update = await rarity_calculator.get_last_rarity_update(collection_id)
                    if last_update and (datetime.now() - last_update).days < 7:
                        continue  # Updated recently
                    
                    # Get NFTs and calculate rarity
                    nfts = await rarity_calculator.get_collection_nfts(collection_id)
                    if nfts:
                        rarity_results = await rarity_calculator.calculate_collection_rarity(collection_id, nfts)
                        
                        if rarity_results:
                            # Update NFT metadata with rarity scores
                            for mint_address, rarity_data in rarity_results.items():
                                await rarity_calculator.update_nft_rarity(
                                    mint_address=mint_address,
                                    rarity_rank=rarity_data['rank'],
                                    rarity_score=rarity_data['score']
                                )
                            
                            updated_collections += 1
                            logger.info(f"Updated rarity for {collection_id}: {len(rarity_results)} NFTs")
                    
                    await asyncio.sleep(2)  # Rate limiting
                    
                except Exception as e:
                    logger.error(f"Failed to calculate rarity for {collection_id}: {e}")
            
            logger.info(f"Rarity calculations completed: {updated_collections} collections updated")
            
        except Exception as e:
            logger.error(f"Rarity calculations failed: {e}")
            raise
    
    async def _database_maintenance(self):
        """Perform database maintenance tasks."""
        logger.info("Starting database maintenance")
        
        try:
            # Clean up old cache entries
            cleaned_cache = await self.cache_manager.cleanup_expired()
            logger.info(f"Cleaned up {cleaned_cache} expired cache entries")
            
            # Check table integrity
            table_checks = ['nft_collections', 'nft_metadata', 'transactions', 'wallet_profiles']
            for table_name in table_checks:
                integrity_result = self.migration_manager.validate_data_integrity(table_name)
                if integrity_result.get('issues'):
                    logger.warning(f"Table {table_name} has {len(integrity_result['issues'])} integrity issues")
            
            logger.info("Database maintenance completed")
            
        except Exception as e:
            logger.error(f"Database maintenance failed: {e}")
            raise
    
    async def get_status(self) -> Dict[str, Any]:
        """Get processor status and statistics."""
        return {
            'is_running': self.is_running,
            'scheduled_tasks': {
                name: {
                    'enabled': task.enabled,
                    'last_run': task.last_run.isoformat() if task.last_run else None,
                    'next_run': task.next_run.isoformat() if task.next_run else None,
                    'schedule': task.schedule,
                    'priority': task.priority.name
                }
                for name, task in self.scheduled_tasks.items()
            },
            'running_tasks': list(self.running_tasks.keys()),
            'recent_history': [
                {
                    'task_name': result.task_name,
                    'status': result.status.value,
                    'start_time': result.start_time.isoformat(),
                    'duration_seconds': result.duration_seconds,
                    'records_processed': result.records_processed,
                    'error_message': result.error_message
                }
                for result in self.task_history[-20:]  # Last 20 tasks
            ]
        }
    
    async def shutdown(self):
        """Graceful shutdown of the processor."""
        logger.info("Shutting down data processor")
        
        self.is_running = False
        self.shutdown_event.set()
        
        # Cancel running tasks
        for task_name, async_task in self.running_tasks.items():
            logger.info(f"Cancelling task: {task_name}")
            async_task.cancel()
        
        # Wait for tasks to complete
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks.values(), return_exceptions=True)
        
        # Close services
        await self.cache_manager.close()
        
        # Shutdown thread pool
        self.executor.shutdown(wait=True)
        
        logger.info("Data processor shutdown complete")


# Factory function
def create_data_processor(
    project_id: str,
    dataset_id: str,
    redis_url: Optional[str] = None,
    enable_celery: bool = False
) -> DataProcessor:
    """Create and configure data processor."""
    return DataProcessor(
        project_id=project_id,
        dataset_id=dataset_id,
        redis_url=redis_url,
        enable_celery=enable_celery
    )