from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from db.base import SessionLocal
from services.graph_service import GraphService
from services.metrics_service import MetricsService
from services.issue_detector import IssueDetector
from services.workflow_generator import WorkflowGenerator
from reasoning.graph_analysis import GraphAnalysis
from core.logging import get_logger
from core.ai_client import get_ai_client

logger = get_logger(__name__)


class MCPTools:
    """MCP tool implementations - thin wrappers over services with AI integration"""
    
    def __init__(self, default_tenant_id: Optional[str] = None):
        self.workflow_generator = WorkflowGenerator()
        self.ai_client = get_ai_client()
        self.default_tenant_id = default_tenant_id or "default"
    
    def _get_db(self) -> Session:
        """Get DB session"""
        return SessionLocal()
    
    def get_current_architecture(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get architecture with tenant isolation"""
        tenant_id = tenant_id or self.default_tenant_id
        db = self._get_db()
        try:
            nodes, edges = GraphService.build_graph(db, tenant_id)
            metrics = MetricsService.compute_global_metrics(db, tenant_id)
            
            return {
                "tenant_id": tenant_id,
                "nodes": [n.model_dump() for n in nodes],
                "edges": [e.model_dump() for e in edges],
                "metrics_summary": metrics,
                "service_count": len(nodes),
                "dependency_count": len(edges)
            }
        finally:
            db.close()
    
    async def get_detected_issues(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get issues with AI enhancement"""
        tenant_id = tenant_id or self.default_tenant_id
        db = self._get_db()
        try:
            issues = await IssueDetector.detect_issues(db, tenant_id)
            
            # Categorize
            by_severity = {}
            by_type = {}
            for issue in issues:
                if issue.severity not in by_severity:
                    by_severity[issue.severity] = []
                by_severity[issue.severity].append(issue.model_dump())
                
                if issue.type not in by_type:
                    by_type[issue.type] = []
                by_type[issue.type].append(issue.model_dump())
            
            return {
                "tenant_id": tenant_id,
                "issues": [i.model_dump() for i in issues],
                "total_count": len(issues),
                "by_severity": by_severity,
                "by_type": by_type,
                "critical_count": len(by_severity.get("critical", [])),
                "high_count": len(by_severity.get("high", []))
            }
        finally:
            db.close()
    
    async def generate_workflows(self, tenant_id: Optional[str] = None, goal: str = "optimize_performance") -> Dict[str, Any]:
        """Generate workflows with AI + LangGraph"""
        tenant_id = tenant_id or self.default_tenant_id
        db = self._get_db()
        try:
            issues = await IssueDetector.detect_issues(db, tenant_id)
            workflows = await self.workflow_generator.generate_workflows_with_ai(db, issues, tenant_id, goal)
            
            return {
                "tenant_id": tenant_id,
                "goal": goal,
                "workflows": [w.model_dump() for w in workflows],
                "count": len(workflows),
                "generated_by": "LangGraph + Azure OpenAI" if self.ai_client.llm else "LangGraph only"
            }
        finally:
            db.close()
    
    async def compare_workflows(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Compare workflows with intelligent ranking"""
        tenant_id = tenant_id or self.default_tenant_id
        db = self._get_db()
        try:
            issues = await IssueDetector.detect_issues(db, tenant_id)
            workflows = await self.workflow_generator.generate_workflows_with_ai(db, issues, tenant_id)
            
            if not workflows:
                return {
                    "tenant_id": tenant_id,
                    "workflows": [],
                    "message": "No workflows generated"
                }
            
            # Comparison matrix
            comparison = {
                "complexity": {w.name: w.complexity_score for w in workflows},
                "risk": {w.name: w.risk_score for w in workflows},
                "changes": {w.name: len(w.proposed_changes) for w in workflows},
                "estimated_impact": {w.name: w.estimated_impact for w in workflows}
            }
            
            # Multi-criteria ranking
            ranked = []
            for w in workflows:
                score = (
                    (10 - w.complexity_score) * 0.3 +  # Lower complexity is better
                    (10 - w.risk_score) * 0.3 +        # Lower risk is better
                    w.estimated_impact * 10 * 0.4       # Higher impact is better
                )
                ranked.append({"workflow": w.name, "score": score})
            
            ranked.sort(key=lambda x: x["score"], reverse=True)
            best = ranked[0]["workflow"]
            
            return {
                "tenant_id": tenant_id,
                "workflows": [w.model_dump() for w in workflows],
                "comparison_matrix": comparison,
                "ranking": ranked,
                "recommendation": {
                    "workflow": best,
                    "reason": f"Best overall score considering complexity, risk, and impact"
                }
            }
        finally:
            db.close()
    
    async def explain_decision(self, workflow_id: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Explain workflow decision with AI reasoning"""
        tenant_id = tenant_id or self.default_tenant_id
        db = self._get_db()
        try:
            issues = await IssueDetector.detect_issues(db, tenant_id)
            workflows = await self.workflow_generator.generate_workflows_with_ai(db, issues, tenant_id)
            
            # Find workflow
            workflow = next((w for w in workflows if w.id == workflow_id), None)
            
            if not workflow:
                return {"error": f"Workflow {workflow_id} not found"}
            
            # Build explanation
            explanation = {
                "tenant_id": tenant_id,
                "workflow_id": workflow.id,
                "workflow_name": workflow.name,
                "description": workflow.description,
                "reasoning": {
                    "issues_addressed": len([i for i in issues if any(n in str(workflow.description) for n in i.affected_nodes)]),
                    "total_issues": len(issues),
                    "changes_proposed": len(workflow.proposed_changes),
                    "complexity_level": self._explain_complexity(workflow),
                    "risk_level": self._explain_risk(workflow),
                    "estimated_impact": f"{workflow.estimated_impact * 100}%"
                },
                "decision_factors": {
                    "pros": workflow.pros,
                    "cons": workflow.cons,
                    "expected_impact": workflow.expected_impact
                },
                "implementation": {
                    "changes": [c.model_dump() for c in workflow.proposed_changes],
                    "complexity_score": workflow.complexity_score,
                    "risk_score": workflow.risk_score
                }
            }
            
            return explanation
        finally:
            db.close()
    
    def get_graph_analysis(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Advanced graph analysis with AI insights"""
        tenant_id = tenant_id or self.default_tenant_id
        db = self._get_db()
        try:
            G = GraphService.get_graph_from_db(db, tenant_id)
            analysis = GraphAnalysis.analyze_architecture(G)
            
            return {
                "tenant_id": tenant_id,
                "graph_metrics": analysis,
                "insights": self._generate_insights(analysis),
                "recommendations": self._generate_recommendations(analysis)
            }
        finally:
            db.close()
    
    def _explain_complexity(self, workflow) -> str:
        """Explain complexity score"""
        score = workflow.complexity_score
        if score <= 3:
            return "LOW - Simple changes with minimal new components"
        elif score <= 6:
            return "MEDIUM - Moderate changes requiring new infrastructure"
        else:
            return "HIGH - Complex changes requiring significant architectural shifts"
    
    def _explain_risk(self, workflow) -> str:
        """Explain risk score"""
        score = workflow.risk_score
        if score <= 3:
            return "LOW - Low risk with easy rollback"
        elif score <= 6:
            return "MEDIUM - Moderate risk requiring careful testing"
        else:
            return "HIGH - High risk with potential for service disruption"
    
    def _generate_insights(self, analysis: Dict) -> List[str]:
        """Generate insights from graph analysis"""
        insights = []
        
        if not analysis.get("is_dag"):
            insights.append("⚠️ CRITICAL: Circular dependencies detected - this can cause deadlocks")
        
        bottlenecks = analysis.get("bottlenecks", [])
        if len(bottlenecks) > 0:
            insights.append(f"⚠️ WARNING: {len(bottlenecks)} bottleneck services found: {', '.join(bottlenecks[:3])}")
        
        if len(analysis.get("critical_paths", [])) > 2:
            insights.append(f"📊 INFO: {len(analysis['critical_paths'])} critical execution paths identified")
        
        avg_degree = analysis.get("avg_degree", 0)
        if avg_degree > 5:
            insights.append(f"⚠️ WARNING: High coupling detected (avg degree: {avg_degree:.1f})")
        elif avg_degree < 2:
            insights.append(f"✅ GOOD: Low coupling (avg degree: {avg_degree:.1f})")
        
        node_count = analysis.get("node_count", 0)
        if node_count > 20:
            insights.append("📈 Large architecture - consider service consolidation")
        
        return insights
    
    def _generate_recommendations(self, analysis: Dict) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        if not analysis.get("is_dag"):
            recommendations.append("Break circular dependencies by introducing message queues or event-driven patterns")
        
        if len(analysis.get("bottlenecks", [])) > 0:
            recommendations.append("Scale bottleneck services horizontally or add caching layers")
        
        if analysis.get("avg_degree", 0) > 5:
            recommendations.append("Reduce coupling by introducing API gateways or service mesh")
        
        if len(recommendations) == 0:
            recommendations.append("Architecture looks healthy - focus on monitoring and optimization")
        
        return recommendations
