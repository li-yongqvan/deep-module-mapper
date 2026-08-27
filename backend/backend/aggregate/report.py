"""Report building for AI aggregation (S5, §5.7).

A report is a plain dict — output-only, so no schema-enforcement overhead. The
shape is stable enough for the CLI and tests to assert against:

- success: ``status="ok"`` + ``manifest.written`` + ``quality`` (when a
  ground truth was available, INV13).
- failure: ``status="failed"`` + ``manifest.written=false`` + ``error``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1


def build_report(
    *,
    status: str,
    repo: dict,
    manifest: dict,
    providers: dict,
    warnings: list[str],
    quality: dict | None = None,
    error: str | None = None,
) -> dict:
    """Assemble one report dict. ``error`` is only present on failure."""
    report: dict = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "repo": repo,
        "manifest": manifest,
        "quality": quality,
        "providers": providers,
        "warnings": warnings,
    }
    if error is not None:
        report["error"] = error
    return report


def write_report(report: dict, path: Path) -> None:
    """Persist a report (best-effort at the call site; failures must not mask
    the primary outcome)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
