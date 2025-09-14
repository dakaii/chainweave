"""Cache management service for ChainWeave.

Provides intelligent caching layer for dashboard and API data:
- Redis-based caching with fallback to in-memory
- TTL management and cache warming
- Pattern-based cache invalidation
- Cache health monitoring
"""

import asyncio
import logging
import json
import hashlib
from typing import Any, Optional, List, Dict, Pattern
from datetime import datetime, timedelta
import pickle
import re

# Optional Redis support
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class CacheManager:
    """Intelligent cache management with Redis and in-memory fallback."""
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_ttl_minutes: int = 15,
        max_memory_items: int = 1000
    ):
        """Initialize cache manager."""
        self.default_ttl_minutes = default_ttl_minutes
        self.max_memory_items = max_memory_items
        
        # Redis connection
        self.redis_client = None
        if REDIS_AVAILABLE and redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=False)
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}, using in-memory cache")
        
        # In-memory fallback cache
        self.memory_cache = {}
        self.memory_ttl = {}
        
        # Cache statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'memory_usage': 0,
            'redis_usage': 0
        }
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            # Try Redis first
            if self.redis_client:
                try:
                    cached_data = await self.redis_client.get(key)
                    if cached_data:
                        self.stats['hits'] += 1
                        self.stats['redis_usage'] += 1
                        return pickle.loads(cached_data)
                except Exception as e:
                    logger.warning(f"Redis get failed for key {key}: {e}")
            
            # Fallback to memory cache
            if key in self.memory_cache:
                # Check TTL
                if key in self.memory_ttl and datetime.now() > self.memory_ttl[key]:
                    # Expired
                    del self.memory_cache[key]
                    del self.memory_ttl[key]
                    self.stats['misses'] += 1
                    return None
                
                self.stats['hits'] += 1
                self.stats['memory_usage'] += 1
                return self.memory_cache[key]
            
            self.stats['misses'] += 1
            return None
            
        except Exception as e:
            logger.error(f"Cache get failed for key {key}: {e}")
            self.stats['misses'] += 1
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl_minutes: Optional[int] = None
    ) -> bool:
        """Set value in cache with TTL."""
        try:
            if ttl_minutes is None:
                ttl_minutes = self.default_ttl_minutes
            
            ttl_seconds = ttl_minutes * 60
            expiry_time = datetime.now() + timedelta(minutes=ttl_minutes)
            
            # Try Redis first
            if self.redis_client:
                try:
                    serialized_data = pickle.dumps(value)
                    await self.redis_client.setex(key, ttl_seconds, serialized_data)
                    self.stats['sets'] += 1
                    return True
                except Exception as e:
                    logger.warning(f"Redis set failed for key {key}: {e}")
            
            # Fallback to memory cache
            # Implement LRU eviction if at capacity
            if len(self.memory_cache) >= self.max_memory_items:
                await self._evict_lru_memory_items()
            
            self.memory_cache[key] = value
            self.memory_ttl[key] = expiry_time
            self.stats['sets'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Cache set failed for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete specific key from cache."""
        try:
            deleted = False
            
            # Delete from Redis
            if self.redis_client:
                try:
                    result = await self.redis_client.delete(key)
                    if result > 0:
                        deleted = True
                except Exception as e:
                    logger.warning(f"Redis delete failed for key {key}: {e}")
            
            # Delete from memory cache
            if key in self.memory_cache:
                del self.memory_cache[key]
                deleted = True
            
            if key in self.memory_ttl:
                del self.memory_ttl[key]
            
            if deleted:
                self.stats['deletes'] += 1
            
            return deleted
            
        except Exception as e:
            logger.error(f"Cache delete failed for key {key}: {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear cache keys matching pattern."""
        try:
            cleared_count = 0
            
            # Clear from Redis
            if self.redis_client:
                try:
                    # Convert glob pattern to match Redis keys
                    redis_pattern = pattern.replace('*', '*')  # Redis uses * for wildcards
                    keys = await self.redis_client.keys(redis_pattern)
                    
                    if keys:
                        cleared_count += await self.redis_client.delete(*keys)
                        
                except Exception as e:
                    logger.warning(f"Redis pattern clear failed for {pattern}: {e}")
            
            # Clear from memory cache
            regex_pattern = pattern.replace('*', '.*')  # Convert to regex
            compiled_pattern = re.compile(regex_pattern)
            
            keys_to_delete = [
                key for key in self.memory_cache.keys() 
                if compiled_pattern.match(key)
            ]
            
            for key in keys_to_delete:
                del self.memory_cache[key]
                if key in self.memory_ttl:
                    del self.memory_ttl[key]
                cleared_count += 1
            
            self.stats['deletes'] += cleared_count
            
            return cleared_count
            
        except Exception as e:
            logger.error(f"Pattern clear failed for {pattern}: {e}")
            return 0
    
    async def get_or_set(
        self, 
        key: str, 
        value_factory,
        ttl_minutes: Optional[int] = None
    ) -> Any:
        """Get value from cache, or set it using factory function if not found."""
        
        # Try to get from cache first
        cached_value = await self.get(key)
        if cached_value is not None:
            return cached_value
        
        # Generate value using factory
        try:
            if asyncio.iscoroutinefunction(value_factory):
                fresh_value = await value_factory()
            else:
                fresh_value = value_factory()
            
            # Cache the fresh value
            await self.set(key, fresh_value, ttl_minutes)
            
            return fresh_value
            
        except Exception as e:
            logger.error(f"Value factory failed for key {key}: {e}")
            return None
    
    async def warm_cache(self, warm_functions: Dict[str, Any]) -> Dict[str, bool]:
        """Warm cache with multiple key-value pairs."""
        results = {}
        
        for cache_key, value_factory in warm_functions.items():
            try:
                # Skip if already cached and fresh
                if await self.get(cache_key) is not None:
                    results[cache_key] = True
                    continue
                
                # Generate and cache value
                if asyncio.iscoroutinefunction(value_factory):
                    value = await value_factory()
                else:
                    value = value_factory()
                
                success = await self.set(cache_key, value)
                results[cache_key] = success
                
                # Rate limiting to prevent overwhelming
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Cache warming failed for {cache_key}: {e}")
                results[cache_key] = False
        
        return results
    
    async def invalidate_related(self, tags: List[str]) -> int:
        """Invalidate cache entries related to specific tags."""
        total_cleared = 0
        
        for tag in tags:
            # Clear keys containing the tag
            pattern = f"*{tag}*"
            cleared = await self.clear_pattern(pattern)
            total_cleared += cleared
        
        return total_cleared
    
    async def get_cache_info(self) -> Dict[str, Any]:
        """Get cache statistics and health info."""
        info = {
            'stats': self.stats.copy(),
            'memory_cache_size': len(self.memory_cache),
            'memory_ttl_entries': len(self.memory_ttl),
            'redis_connected': self.redis_client is not None,
            'hit_rate': 0.0,
            'memory_usage_bytes': 0
        }
        
        # Calculate hit rate
        total_requests = self.stats['hits'] + self.stats['misses']
        if total_requests > 0:
            info['hit_rate'] = (self.stats['hits'] / total_requests) * 100
        
        # Estimate memory usage
        try:
            memory_size = sum(
                len(pickle.dumps(value)) for value in self.memory_cache.values()
            )
            info['memory_usage_bytes'] = memory_size
        except Exception:
            info['memory_usage_bytes'] = 0
        
        # Redis info
        if self.redis_client:
            try:
                redis_info = await self.redis_client.info('memory')
                info['redis_memory_usage'] = redis_info.get('used_memory', 0)
                info['redis_connected'] = True
            except Exception as e:
                logger.warning(f"Failed to get Redis info: {e}")
                info['redis_connected'] = False
        
        return info
    
    async def cleanup_expired(self) -> int:
        """Clean up expired entries from memory cache."""
        current_time = datetime.now()
        expired_keys = []
        
        for key, expiry_time in self.memory_ttl.items():
            if current_time > expiry_time:
                expired_keys.append(key)
        
        for key in expired_keys:
            if key in self.memory_cache:
                del self.memory_cache[key]
            del self.memory_ttl[key]
        
        return len(expired_keys)
    
    async def _evict_lru_memory_items(self, count: int = None) -> int:
        """Evict least recently used items from memory cache."""
        if count is None:
            count = max(1, len(self.memory_cache) // 10)  # Evict 10% by default
        
        # Sort by TTL (oldest first) as a simple LRU approximation
        sorted_items = sorted(
            self.memory_ttl.items(),
            key=lambda x: x[1]
        )
        
        evicted = 0
        for key, _ in sorted_items[:count]:
            if key in self.memory_cache:
                del self.memory_cache[key]
                evicted += 1
            if key in self.memory_ttl:
                del self.memory_ttl[key]
        
        return evicted
    
    def generate_cache_key(self, *args, **kwargs) -> str:
        """Generate consistent cache key from arguments."""
        # Create a deterministic string from arguments
        key_parts = []
        
        for arg in args:
            key_parts.append(str(arg))
        
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        
        key_string = "|".join(key_parts)
        
        # Hash for consistent length
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        
        return f"cache_{key_hash}"
    
    async def close(self):
        """Close cache connections."""
        if self.redis_client:
            try:
                await self.redis_client.close()
            except Exception as e:
                logger.warning(f"Failed to close Redis connection: {e}")
    
    # Context manager support
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Cache decorators for easy use
def cached(ttl_minutes: int = 15, key_prefix: str = ""):
    """Decorator to cache function results."""
    
    def decorator(func):
        cache = CacheManager()
        
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}_{func.__name__}_{cache.generate_cache_key(*args, **kwargs)}"
            
            # Try to get from cache
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl_minutes)
            
            return result
        
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, we need to handle caching differently
            # This would require a synchronous cache implementation
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Global cache instance for convenience
_global_cache_manager = None

async def get_global_cache() -> CacheManager:
    """Get global cache manager instance."""
    global _global_cache_manager
    
    if _global_cache_manager is None:
        _global_cache_manager = CacheManager()
    
    return _global_cache_manager