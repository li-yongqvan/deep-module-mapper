"""End-to-end tests for the v2 pipeline (#24 §17.3/§17.4).

- Full pipeline (integration, real archify + node): scan -> to_archify -> AI
  panel specs (mechanically generated here -- the pipeline contract, not the
  annotation quality) -> assemble -> map.html with a consistent
  node<->panel mapping.  Skips when archify is unavailable.
- Downgrade e2e x3 (review F5): empty ARCHIFY_DIR, missing archify
  installation, node runtime missing -- all must exit 0 with the v1 four
  artefacts and an explicit "archify unavailable" report.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import archify_env
import assemble

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
FIXTURES = REPO_ROOT / "parser" / "tests" / "fixtures"


def _run_script(script: Path, *args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=300,
    )


def _last_json(stdout: str) -> dict:
    return json.loads(stdout.strip().splitlines()[-1])


# --- full pipeline (real archify) -------------------------------------------------

@pytest.fixture(scope="module")
def v2_outputs(tmp_path_factory) -> dict:
    """Run the whole v2 pipeline over sample_pkg with mechanical panel specs."""
    last_review = tmp_path_factory.mktemp("v2e2e")

    analyzed = _run_script(
        SCRIPTS / "analyze.py", str(FIXTURES / "sample_pkg"),
        "--output-dir", str(last_review),
    )
    assert analyzed.returncode == 0, analyzed.stderr
    probe = _last_json(analyzed.stdout)["archify"]
    if not probe["available"]:
        pytest.skip(f"archify unavailable on this machine: {probe['reason']}")

    built = _run_script(SCRIPTS / "to_archify.py", "--last-review", str(last_review))
    assert built.returncode == 0, built.stderr
    to_archify_out = _last_json(built.stdout)

    idmap = json.loads((last_review / "idmap.json").read_text(encoding="utf-8"))
    graph = json.loads((last_review / "graph.json").read_text(encoding="utf-8"))
    panels = last_review / "panels"
    panels.mkdir()
    for module_id, short in idmap.items():
        entry = graph["intra"][module_id]
        funcs = entry["funcs"]
        n_lanes = max(1, -(-len(funcs) // 6))  # ceil: 6 columns per lane
        placements = {
            f["name"]: [f"lane{i // 6}", i % 6, ""] for i, f in enumerate(funcs)
        }
        spec = {
            "module_id": module_id,
            "title": short,
            "promise": f"{module_id} 的机械占位承诺（e2e）。",
            "interp": "机械占位解读（e2e）：函数与调用来自 intra，非 AI 标注。",
            "lanes": [{"id": f"lane{i}", "label": f"L{i}"} for i in range(n_lanes)],
            "nodes": placements,
            "extra_edges": [],
        }
        (panels / f"{short}.json").write_text(
            json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    (panels / "_summary.json").write_text(
        json.dumps({"summary_html": "<p>e2e 总评占位</p>"}, ensure_ascii=False),
        encoding="utf-8",
    )

    assembled = _run_script(SCRIPTS / "assemble.py", "--last-review", str(last_review))
    assert assembled.returncode == 0, assembled.stderr
    return {
        "dir": last_review,
        "assemble": _last_json(assembled.stdout),
        "to_archify": to_archify_out,
        "idmap": idmap,
        "graph": graph,
    }


@pytest.mark.skipif(not archify_env.probe()["available"], reason="archify/node not available")
class TestFullPipeline:
    def test_map_html_written_with_full_panel_coverage(self, v2_outputs):
        out = v2_outputs["assemble"]
        assert out["ok"] is True
        map_html = Path(out["map"]).read_text(encoding="utf-8")
        assert 'id="arch"' in map_html
        panel_ids = set(__import__("re").findall(r'id="panel-([^"]+)"', map_html))
        node_ids = set(v2_outputs["idmap"].values())
        assert panel_ids == node_ids
        assert "e2e 总评占位" in map_html  # summary injected

    def test_panel_workflow_irs_match_intra(self, v2_outputs):
        graph = v2_outputs["graph"]
        panels_dir = Path(v2_outputs["dir"]) / "panels"
        for module_id, short in v2_outputs["idmap"].items():
            ir = json.loads((panels_dir / f"{short}.workflow.json").read_text(encoding="utf-8"))
            entry = graph["intra"][module_id]
            ir_nodes = {n["label"] for n in ir["nodes"]}
            expected_funcs = {f["name"] for f in entry["funcs"]}
            assert ir_nodes == expected_funcs, module_id
            # every intra call appears as an IR edge (self-loops dropped by design)
            name_to_id = {n["label"]: n["id"] for n in ir["nodes"]}
            expected_edges = {
                (name_to_id[c["from"]], name_to_id[c["to"]])
                for c in entry["calls"] if c["from"] != c["to"]
            }
            ir_edges = {(e["from"], e["to"]) for e in ir["edges"]}
            assert expected_edges <= ir_edges, module_id

    def test_map_html_style_matches_raw_deliver(self, v2_outputs):
        # Regression for the all-black map incident: a list-shaped styles value
        # was repr'd by str.format (literal \n escapes + [' '] cruft), silently
        # corrupting the archify theme CSS.  When deduped, the merged style in
        # map.html must be byte-identical to the raw deliver's style block.
        out = v2_outputs["assemble"]
        assert out["styleMode"] == "deduped"
        map_html = Path(out["map"]).read_text(encoding="utf-8")
        first_panel = next(iter(v2_outputs["idmap"].values()))
        panel_html = (Path(v2_outputs["dir"]) / "panels" / f"{first_panel}.html").read_text(encoding="utf-8")
        map_style = assemble.extract_style_blocks(map_html)[0]
        raw_style = assemble.extract_style_blocks(panel_html)[0]
        assert isinstance(map_style, str)
        assert map_style == raw_style

    def test_layout_cache_reused_on_second_run(self, v2_outputs):
        last_review = Path(v2_outputs["dir"])
        second = _run_script(SCRIPTS / "to_archify.py", "--last-review", str(last_review))
        assert second.returncode == 0
        assert _last_json(second.stdout)["layoutReused"] is True


# --- downgrade e2e x3 (review F5) ---------------------------------------------------

class TestDowngradeE2E:
    def _assert_v1_degraded(self, result: subprocess.CompletedProcess, out_dir: Path):
        assert result.returncode == 0, result.stderr  # degradation is not an error
        payload = _last_json(result.stdout)
        assert payload["archify"]["available"] is False
        for name in ("graph.json", "metrics.json", "digest.json", "diagram.svg"):
            assert (out_dir / name).is_file(), name
        return payload

    def test_archify_dir_env_points_to_empty_dir(self, tmp_path):
        out_dir = tmp_path / "out"
        empty = tmp_path / "empty-archify"
        empty.mkdir()
        result = _run_script(
            SCRIPTS / "analyze.py", str(FIXTURES / "sample_pkg"),
            "--output-dir", str(out_dir),
            env_extra={"ARCHIFY_DIR": str(empty)},
        )
        payload = self._assert_v1_degraded(result, out_dir)
        assert "archify not found" in (payload["archify"]["reason"] or "")

    def test_archify_installation_missing(self, tmp_path):
        out_dir = tmp_path / "out"
        fake_home = tmp_path / "home"
        fake_home.mkdir()  # no .claude/skills/archify inside
        result = _run_script(
            SCRIPTS / "analyze.py", str(FIXTURES / "sample_pkg"),
            "--output-dir", str(out_dir),
            env_extra={"ARCHIFY_DIR": "", "HOME": str(fake_home), "USERPROFILE": str(fake_home)},
        )
        self._assert_v1_degraded(result, out_dir)

    def test_node_runtime_missing(self, tmp_path):
        out_dir = tmp_path / "out"
        stub = tmp_path / "stub-archify"
        (stub / "bin").mkdir(parents=True)
        (stub / "bin" / "archify.mjs").write_text("// stub", encoding="utf-8")
        result = _run_script(
            SCRIPTS / "analyze.py", str(FIXTURES / "sample_pkg"),
            "--output-dir", str(out_dir),
            env_extra={"ARCHIFY_DIR": str(stub), "PATH": str(tmp_path)},  # no node on PATH
        )
        payload = self._assert_v1_degraded(result, out_dir)
        assert payload["archify"]["node"] is False
        assert "node" in (payload["archify"]["reason"] or "")
