"""Rate limiting middleware"""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio


class RateLimiter:
    """Simple in-memory rate limiter (use Redis in production)"""
    
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)
        self.lock = asyncio.Lock()
    
    async def is_allowed(self, tenant_id: str, max_requests: int = 1000, window_seconds: int = 60) -> bool:
        """Check if request is allowed within rate limit"""
        async with self.lock:
            now = datetime.utcnow()
            window_start = now - timedelta(seconds=window_seconds)
            
            # Clean old requests
            self.requests[tenant_id] = [
                req_time for req_time in self.requests[tenant_id]
                if req_time > window_start
            ]
            
            # Check limit
            if len(self.requests[tenant_id]) >= max_requests:
                return False
            
            # Add current request
            self.requests[tenant_id].append(now)
            return True


rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware per tenant"""
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        # Get tenant_id from request state (set by auth middleware)
        tenant_id = getattr(request.state, "tenant_id", None)
        
        if tenant_id:
            allowed = await rate_limiter.is_allowed(tenant_id, max_requests=1000, window_seconds=60)
            if not allowed:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        response = await call_next(request)
        return response
