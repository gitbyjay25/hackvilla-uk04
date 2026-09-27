"""Trace context propagation"""
from contextvars import ContextVar
from typing import Optional

# Context vars
_trace_id: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)
_span_id: ContextVar[Optional[str]] = ContextVar('span_id', default=None)
_parent_span_id: ContextVar[Optional[str]] = ContextVar('parent_span_id', default=None)
# Accumulates downstream (child span) latency for the current server span
_downstream_ms: ContextVar[float] = ContextVar('downstream_ms', default=0.0)


def set_trace_context(trace_id: str, span_id: str, parent_span_id: Optional[str] = None):
    """Set trace context"""
    _trace_id.set(trace_id)
    _span_id.set(span_id)
    _parent_span_id.set(parent_span_id)
    _downstream_ms.set(0.0)  # reset downstream accumulator for new span


def get_trace_id() -> Optional[str]:
    """Get current trace ID"""
    return _trace_id.get()


def get_span_id() -> Optional[str]:
    """Get current span ID"""
    return _span_id.get()


def get_parent_span_id() -> Optional[str]:
    """Get parent span ID"""
    return _parent_span_id.get()


def add_downstream_ms(ms: float) -> None:
    """Accumulate child-span latency for the current server span."""
    _downstream_ms.set(_downstream_ms.get() + ms)


def get_downstream_ms() -> float:
    """Return total accumulated downstream latency for the current server span."""
    return _downstream_ms.get()


def clear_trace_context():
    """Clear trace context"""
    _trace_id.set(None)
    _span_id.set(None)
    _parent_span_id.set(None)
    _downstream_ms.set(0.0)
