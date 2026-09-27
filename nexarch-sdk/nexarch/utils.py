"""
Nexarch Utilities - Helper functions
"""
import re
from typing import Dict, Any


def sanitize_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Remove sensitive information from headers.
    
    Args:
        headers: Request headers
        
    Returns:
        Sanitized headers
    """
    sensitive_keys = [
        'authorization', 'cookie', 'api-key', 
        'x-api-key', 'token', 'password'
    ]
    
    sanitized = {}
    for key, value in headers.items():
        if key.lower() in sensitive_keys:
            sanitized[key] = '[REDACTED]'
        else:
            sanitized[key] = value
    
    return sanitized


def extract_route_pattern(path: str) -> str:
    """
    Extract route pattern from a specific path.
    
    Examples:
        /users/123 -> /users/{id}
        /api/v1/products/abc-def -> /api/v1/products/{id}
    
    Args:
        path: Request path
        
    Returns:
        Generalized route pattern
    """
    # Replace UUIDs
    path = re.sub(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
        '{id}',
        path,
        flags=re.IGNORECASE
    )
    
    # Replace numeric IDs
    path = re.sub(r'/\d+', '/{id}', path)
    
    # Replace alphanumeric IDs (common patterns)
    path = re.sub(r'/[a-zA-Z0-9_-]{8,}', '/{id}', path)
    
    return path


def format_bytes(bytes_size: int) -> str:
    """
    Format bytes to human-readable string.
    
    Args:
        bytes_size: Size in bytes
        
    Returns:
        Human-readable size (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def is_traceable_endpoint(path: str) -> bool:
    """
    Determine if an endpoint should be traced.
    
    Args:
        path: Request path
        
    Returns:
        True if endpoint should be traced
    """
    # Skip common health check and static file endpoints
    skip_patterns = [
        r'^/health',
        r'^/ping',
        r'^/metrics',
        r'^/static/',
        r'^\/_next',
        r'^/favicon\.ico'
    ]
    
    for pattern in skip_patterns:
        if re.match(pattern, path):
            return False
    
    return True