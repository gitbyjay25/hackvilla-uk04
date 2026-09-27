"""Async-safe logging queue"""
import threading
import queue
import atexit
from typing import Dict, Any, Optional


# Maximum number of spans held in memory before dropping.  At ~1KB per span this is ~10 MB.
_MAX_QUEUE_SIZE = 10_000


class LogQueue:
    """Thread-safe async log queue"""

    def __init__(self, flush_interval: float = 1.0):
        self._queue = queue.Queue(maxsize=_MAX_QUEUE_SIZE)
        self._exporter = None
        self._flush_interval = flush_interval
        self._worker_thread: Optional[threading.Thread] = None
        self._shutdown = threading.Event()
    
    def set_exporter(self, exporter):
        """Set exporter"""
        self._exporter = exporter
    
    def start(self):
        """Start background worker"""
        if self._worker_thread is None:
            self._worker_thread = threading.Thread(target=self._worker, daemon=True)
            self._worker_thread.start()
            atexit.register(self.shutdown)
    
    def enqueue(self, data: Dict[str, Any]):
        """Enqueue log data"""
        if not data:
            return
        
        try:
            self._queue.put_nowait(data)
        except queue.Full:
            # Drop if full - could log this for monitoring
            pass
    
    def _worker(self):
        """Background worker"""
        while not self._shutdown.is_set():
            batch = []
            try:
                # Collect batch
                while len(batch) < 100:
                    try:
                        item = self._queue.get(timeout=self._flush_interval)
                        batch.append(item)
                    except queue.Empty:
                        break
                
                # Flush batch
                if batch and self._exporter:
                    for item in batch:
                        self._exporter.export(item)
            
            except Exception:
                pass  # Continue on error
    
    def flush(self):
        """Flush all currently-queued items to the exporter immediately.
        Useful before process shutdown to drain without waiting for the worker timer.
        """
        remaining = []
        while not self._queue.empty():
            try:
                remaining.append(self._queue.get_nowait())
            except queue.Empty:
                break

        if remaining and self._exporter:
            for item in remaining:
                try:
                    self._exporter.export(item)
                except Exception:
                    pass

        # Also flush the exporter's own batch buffer (e.g. HttpExporter batches spans)
        if self._exporter and hasattr(self._exporter, 'flush'):
            try:
                self._exporter.flush()
            except Exception:
                pass

    def shutdown(self):
        """Shutdown and flush"""
        self._shutdown.set()
        
        # Flush remaining
        remaining = []
        while not self._queue.empty():
            try:
                remaining.append(self._queue.get_nowait())
            except queue.Empty:
                break
        
        if remaining and self._exporter:
            for item in remaining:
                try:
                    self._exporter.export(item)
                except Exception:
                    pass
        
        if self._worker_thread:
            self._worker_thread.join(timeout=2.0)


# Global instance
_log_queue = LogQueue()


def get_log_queue() -> LogQueue:
    """Get global queue"""
    return _log_queue
