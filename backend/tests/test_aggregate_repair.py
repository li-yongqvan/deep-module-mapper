"""Repair-path tests at the highest seam (S5, D8).

One invalid API output triggers a single repair pass; a repaired valid output
succeeds. An output that stays invalid after repair is an aggregation failure.
Offline — the fake provider scripts the two calls.
"""

from __future__ import annotations

import json

import pytest

from backend.backend.aggregate import AggregationFailed, EXIT_OK, run_aggregation
from backend.backend.aggregate.config import EnvConfig
from backend.backend.aggregate.providers import ProviderResult

VALID_MANIFEST = json.dumps(
    {
        "atoms": [
            {"id": "core", "name": "核心", "description": "核心功能", "files": ["alpha.py", "beta.py"]}
        ]
    },
    ensure_ascii=False,
)


class ScriptedProvider:
    """Returns pre-arranged results and records the user prompts sent."""

    name = "fake"

    def __init__(self, *results: ProviderResult) -> None:
        self._results = list(results)
        self.users: list[str] = []

    def generate(self, system, user, *, temperature=0.1) -> ProviderResult:
        self.users.append(user)
        return self._results.pop(0)


def _write_repo(tmp_path) -> None:
    (tmp_path / "alpha.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (tmp_path / "beta.py").write_text("from alpha import f\n", encoding="utf-8")


def test_invalid_json_is_repaired_then_succeeds(tmp_path):
    _write_repo(tmp_path)
    provider = ScriptedProvider(
        ProviderResult(text="not valid json {", ok=True),
        ProviderResult(text=VALID_MANIFEST, ok=True),
    )
    out = tmp_path / "m.json"

    code = run_aggregation(
        tmp_path, EnvConfig(llm_api_key="sk-test"), api_provider=provider, output=out
    )

    assert code == EXIT_OK
    assert out.exists()
    assert "JSON" in provider.users[1]  # repair prompt carries the JSON error
    assert len(provider.users) == 2  # exactly one repair pass (D8)


def test_missing_coverage_is_repaired_then_succeeds(tmp_path):
    _write_repo(tmp_path)
    partial = json.dumps(
        {"atoms": [{"id": "core", "name": "核心", "description": "核心功能", "files": ["alpha.py"]}]},
        ensure_ascii=False,
    )
    provider = ScriptedProvider(
        ProviderResult(text=partial, ok=True),  # misses beta.py → C2 coverage error
        ProviderResult(text=VALID_MANIFEST, ok=True),
    )
    out = tmp_path / "m.json"

    code = run_aggregation(
        tmp_path, EnvConfig(llm_api_key="sk-test"), api_provider=provider, output=out
    )

    assert code == EXIT_OK
    assert "覆盖缺失" in provider.users[1]
    assert json.loads(out.read_text(encoding="utf-8")) == json.loads(VALID_MANIFEST)


def test_output_still_invalid_after_repair_is_a_failure(tmp_path):
    _write_repo(tmp_path)
    provider = ScriptedProvider(
        ProviderResult(text="not valid json {", ok=True),
        ProviderResult(text="still not valid", ok=True),
    )
    out = tmp_path / "m.json"

    with pytest.raises(AggregationFailed) as excinfo:
        run_aggregation(
            tmp_path, EnvConfig(llm_api_key="sk-test"), api_provider=provider, output=out
        )

    assert "仍无效" in str(excinfo.value)
    assert not out.exists()  # INV5: nothing written on failure
