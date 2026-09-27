from pydantic import BaseModel


class Edge(BaseModel):
    source: str
    target: str
    call_count: int
    avg_latency_ms: float
    error_rate: float
