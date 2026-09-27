"""
Auto-Discovery Module - Automatically detect architecture patterns from FastAPI apps
Discovers:
- All API endpoints and their response models
- Request → Response flows
- Database connections (SQLAlchemy, MongoDB, Redis)
- External service calls (httpx, requests, aiohttp)
- Service boundaries and dependencies
- Traffic patterns and routing
"""
import inspect
import os
from typing import Dict, List, Any, Optional, Set
from datetime import datetime


class ArchitectureDiscovery:
    """Auto-discovers architecture patterns from FastAPI application"""
    
    def __init__(self, app, service_name: str):
        self.app = app
        self.service_name = service_name
        self.endpoints: List[Dict[str, Any]] = []
        self.databases: List[Dict[str, Any]] = []
        self.external_services: Set[str] = set()
        self.dependencies: Dict[str, List[str]] = {}
        
    def discover_all(self) -> Dict[str, Any]:
        """Run all discovery methods"""
        return {
            "service_name": self.service_name,
            "service_type": self._detect_service_type(),
            "endpoints": self.discover_endpoints(),
            "databases": self.discover_databases(),
            "external_services": list(self.external_services),
            "dependencies": self.dependencies,
            "architecture_patterns": self.detect_patterns(),
            "discovered_at": datetime.utcnow().isoformat()
        }
    
    def discover_endpoints(self) -> List[Dict[str, Any]]:
        """
        Discover all API endpoints, their methods, paths, and dependencies
        Maps: endpoint → database connections → external calls
        """
        endpoints = []
        
        try:
            # Get all routes from FastAPI app
            for route in self.app.routes:
                if hasattr(route, 'methods') and hasattr(route, 'path'):
                    endpoint_info = {
                        "path": route.path,
                        "methods": list(route.methods),
                        "name": route.name if hasattr(route, 'name') else None,
                        "endpoint_function": None,
                        "calls_database": False,
                        "calls_external": False,
                        "dependencies": [],
                        "response_model": None,
                        "request_model": None
                    }
                    
                    # Get endpoint function details
                    if hasattr(route, 'endpoint'):
                        func = route.endpoint
                        endpoint_info["endpoint_function"] = func.__name__
                        
                        # Analyze function signature for dependencies
                        sig = inspect.signature(func)
                        for param_name, param in sig.parameters.items():
                            # Check for database session injection
                            if 'db' in param_name.lower() or 'session' in param_name.lower():
                                endpoint_info["calls_database"] = True
                                endpoint_info["dependencies"].append(f"database:{param_name}")
                            
                            # Check for other service dependencies
                            if 'client' in param_name.lower() or 'service' in param_name.lower():
                                endpoint_info["calls_external"] = True
                                endpoint_info["dependencies"].append(f"service:{param_name}")
                        
                        # Get response model
                        if hasattr(route, 'response_model') and route.response_model:
                            endpoint_info["response_model"] = str(route.response_model)
                        
                        # Analyze function source code for patterns
                        try:
                            source = inspect.getsource(func)
                            
                            # Detect database queries
                            if any(keyword in source for keyword in ['query(', 'filter(', 'select(', 'insert(', 'update(', 'delete(']):
                                endpoint_info["calls_database"] = True
                            
                            # Detect external HTTP calls
                            if any(keyword in source for keyword in ['httpx.', 'requests.', 'aiohttp.', '.get(', '.post(', '.put(', '.delete(']):
                                endpoint_info["calls_external"] = True
                            
                            # Detect cache usage
                            if any(keyword in source for keyword in ['redis', 'cache', 'memcached']):
                                endpoint_info["dependencies"].append("cache:redis")
                            
                            # Detect message queue usage
                            if any(keyword in source for keyword in ['celery', 'rabbitmq', 'kafka', 'sqs']):
                                endpoint_info["dependencies"].append("queue:message_queue")
                        
                        except (OSError, TypeError):
                            # Source not available (built-in or compiled)
                            pass
                    
                    endpoints.append(endpoint_info)
            
            self.endpoints = endpoints
            return endpoints
        
        except Exception as e:
            return [{"error": f"Failed to discover endpoints: {str(e)}"}]
    
    def discover_databases(self) -> List[Dict[str, Any]]:
        """
        Discover database connections (SQLAlchemy, MongoDB, Redis, etc.)
        """
        databases = []
        
        try:
            # Check for SQLAlchemy
            try:
                import sqlalchemy
                # Try to find database engines in the app
                if hasattr(self.app, 'state'):
                    for attr_name in dir(self.app.state):
                        attr = getattr(self.app.state, attr_name)
                        if hasattr(attr, 'url'):  # Database engine
                            db_url = str(attr.url)
                            databases.append({
                                "type": "relational",
                                "engine": "sqlalchemy",
                                "driver": db_url.split(':')[0] if ':' in db_url else "unknown",
                                "connection": self._sanitize_db_url(db_url),
                                "discovered_from": "app.state"
                            })
            except ImportError:
                pass
            
            # Check environment variables for database URLs
            db_env_vars = [
                'DATABASE_URL', 'DB_URL', 'SQLALCHEMY_DATABASE_URL',
                'POSTGRES_URL', 'MYSQL_URL', 'MONGODB_URI', 'REDIS_URL'
            ]
            
            for env_var in db_env_vars:
                value = os.environ.get(env_var)
                if value:
                    db_type = "relational"
                    if "mongodb" in value.lower():
                        db_type = "document"
                    elif "redis" in value.lower():
                        db_type = "cache"
                    
                    databases.append({
                        "type": db_type,
                        "engine": env_var.lower().replace('_url', '').replace('_uri', ''),
                        "connection": self._sanitize_db_url(value),
                        "discovered_from": f"env:{env_var}"
                    })
            
            # Check for Redis
            try:
                import redis
                databases.append({
                    "type": "cache",
                    "engine": "redis",
                    "discovered_from": "import:redis"
                })
            except ImportError:
                pass
            
            # Check for MongoDB
            try:
                import pymongo
                databases.append({
                    "type": "document",
                    "engine": "mongodb",
                    "discovered_from": "import:pymongo"
                })
            except ImportError:
                pass
            
            self.databases = databases
            return databases
        
        except Exception as e:
            return [{"error": f"Failed to discover databases: {str(e)}"}]
    
    def detect_patterns(self) -> Dict[str, Any]:
        """
        Detect architectural patterns:
        - Monolith vs Microservice
        - API Gateway pattern
        - Database per service
        - Shared database
        - Circuit breaker
        - Rate limiting
        """
        patterns = {
            "service_type": "unknown",
            "has_api_gateway": False,
            "database_pattern": "unknown",
            "has_circuit_breaker": False,
            "has_rate_limiting": False,
            "has_caching": False,
            "has_authentication": False,
            "middleware_stack": []
        }
        
        try:
            # Detect service type
            endpoint_count = len(self.endpoints)
            if endpoint_count > 20:
                patterns["service_type"] = "monolith"
            elif endpoint_count > 5:
                patterns["service_type"] = "microservice"
            else:
                patterns["service_type"] = "mini-service"
            
            # Check middleware for patterns
            if hasattr(self.app, 'user_middleware'):
                for middleware in self.app.user_middleware:
                    middleware_name = middleware.cls.__name__
                    patterns["middleware_stack"].append(middleware_name)
                    
                    if 'cors' in middleware_name.lower():
                        patterns["has_api_gateway"] = True
                    if 'rate' in middleware_name.lower() or 'limit' in middleware_name.lower():
                        patterns["has_rate_limiting"] = True
                    if 'auth' in middleware_name.lower():
                        patterns["has_authentication"] = True
                    if 'circuit' in middleware_name.lower() or 'breaker' in middleware_name.lower():
                        patterns["has_circuit_breaker"] = True
            
            # Check for caching
            if any('cache' in str(db).lower() or 'redis' in str(db).lower() for db in self.databases):
                patterns["has_caching"] = True
            
            # Database pattern
            db_count = len(self.databases)
            if db_count == 0:
                patterns["database_pattern"] = "stateless"
            elif db_count == 1:
                patterns["database_pattern"] = "shared_database"
            else:
                patterns["database_pattern"] = "database_per_service"
            
            return patterns
        
        except Exception as e:
            patterns["error"] = str(e)
            return patterns
    
    def _detect_service_type(self) -> str:
        """Detect if this is a monolith, microservice, or API gateway"""
        endpoint_count = len(self.app.routes) if hasattr(self.app, 'routes') else 0
        
        if endpoint_count > 30:
            return "monolith"
        elif endpoint_count > 10:
            return "service"
        elif endpoint_count < 5:
            return "microservice"
        else:
            return "api"
    
    def _sanitize_db_url(self, url: str) -> str:
        """Remove credentials from database URL"""
        try:
            # Remove password from URL
            if '@' in url:
                parts = url.split('@')
                if len(parts) >= 2:
                    prefix = parts[0].split('://')[0]
                    user = parts[0].split('://')[1].split(':')[0] if '://' in parts[0] else parts[0].split(':')[0]
                    host_and_rest = '@'.join(parts[1:])
                    return f"{prefix}://{user}:***@{host_and_rest}"
            return url
        except Exception:
            return "***"


class DependencyMapper:
    """
    Maps dependencies between services, databases, and external APIs
    Tracks: endpoint → DB → external API chains
    """
    
    def __init__(self):
        self.dependency_graph: Dict[str, List[Dict[str, Any]]] = {}
        self.latency_chains: List[Dict[str, Any]] = []
    
    def add_dependency(self, source: str, target: str, dep_type: str, metadata: Optional[Dict] = None):
        """Add a dependency edge"""
        if source not in self.dependency_graph:
            self.dependency_graph[source] = []
        
        self.dependency_graph[source].append({
            "target": target,
            "type": dep_type,
            "metadata": metadata or {}
        })
    
    def add_latency_chain(self, chain: List[str], total_latency_ms: float):
        """Track latency propagation through call chain"""
        self.latency_chains.append({
            "chain": chain,
            "total_latency_ms": total_latency_ms,
            "hop_count": len(chain) - 1
        })
    
    def get_dependency_map(self) -> Dict[str, Any]:
        """Get complete dependency mapping"""
        return {
            "dependencies": self.dependency_graph,
            "latency_chains": self.latency_chains,
            "total_services": len(self.dependency_graph),
            "total_dependencies": sum(len(deps) for deps in self.dependency_graph.values())
        }


class TrafficAnalyzer:
    """
    Analyze traffic patterns from captured spans
    Detects:
    - Hot paths (most frequently called endpoints)
    - Error-prone paths
    - Latency distributions
    - Request volumes over time
    """
    
    def __init__(self):
        self.endpoint_stats: Dict[str, Dict[str, Any]] = {}
    
    def record_request(self, endpoint: str, latency_ms: float, status_code: int):
        """Record a request for traffic analysis"""
        if endpoint not in self.endpoint_stats:
            self.endpoint_stats[endpoint] = {
                "total_requests": 0,
                "total_errors": 0,
                "total_latency_ms": 0,
                "min_latency_ms": float('inf'),
                "max_latency_ms": 0,
                "status_codes": {}
            }
        
        stats = self.endpoint_stats[endpoint]
        stats["total_requests"] += 1
        stats["total_latency_ms"] += latency_ms
        stats["min_latency_ms"] = min(stats["min_latency_ms"], latency_ms)
        stats["max_latency_ms"] = max(stats["max_latency_ms"], latency_ms)
        
        if status_code >= 500:
            stats["total_errors"] += 1
        
        status_key = str(status_code)
        stats["status_codes"][status_key] = stats["status_codes"].get(status_key, 0) + 1
    
    def get_traffic_patterns(self) -> Dict[str, Any]:
        """Get analyzed traffic patterns"""
        patterns = {
            "hot_paths": [],
            "error_prone_paths": [],
            "slow_paths": [],
            "total_requests": 0
        }
        
        for endpoint, stats in self.endpoint_stats.items():
            total_requests = stats["total_requests"]
            patterns["total_requests"] += total_requests
            
            avg_latency = stats["total_latency_ms"] / total_requests if total_requests > 0 else 0
            error_rate = stats["total_errors"] / total_requests if total_requests > 0 else 0
            
            # Hot paths (high traffic)
            if total_requests > 100:
                patterns["hot_paths"].append({
                    "endpoint": endpoint,
                    "requests": total_requests,
                    "avg_latency_ms": round(avg_latency, 2)
                })
            
            # Error-prone paths
            if error_rate > 0.05:
                patterns["error_prone_paths"].append({
                    "endpoint": endpoint,
                    "error_rate": round(error_rate, 4),
                    "total_errors": stats["total_errors"]
                })
            
            # Slow paths
            if avg_latency > 1000:
                patterns["slow_paths"].append({
                    "endpoint": endpoint,
                    "avg_latency_ms": round(avg_latency, 2),
                    "max_latency_ms": stats["max_latency_ms"]
                })
        
        # Sort by relevance
        patterns["hot_paths"].sort(key=lambda x: x["requests"], reverse=True)
        patterns["error_prone_paths"].sort(key=lambda x: x["error_rate"], reverse=True)
        patterns["slow_paths"].sort(key=lambda x: x["avg_latency_ms"], reverse=True)
        
        return patterns
