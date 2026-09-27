"""
Nexarch Data Models - Structured telemetry data types
"""
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any


@dataclass
class SpanData:
    """
    Represents a single operation span (OpenTelemetry compatible).
    """
    trace_id: str
    span_id: str
    parent_id: Optional[str]
    service: str
    operation: str
    kind: str  # "server", "client", "internal"
    timestamp: str
    latency_ms: float
    status_code: int
    method: str
    path: str
    query_params: Dict[str, Any]
    status: str  # "ok" or "error"
    error: Optional[str]
    downstream: List[str]  # List of downstream services called
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class ErrorData:
    """
    Represents an error or exception that occurred.
    """
    trace_id: str
    span_id: str
    timestamp: str
    error_type: str
    error_message: str
    traceback: str
    service: str
    operation: str
    method: str
    path: str
    query_params: Dict[str, Any]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class MetricData:
    """
    Represents aggregated metrics.
    """
    timestamp: str
    service: str
    metric_name: str
    metric_value: float
    unit: str
    tags: Dict[str, str]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)