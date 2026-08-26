"""In-memory scan job store with thread-safe lifecycle transitions."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

JobStatus = Literal["pending", "running", "done", "error"]


@dataclass
class Job:
    id: str
    status: JobStatus
    path: Path
    result: dict | None = None
    error: str | None = None
    details: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class JobStore:
    """Module-scoped in-memory job store with a max-job cap."""

    def __init__(self, max_jobs: int = 100):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._max_jobs = max_jobs

    def create(self, path: Path) -> str:
        job_id = uuid.uuid4().hex
        with self._lock:
            self._evict_if_needed()
            self._jobs[job_id] = Job(id=job_id, status="pending", path=path)
        return job_id

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.status = "running"

    def mark_done(self, job_id: str, result: dict) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.status = "done"
                job.result = result

    def mark_error(self, job_id: str, error: str, details: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.status = "error"
                job.error = error
                job.details = details

    def _evict_if_needed(self) -> None:
        while len(self._jobs) >= self._max_jobs:
            terminal = [
                j for j in self._jobs.values() if j.status in ("done", "error")
            ]
            if not terminal:
                # No terminal jobs to evict; create() will still succeed because
                # we do not evict pending/running jobs. This means we can exceed
                # max_jobs transiently while all jobs are active, which is
                # acceptable for the local dev-tool threat model (see design doc).
                return
            oldest = min(terminal, key=lambda j: j.created_at)
            del self._jobs[oldest.id]
