"""
Workflow Graph Service

Converts existing runtime workflow data into visual graph format
for the GET /workflows/architecture/graph endpoint.

This service is READ-ONLY - it does not modify any existing data
or trigger new instrumentation.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any, Tuple
import networkx as nx

from db.models import Span
from services.graph_service import GraphService
from services.metrics_service import MetricsService
from core.ai_client import get_ai_client
from core.logging import get_logger
from models.workflow_graph import (
    WorkflowGraph,
    WorkflowGraphNode,
    WorkflowGraphEdge,
    WorkflowGraphNodeMeta
)

logger = get_logger(__name__)


class WorkflowGraphService:
    """
    Service for building workflow architecture graphs from runtime data.
    
    Uses existing GraphService data and converts it to React Flow-compatible format.
    Does NOT modify any existing data or trigger new instrumentation.
    """
    
    # Technology classification mappings
    TECH_MAPPINGS = {
        "postgres": ("db", "PostgreSQL"),
        "mysql": ("db", "MySQL"),
        "mongo": ("db", "MongoDB"),
        "redis": ("cache", "Redis"),
        "dynamodb": ("db", "DynamoDB"),
        "cosmosdb": ("db", "CosmosDB"),
        "rabbitmq": ("queue", "RabbitMQ"),
        "kafka": ("queue", "Kafka"),
        "sqs": ("queue", "AWS SQS"),
        "celery": ("worker", "Celery"),
        "stripe": ("external", "Stripe API"),
        "twilio": ("external", "Twilio API"),
        "sendgrid": ("external", "SendGrid API"),
    }
    
    @staticmethod
    def build_current_architecture_graph(db: Session, tenant_id: str) -> WorkflowGraph:
        """
        Build the current architecture graph from runtime data.
        
        Uses existing GraphService to get nodes/edges, then converts
        to WorkflowGraph format.
        """
        # Get existing graph data
        nodes, edges = GraphService.build_graph(db, tenant_id)
        metrics = MetricsService.compute_global_metrics(db, tenant_id)
        
        # Convert to workflow graph nodes
        graph_nodes = []
        for node in nodes:
            node_type, tech = WorkflowGraphService._classify_tech(node.id, node.type)
            
            graph_node = WorkflowGraphNode(
                id=node.id,
                type=node_type,
                label=WorkflowGraphService._generate_label(node.id),
                tech=tech,
                meta=WorkflowGraphNodeMeta(
                    avg_latency_ms=node.metrics.avg_latency_ms,
                    error_rate=node.metrics.error_rate,
                    call_count=node.metrics.call_count
                )
            )
            graph_nodes.append(graph_node)
        
        # Convert to workflow graph edges
        graph_edges = []
        for i, edge in enumerate(edges):
            graph_edge = WorkflowGraphEdge(
                id=f"edge_{i}_{edge.source}_{edge.target}",
                source=edge.source,
                target=edge.target,
                latency_ms=edge.avg_latency_ms,
                error=edge.error_rate > 0.05  # Mark as error if >5% error rate
            )
            graph_edges.append(graph_edge)
        
        # Compute tech stack summary
        tech_stack = WorkflowGraphService._compute_tech_stack(graph_nodes)
        
        # Compute stats
        stats = {
            "total_nodes": len(graph_nodes),
            "total_edges": len(graph_edges),
            "total_spans": metrics.get("total_spans", 0),
            "avg_latency_ms": metrics.get("avg_latency_ms", 0),
            "overall_error_rate": metrics.get("error_rate", 0)
        }
        
        return WorkflowGraph(
            workflow_id="current",
            trigger="runtime_discovered",
            description="Current architecture discovered from runtime telemetry",
            nodes=graph_nodes,
            edges=graph_edges,
            tech_stack=tech_stack,
            stats=stats
        )
    
    @staticmethod
    async def generate_workflow_variants(
        db: Session, 
        tenant_id: str,
        num_variants: int = 3
    ) -> List[WorkflowGraph]:
        """
        Generate 2-3 workflow architecture variants from observed runtime patterns.
        
        Analyzes observed data to create:
        1. Most common execution path
        2. Optimized/reduced-latency path
        3. High-reliability path (optional, if data supports it)
        
        Uses LangChain (read-only) for generating descriptions when available.
        """
        # Get the NetworkX graph for analysis
        G = GraphService.get_graph_from_db(db, tenant_id)
        
        if not G or G.number_of_nodes() == 0:
            logger.info(f"No graph data for tenant {tenant_id}, returning empty variants")
            return []
        
        variants = []
        
        # Variant 1: Most common execution path
        if len(variants) < num_variants:
            common_path_variant = WorkflowGraphService._generate_common_path_variant(G, db, tenant_id)
            if common_path_variant:
                variants.append(common_path_variant)
        
        # Variant 2: Optimized/reduced-latency path
        if len(variants) < num_variants:
            optimized_variant = WorkflowGraphService._generate_optimized_variant(G, db, tenant_id)
            if optimized_variant:
                variants.append(optimized_variant)
        
        # Variant 3: High-reliability path
        if len(variants) < num_variants:
            reliability_variant = WorkflowGraphService._generate_reliability_variant(G, db, tenant_id)
            if reliability_variant:
                variants.append(reliability_variant)
        
        # Enhance descriptions with AI if available
        variants = await WorkflowGraphService._enhance_with_ai_descriptions(variants)
        
        logger.info(f"Generated {len(variants)} workflow variants for tenant {tenant_id}")
        return variants
    
    @staticmethod
    def _generate_common_path_variant(G: nx.DiGraph, db: Session, tenant_id: str) -> WorkflowGraph:
        """Generate variant representing the most common execution path."""
        if G.number_of_nodes() == 0:
            return None
        
        # Find nodes with highest call counts (most frequently accessed)
        node_call_counts = {}
        for node_id in G.nodes():
            metrics = G.nodes[node_id].get("metrics", {})
            node_call_counts[node_id] = metrics.get("call_count", 0)
        
        # Select top nodes by call count (at least 50% of nodes, minimum 2)
        sorted_nodes = sorted(node_call_counts.items(), key=lambda x: x[1], reverse=True)
        num_to_include = max(2, len(sorted_nodes) // 2)
        top_nodes = [n[0] for n in sorted_nodes[:num_to_include]]
        
        # Build subgraph with only these nodes
        subgraph = G.subgraph(top_nodes)
        
        # Convert to workflow graph format
        graph_nodes = []
        for node_id in subgraph.nodes():
            node_data = G.nodes[node_id]
            node_type = node_data.get("type", "service")
            classified_type, tech = WorkflowGraphService._classify_tech(node_id, node_type)
            metrics = node_data.get("metrics", {})
            
            graph_nodes.append(WorkflowGraphNode(
                id=node_id,
                type=classified_type,
                label=WorkflowGraphService._generate_label(node_id),
                tech=tech,
                meta=WorkflowGraphNodeMeta(
                    avg_latency_ms=metrics.get("avg_latency_ms", 0),
                    error_rate=metrics.get("error_rate", 0),
                    call_count=metrics.get("call_count", 0)
                )
            ))
        
        graph_edges = []
        for i, (source, target) in enumerate(subgraph.edges()):
            edge_data = G.edges[source, target]
            graph_edges.append(WorkflowGraphEdge(
                id=f"common_edge_{i}",
                source=source,
                target=target,
                latency_ms=edge_data.get("avg_latency_ms", 0),
                error=edge_data.get("error_rate", 0) > 0.05
            ))
        
        tech_stack = WorkflowGraphService._compute_tech_stack(graph_nodes)
        total_calls = sum(n.meta.call_count for n in graph_nodes)
        
        return WorkflowGraph(
            workflow_id="wf_variant_common",
            trigger="frequency_analysis",
            description="Most common execution path - represents the highest traffic workflow through the system",
            nodes=graph_nodes,
            edges=graph_edges,
            tech_stack=tech_stack,
            stats={
                "path_type": "high_frequency",
                "total_nodes": len(graph_nodes),
                "total_edges": len(graph_edges),
                "estimated_call_volume": total_calls
            }
        )
    
    @staticmethod
    def _generate_optimized_variant(G: nx.DiGraph, db: Session, tenant_id: str) -> WorkflowGraph:
        """Generate variant representing an optimized/reduced-latency path."""
        if G.number_of_nodes() == 0:
            return None
        
        # Find the path with lowest total latency
        # Focus on nodes with below-average latency
        all_latencies = []
        for node_id in G.nodes():
            metrics = G.nodes[node_id].get("metrics", {})
            latency = metrics.get("avg_latency_ms", 0)
            if latency > 0:
                all_latencies.append(latency)
        
        if not all_latencies:
            return None
        
        avg_latency = sum(all_latencies) / len(all_latencies)
        
        # Select nodes with below-average latency
        fast_nodes = []
        for node_id in G.nodes():
            metrics = G.nodes[node_id].get("metrics", {})
            latency = metrics.get("avg_latency_ms", 0)
            if latency <= avg_latency or latency == 0:
                fast_nodes.append(node_id)
        
        # Ensure we have at least some nodes
        if len(fast_nodes) < 2:
            fast_nodes = list(G.nodes())[:max(2, len(G.nodes()) // 2)]
        
        subgraph = G.subgraph(fast_nodes)
        
        # Convert to workflow graph format
        graph_nodes = []
        total_latency = 0
        for node_id in subgraph.nodes():
            node_data = G.nodes[node_id]
            node_type = node_data.get("type", "service")
            classified_type, tech = WorkflowGraphService._classify_tech(node_id, node_type)
            metrics = node_data.get("metrics", {})
            latency = metrics.get("avg_latency_ms", 0)
            total_latency += latency
            
            graph_nodes.append(WorkflowGraphNode(
                id=node_id,
                type=classified_type,
                label=WorkflowGraphService._generate_label(node_id),
                tech=tech,
                meta=WorkflowGraphNodeMeta(
                    avg_latency_ms=latency,
                    error_rate=metrics.get("error_rate", 0),
                    call_count=metrics.get("call_count", 0)
                )
            ))
        
        graph_edges = []
        for i, (source, target) in enumerate(subgraph.edges()):
            edge_data = G.edges[source, target]
            graph_edges.append(WorkflowGraphEdge(
                id=f"optimized_edge_{i}",
                source=source,
                target=target,
                latency_ms=edge_data.get("avg_latency_ms", 0),
                error=edge_data.get("error_rate", 0) > 0.05
            ))
        
        tech_stack = WorkflowGraphService._compute_tech_stack(graph_nodes)
        
        return WorkflowGraph(
            workflow_id="wf_variant_optimized",
            trigger="latency_analysis",
            description="Optimized execution path - focuses on low-latency components for fastest response times",
            nodes=graph_nodes,
            edges=graph_edges,
            tech_stack=tech_stack,
            stats={
                "path_type": "low_latency",
                "total_nodes": len(graph_nodes),
                "total_edges": len(graph_edges),
                "estimated_latency_ms": total_latency
            }
        )
    
    @staticmethod
    def _generate_reliability_variant(G: nx.DiGraph, db: Session, tenant_id: str) -> WorkflowGraph:
        """Generate variant representing a high-reliability path."""
        if G.number_of_nodes() == 0:
            return None
        
        # Select nodes with lowest error rates
        reliable_nodes = []
        for node_id in G.nodes():
            metrics = G.nodes[node_id].get("metrics", {})
            error_rate = metrics.get("error_rate", 0)
            if error_rate < 0.01:  # Less than 1% error rate
                reliable_nodes.append(node_id)
        
        # If few reliable nodes, include all with < 5% error rate
        if len(reliable_nodes) < 2:
            reliable_nodes = []
            for node_id in G.nodes():
                metrics = G.nodes[node_id].get("metrics", {})
                error_rate = metrics.get("error_rate", 0)
                if error_rate < 0.05:
                    reliable_nodes.append(node_id)
        
        # Fallback: use all nodes
        if len(reliable_nodes) < 2:
            reliable_nodes = list(G.nodes())
        
        subgraph = G.subgraph(reliable_nodes)
        
        # Convert to workflow graph format
        graph_nodes = []
        for node_id in subgraph.nodes():
            node_data = G.nodes[node_id]
            node_type = node_data.get("type", "service")
            classified_type, tech = WorkflowGraphService._classify_tech(node_id, node_type)
            metrics = node_data.get("metrics", {})
            
            graph_nodes.append(WorkflowGraphNode(
                id=node_id,
                type=classified_type,
                label=WorkflowGraphService._generate_label(node_id),
                tech=tech,
                meta=WorkflowGraphNodeMeta(
                    avg_latency_ms=metrics.get("avg_latency_ms", 0),
                    error_rate=metrics.get("error_rate", 0),
                    call_count=metrics.get("call_count", 0)
                )
            ))
        
        graph_edges = []
        for i, (source, target) in enumerate(subgraph.edges()):
            edge_data = G.edges[source, target]
            graph_edges.append(WorkflowGraphEdge(
                id=f"reliable_edge_{i}",
                source=source,
                target=target,
                latency_ms=edge_data.get("avg_latency_ms", 0),
                error=edge_data.get("error_rate", 0) > 0.05
            ))
        
        tech_stack = WorkflowGraphService._compute_tech_stack(graph_nodes)
        avg_error = sum(n.meta.error_rate for n in graph_nodes) / len(graph_nodes) if graph_nodes else 0
        
        return WorkflowGraph(
            workflow_id="wf_variant_reliable",
            trigger="reliability_analysis",
            description="High-reliability path - prioritizes components with lowest error rates for maximum stability",
            nodes=graph_nodes,
            edges=graph_edges,
            tech_stack=tech_stack,
            stats={
                "path_type": "high_reliability",
                "total_nodes": len(graph_nodes),
                "total_edges": len(graph_edges),
                "avg_error_rate": avg_error
            }
        )
    
    @staticmethod
    async def _enhance_with_ai_descriptions(variants: List[WorkflowGraph]) -> List[WorkflowGraph]:
        """
        Enhance workflow variant descriptions using LangChain.
        
        This is READ-ONLY - uses existing AI client configuration.
        Falls back gracefully if AI is unavailable.
        """
        ai_client = get_ai_client()
        
        if not ai_client.llm:
            logger.info("AI not available, using default descriptions")
            return variants
        
        try:
            for variant in variants:
                # Generate enhanced description
                prompt = f"""Provide a brief, one-sentence technical description for this workflow architecture variant:

Workflow ID: {variant.workflow_id}
Type: {variant.stats.get('path_type', 'general')}
Nodes: {len(variant.nodes)}
Tech Stack: {variant.tech_stack}

Return only the description text, no formatting."""
                
                response = await ai_client.llm.ainvoke(prompt)
                if response and response.content:
                    variant.description = response.content.strip()
            
            logger.info("Enhanced workflow descriptions with AI")
        except Exception as e:
            logger.warning(f"AI description enhancement failed: {e}, using defaults")
        
        return variants
    
    @staticmethod
    def _classify_tech(node_id: str, node_type: str) -> Tuple[str, str]:
        """
        Classify node technology based on ID and type.
        
        Returns (graph_type, technology_name)
        """
        node_lower = node_id.lower()
        
        # Check against known technology patterns
        for pattern, (graph_type, tech_name) in WorkflowGraphService.TECH_MAPPINGS.items():
            if pattern in node_lower:
                return graph_type, tech_name
        
        # Default classifications based on node type
        if node_type == "database":
            return "db", "Database"
        elif node_type == "external":
            if "http" in node_lower or "api" in node_lower:
                return "external", "External API"
            return "external", "External Service"
        else:
            # Default to API service
            return "api", "FastAPI"
    
    @staticmethod
    def _generate_label(node_id: str) -> str:
        """Generate human-readable label from node ID."""
        # Extract meaningful name from ID
        label = node_id
        
        # Remove common prefixes/protocols
        for prefix in ["http://", "https://", "postgres://", "redis://", "mongodb://"]:
            if label.startswith(prefix):
                label = label[len(prefix):]
        
        # Capitalize and clean up
        label = label.replace("_", " ").replace("-", " ")
        return label.title() if label else node_id
    
    @staticmethod
    def _compute_tech_stack(nodes: List[WorkflowGraphNode]) -> Dict[str, List[str]]:
        """Compute technology stack summary from nodes."""
        tech_stack = {
            "services": [],
            "databases": [],
            "caches": [],
            "queues": [],
            "external": [],
            "workers": []
        }
        
        for node in nodes:
            if node.type == "api":
                if node.tech not in tech_stack["services"]:
                    tech_stack["services"].append(node.tech)
            elif node.type == "db":
                if node.tech not in tech_stack["databases"]:
                    tech_stack["databases"].append(node.tech)
            elif node.type == "cache":
                if node.tech not in tech_stack["caches"]:
                    tech_stack["caches"].append(node.tech)
            elif node.type == "queue":
                if node.tech not in tech_stack["queues"]:
                    tech_stack["queues"].append(node.tech)
            elif node.type == "external":
                if node.tech not in tech_stack["external"]:
                    tech_stack["external"].append(node.tech)
            elif node.type == "worker":
                if node.tech not in tech_stack["workers"]:
                    tech_stack["workers"].append(node.tech)
        
        # Remove empty categories
        return {k: v for k, v in tech_stack.items() if v}
