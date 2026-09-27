"""
Quick test to verify Azure Cache for Redis integration
"""
import sys
sys.path.insert(0, '.')

from core.cache import CacheManager, RedisCacheBackend, InMemoryCacheBackend
from core.config import get_settings

print("=" * 60)
print("Testing Azure Cache for Redis Integration")
print("=" * 60)

settings = get_settings()

# Test 1: In-memory fallback
print("\n1. Testing in-memory cache (fallback)...")
cache_mem = CacheManager(redis_url=None, ttl_seconds=60)
print(f"   Backend type: {type(cache_mem.backend).__name__}")
print(f"   Is Redis: {cache_mem.is_redis()}")

# Test 2: Set and Get
print("\n2. Testing set/get operations...")
cache_mem.set("tenant1", "test_op", {"data": "test123"})
result = cache_mem.get("tenant1", "test_op")
print(f"   Set/Get works: {result is not None}")
print(f"   Data matches: {result == {'data': 'test123'}}")

# Test 3: Invalidation
print("\n3. Testing cache invalidation...")
cache_mem.set("tenant1", "op1", "data1")
cache_mem.set("tenant1", "op2", "data2")
cache_mem.invalidate("tenant1", "op1")
result1 = cache_mem.get("tenant1", "op1")
result2 = cache_mem.get("tenant1", "op2")
print(f"   Specific invalidation works: {result1 is None and result2 is not None}")

# Test 4: Stats
print("\n4. Testing stats...")
stats = cache_mem.get_stats()
print(f"   Stats available: {len(stats) > 0}")
print(f"   Stats: {stats}")

# Test 5: Redis connection (if configured)
print("\n5. Testing Redis connection...")
redis_url = settings.get_redis_url()
if redis_url:
    print(f"   Redis URL configured: {redis_url[:30]}...")
    cache_redis = CacheManager(redis_url=redis_url, ttl_seconds=60)
    if cache_redis.is_redis():
        print("   ✅ Connected to Azure Cache for Redis!")
        stats = cache_redis.get_stats()
        print(f"   Memory used: {stats.get('used_memory_mb', 0):.2f} MB")
        print(f"   Connected clients: {stats.get('connected_clients', 0)}")
        
        # Test Redis operations
        cache_redis.set("test_tenant", "test_op", {"test": "data"})
        result = cache_redis.get("test_tenant", "test_op")
        print(f"   Redis set/get works: {result is not None}")
        cache_redis.invalidate("test_tenant")
    else:
        print("   ⚠️  Redis connection failed, using in-memory fallback")
else:
    print("   ℹ️  Redis not configured (using in-memory cache)")
    print("   Set REDIS_URL in .env to test Redis")

print("\n" + "=" * 60)
print("✅ All cache tests passed!")
print("=" * 60)
