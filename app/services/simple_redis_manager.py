# Create this as app/services/simple_redis_manager.py

import asyncio
import json
import logging
from typing import Any, Optional
from datetime import datetime, timedelta

try:
    import fakeredis.aioredis as fake_aioredis
    FAKEREDIS_AVAILABLE = True
    print("✅ FakeRedis is available")
except ImportError:
    FAKEREDIS_AVAILABLE = False
    print("❌ FakeRedis not available, using memory fallback")

logger = logging.getLogger(__name__)

class SimpleRedisManager:
    """Very simple Redis manager to start with"""
    
    def __init__(self):
        self.fake_redis = None
        self.memory_cache = {}  # Fallback if FakeRedis fails
        self.is_connected = False
        
        # Simple stats
        self.cache_hits = 0
        self.cache_misses = 0
    
    async def connect(self):
        """Connect to FakeRedis (no server needed)"""
        try:
            if FAKEREDIS_AVAILABLE:
                self.fake_redis = fake_aioredis.FakeRedis()
                await self.fake_redis.ping()
                print("✅ Connected to FakeRedis (simulated Redis)")
                self.is_connected = True
            else:
                print("📝 Using simple memory cache")
                self.memory_cache = {}
                self.is_connected = True
                
        except Exception as e:
            print(f"⚠️ FakeRedis failed, using memory: {e}")
            self.memory_cache = {}
            self.is_connected = True
    
    async def disconnect(self):
        """Close connections"""
        if self.fake_redis:
            await self.fake_redis.close()
        self.memory_cache = {}
        self.is_connected = False
        print("✅ Cache disconnected")
    
    async def set_news(self, category: str, articles: list, ttl_seconds: int = 7200) -> bool:
        """Store news articles for a category"""
        try:
            cache_key = f"news:{category.lower()}"
            timestamp_key = f"timestamp:{category.lower()}"
            current_time = datetime.now()
            
            if self.fake_redis:
                # Store in FakeRedis
                await self.fake_redis.setex(cache_key, ttl_seconds, json.dumps(articles))
                await self.fake_redis.setex(timestamp_key, ttl_seconds, current_time.isoformat())
                print(f"✅ Cached {len(articles)} articles for {category} in FakeRedis")
            else:
                # Store in memory with expiration
                expires_at = current_time + timedelta(seconds=ttl_seconds)
                self.memory_cache[cache_key] = {
                    'data': articles,
                    'expires_at': expires_at
                }
                self.memory_cache[timestamp_key] = {
                    'data': current_time.isoformat(),
                    'expires_at': expires_at
                }
                print(f"✅ Cached {len(articles)} articles for {category} in memory")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to cache {category}: {e}")
            return False
    
    async def get_news(self, category: str) -> Optional[list]:
        """Get cached news articles for a category"""
        try:
            cache_key = f"news:{category.lower()}"
            
            if self.fake_redis:
                # Get from FakeRedis
                cached_data = await self.fake_redis.get(cache_key)
                if cached_data:
                    self.cache_hits += 1
                    articles = json.loads(cached_data)
                    print(f"✅ Cache HIT for {category} - {len(articles)} articles")
                    return articles
                else:
                    self.cache_misses += 1
                    print(f"❌ Cache MISS for {category}")
                    return None
            else:
                # Get from memory
                cached_item = self.memory_cache.get(cache_key)
                if cached_item and cached_item['expires_at'] > datetime.now():
                    self.cache_hits += 1
                    print(f"✅ Cache HIT for {category} - {len(cached_item['data'])} articles")
                    return cached_item['data']
                else:
                    self.cache_misses += 1
                    print(f"❌ Cache MISS for {category}")
                    return None
                    
        except Exception as e:
            print(f"❌ Failed to get cache for {category}: {e}")
            self.cache_misses += 1
            return None
    
    async def get_timestamp(self, category: str) -> Optional[datetime]:
        """Get when category was last cached"""
        try:
            timestamp_key = f"timestamp:{category.lower()}"
            
            if self.fake_redis:
                cached_timestamp = await self.fake_redis.get(timestamp_key)
                if cached_timestamp:
                    return datetime.fromisoformat(cached_timestamp)
            else:
                cached_item = self.memory_cache.get(timestamp_key)
                if cached_item and cached_item['expires_at'] > datetime.now():
                    return datetime.fromisoformat(cached_item['data'])
            
            return None
            
        except Exception as e:
            print(f"❌ Failed to get timestamp for {category}: {e}")
            return None
    
    async def clear_category(self, category: str) -> bool:
        """Clear cache for a specific category"""
        try:
            cache_key = f"news:{category.lower()}"
            timestamp_key = f"timestamp:{category.lower()}"
            
            if self.fake_redis:
                await self.fake_redis.delete(cache_key, timestamp_key)
            else:
                self.memory_cache.pop(cache_key, None)
                self.memory_cache.pop(timestamp_key, None)
            
            print(f"✅ Cleared cache for {category}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to clear cache for {category}: {e}")
            return False
    
    def get_stats(self) -> dict:
        """Get simple cache statistics"""
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "connected": self.is_connected,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": round(hit_rate, 1),
            "cache_type": "FakeRedis" if self.fake_redis else "Memory"
        }

# Create global instance
simple_cache = SimpleRedisManager()