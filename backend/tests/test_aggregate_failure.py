"""Failure-path tests at the highest seam (S5, D9/U1, INV5).

When the authoritative API fails, the runner writes a ``status=failed`` report,
leaves any existing scaffold manifest untouched, writes nothing, and raises
AggregationFailed (→ exit 2 with the retryable message in the CLI).
Offline — a non-retryable API failure stops the retry loop immediately (the
retry-until-exhausted behavior itself is covered in S2).
"""

from __future__ import annotations

import json

import pytest

from backend.backend.aggregate import AggregationFailed, run_aggregation
from backend.backend.aggregate.config import EnvConfig
from backend.backend.aggregate.providers import ProviderResult

SCAFFOLD = json.dumps(
    {"atoms": [{"id": "old", "name": "旧", "description": "手写脚手架", "files": ["alpha.py"]}]},
    ensure_ascii=False,
)


class FakeProvider:
    name = "fake"

    def __init__(self, result: ProviderResult) -> None:
        self.result = result

    def generate(self, system, user, *, temperature=0.1) -> ProviderResult:
        return self.result


def _write_repo(tmp_path) -> None:
    (tmp_path / "alpha.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (tmp_path / "beta.py").write_text("from alpha import f\n", encoding="utf-8")


def test_api_failure_writes_failed_report_and_leaves_scaffold_untouched(tmp_path):
    _write_repo(tmp_path)
    scaffold = tmp_path / "frontend/src/manifest/feature-atoms.json"
    scaffold.parent.mkdir(parents=True)
    scaffold.write_text(SCAFFOLD, encoding="utf-8")

    with pytest.raises(AggregationFailed) as excinfo:
        run_aggregation(
            tmp_path,
            EnvConfig(llm_api_key="sk-test"),
            api_provider=FakeProvider(
                ProviderResult(text=None, ok=False, error="http 500: boom", retryable=False)
            ),
        )

    assert "http 500" in str(excinfo.value)
    assert scaffold.read_text(encoding="utf-8") == SCAFFOLD  # scaffold preserved, not a fallback
    report = json.loads(
        (tmp_path / "frontend/src/manifest/feature-atoms.report.json").read_text(encoding="utf-8")
    )
    assert report["status"] == "failed"
    assert report["manifest"] == {"written": False}
    assert "http 500" in report["error"]
    assert report["providers"]["api"]["ok"] is False
    assert report["providers"]["api"]["attempts"] == 1


def test_failure_writes_no_manifest_even_with_explicit_output(tmp_path):
    _write_repo(tmp_path)
    out = tmp_path / "m.json"

    with pytest.raises(AggregationFailed):
        run_aggregation(
            tmp_path,
            EnvConfig(llm_api_key="sk-test"),
            api_provider=FakeProvider(
                ProviderResult(text=None, ok=False, error="http 400: bad request", retryable=False)
            ),
            output=out,
        )

    assert not out.exists()  # INV5: no manifest written on any AI failure
