"""Dashboard – Insights sub-router: /insights, /recommendations, /workflows"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from db.base import get_db
from db.models import Span
import networkx as nx
from dependencies.auth import get_tenant_id_from_jwt
from core.cache import get_cache_manager
from core.ai_client import get_ai_client
from services.graph_service import GraphService
from services.metrics_service import MetricsService
from services.issue_detector import IssueDetector
from services.workflow_generator import WorkflowGenerator
from reasoning.graph_analysis import GraphAnalysis
from datetime import datetime, timedelta
from core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/insights")
async def get_ai_insights(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db)
):
    """AI-powered insights and anomalies. Cached per tenant."""
    cache = get_cache_manager()
    cached = cache.get(tenant_id, "ai_insights") if cache else None
    if cached:
        return cached

    try:
        metrics = MetricsService.compute_global_metrics(db, tenant_id)
        start_time = datetime.utcnow() - timedelta(hours=24)
        recent_spans = db.query(Span).filter(
            Span.tenant_id == tenant_id,
            Span.start_time >= start_time,
        ).all()

        trends = []
        if recent_spans:
            hourly: dict = {}
            for span in recent_spans:
                hour = span.start_time.replace(minute=0, second=0, microsecond=0)
                hourly.setdefault(hour, []).append(span.latency_ms)
            for hour, lats in hourly.items():
                trends.append({"timestamp": hour.isoformat(), "avg_latency": sum(lats) / len(lats)})

        ai_client = get_ai_client()

        if ai_client.llm:
            insights_data = await ai_client.generate_dashboard_insights(metrics, trends)
            if cache:
                cache.set(tenant_id, "ai_insights", insights_data)
            return insights_data

        # Rule-based fallback
        insights = []
        if metrics["error_rate"] > 0.05:
            insights.append({
                "type": "alert", "severity": "high",
                "title": "High Error Rate Detected",
                "description": f"Error rate is {metrics['error_rate']*100:.1f}%, above the 5% threshold",
                "recommendation": "Review recent deployments and check service logs",
                "confidence": 0.95,
            })
        if metrics["avg_latency_ms"] > 1000:
            insights.append({
                "type": "alert", "severity": "medium",
                "title": "High Latency Detected",
                "description": f"Average latency is {metrics['avg_latency_ms']:.0f}ms",
                "recommendation": "Consider adding caching or optimising database queries",
                "confidence": 0.90,
            })
        if len(trends) > 2:
            recent_avg = sum(t["avg_latency"] for t in trends[-3:]) / 3
            if recent_avg > metrics["avg_latency_ms"] * 1.5:
                insights.append({
                    "type": "anomaly", "severity": "medium",
                    "title": "Latency Spike Detected",
                    "description": "Recent latency is 50% higher than average",
                    "recommendation": "Investigate recent changes or increased load",
                    "confidence": 0.85,
                })

        result = {
            "insights": insights, "anomalies": [],
            "recommendations": [
                "Enable Redis caching to improve response times",
                "Implement circuit breakers for external API calls",
                "Add database read replicas to distribute load",
            ],
        }
        if cache:
            cache.set(tenant_id, "ai_insights", result)
        return result

    except Exception as e:
        logger.error(f"Error generating insights: {e}")
        return {"insights": [], "anomalies": [], "recommendations": [], "error": str(e)}


@router.get("/recommendations")
async def get_ai_architecture_recommendations(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db)
):
    """AI-powered architecture recommendations. Cached per tenant."""
    cache = get_cache_manager()
    cached = cache.get(tenant_id, "ai_recommendations") if cache else None
    if cached:
        return cached

    try:
        nodes, edges = GraphService.build_graph(db, tenant_id)
        issues = await IssueDetector.detect_issues(db, tenant_id)
        # Build nx graph from already-loaded data — avoids a second DB round-trip
        G = nx.DiGraph()
        for node in nodes:
            G.add_node(node.id, type=node.type, metrics=node.metrics.model_dump())
        for edge in edges:
            G.add_edge(edge.source, edge.target,
                       call_count=edge.call_count,
                       avg_latency_ms=edge.avg_latency_ms,
                       error_rate=edge.error_rate)
        analysis = GraphAnalysis.analyze_architecture(G)

        architecture = {
            "services": [{"name": n.id, "type": n.type, "metrics": n.metrics.model_dump()} for n in nodes],
            "dependencies": [{"from": e.source, "to": e.target} for e in edges],
            "is_dag": analysis.get("is_dag", True),
            "bottlenecks": analysis.get("bottlenecks", []),
        }

        ai_client = get_ai_client()
        if ai_client.llm:
            recommendations = await ai_client.generate_architecture_recommendation(
                architecture=architecture,
                issues=[i.model_dump() for i in issues],
                constraints={"budget": "medium", "timeline": "3-6 months"},
            )
            result = {
                "recommendations": recommendations,
                "current_state": {
                    "services": len(nodes),
                    "dependencies": len(edges),
                    "critical_issues": len([i for i in issues if i.severity == "critical"]),
                    "architecture_type": "microservices" if len(nodes) > 5 else "monolith",
                },
                "generated_at": datetime.utcnow().isoformat(),
            }
        else:
            result = {
                "recommendations": {
                    "architecture_type": "microservices" if len(nodes) > 5 else "monolith",
                    "patterns": ["circuit-breaker", "rate-limiting", "caching"],
                    "optimizations": [
                        "Add Redis caching layer",
                        "Implement async processing for long-running tasks",
                        "Add database connection pooling",
                    ],
                    "migrations": [],
                    "risk_assessment": "medium",
                    "estimated_effort": "2-3 months",
                    "priority": "medium",
                },
                "note": "Azure OpenAI not configured - using rule-based recommendations",
                "generated_at": datetime.utcnow().isoformat(),
            }

        if cache:
            cache.set(tenant_id, "ai_recommendations", result)
        return result

    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        return {"error": str(e), "recommendations": None}


@router.get("/workflows")
async def generate_workflow_alternatives(
    tenant_id: str = Depends(get_tenant_id_from_jwt),
    db: Session = Depends(get_db),
    goal: str = Query(
        default="optimize_performance",
        description="optimize_performance | reduce_cost | improve_reliability",
    ),
):
    """
    AI-powered workflow alternatives (THE KILLER FEATURE).
    Generates architecture refactoring workflows via Azure OpenAI + LangGraph.
    Cached per tenant + goal.
    """
    cache_key = f"workflows_{goal}"
    cache = get_cache_manager()
    cached = cache.get(tenant_id, cache_key) if cache else None
    if cached:
        logger.info(f"Returning cached workflows tenant={tenant_id} goal={goal}")
        return cached

    try:
        nodes, edges = GraphService.build_graph(db, tenant_id)
        issues = await IssueDetector.detect_issues(db, tenant_id)
        # Build nx graph from already-loaded nodes/edges — avoids a second DB round-trip
        G = nx.DiGraph()
        for _n in nodes:
            G.add_node(_n.id, type=_n.type, metrics=_n.metrics.model_dump())
        for _e in edges:
            G.add_edge(_e.source, _e.target, call_count=_e.call_count, avg_latency_ms=_e.avg_latency_ms, error_rate=_e.error_rate)
        analysis = GraphAnalysis.analyze_architecture(G)

        architecture = {
            "services":     [{"name": n.id, "type": n.type, "metrics": n.metrics.model_dump()} for n in nodes],
            "dependencies": [{"from": e.source, "to": e.target, "metrics": e.model_dump()} for e in edges],
            "analysis":     {"is_dag": analysis.get("is_dag", True), "bottlenecks": analysis.get("bottlenecks", []), "critical_paths": analysis.get("critical_paths", [])},
        }

        ai_client = get_ai_client()
        if ai_client.llm:
            logger.info(f"Generating AI workflows tenant={tenant_id} goal={goal}")
            ai_result = await ai_client.generate_workflow_alternatives(
                architecture=architecture,
                issues=[i.model_dump() for i in issues],
                goal=goal,
            )
            generator = WorkflowGenerator()
            workflows = generator.generate_workflows_sync(db, issues, tenant_id)
            result = {
                "ai_workflows": ai_result.get("workflows", []),
                "langgraph_workflow": workflows[0].model_dump() if workflows else None,
                "goal": goal,
                "architecture_summary": {
                    "total_services": len(nodes),
                    "total_dependencies": len(edges),
                    "critical_issues": len([i for i in issues if i.severity == "critical"]),
                },
                "generated_at": datetime.utcnow().isoformat(),
            }
        else:
            logger.warning("Azure OpenAI not configured, using LangGraph fallback")
            generator = WorkflowGenerator()
            workflows = generator.generate_workflows_sync(db, issues, tenant_id)
            result = {
                "workflows": [w.model_dump() for w in workflows],
                "goal": goal,
                "architecture_summary": {"total_services": len(nodes), "total_dependencies": len(edges), "critical_issues": len([i for i in issues if i.severity == "critical"])},
                "note": "Azure OpenAI not configured - using LangGraph pipeline only",
                "generated_at": datetime.utcnow().isoformat(),
            }

        if cache:
            cache.set(tenant_id, cache_key, result)
        return result

    except Exception as e:
        logger.error(f"Error generating workflows: {e}")
        return {"workflows": [], "error": str(e), "note": "Failed to generate workflows"}
