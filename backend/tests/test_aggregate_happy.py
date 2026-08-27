"""Happy-path tests at the highest seam — run_aggregation (S5).

A fake API provider returns a valid manifest; the runner must scan, validate,
compare against a ground truth, write the drop-in manifest + report, and return
EXIT_OK. Offline.
"""

from __future__ import annotations

import json

import pytest

from backend.backend.aggregate import EXIT_OK, FatalError, run_aggregation
from backend.backend.aggregate.config import EnvConfig
from backend.backend.aggregate.providers import ProviderResult

VALID_MANIFEST = {
    "atoms": [
        {"id": "core", "name": "核心", "description": "核心功能", "files": ["alpha.py", "beta.py"]}
    ]
}


class FakeProvider:
    name = "fake"

    def __init__(self, result: ProviderResult) -> None:
        self.result = result

    def generate(self, system, user, *, temperature=0.1) -> ProviderResult:
        return self.result


def _write_repo(tmp_path) -> None:
    (tmp_path / "alpha.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (tmp_path / "beta.py").write_text("from alpha import f\n\ndef g():\n    return f()\n", encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg/__init__.py").write_text("", encoding="utf-8")


def _ok(result_text: str = json.dumps(VALID_MANIFEST, ensure_ascii=False)) -> ProviderResult:
    return ProviderResult(text=result_text, ok=True)


def test_happy_path_writes_manifest_and_report_with_quality(tmp_path):
    _write_repo(tmp_path)
    cfg = EnvConfig(llm_api_key="sk-test")
    out = tmp_path / "nested/manifests/feature-atoms.json"  # mkdir parents (F9)
    gt = tmp_path / "gt.json"
    gt.write_text(json.dumps(VALID_MANIFEST, ensure_ascii=False), encoding="utf-8")

    code = run_aggregation(tmp_path, cfg, api_provider=FakeProvider(_ok()), output=out, compare=gt)

    assert code == EXIT_OK
    assert json.loads(out.read_text(encoding="utf-8")) == VALID_MANIFEST
    report = json.loads(
        (out.parent / "feature-atoms.report.json").read_text(encoding="utf-8")
    )
    assert report["status"] == "ok"
    assert report["manifest"] == {
        "written": True,
        "source": "ai",
        "path": str(out),
        "atomCount": 1,
        "coverage": {
            "productionFiles": 2,
            "assigned": 2,
            "missing": [],
            "duplicated": [],
            "noiseFiles": [],
            "unknownFiles": [],
        },
    }
    q = report["quality"]
    assert q["groundTruthPath"] == str(gt)
    assert q["accuracy"] == 1.0
    assert q["correctCount"] == 2 and q["gtProductionTotal"] == 2
    assert q["aiMissed"] == [] and q["aiExtra"] == []
    assert report["repo"]["productionModules"] == 2
    assert report["providers"]["api"] == {"ok": True, "attempts": 1, "error": None}
    assert report["warnings"] == []


def test_default_output_lives_under_repo(tmp_path):
    _write_repo(tmp_path)

    code = run_aggregation(tmp_path, EnvConfig(llm_api_key="sk-test"), api_provider=FakeProvider(_ok()))

    assert code == EXIT_OK
    assert (tmp_path / "frontend/src/manifest/feature-atoms.json").exists()


def test_default_ground_truth_is_existing_output(tmp_path):
    _write_repo(tmp_path)
    default = tmp_path / "frontend/src/manifest/feature-atoms.json"
    default.parent.mkdir(parents=True)
    default.write_text(json.dumps(VALID_MANIFEST, ensure_ascii=False), encoding="utf-8")

    code = run_aggregation(tmp_path, EnvConfig(llm_api_key="sk-test"), api_provider=FakeProvider(_ok()))

    assert code == EXIT_OK
    report = json.loads(
        (tmp_path / "frontend/src/manifest/feature-atoms.report.json").read_text(encoding="utf-8")
    )
    assert report["quality"] is not None and report["quality"]["accuracy"] == 1.0
    assert json.loads(default.read_text(encoding="utf-8")) == VALID_MANIFEST  # overwritten drop-in


def test_dry_run_prints_and_writes_nothing(tmp_path, capsys):
    _write_repo(tmp_path)

    code = run_aggregation(
        tmp_path,
        EnvConfig(llm_api_key="sk-test"),
        api_provider=FakeProvider(_ok()),
        dry_run=True,
    )

    assert code == EXIT_OK
    assert "core" in capsys.readouterr().out
    assert not (tmp_path / "frontend/src/manifest/feature-atoms.json").exists()
    assert not (tmp_path / "frontend/src/manifest/feature-atoms.report.json").exists()


def test_missing_ground_truth_warns_but_succeeds(tmp_path):
    _write_repo(tmp_path)
    out = tmp_path / "m.json"

    code = run_aggregation(
        tmp_path,
        EnvConfig(llm_api_key="sk-test"),
        api_provider=FakeProvider(_ok()),
        output=out,
        compare=tmp_path / "no-such-gt.json",
    )

    assert code == EXIT_OK
    report = json.loads((out.parent / "feature-atoms.report.json").read_text(encoding="utf-8"))
    assert report["quality"] is None
    assert any("ground truth" in w for w in report["warnings"])


def test_bad_repo_path_is_fatal(tmp_path):
    with pytest.raises(FatalError):
        run_aggregation(tmp_path / "nope", EnvConfig(llm_api_key="sk-test"))


def test_missing_api_key_is_fatal(tmp_path):
    with pytest.raises(FatalError):
        run_aggregation(tmp_path, EnvConfig(llm_api_key=None))
