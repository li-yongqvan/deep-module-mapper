"""Background scanner worker."""

from __future__ import annotations

from pathlib import Path

from parser import scan_codebase

from .store import JobStore


def _scan_worker(store: JobStore, job_id: str, path: Path) -> None:
    """Run parser.scan_codebase in a background thread."""
    store.mark_running(job_id)
    try:
        result = scan_codebase(path)
        store.mark_done(job_id, result)
    except Exception as exc:  # pragma: no cover - defensive catch
        store.mark_error(
            job_id,
            error="scan_failed",
            details=f"{type(exc).__name__}: {exc}",
        )
