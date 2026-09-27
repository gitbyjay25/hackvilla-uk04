from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Annotated
import operator
from models.issue import Issue
from models.workflow import Workflow, WorkflowChange
from reasoning.rules import RuleEngine
from reasoning.graph_analysis import GraphAnalysis
import networkx as nx
import uuid


class ReasoningState(TypedDict):
    """LangGraph state"""
    graph: nx.DiGraph
    issues: Annotated[List[Issue], operator.add]
    issue_categories: dict
    strategy_selection: dict
    workflows: Annotated[List[Workflow], operator.add]
    analysis_complete: bool


class WorkflowReasoningPipeline:
    """Non-linear reasoning using LangGraph"""
    
    def __init__(self):
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build LangGraph pipeline with parallel strategy generation branches.

        Topology:
            detect_issues → classify_issues → analyze_graph → select_strategies
                                                                      │
                               ┌──────────────────────────────────────┤
                               ▼                  ▼                   ▼
                        generate_minimal  generate_performance  generate_cost
                               │                  │                   │
                               └──────────────────┴───────────────────┘
                                                  ▼
                                               finalize → END

        All three generators run in parallel after `select_strategies`.
        LangGraph waits for all branches to complete (fan-in) before `finalize`.
        The `workflows` field uses operator.add so each branch appends to the list.
        """
        workflow = StateGraph(ReasoningState)

        # Nodes
        workflow.add_node("detect_issues", self._detect_issues)
        workflow.add_node("classify_issues", self._classify_issues)
        workflow.add_node("analyze_graph", self._analyze_graph)
        workflow.add_node("select_strategies", self._select_strategies)
        workflow.add_node("generate_minimal", self._generate_minimal)
        workflow.add_node("generate_performance", self._generate_performance)
        workflow.add_node("generate_cost", self._generate_cost)
        workflow.add_node("finalize", self._finalize)

        # Linear pipeline: entry → strategy selection
        workflow.set_entry_point("detect_issues")
        workflow.add_edge("detect_issues", "classify_issues")
        workflow.add_edge("classify_issues", "analyze_graph")
        workflow.add_edge("analyze_graph", "select_strategies")

        # Parallel fan-out: add three independent edges from select_strategies.
        # LangGraph will execute all three destination nodes (one after another in the
        # same super-step, accumulating results via the operator.add reducer on `workflows`).
        workflow.add_edge("select_strategies", "generate_minimal")
        workflow.add_edge("select_strategies", "generate_performance")
        workflow.add_edge("select_strategies", "generate_cost")

        # Fan-in: each branch converges at finalize; finalize runs after all three complete.
        workflow.add_edge("generate_minimal", "finalize")
        workflow.add_edge("generate_performance", "finalize")
        workflow.add_edge("generate_cost", "finalize")
        workflow.add_edge("finalize", END)

        return workflow.compile()
    
    def _detect_issues(self, state: ReasoningState) -> ReasoningState:
        """Node: Detect issues"""
        G = state["graph"]
        issues = RuleEngine.run_all_rules(G)
        return {"issues": issues}
    
    def _classify_issues(self, state: ReasoningState) -> ReasoningState:
        """Node: Classify issues"""
        issues = state["issues"]
        
        categories = {
            "performance": [],
            "reliability": [],
            "scalability": [],
            "complexity": []
        }
        
        for issue in issues:
            if issue.type in ["high_latency_edge", "deep_sync_chain"]:
                categories["performance"].append(issue)
            elif issue.type in ["high_error_rate", "single_point_of_failure"]:
                categories["reliability"].append(issue)
            elif issue.type in ["fan_out_overload"]:
                categories["scalability"].append(issue)
        
        return {"issue_categories": categories}
    
    def _analyze_graph(self, state: ReasoningState) -> ReasoningState:
        """Node: Graph analysis"""
        G = state["graph"]
        analysis = GraphAnalysis.analyze_architecture(G)
        return {"strategy_selection": {"graph_analysis": analysis}}
    
    def _select_strategies(self, state: ReasoningState) -> ReasoningState:
        """Node: Select strategies"""
        categories = state["issue_categories"]
        
        strategies = {
            "needs_caching": len(categories.get("performance", [])) > 0,
            "needs_async": any(i.type == "deep_sync_chain" for i in categories.get("performance", [])),
            "needs_circuit_breaker": len(categories.get("reliability", [])) > 0,
            "needs_consolidation": len(categories.get("scalability", [])) > 0
        }
        
        return {"strategy_selection": {**state.get("strategy_selection", {}), **strategies}}
    
    def _generate_minimal(self, state: ReasoningState) -> ReasoningState:
        """Node: Minimal workflow"""
        issues = state["issues"][:3]
        changes = []
        
        for issue in issues:
            if issue.type == "high_latency_edge":
                changes.append(WorkflowChange(
                    type="caching",
                    target=issue.affected_nodes[0],
                    description=f"Add cache layer for {issue.affected_nodes[0]}",
                    impact="Reduce latency by 30-50%"
                ))
            elif issue.type == "high_error_rate":
                changes.append(WorkflowChange(
                    type="resilience",
                    target=issue.affected_nodes[0],
                    description=f"Add circuit breaker to {issue.affected_nodes[0]}",
                    impact="Prevent cascade failures"
                ))
        
        if not changes:
            changes.append(WorkflowChange(
                type="monitoring",
                target="all",
                description="Enhance observability",
                impact="Better visibility"
            ))
        
        workflow = Workflow(
            id=f"workflow-{uuid.uuid4().hex[:8]}",
            name="Minimal Change",
            description="Quick fixes with minimal infrastructure changes",
            proposed_changes=changes,
            pros=["Low risk", "Fast implementation", "Minimal downtime"],
            cons=["Limited impact", "May not solve root causes"],
            complexity_score=2,
            risk_score=1,
            expected_impact={
                "latency_improvement": "10-20%",
                "error_reduction": "20-30%",
                "cost_increase": "5-10%"
            }
        )
        
        return {"workflows": [workflow]}
    
    def _generate_performance(self, state: ReasoningState) -> ReasoningState:
        """Node: Performance workflow"""
        issues = state["issues"]
        strategies = state.get("strategy_selection", {})
        changes = []
        
        if strategies.get("needs_caching"):
            perf_issues = [i for i in issues if i.type == "high_latency_edge"][:2]
            for issue in perf_issues:
                changes.append(WorkflowChange(
                    type="distributed_cache",
                    target=issue.affected_nodes[0],
                    description=f"Implement Redis cache for {issue.affected_nodes[0]}",
                    impact="50-70% latency reduction"
                ))
        
        if strategies.get("needs_async"):
            changes.append(WorkflowChange(
                type="async_pattern",
                target="architecture",
                description="Convert sync chains to async with message queue",
                impact="Decouple services, improve throughput"
            ))
        
        if not changes:
            changes.append(WorkflowChange(
                type="optimization",
                target="architecture",
                description="Add CDN and edge caching",
                impact="Global latency reduction"
            ))
        
        workflow = Workflow(
            id=f"workflow-{uuid.uuid4().hex[:8]}",
            name="Performance Optimized",
            description="Maximize throughput and reduce latency",
            proposed_changes=changes,
            pros=["Significant latency reduction", "Better scalability", "Improved UX"],
            cons=["Higher cost", "More complexity", "Longer implementation"],
            complexity_score=6,
            risk_score=4,
            expected_impact={
                "latency_improvement": "50-70%",
                "error_reduction": "10-20%",
                "cost_increase": "30-50%"
            }
        )
        
        return {"workflows": [workflow]}
    
    def _generate_cost(self, state: ReasoningState) -> ReasoningState:
        """Node: Cost workflow"""
        issues = state["issues"]
        strategies = state.get("strategy_selection", {})
        changes = []
        
        if strategies.get("needs_consolidation"):
            fan_out = [i for i in issues if i.type == "fan_out_overload"][:1]
            for issue in fan_out:
                changes.append(WorkflowChange(
                    type="consolidation",
                    target=issue.affected_nodes[0],
                    description=f"Consolidate downstream calls from {issue.affected_nodes[0]}",
                    impact="Reduce API calls by 40%"
                ))
        
        error_issues = [i for i in issues if i.type == "high_error_rate"][:1]
        for issue in error_issues:
            changes.append(WorkflowChange(
                type="retry_optimization",
                target=issue.affected_nodes[0],
                description=f"Optimize retry logic in {issue.affected_nodes[0]}",
                impact="Reduce wasted compute"
            ))
        
        if not changes:
            changes.append(WorkflowChange(
                type="right_sizing",
                target="infrastructure",
                description="Right-size service instances",
                impact="20-30% cost reduction"
            ))
        
        workflow = Workflow(
            id=f"workflow-{uuid.uuid4().hex[:8]}",
            name="Cost Optimized",
            description="Reduce operational costs while maintaining reliability",
            proposed_changes=changes,
            pros=["Lower operational cost", "Better resource utilization", "Reduced waste"],
            cons=["May impact peak performance", "Requires monitoring"],
            complexity_score=4,
            risk_score=3,
            expected_impact={
                "latency_improvement": "5-10%",
                "error_reduction": "15-25%",
                "cost_increase": "-20% to -30%"
            }
        )
        
        return {"workflows": [workflow]}
    
    def _finalize(self, state: ReasoningState) -> ReasoningState:
        """Node: Finalize — only marks complete once all 3 parallel branches have contributed.

        With a fan-in from generate_minimal, generate_performance, and
        generate_cost, LangGraph may invoke this node once per incoming edge
        (before the operator.add reducer has merged all branches).  Guard by
        waiting until three workflow items are present.
        """
        if len(state.get("workflows", [])) < 3:
            # Partial state — at least one branch hasn't completed yet; no-op.
            return {}
        return {"analysis_complete": True}
    
    def run(self, G: nx.DiGraph) -> List[Workflow]:
        """Execute pipeline"""
        initial_state = {
            "graph": G,
            "issues": [],
            "issue_categories": {},
            "strategy_selection": {},
            "workflows": [],
            "analysis_complete": False
        }
        
        result = self.graph.invoke(initial_state)
        return result.get("workflows", [])
