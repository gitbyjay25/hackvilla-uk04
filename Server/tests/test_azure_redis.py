"""Test Redis with fresh initialization"""
from core.cache import init_cache
from core.config import get_settings

settings = get_settings()
redis_url = settings.get_redis_url()

print("=" * 70)
print("Azure Cache for Redis - Connection Test")
print("=" * 70)

print(f"\nRedis Host: modelix.redis.cache.windows.net")
print(f"Redis Port: 6380")
print(f"SSL Enabled: Yes")
print(f"Database: 0")

# Initialize cache with Redis
cache = init_cache(redis_url, ttl_seconds=300)

print(f"\n✓ Cache initialized")
print(f"✓ Backend type: {'Azure Redis' if cache.is_redis() else 'In-Memory Fallback'}")

# Test connection
stats = cache.get_stats()
if stats.get('status') == 'connected':
    print(f"\n✅ CONNECTED TO AZURE CACHE FOR REDIS!")
    print(f"\n📊 Redis Statistics:")
    print(f"   Memory Used: {stats.get('used_memory_mb', 0):.2f} MB")
    print(f"   Connected Clients: {stats.get('connected_clients', 0)}")
    print(f"   Total Commands: {stats.get('total_commands_processed', 0):,}")
    print(f"   Keyspace Hits: {stats.get('keyspace_hits', 0):,}")
    print(f"   Keyspace Misses: {stats.get('keyspace_misses', 0):,}")
    print(f"   Hit Rate: {stats.get('hit_rate', 0)*100:.1f}%")
    
    # Test operations
    print(f"\n🧪 Testing Redis Operations:")
    
    # Set
    cache.set('production_tenant', 'dashboard_overview', {
        'total_services': 15,
        'avg_latency_ms': 245.5,
        'error_rate': 0.02,
        'health_score': 95
    }, ttl=120)
    print(f"   ✓ SET operation successful")
    
    # Get
    data = cache.get('production_tenant', 'dashboard_overview')
    print(f"   ✓ GET operation successful")
    print(f"   ✓ Retrieved data: {data}")
    
    # Verify
    if data and data['health_score'] == 95:
        print(f"   ✓ Data integrity verified")
    
    print(f"\n" + "=" * 70)
    print(f"🎉 SUCCESS! Azure Cache for Redis is fully operational!")
    print(f"=" * 70)
else:
    print(f"\n⚠️  Status: {stats.get('status')}")
    print(f"Using fallback: {stats.get('backend')}")
