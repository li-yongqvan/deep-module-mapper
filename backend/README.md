# Deep Module Mapper Backend

HTTP API that wraps `parser.scan_codebase()` and exposes three endpoints for frontend polling.

## Prerequisites

- Python 3.10+
- The `parser/` sibling package must be available as an editable install.

## Install

From the repository root:

```bash
python -m pip install -e parser/ -e backend/
```

## Start the server

From the repository root:

```bash
python -m uvicorn backend.app:app --reload --port 8123
```

The server binds `127.0.0.1:8123` by default. Use `--host` and `--port` to override.

**Note**: Use `python -m uvicorn` (not bare `uvicorn`) if your system has multiple Python versions, so the command uses the interpreter that has `backend` installed.

**Note**: `--reload` restarts the process on code changes and may interrupt in-flight scans. Remove it for long-running scans.

## Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/scan` | Start a scan. Body: `{"path": "<repo-path>"}`. Returns `202` with `{"jobId": "..."}`. |
| GET | `/api/scan/{job_id}/status` | Get job status: `pending`, `running`, `done`, or `error`. On `error`, also returns `error`/`details`. |
| GET | `/api/scan/{job_id}/graph` | Get the Graph JSON when status is `done`. Returns `409` while running/pending, `500` on error, `404` for unknown job. |

## Example curl

```bash
# Start scan
JOB=$(curl -s -X POST http://127.0.0.1:8123/api/scan \
  -H "Content-Type: application/json" \
  -d '{"path":"backend/tests/fixtures/mini_pkg"}' | python -c "import sys,json; print(json.load(sys.stdin)['jobId'])")

# Poll status until done
curl -s http://127.0.0.1:8123/api/scan/$JOB/status

# Fetch graph
curl -s http://127.0.0.1:8123/api/scan/$JOB/graph | python -m json.tool
```

## CORS

For local development, CORS defaults to `["*"]`. Set `BACKEND_CORS_ORIGINS` to a comma-separated list to restrict origins:

```bash
BACKEND_CORS_ORIGINS="http://localhost:3000,http://localhost:5173" python -m uvicorn backend.app:app --port 8123
```

## Run tests

From the repository root:

```bash
python -m pytest parser/tests backend/tests -q
```

## Design baseline

See `wayfinder/handoff-build-core-backend-api.md` and the audited design document for architecture decisions.
