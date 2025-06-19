import redis
import aioredis
import json
import pickle
import logging
import asyncio
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
import os
from dataclasses import dataclass, asdict
import orjson

logger = logging.getLogger(__name__)

@dataclass
class CacheStats:
    """Redis cache statistics"""
    total_keys: int
    memory_usage: str
    hit_rate: float
    miss_rate: float
    total_commands: int
    connected_clients: int
    uptime_seconds: int
    keyspace_hits: int
    keyspace_misses: int

@dataclass
class CacheEntry:
    """Represents a cached entry with metadata"""
    data: Any
    created_at: datetime
    expires_at: Optional[datetime]
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    size_bytes: int = 0

class RedisManager:
    """Advanced Redis cache manager with analytics and monitoring"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.async_redis: Optional[aioredis.Redis] = None
        self.is_connected = False
        self.fallback_cache = {}  # Memory fallback when Redis is down
        
        # Configuration
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.redis_db = int(os.getenv("REDIS_DB", 0))
        self.redis_password = os.getenv("REDIS_PASSWORD", None)
        
        # Cache settings
        self.default_ttl = int(os.getenv("CACHE_TTL", 7200))  # 2 hours
        self.key_prefix = os.getenv("CACHE_PREFIX", "ai_novine:")
        
        # Metrics
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_sets = 0
        self.cache_deletes = 0
    
    async def connect(self):
        """Initialize Redis connections"""
        try:
            # Sync Redis connection
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                password=self.redis_password,
                decode_responses=False,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # Async Redis connection
            self.async_redis = await aioredis.from_url(
                f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}",
                password=self.redis_password,
                encoding="utf-8",
                decode_responses=False
            )
            
            # Test connections
            await self.async_redis.ping()
            self.redis_client.ping()
            
            self.is_connected = True
            logger.info(f"✅ Connected to Redis at {self.redis_host}:{self.redis_port}")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            logger.warning("📝 Using memory fallback cache")
            self.is_connected = False
    
    async def disconnect(self):
        """Close Redis connections"""
        try:
            if self.async_redis:
                await self.async_redis.close()
            if self.redis_client:
                self.redis_client.close()
            self.is_connected = False
            logger.info("✅ Redis connections closed")
        except Exception as e:
            logger.error(f"❌ Error closing Redis connections: {e}")
    
    def _make_key(self, key: str) -> str:
        """Create prefixed cache key"""
        return f"{self.key_prefix}{key}"
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in cache with TTL"""
        try:
            cache_key = self._make_key(key)
            ttl = ttl or self.default_ttl
            
            if self.is_connected:
                # Create cache entry with metadata
                cache_entry = CacheEntry(
                    data=value,
                    created_at=datetime.now(),
                    expires_at=datetime.now() + timedelta(seconds=ttl),
                    size_bytes=len(str(value))
                )
                
                # Serialize using orjson for better performance
                serialized_data = orjson.dumps(asdict(cache_entry))
                
                # Set in Redis with TTL
                await self.async_redis.setex(cache_key, ttl, serialized_data)
                
                # Update metrics
                await self._update_key_metrics(cache_key, len(serialized_data))
                
            else:
                # Fallback to memory cache
                self.fallback_cache[cache_key] = {
                    'value': value,
                    'expires_at': datetime.now() + timedelta(seconds=ttl)
                }
            
            self.cache_sets += 1
            logger.debug(f"✅ Cached key: {key} (TTL: {ttl}s)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to set cache key {key}: {e}")
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache"""
        try:
            cache_key = self._make_key(key)
            
            if self.is_connected:
                # Get from Redis
                cached_data = await self.async_redis.get(cache_key)
                
                if cached_data:
                    # Deserialize cache entry
                    cache_entry_dict = orjson.loads(cached_data)
                    cache_entry = CacheEntry(**cache_entry_dict)
                    
                    # Update access metadata
                    cache_entry.access_count += 1
                    cache_entry.last_accessed = datetime.now()
                    
                    # Update in Redis (fire and forget)
                    asyncio.create_task(self._update_access_metadata(cache_key, cache_entry))
                    
                    self.cache_hits += 1
                    logger.debug(f"✅ Cache hit for key: {key}")
                    return cache_entry.data
                else:
                    self.cache_misses += 1
                    logger.debug(f"❌ Cache miss for key: {key}")
                    return None
            else:
                # Fallback to memory cache
                cached_item = self.fallback_cache.get(cache_key)
                if cached_item and cached_item['expires_at'] > datetime.now():
                    self.cache_hits += 1
                    return cached_item['value']
                else:
                    self.cache_misses += 1
                    return None
            
        except Exception as e:
            logger.error(f"❌ Failed to get cache key {key}: {e}")
            self.cache_misses += 1
            return None
    
    async def delete(self, key: str) -> bool:
        """Delete a key from cache"""
        try:
            cache_key = self._make_key(key)
            
            if self.is_connected:
                result = await self.async_redis.delete(cache_key)
                deleted = result > 0
            else:
                deleted = cache_key in self.fallback_cache
                if deleted:
                    del self.fallback_cache[cache_key]
            
            if deleted:
                self.cache_deletes += 1
                logger.debug(f"✅ Deleted cache key: {key}")
            
            return deleted
            
        except Exception as e:
            logger.error(f"❌ Failed to delete cache key {key}: {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching a pattern"""
        try:
            if not self.is_connected:
                # Clear from memory cache
                keys_to_delete = [k for k in self.fallback_cache.keys() if pattern in k]
                for key in keys_to_delete:
                    del self.fallback_cache[key]
                return len(keys_to_delete)
            
            # Get all keys matching pattern
            search_pattern = self._make_key(f"*{pattern}*")
            keys = await self.async_redis.keys(search_pattern)
            
            if keys:
                deleted = await self.async_redis.delete(*keys)
                logger.info(f"✅ Cleared {deleted} keys matching pattern: {pattern}")
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"❌ Failed to clear keys with pattern {pattern}: {e}")
            return 0
    
    async def clear_all(self) -> bool:
        """Clear all cache entries"""
        try:
            if not self.is_connected:
                self.fallback_cache.clear()
                return True
            
            # Clear all keys with our prefix
            pattern = f"{self.key_prefix}*"
            keys = await self.async_redis.keys(pattern)
            
            if keys:
                deleted = await self.async_redis.delete(*keys)
                logger.info(f"✅ Cleared all cache ({deleted} keys)")
                return True
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to clear all cache: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache"""
        try:
            cache_key = self._make_key(key)
            
            if self.is_connected:
                result = await self.async_redis.exists(cache_key)
                return result > 0
            else:
                cached_item = self.fallback_cache.get(cache_key)
                return cached_item and cached_item['expires_at'] > datetime.now()
            
        except Exception as e:
            logger.error(f"❌ Failed to check key existence {key}: {e}")
            return False
    
    async def get_stats(self) -> CacheStats:
        """Get comprehensive cache statistics"""
        try:
            if not self.is_connected:
                return CacheStats(
                    total_keys=len(self.fallback_cache),
                    memory_usage="Unknown (fallback mode)",
                    hit_rate=self._calculate_hit_rate(),
                    miss_rate=self._calculate_miss_rate(),
                    total_commands=self.cache_hits + self.cache_misses + self.cache_sets,
                    connected_clients=0,
                    uptime_seconds=0,
                    keyspace_hits=self.cache_hits,
                    keyspace_misses=self.cache_misses
                )
            
            # Get Redis info
            info = await self.async_redis.info()
            
            # Count our keys
            our_keys = await self.async_redis.keys(f"{self.key_prefix}*")
            
            return CacheStats(
                total_keys=len(our_keys),
                memory_usage=info.get('used_memory_human', 'Unknown'),
                hit_rate=self._calculate_hit_rate(),
                miss_rate=self._calculate_miss_rate(),
                total_commands=info.get('total_commands_processed', 0),
                connected_clients=info.get('connected_clients', 0),
                uptime_seconds=info.get('uptime_in_seconds', 0),
                keyspace_hits=info.get('keyspace_hits', 0),
                keyspace_misses=info.get('keyspace_misses', 0)
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to get cache stats: {e}")
            return CacheStats(
                total_keys=0, memory_usage="Error", hit_rate=0.0, miss_rate=0.0,
                total_commands=0, connected_clients=0, uptime_seconds=0,
                keyspace_hits=0, keyspace_misses=0
            )
    
    async def get_key_details(self) -> List[Dict]:
        """Get detailed information about all cached keys"""
        try:
            if not self.is_connected:
                return [
                    {
                        'key': key.replace(self.key_prefix, ''),
                        'type': 'fallback',
                        'ttl': -1,
                        'size': len(str(value['value'])),
                        'expires_at': value['expires_at'].isoformat()
                    }
                    for key, value in self.fallback_cache.items()
                ]
            
            # Get all our keys
            pattern = f"{self.key_prefix}*"
            keys = await self.async_redis.keys(pattern)
            
            key_details = []
            for key_bytes in keys:
                key = key_bytes.decode('utf-8')
                try:
                    # Get TTL
                    ttl = await self.async_redis.ttl(key)
                    
                    # Get memory usage
                    memory_usage = await self.async_redis.memory_usage(key)
                    
                    # Get cache entry for metadata
                    cached_data = await self.async_redis.get(key)
                    if cached_data:
                        cache_entry_dict = orjson.loads(cached_data)
                        cache_entry = CacheEntry(**cache_entry_dict)
                        
                        key_details.append({
                            'key': key.replace(self.key_prefix, ''),
                            'type': 'redis',
                            'ttl': ttl,
                            'size': memory_usage or cache_entry.size_bytes,
                            'created_at': cache_entry.created_at.isoformat(),
                            'expires_at': cache_entry.expires_at.isoformat() if cache_entry.expires_at else None,
                            'access_count': cache_entry.access_count,
                            'last_accessed': cache_entry.last_accessed.isoformat() if cache_entry.last_accessed else None
                        })
                
                except Exception as e:
                    logger.warning(f"❌ Failed to get details for key {key}: {e}")
            
            return key_details
            
        except Exception as e:
            logger.error(f"❌ Failed to get key details: {e}")
            return []
    
    async def _update_access_metadata(self, cache_key: str, cache_entry: CacheEntry):
        """Update access metadata for a cache entry"""
        try:
            # Get current TTL
            ttl = await self.async_redis.ttl(cache_key)
            if ttl > 0:
                # Re-serialize and update
                serialized_data = orjson.dumps(asdict(cache_entry))
                await self.async_redis.setex(cache_key, ttl, serialized_data)
        except Exception as e:
            logger.warning(f"Failed to update access metadata for {cache_key}: {e}")
    
    async def _update_key_metrics(self, cache_key: str, size_bytes: int):
        """Update metrics for cache operations"""
        try:
            # Store metrics in Redis (optional - for advanced analytics)
            metrics_key = f"{self.key_prefix}metrics:daily:{datetime.now().strftime('%Y-%m-%d')}"
            await self.async_redis.hincrby(metrics_key, "total_sets", 1)
            await self.async_redis.hincrby(metrics_key, "total_bytes", size_bytes)
            await self.async_redis.expire(metrics_key, 86400 * 7)  # Keep for 7 days
        except Exception as e:
            logger.warning(f"Failed to update metrics: {e}")
    
    def _calculate_hit_rate(self) -> float:
        """Calculate cache hit rate percentage"""
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100) if total > 0 else 0.0
    
    def _calculate_miss_rate(self) -> float:
        """Calculate cache miss rate percentage"""
        total = self.cache_hits + self.cache_misses
        return (self.cache_misses / total * 100) if total > 0 else 0.0
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        try:
            if not self.is_connected:
                return {
                    "status": "degraded",
                    "redis_connected": False,
                    "fallback_active": True,
                    "message": "Using memory fallback cache"
                }
            
            # Test Redis connection
            start_time = datetime.now()
            await self.async_redis.ping()
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                "status": "healthy",
                "redis_connected": True,
                "fallback_active": False,
                "response_time_ms": round(response_time, 2),
                "hit_rate": round(self._calculate_hit_rate(), 2),
                "total_operations": self.cache_hits + self.cache_misses + self.cache_sets
            }
            
        except Exception as e:
            return {
                "status": "error",
                "redis_connected": False,
                "fallback_active": True,
                "error": str(e)
            }

# Global Redis manager instance
redis_manager = RedisManager()