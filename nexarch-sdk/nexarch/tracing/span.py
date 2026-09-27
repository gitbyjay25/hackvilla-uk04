"""Span model"""
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class Span:
    """Distributed trace span"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    service_name: str
    operation: str
    kind: str  # server, client, internal
    start_time: str
    end_time: Optional[str]
    latency_ms: Optional[float]
    status_code: Optional[int]
    error: Optional[str]
    tags: Dict[str, Any]
    
    def to_dict(self) -> dict:
        """To dict"""
        return asdict(self)
    
    @staticmethod
    def create_server_span(trace_id: str, span_id: str, service: str, operation: str) -> 'Span':
        """Create server span"""
        return Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=None,
            service_name=service,
            operation=operation,
            kind="server",
            start_time=datetime.utcnow().isoformat(),
            end_time=None,
            latency_ms=None,
            status_code=None,
            error=None,
            tags={}
        )
    
    @staticmethod
    def create_client_span(trace_id: str, span_id: str, parent_span_id: str, 
                          service: str, operation: str) -> 'Span':
        """Create client span"""
        return Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            service_name=service,
            operation=operation,
            kind="client",
            start_time=datetime.utcnow().isoformat(),
            end_time=None,
            latency_ms=None,
            status_code=None,
            error=None,
            tags={}
        )
    
    def finish(self, status_code: Optional[int] = None, error: Optional[str] = None):
        """Finish span"""
        self.end_time = datetime.utcnow().isoformat()
        if self.start_time and self.end_time:
            try:
                start = datetime.fromisoformat(self.start_time)
                end = datetime.fromisoformat(self.end_time)
                self.latency_ms = (end - start).total_seconds() * 1000
            except (ValueError, AttributeError) as e:
                # If datetime parsing fails, set default
                self.latency_ms = 0.0
        self.status_code = status_code
        self.error = error
