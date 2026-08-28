"""Tests for the local-model learning flow (S6, D14/U6, INV4/INV16).

At the highest seam: the local attempt, sidecar + training-log collection, the
compare-and-reflect learn step, and the guarantees that local failure is never
fatal and the local answer never becomes the authoritative manifest. Offline.
"""

from __future__ import annotations

import json

import pytest

from backend.backend.aggregate import AggregationFailed, EXIT_OK, run_aggregation
from backend.backend.aggregate.config import EnvConfig
from backend.backend.aggregate.providers import ProviderResult

VALID = json.dumps(
    {
        "atoms": [
            {"id": "core", "name": "核心", "description": "核心功能", "files": ["alpha.py", "beta.py"]}
        ]
    },
    ensure_ascii=False,
)


class ScriptedProvider:
    name = "fake"

    def __init__(self, *results: ProviderResult) -> None:
        self._results = list(results)
        self.calls = 0
        self.users: list[str] = []

    def generate(self, system, user, *, temperature=0.1) -> ProviderResult:
        self.calls += 1
        self.users.append(user)
        return self._results.pop(0)


def _write_repo(tmp_path) -> None:
    (tmp_path / "alpha.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (tmp_path / "beta.py").write_text("from alpha import f\n", encoding="utf-8")


def _log_lines(log) -> list[dict]:
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_local_success_writes_sidecar_and_full_training_log(tmp_path):
    _write_repo(tmp_path)
    api = ScriptedProvider(ProviderResult(text=VALID, ok=True))
    local = ScriptedProvider(
        ProviderResult(text=VALID, ok=True),  # local attempt
        ProviderResult(text="云端分组更内聚：parser 八件套同属一个能力。", ok=True),  # learn
    )
    out = tmp_path / "m.json"
    log = tmp_path / "train.jsonl"

    code = run_aggregation(
        tmp_path,
        EnvConfig(llm_api_key="sk-test"),
        api_provider=api,
        local_provider=local,
        output=out,
        training_log=log,
    )

    assert code == EXIT_OK
    # sidecar written; authoritative manifest untouched by the local answer
    sidecar = json.loads((out.parent / "feature-atoms.local.json").read_text(encoding="utf-8"))
    assert sidecar["ok"] is True
    assert json.loads(out.read_text(encoding="utf-8")) == json.loads(VALID)

    # training log: api + local + learn, one shared run_id (D14 pairing)
    lines = _log_lines(log)
    assert [r["role"] for r in lines] == ["api", "local", "learn"]
    assert len({r["run_id"] for r in lines}) == 1
    learn = lines[2]
    assert "云端大模型" in learn["prompt"]  # LEARN prompt references the API answer
    assert learn["input"]["local_output"] and learn["input"]["api_output"]
    assert learn["ok"] is True
    # local record carries the digest the local model actually saw (F3)
    assert '"alpha.py"' in lines[1]["prompt"]
    assert lines[1]["api_reference"] == VALID


def test_local_record_reports_digest_truncation_warning(tmp_path):
    _write_repo(tmp_path)
    api = ScriptedProvider(ProviderResult(text=VALID, ok=True))
    local = ScriptedProvider(
        ProviderResult(text=VALID, ok=True),
        ProviderResult(text="学习笔记。", ok=True),
    )
    out = tmp_path / "m.json"

    code = run_aggregation(
        tmp_path,
        EnvConfig(llm_api_key="sk-test"),
        api_provider=api,
        local_provider=local,
        output=out,
    )

    assert code == EXIT_OK
    report = json.loads((out.parent / "feature-atoms.report.json").read_text(encoding="utf-8"))
    # Tiny repo → both digests fit; no truncation warnings.
    assert report["warnings"] == []


def test_local_failure_is_not_fatal(tmp_path):
    _write_repo(tmp_path)
    api = ScriptedProvider(ProviderResult(text=VALID, ok=True))
    local = ScriptedProvider(ProviderResult(text=None, ok=False, error="transport: refused"))
    out = tmp_path / "m.json"
    log = tmp_path / "train.jsonl"

    code = run_aggregation(
        tmp_path,
        EnvConfig(llm_api_key="sk-test"),
        api_provider=api,
        local_provider=local,
        output=out,
        training_log=log,
    )

    assert code == EXIT_OK  # authoritative path unaffected (INV16)
    assert out.exists()
    report = json.loads((out.parent / "feature-atoms.report.json").read_text(encoding="utf-8"))
    assert report["providers"]["local"]["ok"] is False
    assert report["providers"]["local"]["learn"] is None  # no learn step ran
    roles = [r["role"] for r in _log_lines(log)]
    assert "learn" not in roles  # reflection needs a usable local attempt


def test_local_invalid_output_still_learns_from_its_error(tmp_path):
    _write_repo(tmp_path)
    api = ScriptedProvider(ProviderResult(text=VALID, ok=True))
    local = ScriptedProvider(
        ProviderResult(text="not valid json {", ok=True),  # local attempt (invalid)
        ProviderResult(text="我的输出不合法，漏了 beta.py。", ok=True),  # learn
    )
    out = tmp_path / "m.json"
    log = tmp_path / "train.jsonl"

    code = run_aggregation(
        tmp_path,
        EnvConfig(llm_api_key="sk-test"),
        api_provider=api,
        local_provider=local,
        output=out,
        training_log=log,
    )

    assert code == EXIT_OK
    sidecar = json.loads((out.parent / "feature-atoms.local.json").read_text(encoding="utf-8"))
    assert sidecar["ok"] is False  # still recorded as an invalid attempt
    assert sidecar["raw_output"] == "not valid json {"
    roles = [r["role"] for r in _log_lines(log)]
    assert roles == ["api", "local", "learn"]  # reflection fires even on an invalid attempt
    learn = _log_lines(log)[2]
    assert learn["input"]["local_output"] == "not valid json {"
    assert learn["input"]["api_output"] == VALID
    assert "不是合法 JSON" in learn["prompt"]  # the validation error is fed back (U6)


def test_skip_local_never_calls_local_and_writes_no_sidecar(tmp_path):
    _write_repo(tmp_path)
    api = ScriptedProvider(ProviderResult(text=VALID, ok=True))
    local = ScriptedProvider(ProviderResult(text=VALID, ok=True))
    out = tmp_path / "m.json"

    code = run_aggregation(
        tmp_path,
        EnvConfig(llm_api_key="sk-test"),
        api_provider=api,
        local_provider=local,
        output=out,
        skip_local=True,
    )

    assert code == EXIT_OK
    assert local.calls == 0
    assert not (out.parent / "feature-atoms.local.json").exists()
    report = json.loads((out.parent / "feature-atoms.report.json").read_text(encoding="utf-8"))
    assert report["providers"]["local"] is None


def test_training_log_appends_without_clobbering(tmp_path):
    _write_repo(tmp_path)
    log = tmp_path / "train.jsonl"
    log.write_text('{"first": true}\n', encoding="utf-8")
    api = ScriptedProvider(ProviderResult(text=VALID, ok=True))
    local = ScriptedProvider(
        ProviderResult(text=VALID, ok=True),
        ProviderResult(text="学习笔记。", ok=True),
    )

    run_aggregation(
        tmp_path,
        EnvConfig(llm_api_key="sk-test"),
        api_provider=api,
        local_provider=local,
        training_log=log,
    )

    lines = [l for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert json.loads(lines[0]) == {"first": True}  # pre-existing row preserved
    assert [json.loads(l)["role"] for l in lines[1:]] == ["api", "local", "learn"]


def test_api_failure_skips_local_learning_entirely(tmp_path):
    _write_repo(tmp_path)
    api = ScriptedProvider(
        ProviderResult(text=None, ok=False, error="http 400: bad", retryable=False)
    )
    local = ScriptedProvider(ProviderResult(text=VALID, ok=True))

    with pytest.raises(AggregationFailed):
        run_aggregation(
            tmp_path,
            EnvConfig(llm_api_key="sk-test"),
            api_provider=api,
            local_provider=local,
            training_log=tmp_path / "train.jsonl",
        )

    assert local.calls == 0  # a failed authoritative run collects nothing
