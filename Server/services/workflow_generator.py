from sqlalchemy.orm import Session
from models.workflow import Workflow
from models.issue import Issue
from services.graph_service import GraphService
from reasoning.langgraph_pipeline import WorkflowReasoningPipeline
from core.logging import get_logger
from core.ai_client import get_ai_client
from typing import List
import asyncio

logger = get_logger(__name__)


class WorkflowGenerator:
    
    def __init__(self):
        self.pipeline = WorkflowReasoningPipeline()
        self.ai_client = get_ai_client()
    
    async def generate_workflows_with_ai(self, db: Session, issues: List[Issue], tenant_id: str, goal: str = "optimize_performance") -> List[Workflow]:
        """
        Generate workflows using BOTH LangGraph + Azure OpenAI for maximum intelligence
        Combines rule-based reasoning with AI creativity
        """
        G = GraphService.get_graph_from_db(db, tenant_id)
        
        # Get architecture summary
        nodes, edges = GraphService.build_graph(db, tenant_id)
        architecture = {
            "services": [{"name": n.id, "type": n.type, "metrics": n.metrics.model_dump()} for n in nodes],
            "dependencies": [{"from": e.source, "to": e.target} for e in edges],
        }
        
        # LangGraph reasoning (rule-based)
        langgraph_workflows = self.pipeline.run(G)
        logger.info(f"LangGraph generated {len(langgraph_workflows)} workflows")
        
        # Azure OpenAI reasoning (AI-powered)
        ai_workflows = []
        if self.ai_client.llm:
            try:
                ai_result = await self.ai_client.generate_workflow_alternatives(
                    architecture=architecture,
                    issues=[i.model_dump() for i in issues],
                    goal=goal
                )
                
                # Convert AI workflows to Workflow objects
                for ai_workflow in ai_result.get("workflows", []):
                    workflow = Workflow(
                        name=ai_workflow.get("name", "AI Generated Workflow"),
                        description=ai_workflow.get("description", ""),
                        steps=ai_workflow.get("steps", []),
                        estimated_impact=ai_workflow.get("impact_score", 0.8),
                        complexity="medium",
                        tenant_id=tenant_id
                    )
                    ai_workflows.append(workflow)
                
                logger.info(f"Azure OpenAI generated {len(ai_workflows)} creative workflows")
            except Exception as e:
                logger.error(f"AI workflow generation failed: {e}")
        
        # Combine both approaches
        all_workflows = langgraph_workflows + ai_workflows
        logger.info(f"Total workflows generated: {len(all_workflows)} (LangGraph: {len(langgraph_workflows)}, AI: {len(ai_workflows)})")
        
        return all_workflows
    
    def generate_workflows_sync(self, db: Session, issues: List[Issue], tenant_id: str) -> List[Workflow]:
        """
        LangGraph-only fallback for contexts where asyncio.run() is not usable.
        Callers inside async handlers should use `await generate_workflows_with_ai()` directly.
        """
        G = GraphService.get_graph_from_db(db, tenant_id)
        workflows = self.pipeline.run(G)
        logger.info(f"Generated {len(workflows)} workflows via LangGraph (sync) for tenant {tenant_id}")
        return workflows


