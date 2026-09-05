"""Unit tests for the v2 archify pipeline (#24 §17.2).

Covers: module-id mapping sanitize + collision assertion, function-id
sanitization, workflow-IR building (coverage / col clamp / cycle emphasis /
extra edges), in-process layout geometry, layout cache reuse, the
panel-id <-> ``data-node-id`` mapping guard, the style merge fallback, the
UTF-8 subprocess wrapper (GBK regression pin), and the archify probe.
Node/archify themselves are only exercised by the integration tests that skip
when archify is unavailable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import archify_env
import assemble
import to_archify
from to_archify import (
    assert_no_collisions,
    build_ir,
    count_crossings,
    evaluate,
    map_module_id,
    solve_layout,
)

# --- module id mapping (review F3) ---------------------------------------------
class TestModuleIdMapping:
    def test_design_examples(self):
        assert map_module_id("parser/_edges.py") == "parser__edges"
        assert map_module_id("main.py") == "main"
        assert map_module_id("pkg/sub/_deep_mod.py") == "pkg__sub__deep_mod"

    def test_id_pattern_satisfied(self):
        import re
        pattern = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")
        for mid in ("parser/_edges.py", "a/b/_c.py", "_x.py", "deep/nest/_name.py"):
            assert pattern.match(map_module_id(mid)), mid

    def test_collision_is_fatal(self):
        with pytest.raises(ValueError, match="collision"):
            assert_no_collisions({"parser/_edges.py": "parser__edges",
                                  "parser/edges.py": "parser__edges"})

    def test_clean_mapping_passes(self):
        assert_no_collisions({"parser/_edges.py": "parser__edges"}) is None


# --- workflow IR building --------------------------------------------------------
class TestBuildWorkflowIr:
    @staticmethod
    def _intra():
        return {
            "funcs": [{"name": "run", "line": 1}, {"name": "_helper", "line": 5},
                      {"name": "_fmt", "line": 9}, {"name": "_fmt_impl", "line": 12}],
            "calls": [
                {"from": "run", "to": "_helper", "line": 3},
                {"from": "_helper", "to": "_fmt", "line": 6},
                {"from": "_fmt", "to": "_fmt_impl", "line": 10},
                {"from": "_fmt_impl", "to": "_fmt", "line": 13},  # mutual cycle
            ],
        }

    @staticmethod
    def _spec():
        return {
            "module_id": "m/x.py",
            "title": "X",
            "promise": "does x",
            "interp": "how",
            "lanes": [{"id": "l1", "label": "one"}, {"id": "l2", "label": "two"}],
            "nodes": {
                "run": ["l1", 0, "entry"],
                "_helper": ["l1", 1, ""],
                "_fmt": ["l2", 0],
                "_fmt_impl": ["l2", 1, "impl"],
            },
            "extra_edges": [],
        }

    def test_happy_path_ir_shape(self):
        ir = assemble.build_workflow_ir(self._spec(), self._intra())
        assert ir["schema_version"] == 2 and ir["diagram_type"] == "workflow"
        ids = {n["id"] for n in ir["nodes"]}
        assert ids == {"run", "helper", "fmt", "fmt_impl"}  # leading underscores stripped
        assert all(n["col"] <= 5 for n in ir["nodes"])
        pairs = {(e["from"], e["to"]) for e in ir["edges"]}
        assert ("run", "helper") in pairs and ("fmt", "fmt_impl") in pairs

    def test_mutual_cycle_edges_highlighted(self):
        ir = assemble.build_workflow_ir(self._spec(), self._intra())
        by_pair = {(e["from"], e["to"]): e for e in ir["edges"]}
        assert by_pair[("fmt", "fmt_impl")]["variant"] == "emphasis"
        assert by_pair[("fmt_impl", "fmt")]["variant"] == "emphasis"

    def test_extra_edge_labels_existing_edge(self):
        spec = self._spec()
        spec["extra_edges"] = [{"from": "run", "to": "_helper", "label": "辅助"}]
        ir = assemble.build_workflow_ir(spec, self._intra())
        edge = next(e for e in ir["edges"] if (e["from"], e["to"]) == ("run", "helper"))
        assert edge["label"] == "辅助"
        assert len(ir["edges"]) == 4  # merged, not duplicated

    def test_missing_function_placement_is_fatal(self):
        spec = self._spec()
        del spec["nodes"]["_fmt_impl"]
        with pytest.raises(assemble.SpecError, match="missing"):
            assemble.build_workflow_ir(spec, self._intra())

    def test_unknown_function_is_fatal(self):
        spec = self._spec()
        spec["nodes"]["typo_name"] = ["l1", 3]
        with pytest.raises(assemble.SpecError, match="unknown functions"):
            assemble.build_workflow_ir(spec, self._intra())

    def test_col_clamped_to_five_then_collision_fatal(self):
        spec = self._spec()
        spec["nodes"]["run"] = ["l1", 9]
        spec["nodes"]["_helper"] = ["l1", 5]  # clamps to 5 == run's clamp
        with pytest.raises(assemble.SpecError, match="share lane"):
            assemble.build_workflow_ir(spec, self._intra())

    def test_col_clamp_keeps_distinct_cells(self):
        spec = self._spec()
        spec["nodes"]["run"] = ["l1", 7]
        ir = assemble.build_workflow_ir(spec, self._intra())
        run_node = next(n for n in ir["nodes"] if n["id"] == "run")
        assert run_node["col"] == 5

    def test_func_id_collision_after_sanitize_is_fatal(self):
        intra = {"funcs": [{"name": "_x", "line": 1}, {"name": "x", "line": 2}],
                 "calls": []}
        spec = {"module_id": "m.py", "lanes": [{"id": "l", "label": "L"}],
                "nodes": {"_x": ["l", 0], "x": ["l", 1]}}
        with pytest.raises(assemble.SpecError, match="collision"):
            assemble.build_workflow_ir(spec, intra)

    def test_self_recursion_dropped_and_module_pseudo_sanitized(self):
        intra = {
            "funcs": [{"name": "<module>", "line": 0}, {"name": "main", "line": 1}],
            "calls": [{"from": "<module>", "to": "main", "line": 9},
                      {"from": "main", "to": "main", "line": 4}],
        }
        spec = {"module_id": "m.py", "lanes": [{"id": "l", "label": "L"}],
                "nodes": {"<module>": ["l", 0], "main": ["l", 1]}}
        ir = assemble.build_workflow_ir(spec, intra)
        pairs = {(e["from"], e["to"]) for e in ir["edges"]}
        assert pairs == {("top_level", "main")}  # self-loop gone, pseudo renamed

    def test_extra_edge_unknown_endpoint_fatal(self):
        spec = self._spec()
        spec["extra_edges"] = [{"from": "run", "to": "ghost", "label": "x"}]
        with pytest.raises(assemble.SpecError, match="unplaced"):
            assemble.build_workflow_ir(spec, self._intra())


# --- in-process layout geometry ----------------------------------------------------
class TestLayout:
    def test_baseline_clean_when_dag_rows_aligned(self):
        # a -> b -> c laid out left-to-right never crosses
        pos = solve_layout(["a", "b", "c"], [("a", "b"), ("b", "c")], {"g": ["a", "b", "c"]})
        assert evaluate(pos, [("a", "b"), ("b", "c")], {"g": ["a", "b", "c"]})[0] == 0

    def test_crossing_counted(self):
        pos = {"a": (0, 0), "b": (2, 0), "c": (1, 1), "d": (3, 1)}
        # a->d and b->c cross when drawn straight
        assert count_crossings(pos, [("a", "d"), ("b", "c")]) >= 1

    def test_search_is_deterministic_fixed_seed(self):
        edges = [("a", "c"), ("b", "d"), ("c", "e"), ("d", "a"), ("e", "b")]
        ids = list("abcde")
        groups = {"g": ids}
        p1 = solve_layout(ids, edges, groups)
        p2 = solve_layout(ids, edges, groups)
        assert p1 == p2

    def test_grid_cells_never_overlap(self):
        pos = solve_layout(list("abcdef"), [("a", "f")], {"g": list("abcdef")})
        rects = [to_archify._cell_rect(*pos[mid]) for mid in pos]
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                assert not to_archify._rects_overlap(rects[i], rects[j])

    def test_layout_cache_reused_until_module_set_changes(self, tmp_path: Path):
        cache = tmp_path / "layout.json"
        to_archify.save_layout_cache(cache, ["a.py", "b.py"], {"a.py": (0, 0), "b.py": (1, 0)}, "showcase")
        assert to_archify.load_cached_layout(cache, ["b.py", "a.py"]) == {"a.py": (0, 0), "b.py": (1, 0)}
        assert to_archify.load_cached_layout(cache, ["a.py", "c.py"]) is None


# --- build_ir ------------------------------------------------------------------------
class TestBuildIr:
    def _metrics(self):
        return {
            "repo": "demo",
            "modules": [
                {"id": "p/_a.py", "depthScore": "deep", "ports": 8, "fanOut": 2},
                {"id": "p/_b.py", "depthScore": "shallow", "ports": 1, "fanOut": 6},
            ],
            "aggregatedEdges": [{"source": "p/_a.py", "target": "p/_b.py"}],
        }

    def test_ir_components_tags_and_mapping(self):
        mapping = {"p/_a.py": "p__a", "p/_b.py": "p__b"}
        pos = {"p/_a.py": (0, 0), "p/_b.py": (1, 0)}
        ir = build_ir({}, self._metrics(), pos, mapping, "demo")
        by_id = {c["id"]: c for c in ir["components"]}
        assert by_id["p__b"]["tag"] == "浅"  # shallow wins... then fanOut overrides? design: both possible, prototype kept one
        assert by_id["p__a"]["sublabel"].startswith("深")
        assert ir["connections"] == [{"from": "p__a", "to": "p__b"}]
        assert ir["boundaries"][0]["wraps"] == ["p__a", "p__b"]

    def test_shallow_and_fanout_tags(self):
        metrics = self._metrics()
        metrics["modules"][1]["depthScore"] = "moderate"
        metrics["modules"][1]["fanOut"] = 6
        mapping = {"p/_a.py": "p__a", "p/_b.py": "p__b"}
        pos = {"p/_a.py": (0, 0), "p/_b.py": (1, 0)}
        ir = build_ir({}, metrics, pos, mapping, "demo")
        comp = next(c for c in ir["components"] if c["id"] == "p__b")
        assert comp["tag"] == "扇出偏高"  # moderate -> no 浅 tag, fanOut tag applies


# --- style merge + svg guards (F8 / §13.4-2) -------------------------------------------
class TestAssembleExtraction:
    def test_merge_styles_dedupes_when_identical(self):
        blocks = [["<style>a{}</style>"], ["<style>a{}</style>"]]
        merged, mode = assemble.merge_styles(blocks)
        assert mode == "deduped" and merged == "<style>a{}</style>"

    def test_merge_styles_concatenates_on_mismatch(self):
        blocks = [["<style>a{}</style>"], ["<style>b{}</style>"]]
        merged, mode = assemble.merge_styles(blocks)
        assert mode == "concatenated"
        assert merged.index("<style>a") < merged.index("<style>b")
        assert "F8" in merged  # premise note present

    def test_merge_styles_flattens_stray_nesting(self):
        # Production once passed [[[block]], [[block]]]: flat[0] was a *list*,
        # so str.format repr'd it -- literal "\n" escapes + [' '] cruft that
        # silently broke the archify theme CSS (the all-black map incident).
        # Whatever the nesting, this must come back as a plain string.
        block = "<style>a{}</style>"
        merged, mode = assemble.merge_styles([[[block]], [[block]]])
        assert mode == "deduped"
        assert merged == block
        assert isinstance(merged, str)

    def test_merge_styles_rejects_non_string_blocks(self):
        with pytest.raises(TypeError):
            assemble.merge_styles([["<style>a{}</style>", 42]])

    def test_unique_ids_leaves_data_node_id_alone(self):
        svg = '<g id="node-1" data-node-id="main"><use href="#dot"/><title>aria</title></g>'
        out = assemble.unique_ids(svg, "arch")
        assert 'id="arch-node-1"' in out
        assert 'data-node-id="main"' in out  # the §13.4-2 incident, pinned
        assert 'href="#arch-dot"' in out

    def test_unique_ids_rewrites_aria_labelledby(self):
        svg = '<svg aria-labelledby="t1 t2"><title id="t1"/><desc id="t2"/></svg>'
        out = assemble.unique_ids(svg, "w")
        assert 'aria-labelledby="w-t1 w-t2"' in out

    def test_assert_panel_mapping_catches_mismatch(self):
        svg = '<g data-node-id="a"></g><g data-node-id="b"></g>'
        assemble.assert_panel_mapping(svg, ["a", "b"])
        with pytest.raises(RuntimeError, match="panels without node"):
            assemble.assert_panel_mapping(svg, ["a"])
        with pytest.raises(RuntimeError, match="nodes without panel"):
            assemble.assert_panel_mapping(svg, ["a", "b", "c"])


# --- subprocess wrapper (GBK regression pin, review F8) -------------------------------
class TestSubprocessWrapper:
    def test_run_node_pins_utf8_replace(self, monkeypatch):
        captured = {}

        def fake_run(cmd, **kwargs):
            captured.update(kwargs)
            captured["cmd"] = cmd

            class R:
                returncode = 0
                stdout = "{}"
                stderr = ""

            return R()

        monkeypatch.setattr(archify_env.subprocess, "run", fake_run)
        archify_env.run_node(["--version"])
        assert captured["encoding"] == "utf-8"
        assert captured["errors"] == "replace"
        assert captured["capture_output"] is True
        assert captured["cmd"][0] == "node"

    def test_probe_reports_node_missing_as_degraded(self, monkeypatch, tmp_path):
        archify_dir = tmp_path / "archify"
        (archify_dir / "bin").mkdir(parents=True)
        (archify_dir / "bin" / "archify.mjs").write_text("{}", encoding="utf-8")

        def boom(*args, **kwargs):
            raise OSError("node not found")

        monkeypatch.setattr(archify_env, "run_node", boom)
        result = archify_env.probe(env={"ARCHIFY_DIR": str(archify_dir)}, home=tmp_path)
        assert result["available"] is False and result["node"] is False

    def test_probe_env_dir_overrides_home(self, tmp_path):
        env_dir = tmp_path / "env-archify"
        (env_dir / "bin").mkdir(parents=True)
        (env_dir / "bin" / "archify.mjs").write_text("", encoding="utf-8")
        result = archify_env.probe(env={"ARCHIFY_DIR": str(env_dir)}, home=tmp_path)
        assert result["dir"] == str(env_dir)  # dir ok; node probe may pass or fail on this machine

    def test_probe_missing_dir_degrades(self, tmp_path):
        result = archify_env.probe(env={}, home=tmp_path)
        assert result["available"] is False
        assert "archify not found" in (result["reason"] or "")
