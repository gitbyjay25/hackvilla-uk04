"""Dashboard – Overview sub-router: /overview, /architecture-map, /services, /health, /dependencies, /bottlenecks"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import networkx as nx
from db.base import get_db
from db.models import Span
from dependencies.auth import get_tenant_id_from_jwt
from core.cache import get_cache_manager
from services.graph_service import GraphService
from services.metrics_service import MetricsService
from services.issue_detector import IssueDetector
from reasoning.graph_analysis import GraphAnalysis
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


class DashboardOverview(BaseModel):
    total_services: int
    total_requests: int
    avg_latency_ms: float
    error_rate: float
    health_score: int
    critical_issues: int
    warnings: int
    architecture_complexity: float
    active_incidents: int
    uptime_percentage: float
    last_updated: str


class ServiceDetail(BaseModel):
    name: str
    type: str
    request_count: int
    avg_latency_ms: float
    error_rate: float
    dependencies: List[str]
    dependents: List[str]
    health_status: str
    last_seen: str


@router.get("/overview", response_model=DashboardOverview)
async def get_dashboard_overview(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db)
):
    """High-level dashboard overview with all key metrics. Cached 2 min."""
    cache = get_cache_manager()
    cached = cache.get(tenant_id, "dashboard_overview") if cache else None
    if cached:
        logger.info(f"✓ Cache HIT: dashboard_overview tenant {tenant_id}")
        return DashboardOverview(**cached)

    logger.info(f"✗ Cache MISS: dashboard_overview tenant {tenant_id}")

    nodes, edges = GraphService.build_graph(db, tenant_id)
    metrics = MetricsService.compute_global_metrics(db, tenant_id)
    issues = await IssueDetector.detect_issues(db, tenant_id)

    health_score = 100
    if metrics["error_rate"] > 0.05:
        health_score -= 30
    if metrics["avg_latency_ms"] > 1000:
        health_score -= 20
    critical_issues = len([i for i in issues if i.severity == "critical"])
    health_score -= critical_issues * 10
    health_score = max(0, min(100, health_score))

    # Build nx graph from already-loaded data — no second DB round-trip
    G = nx.DiGraph()
    for node in nodes:
        G.add_node(node.id, type=node.type, metrics=node.metrics.model_dump())
    for edge in edges:
        G.add_edge(edge.source, edge.target,
                   call_count=edge.call_count,
                   avg_latency_ms=edge.avg_latency_ms,
                   error_rate=edge.error_rate)
    analysis = GraphAnalysis.analyze_architecture(G)
    uptime = (1 - metrics["error_rate"]) * 100

    overview = {
        "total_services": len(nodes),
        "total_requests": metrics["total_spans"],
        "avg_latency_ms": metrics["avg_latency_ms"],
        "error_rate": metrics["error_rate"],
        "health_score": health_score,
        "critical_issues": critical_issues,
        "warnings": len([i for i in issues if i.severity in ["high", "medium"]]),
        "architecture_complexity": analysis.get("avg_degree", 0),
        "active_incidents": critical_issues,
        "uptime_percentage": round(uptime, 2),
        "last_updated": datetime.utcnow().isoformat(),
    }

    if cache:
        cache.set(tenant_id, "dashboard_overview", overview, ttl=120)

    return DashboardOverview(**overview)


@router.get("/architecture-map")
async def get_architecture_map(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db)
):
    """Architecture graph data optimised for visualisation."""
    try:
        nodes, edges = GraphService.build_graph(db, tenant_id)
        # Build the NetworkX graph from the already-fetched nodes/edges to avoid a second DB round trip
        import networkx as _nx
        G = _nx.DiGraph()
        for n in nodes:
            G.add_node(n.id, type=n.type)
        for e in edges:
            G.add_edge(e.source, e.target, call_count=e.call_count, avg_latency_ms=e.avg_latency_ms)
        analysis = GraphAnalysis.analyze_architecture(G)

        enriched_nodes = []
        for i, node in enumerate(nodes):
            nd = node.model_dump()
            nd["position"] = {"x": (i % 5) * 200, "y": (i // 5) * 150}
            enriched_nodes.append(nd)

        return {
            "nodes": enriched_nodes,
            "edges": [e.model_dump() for e in edges],
            "graph_stats": {
                "total_nodes": analysis.get("node_count", 0),
                "total_edges": analysis.get("edge_count", 0),
                "is_dag": analysis.get("is_dag", True),
                "avg_degree": analysis.get("avg_degree", 0),
            },
            "bottlenecks": analysis.get("bottlenecks", []),
            "critical_paths": analysis.get("critical_paths", []),
        }
    except Exception as e:
        logger.error(f"Failed to build architecture-map for tenant {tenant_id}: {e}")
        return {
            "nodes": [],
            "edges": [],
            "graph_stats": {
                "total_nodes": 0,
                "total_edges": 0,
                "is_dag": True,
                "avg_degree": 0,
            },
            "bottlenecks": [],
            "critical_paths": [],
            "error": "architecture_map_unavailable",
        }


@router.get("/services", response_model=List[ServiceDetail])
async def get_services(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db)
):
    """Detailed information about all services."""
    nodes, edges = GraphService.build_graph(db, tenant_id)

    services = []
    for node in nodes:
        dependencies = [e.target for e in edges if e.source == node.id]
        dependents = [e.source for e in edges if e.target == node.id]

        if node.metrics.error_rate > 0.1:
            health_status = "critical"
        elif node.metrics.error_rate > 0.05 or node.metrics.avg_latency_ms > 2000:
            health_status = "warning"
        else:
            health_status = "healthy"

        last_span = (
            db.query(Span)
            .filter(Span.tenant_id == tenant_id, Span.service_name == node.id)
            .order_by(Span.start_time.desc())
            .first()
        )
        last_seen = last_span.start_time.isoformat() if last_span else "unknown"

        services.append(ServiceDetail(
            name=node.id,
            type=node.type,
            request_count=node.metrics.call_count,
            avg_latency_ms=node.metrics.avg_latency_ms,
            error_rate=node.metrics.error_rate,
            dependencies=dependencies,
            dependents=dependents,
            health_status=health_status,
            last_seen=last_seen,
        ))

    return services


@router.get("/services/{service_name}/metrics")
async def get_service_metrics(
    service_name: str,
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db)
):
    """Metrics for a specific service."""
    nodes, _edges = GraphService.build_graph(db, tenant_id)
    node = next((n for n in nodes if n.id == service_name), None)
    if not node:
        raise HTTPException(status_code=404, detail="Service not found")
    return node.metrics


@router.get("/health")
async def get_system_health(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db)
):
    """System health scores by category."""
    metrics = MetricsService.compute_global_metrics(db, tenant_id)
    issues = await IssueDetector.detect_issues(db, tenant_id)
    G = GraphService.get_graph_from_db(db, tenant_id)
    analysis = GraphAnalysis.analyze_architecture(G)

    def latency_score(ms):
        if ms > 2000: return 50
        if ms > 1000: return 70
        if ms > 500:  return 85
        return 100

    def error_score(rate):
        if rate > 0.1:  return 50
        if rate > 0.05: return 70
        if rate > 0.02: return 85
        return 100

    perf   = latency_score(metrics["avg_latency_ms"])
    rel    = error_score(metrics["error_rate"])
    arch   = max(0, 100 - len([i for i in issues if i.severity == "critical"]) * 15
                         - len([i for i in issues if i.severity == "high"]) * 10)
    scale  = max(0, 100
                 - (0 if analysis.get("is_dag") else 20)
                 - (15 if len(analysis.get("bottlenecks", [])) > 2 else 0))
    overall = (perf + rel + arch + scale) // 4

    return {
        "overall_health": overall,
        "categories": {
            "performance":   {"score": perf,  "status": "good" if perf  >= 80 else "warning" if perf  >= 60 else "critical", "metrics": {"avg_latency_ms": metrics["avg_latency_ms"]}},
            "reliability":   {"score": rel,   "status": "good" if rel   >= 80 else "warning" if rel   >= 60 else "critical", "metrics": {"error_rate": metrics["error_rate"]}},
            "architecture":  {"score": arch,  "status": "good" if arch  >= 80 else "warning" if arch  >= 60 else "critical", "metrics": {"critical_issues": len([i for i in issues if i.severity == "critical"]), "total_issues": len(issues)}},
            "scalability":   {"score": scale, "status": "good" if scale >= 80 else "warning" if scale >= 60 else "critical", "metrics": {"bottlenecks": len(analysis.get("bottlenecks", [])), "has_cycles": not analysis.get("is_dag", True)}},
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/dependencies")
async def get_dependency_matrix(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db)
):
    """Dependency matrix for visualisation."""
    nodes, edges = GraphService.build_graph(db, tenant_id)
    service_names = [n.id for n in nodes]
    matrix = []
    for source in service_names:
        row = {}
        for target in service_names:
            edge = next((e for e in edges if e.source == source and e.target == target), None)
            row[target] = {"has_dependency": bool(edge), **({"call_count": edge.call_count, "avg_latency_ms": edge.avg_latency_ms, "error_rate": edge.error_rate} if edge else {})}
        matrix.append({"service": source, "dependencies": row})
    return {"services": service_names, "matrix": matrix}


@router.get("/bottlenecks")
async def get_bottlenecks(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db)
):
    """Critical path analysis and bottlenecks."""
    G = GraphService.get_graph_from_db(db, tenant_id)
    analysis = GraphAnalysis.analyze_architecture(G)
    return {
        "bottlenecks": analysis.get("bottlenecks", []),
        "critical_paths": analysis.get("critical_paths", []),
        "cycles": analysis.get("cycles", []),
        "recommendations": [
            f"Service '{b}' is a bottleneck - consider adding redundancy"
            for b in analysis.get("bottlenecks", [])[:3]
        ],
    }
