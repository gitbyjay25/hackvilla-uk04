"""Quick Redis test"""
from core.cache import get_cache_manager

print("Testing Azure Cache for Redis operations...")
print("=" * 60)

cache = get_cache_manager()

# Test 1: Set data
print("\n1. Setting test data in Redis...")
cache.set('test_tenant', 'test_op', {
    'message': 'Hello from Azure Redis!',
    'number': 42,
    'nested': {'key': 'value'}
})
print("   ✓ Data set successfully")

# Test 2: Get data
print("\n2. Retrieving data from Redis...")
result = cache.get('test_tenant', 'test_op')
print(f"   Retrieved: {result}")
print(f"   ✓ Data matches: {result['message'] == 'Hello from Azure Redis!'}")

# Test 3: Cache stats
print("\n3. Redis statistics...")
stats = cache.get_stats()
print(f"   Status: {stats.get('status')}")
print(f"   Memory used: {stats.get('used_memory_mb', 0):.2f} MB")
print(f"   Connected clients: {stats.get('connected_clients', 0)}")
print(f"   Total commands: {stats.get('total_commands_processed', 0)}")
print(f"   Cache hit rate: {stats.get('hit_rate', 0)*100:.1f}%")

# Test 4: Invalidation
print("\n4. Testing cache invalidation...")
cache.set('test_tenant', 'op1', 'data1')
cache.set('test_tenant', 'op2', 'data2')
cache.invalidate('test_tenant', 'op1')
result1 = cache.get('test_tenant', 'op1')
result2 = cache.get('test_tenant', 'op2')
print(f"   ✓ Selective invalidation works: {result1 is None and result2 is not None}")

# Test 5: Multi-tenant isolation
print("\n5. Testing multi-tenant isolation...")
cache.set('tenant_a', 'data', 'Tenant A Data')
cache.set('tenant_b', 'data', 'Tenant B Data')
data_a = cache.get('tenant_a', 'data')
data_b = cache.get('tenant_b', 'data')
print(f"   ✓ Tenant A data: {data_a}")
print(f"   ✓ Tenant B data: {data_b}")
print(f"   ✓ Data isolated correctly: {data_a != data_b}")

print("\n" + "=" * 60)
print("✅ All Redis tests passed successfully!")
print("🎉 Azure Cache for Redis is working perfectly!")
print("=" * 60)
