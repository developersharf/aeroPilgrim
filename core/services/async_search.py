"""
PHASE 8 — Async search runner.

Wraps the orchestrator in a lightweight thread-based job system so the
HTTP request returns immediately with a ``job_id`` and the heavy
``get_flight_data()`` call happens in a daemon thread.

Production-ready when Django's channels or Celery is wired in: swap
``dispatch_async_search`` for `task.delay()` and nothing else changes.
"""

from core.services.search_orchestrator import (  # noqa: F401  re-export
    dispatch_async_search,
)
