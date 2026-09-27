from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Any, Optional


class SchemaModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")


class NodeMetrics(SchemaModel):
    avg_latency_ms: float
    error_rate: float
    call_count: int


class Node(SchemaModel):
    id: str
    type: str  # service, database, external
    metrics: NodeMetrics


class Edge(SchemaModel):
    source: str
    target: str
    call_count: int
    avg_latency_ms: float
    error_rate: float


class ArchitectureResponse(SchemaModel):
    nodes: List[Node]
    edges: List[Edge]
    metrics_summary: Dict[str, Any]


class Issue(SchemaModel):
    id: Optional[str] = None
    severity: str  # critical, high, medium, low
    type: str
    description: str
    affected_nodes: List[str] = Field(default_factory=list)
    affected_services: List[str] = Field(default_factory=list)
    metric_value: Optional[float] = None
    recommendation: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)


class IssuesResponse(SchemaModel):
    issues: List[Issue]
    total_count: int
