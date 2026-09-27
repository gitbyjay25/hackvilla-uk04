"""Requests instrumentation"""
import time
import uuid
from typing import Optional
from ..tracing import get_trace_id, get_span_id, Span, add_downstream_ms
from ..queue import get_log_queue

_original_request = None
_is_patched = False


def patch_requests():
    """Monkey-patch requests"""
    global _original_request, _is_patched
    
    if _is_patched:
        return
    
    try:
        import requests
        _original_request = requests.Session.request
        requests.Session.request = _instrumented_request
        _is_patched = True
    except ImportError:
        pass


def _instrumented_request(self, method, url, **kwargs):
    """Instrumented request"""
    trace_id = get_trace_id()
    parent_span_id = get_span_id()
    
    if not trace_id:
        return _original_request(self, method, url, **kwargs)
    
    # Create client span
    span_id = str(uuid.uuid4())
    span = Span.create_client_span(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        service="downstream",
        operation=f"{method} {url}"
    )
    
    start = time.time()
    error: Optional[str] = None
    status_code: Optional[int] = None
    
    try:
        response = _original_request(self, method, url, **kwargs)
        status_code = response.status_code
        return response
    except Exception as e:
        error = str(e)
        raise
    finally:
        latency_ms = round((time.time() - start) * 1000, 2)
        span.finish(status_code=status_code, error=error)
        add_downstream_ms(latency_ms)
        
        # Enqueue span
        get_log_queue().enqueue({
            "type": "span",
            "timestamp": span.start_time,
            "data": {
                **span.to_dict(),
                "latency_ms": latency_ms,
                "http_latency": latency_ms,
            }
        })
