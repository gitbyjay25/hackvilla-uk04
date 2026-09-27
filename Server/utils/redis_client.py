"""
Redis cache client utilities
"""
from typing import Optional


async def cache_delete(key: str) -> bool:
    """
    Delete a key from cache
    
    Args:
        key: Cache key to delete
        
    Returns:
        True if successful, False otherwise
    """
    try:
        from core.cache import get_cache_manager
        cache_manager = get_cache_manager()
        if cache_manager:
            await cache_manager.delete(key)
            return True
    except Exception as e:
        print(f"Cache delete error: {e}")
    
    return False
