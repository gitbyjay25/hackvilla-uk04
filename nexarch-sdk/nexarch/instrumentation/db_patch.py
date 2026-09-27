"""
Database instrumentation - Auto-capture all database queries
Supports: SQLAlchemy, MongoDB, Redis, PostgreSQL, MySQL
"""
import re
import time
import uuid
from typing import Optional, Any
from ..tracing import get_trace_id, get_span_id, Span, add_downstream_ms
from ..queue import get_log_queue
from datetime import datetime

# ── SQL sanitizer ─────────────────────────────────────────────────────────────
# Compiled once at import time for performance.
_RE_SINGLE_QUOTED   = re.compile(r"'(?:[^'\\]|\\.)*'")
_RE_DOUBLE_QUOTED   = re.compile(r'"(?:[^"\\]|\\.)*"')
_RE_NUMERIC_LITERAL = re.compile(r'\b\d+(\.\d+)?\b')
_RE_IN_LIST         = re.compile(r'IN\s*\([^)]+\)', re.IGNORECASE)
_RE_WHITESPACE      = re.compile(r'\s+')


def sanitize_sql(statement: str, max_length: int = 500) -> str:
    """
    Strip literal values from a SQL statement so it can be stored and
    compared safely without leaking PII or credentials.

    Transformations applied (in order):
    1. Replace single-quoted strings  → '?'
    2. Replace double-quoted strings  → '?'
    3. Replace IN (...) value lists   → IN (?)
    4. Replace numeric literals       → ?
    5. Collapse whitespace
    6. Truncate to *max_length* chars

    Examples
    --------
    >>> sanitize_sql("SELECT * FROM users WHERE id = 123")
    'SELECT * FROM users WHERE id = ?'
    >>> sanitize_sql("INSERT INTO t (a,b) VALUES ('hello', 42)")
    "INSERT INTO t (a,b) VALUES ('?', ?)"
    """
    if not statement:
        return ''
    s = _RE_SINGLE_QUOTED.sub("'?'", statement)
    s = _RE_DOUBLE_QUOTED.sub('"?"', s)
    s = _RE_IN_LIST.sub('IN (?)', s)
    s = _RE_NUMERIC_LITERAL.sub('?', s)
    s = _RE_WHITESPACE.sub(' ', s).strip()
    return s[:max_length]


_is_patched = False
_redis_is_patched = False
_pymongo_is_patched = False
_original_execute = None
_original_execute_async = None


def patch_sqlalchemy():
    """Monkey-patch SQLAlchemy to capture all database queries"""
    global _is_patched, _original_execute, _original_execute_async
    
    if _is_patched:
        return
    
    try:
        from sqlalchemy import event
        from sqlalchemy.engine import Engine
        
        @event.listens_for(Engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Capture query start"""
            context._nexarch_query_start = time.time()
            context._nexarch_statement = statement
        
        @event.listens_for(Engine, "after_cursor_execute")
        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Capture query completion"""
            trace_id = get_trace_id()
            parent_span_id = get_span_id()
            
            if not trace_id:
                return
            
            # Calculate latency
            start_time = getattr(context, '_nexarch_query_start', time.time())
            latency_ms = round((time.time() - start_time) * 1000, 2)
            
            # Create span for database query
            span_id = str(uuid.uuid4())
            span = Span(
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
                service_name="database",
                operation="db.query",
                kind="client",
                start_time=datetime.utcnow().isoformat(),
                end_time=None,
                latency_ms=None,
                status_code=None,
                error=None,
                tags={
                    "db.system": conn.engine.dialect.name,
                    "db.statement": sanitize_sql(statement),  # Strip literals, limit length
                    "db.operation": _extract_operation(statement),
                    "db.table": _extract_table(statement),
                    "span.kind": "client"
                }
            )
            span.finish(status_code=200)
            
            # Enqueue span
            get_log_queue().enqueue({
                "type": "span",
                "timestamp": span.start_time,
                "data": {
                    **span.to_dict(),
                    "latency_ms": latency_ms,
                    "db_latency": latency_ms
                }
            })
            add_downstream_ms(latency_ms)  # accumulate into parent span
        
        _is_patched = True
        print("[Nexarch] SQLAlchemy instrumentation enabled")
    
    except ImportError:
        pass
    except Exception as e:
        print(f"[Nexarch] Warning: Failed to patch SQLAlchemy: {e}")


def patch_redis():
    """Monkey-patch Redis client to capture cache operations"""
    global _redis_is_patched
    if _redis_is_patched:
        return
    try:
        import redis
        original_execute_command = redis.Redis.execute_command
        
        def instrumented_execute_command(self, *args, **kwargs):
            trace_id = get_trace_id()
            parent_span_id = get_span_id()
            
            if not trace_id:
                return original_execute_command(self, *args, **kwargs)
            
            start_time = time.time()
            command = args[0] if args else "unknown"
            
            # Create span
            span_id = str(uuid.uuid4())
            span = Span(
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
                service_name="redis",
                operation=f"redis.{command}",
                kind="client",
                start_time=datetime.utcnow().isoformat(),
                end_time=None,
                latency_ms=None,
                status_code=None,
                error=None,
                tags={
                    "db.system": "redis",
                    "db.operation": command,
                    "cache.operation": command,
                    "span.kind": "client"
                }
            )
            
            error = None
            try:
                result = original_execute_command(self, *args, **kwargs)
                return result
            except Exception as e:
                error = str(e)
                raise
            finally:
                latency_ms = round((time.time() - start_time) * 1000, 2)
                span.finish(status_code=200 if not error else 500, error=error)
                
                get_log_queue().enqueue({
                    "type": "span",
                    "timestamp": span.start_time,
                    "data": {
                        **span.to_dict(),
                        "latency_ms": latency_ms,
                        "cache_latency": latency_ms
                    }
                })
                add_downstream_ms(latency_ms)  # accumulate into parent span
        
        redis.Redis.execute_command = instrumented_execute_command
        _redis_is_patched = True
        print("[Nexarch] Redis instrumentation enabled")
    
    except ImportError:
        pass
    except Exception as e:
        print(f"[Nexarch] Warning: Failed to patch Redis: {e}")


def patch_pymongo():
    """Monkey-patch PyMongo to capture MongoDB operations"""
    global _pymongo_is_patched
    if _pymongo_is_patched:
        return
    try:
        from pymongo import monitoring
        
        class NexarchCommandLogger(monitoring.CommandListener):
            def started(self, event):
                """Command started"""
                trace_id = get_trace_id()
                if not trace_id:
                    return
                
                # Store start time
                if not hasattr(self, '_requests'):
                    self._requests = {}
                self._requests[event.request_id] = {
                    'start_time': time.time(),
                    'command': event.command_name,
                    'database': event.database_name
                }
            
            def succeeded(self, event):
                """Command succeeded"""
                self._handle_completion(event, error=None)
            
            def failed(self, event):
                """Command failed"""
                self._handle_completion(event, error=event.failure)
            
            def _handle_completion(self, event, error):
                trace_id = get_trace_id()
                parent_span_id = get_span_id()
                
                if not trace_id or not hasattr(self, '_requests'):
                    return
                
                request_data = self._requests.get(event.request_id)
                if not request_data:
                    return
                
                latency_ms = round((time.time() - request_data['start_time']) * 1000, 2)
                
                # Create span
                span_id = str(uuid.uuid4())
                span = Span(
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=parent_span_id,
                    service_name="mongodb",
                    operation=f"mongodb.{request_data['command']}",
                    kind="client",
                    start_time=datetime.utcnow().isoformat(),
                    end_time=None,
                    latency_ms=None,
                    status_code=None,
                    error=None,
                    tags={
                        "db.system": "mongodb",
                        "db.operation": request_data['command'],
                        "db.name": request_data['database'],
                        "span.kind": "client"
                    }
                )
                span.finish(status_code=200 if not error else 500, error=str(error) if error else None)
                
                get_log_queue().enqueue({
                    "type": "span",
                    "timestamp": span.start_time,
                    "data": {
                        **span.to_dict(),
                        "latency_ms": latency_ms,
                        "db_latency": latency_ms
                    }
                })
                add_downstream_ms(latency_ms)  # accumulate into parent span
                
                # Cleanup
                del self._requests[event.request_id]
        
        monitoring.register(NexarchCommandLogger())
        _pymongo_is_patched = True
        print("[Nexarch] MongoDB instrumentation enabled")
    
    except ImportError:
        pass
    except Exception as e:
        print(f"[Nexarch] Warning: Failed to patch MongoDB: {e}")


def _extract_operation(statement: str) -> str:
    """Extract SQL operation (SELECT, INSERT, UPDATE, DELETE)"""
    try:
        if not statement:
            return "UNKNOWN"
        statement = statement.strip().upper()
        operations = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER']
        for op in operations:
            if statement.startswith(op):
                return op
        return "QUERY"
    except Exception:
        return "UNKNOWN"


def _extract_table(statement: str) -> str:
    """Extract table name from SQL statement"""
    try:
        if not statement:
            return "unknown"
        statement = statement.strip().upper()
        
        # SELECT FROM
        if 'FROM' in statement:
            parts = statement.split('FROM')[1].split()
            if parts:
                return parts[0].strip().replace('`', '').replace('"', '')
        
        # INSERT INTO
        if 'INSERT INTO' in statement:
            parts = statement.split('INSERT INTO')[1].split()
            if parts:
                return parts[0].strip().replace('`', '').replace('"', '')
        
        # UPDATE
        if 'UPDATE' in statement:
            parts = statement.split('UPDATE')[1].split()
            if parts:
                return parts[0].strip().replace('`', '').replace('"', '')
        
        return "unknown"
    except Exception:
        return "unknown"


def patch_all_databases():
    """Patch all supported database drivers"""
    patch_sqlalchemy()
    patch_redis()
    patch_pymongo()
