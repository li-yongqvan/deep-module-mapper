"""Starlette ASGI application for the Deep Module Mapper backend."""

from __future__ import annotations

import json
import os
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .models import ScanRequest, StatusResponse
from .scanner import _scan_worker
from .store import JobStore

DEFAULT_PORT = 8123

_store = JobStore(max_jobs=100)


def _cors_origins() -> list[str]:
    """Return allowed CORS origins.

    Defaults to ["*"] for local development because the frontend port is not
    yet fixed. Override with a comma-separated BACKEND_CORS_ORIGINS env var.
    """
    raw = os.getenv("BACKEND_CORS_ORIGINS")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return ["*"]


def _error_response(error: str, details: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": error, "details": details}, status_code=status_code)


async def scan_endpoint(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return _error_response(
            "invalid_json", "Request body is not valid JSON.", 400
        )

    try:
        scan_req = ScanRequest.model_validate(body)
    except Exception as exc:
        return _error_response("invalid_request", str(exc), 400)

    resolved = Path(scan_req.path).expanduser().resolve()
    if not resolved.exists() or not resolved.is_dir():
        return _error_response(
            "path_not_found",
            f"Path does not exist or is not a directory: {scan_req.path}",
            400,
        )

    job_id = _store.create(resolved)

    import threading

    threading.Thread(
        target=_scan_worker,
        args=(_store, job_id, resolved),
        daemon=True,
    ).start()

    return JSONResponse({"jobId": job_id}, status_code=202)


async def status_endpoint(request: Request) -> JSONResponse:
    job_id = request.path_params["job_id"]
    job = _store.get(job_id)
    if job is None:
        return _error_response("job_not_found", f"Job {job_id} not found.", 404)

    response = StatusResponse(status=job.status, error=job.error, details=job.details)
    return JSONResponse(response.model_dump(exclude_none=True))


async def graph_endpoint(request: Request) -> JSONResponse:
    job_id = request.path_params["job_id"]
    job = _store.get(job_id)
    if job is None:
        return _error_response("job_not_found", f"Job {job_id} not found.", 404)

    if job.status == "done":
        return JSONResponse(job.result)
    if job.status == "error":
        return _error_response(
            job.error or "scan_error",
            job.details or "Scan failed.",
            500,
        )

    return _error_response(
        "job_not_ready",
        f"Job is {job.status}. Poll /api/scan/{job_id}/status first.",
        409,
    )


routes = [
    Route("/api/scan", scan_endpoint, methods=["POST"]),
    Route("/api/scan/{job_id}/status", status_endpoint, methods=["GET"]),
    Route("/api/scan/{job_id}/graph", graph_endpoint, methods=["GET"]),
]

app = Starlette(routes=routes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)
