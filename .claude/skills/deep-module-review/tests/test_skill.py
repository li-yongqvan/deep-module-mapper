"""Unit tests for the ``/deep-module-review`` skill scripts (#24 §8.2).

Covers: depth-score boundaries, edge aggregation, SCC cycle detection, orphan
three-way classification, ``__init__`` facade re-pointing, digest noise filter,
SVG node count, and an integration check against the real parser fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import analyze
import digest as digest_mod
import diagram
import metrics
from metrics import compute_metrics, depth_score

# --- helpers -----------------------------------------------------------------


def _module(mid: str, lines: list[int]) -> dict:
    ports = [
        {
            "kind": "function",
            "name": f"f{i}",
            "line": ln,
            "signature": f"def f{i}():",
            "params": [],
        }
        for i, ln in enumerate(lines)
    ]
    return {"id": mid, "path": mid, "ports": ports}


def graph(
    modules: dict[str, list[int]] | None = None,
    edges: list[dict] | None = None,
    external: list[str] | None = None,
) -> dict:
    """Build a minimal parser-shaped Graph dict from simple specs.

    ``modules`` maps module id -> port line numbers. ``edges`` entries may be
    dicts {source,target,kind?,targetPort?,sites?}. ``external`` are third-party
    ids referenced from source modules (produce no edges, as in the parser).
    """
    modules = modules or {}
    mods = [_module(mid, lines) for mid, lines in modules.items()]
    ports = []
    for m in mods:
        for p in m["ports"]:
            ports.append(p | {"moduleId": m["id"]})
    edge_list = []
    for i, e in enumerate(edges or []):
        edge_list.append(
            {
                "source": e["source"],
                "target": e["target"],
                "kind": e.get("kind", "import"),
                "sites": e.get("sites") or [{"line": i}],
                **({"targetPort": e["targetPort"]} if "targetPort" in e else {}),
            }
        )
    external_mods = [{"id": x, "name": x, "kind": "third_party"} for x in (external or [])]
    return {
        "modules": mods,
        "ports": ports,
        "edges": edge_list,
        "externalModules": external_mods,
        "diagnostics": [],
    }


# --- depth scoring ------------------------------------------------------------
class TestDepthScore:
    def test_zero_ports_is_shallow(self):
        assert depth_score([]) == ("shallow", None)

    def test_ratio_at_or_above_deep_threshold(self):
        # maxLine=100 / 2 ports = 50  -> deep (>= 50)
        assert depth_score([{"line": 1}, {"line": 100}])[0] == "deep"

    def test_ratio_in_moderate_band(self):
        # maxLine=30 / 2 ports = 15  -> moderate (>= 15, < 50)
        assert depth_score([{"line": 1}, {"line": 30}])[0] == "moderate"

    def test_ratio_below_moderate_is_shallow(self):
        # maxLine=20 / 2 ports = 10 -> shallow
        assert depth_score([{"line": 1}, {"line": 20}])[0] == "shallow"


# --- edge aggregation ---------------------------------------------------------
class TestEdgeAggregation:
    def test_groups_kinds_by_source_target(self):
        g = graph(
            {"a.py": [1], "b.py": [1], "c.py": [1]},
            edges=[
                {"source": "a.py", "target": "b.py", "kind": "import"},
                {"source": "a.py", "target": "b.py", "kind": "call"},
                {"source": "a.py", "target": "c.py", "kind": "import"},
            ],
        )
        m = compute_metrics(g, "repo")
        by_pair = {(e["source"], e["target"]): e for e in m["aggregatedEdges"]}
        assert set(by_pair) == {("a.py", "b.py"), ("a.py", "c.py")}
        assert by_pair[("a.py", "b.py")]["kinds"] == ["call", "import"]
        assert by_pair[("a.py", "b.py")]["weight"] == 2

    def test_third_party_target_not_a_review_edge(self):
        g = graph({"a.py": [1], "b.py": [1]}, external=["requests"])
        g["edges"].append(
            {"source": "a.py", "target": "requests", "kind": "import", "sites": [{"line": 1}]}
        )
        m = compute_metrics(g, "repo")
        assert all(e["target"] != "requests" for e in m["aggregatedEdges"])
        row = next(r for r in m["modules"] if r["id"] == "a.py")
        assert row["externalDeps"] == ["requests"]


# --- cycle detection ----------------------------------------------------------
class TestCycleDetection:
    def test_detects_two_node_cycle(self):
        g = graph(
            {"a.py": [1], "b.py": [1]},
            edges=[{"source": "a.py", "target": "b.py"}, {"source": "b.py", "target": "a.py"}],
        )
        m = compute_metrics(g, "repo")
        assert m["summary"]["cycles"] == 1
        assert m["summary"]["cycleModules"] == 2
        assert sorted(m["cycles"][0]["modules"]) == ["a.py", "b.py"]
        by_id = {r["id"]: r["finding"] for r in m["modules"]}
        assert by_id["a.py"] == "cycle/scc"
        assert by_id["b.py"] == "cycle/scc"

    def test_dag_not_a_cycle(self):
        g = graph(
            {"a.py": [1], "b.py": [1], "c.py": [1]},
            edges=[
                {"source": "a.py", "target": "b.py"},
                {"source": "b.py", "target": "c.py"},
            ],
        )
        m = compute_metrics(g, "repo")
        assert m["summary"]["cycles"] == 0
        assert all(r["finding"] is None for r in m["modules"])


# --- orphan three-way classification ------------------------------------------
class TestOrphanClassification:
    def test_isolated_third_party_only_normal(self):
        g = graph(
            {"a.py": [1], "b.py": [1], "c.py": [1], "d.py": [1]},
            edges=[
                {"source": "a.py", "target": "c.py"},  # a, c: normal
                {"source": "b.py", "target": "requests", "kind": "import"},
            ],
            external=["requests"],
        )
        # add the third-party edge to b.py through graph["edges"] so the parser
        # shape matches reality (external targets are in externalModules only)
        g["edges"].append({"source": "b.py", "target": "requests", "kind": "import"})
        m = compute_metrics(g, "repo")
        by_id = {r["id"]: r for r in m["modules"]}
        assert by_id["a.py"]["finding"] is None
        assert by_id["c.py"]["finding"] is None
        assert by_id["b.py"]["finding"] == "orphan/third-party-only"
        assert by_id["d.py"]["finding"] == "orphan/isolated"
        assert m["summary"]["isolated"] == 1
        assert m["summary"]["thirdPartyOnly"] == 1
        assert m["orphans"]["isolated"] == [{"id": "d.py", "depthScore": "shallow"}]


# --- __init__ facade re-pointing ----------------------------------------------
class TestFacadeResolution:
    def test_consumer_import_through_init_redirects_to_producer(self):
        g = graph(
            {
                "main.py": [1],
                "pkg/core.py": [30, 60],  # deep producer
                "pkg/__init__.py": [5],  # facade, re-exports run from core
            }
        )
        # backing re-export edge (facade -> producer)
        g["edges"].append(
            {"source": "pkg/__init__.py", "target": "pkg/core.py",
             "kind": "from_import", "targetPort": "run"}
        )
        # consumer imports `run` *through* the package facade
        g["edges"].append(
            {"source": "main.py", "target": "pkg/__init__.py",
             "kind": "from_import", "targetPort": "run"}
        )
        m = compute_metrics(g, "repo")
        ids = [r["id"] for r in m["modules"]]
        assert "pkg/__init__.py" not in ids  # facades excluded from nodes
        edges = {(e["source"], e["target"]): e for e in m["aggregatedEdges"]}
        assert ("main.py", "pkg/core.py") in edges
        assert edges[("main.py", "pkg/core.py")]["viaFacade"] == "pkg/__init__.py"
        core = next(r for r in m["modules"] if r["id"] == "pkg/core.py")
        assert core["viaFacade"] is True
        assert core["finding"] is None  # public API is not "dead"/isolated


# --- digest -------------------------------------------------------------------
class TestDigest:
    def test_noise_modules_filtered_and_never_dropped_fields(self):
        g = graph(
            {
                "lib.py": [1, 40],
                "tests/test_lib.py": [1],
            },
            edges=[{"source": "tests/test_lib.py", "target": "lib.py"}],
        )
        d = digest_mod.build_digest(g, root="repo")
        payload = json.loads(d.text)
        ids = [x["id"] for x in payload["modules"]]
        assert ids == ["lib.py"]  # /tests/ noise dropped
        assert payload["repo"] == "repo"
        assert d.truncation == "none"  # small graph fits 40K budget


# --- SVG ----------------------------------------------------------------------
class TestDiagram:
    def test_node_count_matches_production_modules(self):
        g = graph(
            {
                "a.py": [1],
                "b.py": [1],
                "c.py": [1],
                "d/__init__.py": [1],  # excluded facade
                "tests/test_x.py": [1],  # excluded noise
            },
            edges=[
                {"source": "a.py", "target": "b.py"},
                {"source": "b.py", "target": "c.py"},
            ],
        )
        m = compute_metrics(g, "repo")
        svg = diagram.build_svg(m, repo_name="repo")
        assert svg.startswith("<svg")  # valid standalone svg root
        assert svg.count('class="node"') == 3
        assert svg.count("<line") == 2  # two internal edges
        # each module depth-coloured from the traffic-light palette
        assert svg.count("#f87171") >= 3  # shallow red present


# --- integration with the real parser -----------------------------------------
class TestIntegrationWithParser:
    def test_scan_fixture_produces_production_only_metrics(self, repo_root: Path):
        from parser import scan_codebase

        g = scan_codebase(repo_root / "parser" / "tests" / "fixtures" / "sample_pkg")
        m = compute_metrics(g, "sample_pkg")
        ids = [r["id"] for r in m["modules"]]
        assert set(ids) == {"core.py", "main.py", "utils.py"}  # __init__ excluded
        by_pair = {(e["source"], e["target"]) for e in m["aggregatedEdges"]}
        assert by_pair == {("main.py", "core.py"), ("main.py", "utils.py")}


# --- repo-root discovery (skill portability, 2026-09-05) ----------------------
class TestFindRepoRoot:
    """analyze._find_repo_root: env override → walk-up → sibling deep-module-mapper/."""

    @staticmethod
    def _mk_repo(root: Path) -> Path:
        (root / "parser").mkdir(parents=True)
        (root / "parser" / "_scanner.py").write_text("# stub", encoding="utf-8")
        return root

    def test_walk_up_finds_owning_repo(self, tmp_path):
        repo = self._mk_repo(tmp_path / "repo")
        start = repo / ".claude" / "skills" / "deep-module-review" / "scripts"
        start.mkdir(parents=True)
        assert analyze._find_repo_root(start) == repo

    def test_sibling_deep_module_mapper_resolves(self, tmp_path):
        repo = self._mk_repo(tmp_path / "deep-module-mapper")
        start = tmp_path / ".claude" / "skills" / "deep-module-review" / "scripts"
        start.mkdir(parents=True)
        assert analyze._find_repo_root(start) == repo

    def test_env_override_wins_over_walk_up(self, tmp_path, monkeypatch):
        env_repo = self._mk_repo(tmp_path / "env-repo")
        walk_repo = self._mk_repo(tmp_path / "walk" / "repo")
        start = walk_repo / "scripts"
        start.mkdir(parents=True)
        monkeypatch.setenv("DEEP_MODULE_MAPPER_ROOT", str(env_repo))
        assert analyze._find_repo_root(start) == env_repo

    def test_env_override_must_own_parser(self, tmp_path, monkeypatch):
        self._mk_repo(tmp_path / "repo")
        start = tmp_path / "repo" / "scripts"
        start.mkdir(parents=True)
        monkeypatch.setenv("DEEP_MODULE_MAPPER_ROOT", str(tmp_path / "nonexistent"))
        assert analyze._find_repo_root(start) == tmp_path / "repo"  # falls through

    def test_missing_everywhere_raises(self, tmp_path):
        start = tmp_path / "scripts"
        start.mkdir()
        with pytest.raises(RuntimeError, match="DEEP_MODULE_MAPPER_ROOT"):
            analyze._find_repo_root(start)
