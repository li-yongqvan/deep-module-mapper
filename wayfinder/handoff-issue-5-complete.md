---
name: handoff-issue-5-complete
wayfinder: handoff
ticket: "#5"
status: complete
---

# Handoff: Issue #5 — Core Backend API Complete

**Ticket**: https://github.com/li-yongqvan/deep-module-mapper/issues/5  
**PR**: https://github.com/li-yongqvan/deep-module-mapper/pull/6  
**Merged**: `master` @ `3e48ac9`  
**Worktree**: removed after merge  

## What shipped

A runnable `backend/` Python package wrapping `parser.scan_codebase()`:

- `POST /api/scan` — accepts `{"path": "..."}`, returns `202` with `{"jobId": "..."}`
- `GET /api/scan/:jobId/status` — returns `pending|running|done|error`; on error includes `error`/`details`
- `GET /api/scan/:jobId/graph` — returns Graph JSON when `done`; `409` while running/pending, `500` on error, `404` for unknown job

Plus:

- `backend/tests/` with `TestClient`-based tests and fixtures
- `backend/README.md` with install/start/test/curl instructions
- `wayfinder/grilling-decisions/issue-5-backend-decisions.md` archiving D4-D7 decisions

## Locked decisions

| Decision | Choice |
|---|---|
| Framework | Starlette `>=1.3.1,<2` + Uvicorn |
| Background scan | `threading.Thread(daemon=True)` |
| Error body | `{"error": "snake_case", "details": "..."}` |
| Bind address | `127.0.0.1:8123` |
| CORS | Local dev defaults to `["*"]`, override with `BACKEND_CORS_ORIGINS` comma-separated env var |
| Job eviction | Max 100 jobs; only evict oldest `done`/`error` jobs |
| Path sandbox | None in this ticket; any local directory scannable |
| Persistence | None; all state in memory |

## Verification

```bash
python -m pip install -e parser/ -e backend/
python -m pytest parser/tests backend/tests -q
```

Result: **44 passed**.

Manual smoke test with `python -m uvicorn backend.app:app --port 8123` also passed end-to-end.

## Known risks and limits

1. **CORS `*`** — acceptable only because the server binds `127.0.0.1`. Once the frontend dev port is known, tighten the default origin.
2. **No path sandbox** — any local directory can be scanned. Add a configured sandbox if the tool is ever exposed beyond localhost.
3. **No concurrent scan limit** — accepted for a local dev tool; unbounded POSTs can spawn unbounded threads.
4. **OSError can crash a scan** — parser handles parse errors as diagnostics but does not catch file I/O errors (e.g. permission denied, file deleted mid-scan). This is a parser limitation, not touched in this ticket per the red line.
5. **`--reload` kills in-flight scans** — documented in README; remove `--reload` for long scans.
6. **Environment quirk** — the machine has multiple Python interpreters. Always use `python -m uvicorn` and `python -m pytest`, not bare `uvicorn`/`pytest`.

## Next steps for the coordinator

1. **Update the project map / milestone** — mark issue #5 complete and unblock any downstream tickets that depend on the backend API.
2. **Point the frontend team at the endpoints** — contract is three endpoints above; default base URL is `http://127.0.0.1:8123`.
3. **Decide the frontend dev port** — once known, update `backend/app.py` default CORS origins and `backend/README.md`.
4. **Schedule follow-up tickets** (out of scope here):
   - Design-canvas persistence (`/api/designs`)
   - AI descriptions (`/api/descriptions/*`)
   - AI review (`/api/review`)
   - Path sandbox / auth if the backend leaves localhost
   - Database persistence for scan history

## Completion criterion

This handoff is done when the coordinator has updated the project map and confirmed the frontend integration path.
