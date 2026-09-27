"""HTTPX instrumentation"""
import time
import uuid
from typing import Optional
from ..tracing import get_trace_id, get_span_id, Span, add_downstream_ms
from ..queue import get_log_queue
import time

_original_send = None
_original_async_send = None
_is_patched = False


def patch_httpx():
    """Monkey-patch httpx"""
    global _original_send, _original_async_send, _is_patched
    
    if _is_patched:
        return
    
    try:
        import httpx
        _original_send = httpx.Client.send
        _original_async_send = httpx.AsyncClient.send
        
        httpx.Client.send = _instrumented_send
        httpx.AsyncClient.send = _instrumented_async_send
        _is_patched = True
    except ImportError:
        pass


def _instrumented_send(self, request, **kwargs):
    """Instrumented sync send"""
    trace_id = get_trace_id()
    parent_span_id = get_span_id()
    
    if not trace_id:
        return _original_send(self, request, **kwargs)
    
    # Create span
    span_id = str(uuid.uuid4())
    span = Span.create_client_span(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        service="downstream",
        operation=f"{request.method} {request.url}"
    )
    
    error: Optional[str] = None
    status_code: Optional[int] = None
    start = time.time()
    
    try:
        response = _original_send(self, request, **kwargs)
        status_code = response.status_code
        return response
    except Exception as e:
        error = str(e)
        raise
    finally:
        latency_ms = round((time.time() - start) * 1000, 2)
        span.finish(status_code=status_code, error=error)
        add_downstream_ms(latency_ms)
        
        get_log_queue().enqueue({
            "type": "span",
            "timestamp": span.start_time,
            "data": {
                **span.to_dict(),
                "latency_ms": latency_ms,
                "http_latency": latency_ms,
            }
        })


async def _instrumented_async_send(self, request, **kwargs):
    """Instrumented async send"""
    trace_id = get_trace_id()
    parent_span_id = get_span_id()
    
    if not trace_id:
        return await _original_async_send(self, request, **kwargs)
    
    # Create span
    span_id = str(uuid.uuid4())
    span = Span.create_client_span(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        service="downstream",
        operation=f"{request.method} {request.url}"
    )
    
    error: Optional[str] = None
    status_code: Optional[int] = None
    start = time.time()
    
    try:
        response = await _original_async_send(self, request, **kwargs)
        status_code = response.status_code
        return response
    except Exception as e:
        error = str(e)
        raise
    finally:
        latency_ms = round((time.time() - start) * 1000, 2)
        span.finish(status_code=status_code, error=error)
        add_downstream_ms(latency_ms)
        
        get_log_queue().enqueue({
            "type": "span",
            "timestamp": span.start_time,
            "data": {
                **span.to_dict(),
                "latency_ms": latency_ms,
                "http_latency": latency_ms,
            }
        })
