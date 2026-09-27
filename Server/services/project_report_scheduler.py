from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime
from typing import Optional

from core.logging import get_logger
from db.base import SessionLocal
from db.models import Tenant
from services.project_analytics_service import ProjectAnalyticsService

logger = get_logger(__name__)

_SCHEDULER_INTERVAL_SECONDS = 1800
_scheduler_thread: Optional[threading.Thread] = None
_scheduler_stop_event = threading.Event()
_scheduler_lock = threading.Lock()


def _run_scheduler() -> None:
    logger.info("[ProjectReportScheduler] started")
    while not _scheduler_stop_event.is_set():
        db = SessionLocal()
        try:
            tenant_rows = db.query(Tenant).filter(Tenant.is_active == True).all()
            for tenant in tenant_rows:
                try:
                    asyncio.run(ProjectAnalyticsService.ensure_daily_reports_for_tenant(db, tenant.id))
                except Exception as exc:
                    logger.warning(
                        "[ProjectReportScheduler] tenant=%s daily report pass failed: %s",
                        tenant.id,
                        exc,
                    )
        except Exception as exc:
            logger.warning("[ProjectReportScheduler] scheduler cycle failed: %s", exc)
        finally:
            db.close()

        # Sleep in small slices so shutdown is responsive.
        remaining = _SCHEDULER_INTERVAL_SECONDS
        while remaining > 0 and not _scheduler_stop_event.is_set():
            sleep_for = min(5, remaining)
            time.sleep(sleep_for)
            remaining -= sleep_for

    logger.info("[ProjectReportScheduler] stopped")


def start_project_report_scheduler() -> None:
    global _scheduler_thread
    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            return
        _scheduler_stop_event.clear()
        _scheduler_thread = threading.Thread(
            target=_run_scheduler,
            name="project-report-scheduler",
            daemon=True,
        )
        _scheduler_thread.start()


def stop_project_report_scheduler() -> None:
    global _scheduler_thread
    with _scheduler_lock:
        _scheduler_stop_event.set()
        if _scheduler_thread and _scheduler_thread.is_alive():
            _scheduler_thread.join(timeout=5)
        _scheduler_thread = None
