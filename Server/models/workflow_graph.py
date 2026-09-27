"""
Workflow Architecture Graph Models

Pydantic models for the GET /workflows/architecture/graph endpoint.
These models are designed to be directly consumable by React Flow
for visual workflow graph rendering.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class WorkflowGraphNodeMeta(BaseModel):
    """Metadata for a graph node"""
    avg_latency_ms: float = 0.0
    error_rate: float = 0.0
    call_count: int = 0


class WorkflowGraphNode(BaseModel):
    """
    Node in a workflow graph.
    
    Represents a service, database, external API, queue, cache, or worker
    in the architecture.
    """
    id: str = Field(..., description="Unique node identifier")
    type: str = Field(..., description="Node type: api | db | external | queue | cache | worker")
    label: str = Field(..., description="Human-readable name")
    tech: str = Field(..., description="Technology used: FastAPI, PostgreSQL, Redis, etc.")
    meta: WorkflowGraphNodeMeta = Field(default_factory=WorkflowGraphNodeMeta)


class WorkflowGraphEdge(BaseModel):
    """
    Edge in a workflow graph.
    
    Represents a dependency/call relationship between two nodes.
    """
    id: str = Field(..., description="Unique edge identifier")
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    latency_ms: float = Field(default=0.0, description="Average latency in milliseconds")
    error: bool = Field(default=False, description="Whether this edge has error occurrences")


class WorkflowGraph(BaseModel):
    """
    Complete workflow graph structure.
    
    Represents either the current architecture or a generated workflow variant.
    """
    workflow_id: str = Field(..., description="Unique workflow identifier")
    trigger: str = Field(default="runtime_discovered", description="How this workflow was triggered/discovered")
    description: str = Field(default="", description="Human-readable description of the workflow")
    nodes: List[WorkflowGraphNode] = Field(default_factory=list)
    edges: List[WorkflowGraphEdge] = Field(default_factory=list)
    tech_stack: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Technology stack grouped by category (e.g., {'databases': ['PostgreSQL'], 'caches': ['Redis']})"
    )
    stats: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary statistics for this workflow"
    )


class WorkflowArchitectureGraphResponse(BaseModel):
    """
    Response model for GET /workflows/architecture/graph endpoint.
    
    Contains the current discovered architecture graph plus
    2-3 automatically generated workflow variants.
    """
    current_architecture: WorkflowGraph = Field(
        ...,
        description="Current architecture workflow graph discovered from runtime data"
    )
    generated_workflows: List[WorkflowGraph] = Field(
        default_factory=list,
        description="Generated workflow architecture variants (2-3)"
    )
