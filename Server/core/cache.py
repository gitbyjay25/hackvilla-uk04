"""
Production-grade caching layer with Azure Cache for Redis
Falls back to in-memory cache if Redis unavailable
"""
from functools import lru_cache
from typing import Optional, Any, Dict
import json
import hashlib
from datetime import datetime, timedelta
import pickle
from core.logging import get_logger

logger = get_logger(__name__)

# Try to import Redis
try:
    import redis
    from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available - using in-memory cache")


class RedisCacheBackend:
    """Azure Cache for Redis backend"""
    
    def __init__(self, redis_url: str, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self.redis_client = None
        self._connected = False
        
        try:
            # Parse Redis URL and create client
            # Format: redis://[:password]@host:port/db or rediss:// for SSL
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=False,  # We'll use pickle
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            self.redis_client.ping()
            self._connected = True
            logger.info(f"✅ Connected to Azure Cache for Redis")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            self._connected = False
            self.redis_client = None
    
    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        if not self._connected or not self.redis_client:
            return False
        
        try:
            self.redis_client.ping()
            return True
        except:
            self._connected = False
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Get from Redis"""
        if not self.is_connected():
            return None
        
        try:
            data = self.redis_client.get(key)
            if data:
                return pickle.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis GET error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set in Redis with TTL"""
        if not self.is_connected():
            return
        
        try:
            ttl = ttl or self.ttl_seconds
            pickled = pickle.dumps(value)
            self.redis_client.setex(key, ttl, pickled)
        except Exception as e:
            logger.error(f"Redis SET error: {e}")
    
    def delete(self, key: str):
        """Delete from Redis"""
        if not self.is_connected():
            return
        
        try:
            self.redis_client.delete(key)
        except Exception as e:
            logger.error(f"Redis DELETE error: {e}")
    
    def delete_pattern(self, pattern: str):
        """Delete all keys matching pattern"""
        if not self.is_connected():
            return
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"Deleted {len(keys)} keys matching pattern: {pattern}")
        except Exception as e:
            logger.error(f"Redis DELETE PATTERN error: {e}")
    
    def clear(self):
        """Clear entire cache (use with caution!)"""
        if not self.is_connected():
            return
        
        try:
            self.redis_client.flushdb()
            logger.warning("Redis cache cleared (FLUSHDB)")
        except Exception as e:
            logger.error(f"Redis FLUSHDB error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get Redis stats"""
        if not self.is_connected():
            return {"status": "disconnected"}
        
        try:
            info = self.redis_client.info()
            return {
                "status": "connected",
                "used_memory_mb": info.get("used_memory", 0) / 1024 / 1024,
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": info.get("keyspace_hits", 0) / max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1), 1)
            }
        except Exception as e:
            logger.error(f"Redis INFO error: {e}")
            return {"status": "error", "error": str(e)}


class InMemoryCacheBackend:
    """Fallback in-memory cache"""
    
    def __init__(self, ttl_seconds: int = 300):
        self._cache: Dict[str, tuple] = {}
        self.ttl_seconds = ttl_seconds
        logger.info("Using in-memory cache (fallback)")
    
    def is_connected(self) -> bool:
        return True
    
    def get(self, key: str) -> Optional[Any]:
        """Get from memory cache"""
        if key in self._cache:
            cached_data, cached_time = self._cache[key]
            
            # Check if expired
            if datetime.utcnow() - cached_time < timedelta(seconds=self.ttl_seconds):
                return cached_data
            else:
                del self._cache[key]
        
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set in memory cache"""
        self._cache[key] = (value, datetime.utcnow())
    
    def delete(self, key: str):
        """Delete from memory cache"""
        if key in self._cache:
            del self._cache[key]
    
    def delete_pattern(self, pattern: str):
        """Delete all keys matching pattern"""
        # Simple pattern matching for in-memory
        pattern_prefix = pattern.replace("*", "")
        keys_to_delete = [k for k in self._cache.keys() if k.startswith(pattern_prefix)]
        for key in keys_to_delete:
            del self._cache[key]
    
    def clear(self):
        """Clear entire cache"""
        self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory cache stats"""
        return {
            "status": "in-memory",
            "total_keys": len(self._cache),
            "backend": "in-memory-fallback"
        }


class CacheManager:
    """
    Unified cache manager with Azure Cache for Redis
    Automatically falls back to in-memory if Redis unavailable
    """
    
    def __init__(self, redis_url: Optional[str] = None, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        
        # Try to use Redis first
        if redis_url and REDIS_AVAILABLE:
            self.backend = RedisCacheBackend(redis_url, ttl_seconds)
            if not self.backend.is_connected():
                logger.warning("Redis connection failed, falling back to in-memory cache")
                self.backend = InMemoryCacheBackend(ttl_seconds)
        else:
            logger.info("Redis not configured or unavailable, using in-memory cache")
            self.backend = InMemoryCacheBackend(ttl_seconds)
    
    def _generate_key(self, tenant_id: str, operation: str, **kwargs) -> str:
        """Generate cache key with namespace"""
        if kwargs:
            params = json.dumps(kwargs, sort_keys=True)
            hash_suffix = hashlib.md5(params.encode()).hexdigest()[:8]
            return f"nexarch:{tenant_id}:{operation}:{hash_suffix}"
        return f"nexarch:{tenant_id}:{operation}"
    
    def get(self, tenant_id: str, operation: str, **kwargs) -> Optional[Any]:
        """Get from cache"""
        key = self._generate_key(tenant_id, operation, **kwargs)
        return self.backend.get(key)
    
    def set(self, tenant_id: str, operation: str, data: Any, ttl: Optional[int] = None, **kwargs):
        """Set cache with optional custom TTL"""
        key = self._generate_key(tenant_id, operation, **kwargs)
        self.backend.set(key, data, ttl or self.ttl_seconds)
    
    def invalidate(self, tenant_id: str, operation: Optional[str] = None):
        """Invalidate cache for tenant (or specific operation)"""
        if operation:
            pattern = f"nexarch:{tenant_id}:{operation}*"
        else:
            pattern = f"nexarch:{tenant_id}:*"
        
        self.backend.delete_pattern(pattern)
        logger.info(f"Invalidated cache for tenant {tenant_id}, operation: {operation or 'all'}")
    
    def invalidate_all(self):
        """Invalidate all cache (admin only)"""
        self.backend.clear()
        logger.warning("All cache invalidated")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.backend.get_stats()
    
    def is_redis(self) -> bool:
        """Check if using Redis backend"""
        return isinstance(self.backend, RedisCacheBackend)


# Global cache instance (initialized in main.py)
_cache_manager: Optional[CacheManager] = None


def init_cache(redis_url: Optional[str] = None, ttl_seconds: int = 300) -> CacheManager:
    """Initialize global cache manager"""
    global _cache_manager
    _cache_manager = CacheManager(redis_url, ttl_seconds)
    return _cache_manager


def get_cache_manager() -> CacheManager:
    """Get global cache manager (creates in-memory if not initialized)"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager(redis_url=None, ttl_seconds=300)
    return _cache_manager


# NOTE: Do not import `cache_manager` directly — use get_cache_manager() so you always
# get the Redis-initialized singleton set by init_cache() during app startup.
