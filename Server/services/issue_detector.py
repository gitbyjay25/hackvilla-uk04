from sqlalchemy.orm import Session
import networkx as nx
from services.graph_service import GraphService
from services.metrics_service import MetricsService
from reasoning.rules import RuleEngine
from models.issue import Issue
from core.ai_client import get_ai_client
from core.logging import get_logger
from typing import List
import asyncio

logger = get_logger(__name__)


class IssueDetector:
    
    @staticmethod
    async def detect_issues_with_ai(db: Session, tenant_id: str) -> List[Issue]:
        """
        Detect issues using BOTH rule-based engine + Azure OpenAI.
        Graph is built exactly once and reused for both.
        """
        # Build graph ONCE — reused by rule engine and AI
        nodes, edges = GraphService.build_graph(db, tenant_id)

        # Reconstruct NetworkX graph from already-loaded data (no second DB query)
        G = nx.DiGraph()
        for node in nodes:
            G.add_node(node.id, type=node.type, metrics=node.metrics.model_dump())
        for edge in edges:
            G.add_edge(edge.source, edge.target,
                       call_count=edge.call_count,
                       avg_latency_ms=edge.avg_latency_ms,
                       error_rate=edge.error_rate)

        # Rule-based detection (fast, deterministic)
        rule_issues = RuleEngine.run_all_rules(G)
        logger.info(f"Rule engine detected {len(rule_issues)} issues")

        # AI-powered anomaly detection (intelligent, context-aware)
        ai_client = get_ai_client()
        ai_issues = []

        if ai_client.llm:
            try:
                # Reuse already-computed global metrics
                metrics = MetricsService.compute_global_metrics(db, tenant_id)
                
                architecture = {
                    "services": [{"name": n.id, "type": n.type, "metrics": n.metrics.model_dump()} for n in nodes],
                    "dependencies": [{"from": e.source, "to": e.target, "latency_ms": e.avg_latency_ms} for e in edges],
                    "global_metrics": metrics
                }
                
                # Use AI to find subtle issues
                ai_recommendations = await ai_client.generate_architecture_recommendation(
                    architecture=architecture,
                    issues=[i.model_dump() for i in rule_issues],
                    constraints={"timeline": "immediate", "risk_tolerance": "low"}
                )
                
                # Convert AI insights to Issue objects
                for insight in ai_recommendations.get("patterns", [])[:5]:  # Top 5 AI insights
                    ai_issue = Issue(
                        type="ai_detected_pattern",
                        severity="medium",
                        description=f"AI Detected: {insight}",
                        affected_services=[],
                        recommendation=f"Review and optimize based on AI analysis",
                        tenant_id=tenant_id
                    )
                    ai_issues.append(ai_issue)
                
                logger.info(f"Azure OpenAI detected {len(ai_issues)} additional patterns")
            
            except Exception as e:
                logger.error(f"AI issue detection failed: {e}")
        
        # Combine rule-based + AI issues
        all_issues = rule_issues + ai_issues
        logger.info(f"Total issues detected: {len(all_issues)} (Rules: {len(rule_issues)}, AI: {len(ai_issues)})")
        
        return all_issues
    
    
    @staticmethod
    async def detect_issues(db: Session, tenant_id: str) -> List[Issue]:
        """Detect issues using proper async/await pattern"""
        try:
            return await IssueDetector.detect_issues_with_ai(db, tenant_id)
        except Exception as e:
            # Fallback to rule-based only
            logger.warning(f"AI detection failed ({e}), falling back to rule-based detection")
            G = GraphService.get_graph_from_db(db, tenant_id)
            issues = RuleEngine.run_all_rules(G)
            logger.info(f"Detected {len(issues)} issues for tenant {tenant_id} (rule-based only)")
            return issues

