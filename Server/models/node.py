from pydantic import BaseModel


class NodeMetrics(BaseModel):
    avg_latency_ms: float
    error_rate: float
    call_count: int


class Node(BaseModel):
    id: str
    type: str  # service, database, external
    metrics: NodeMetrics
