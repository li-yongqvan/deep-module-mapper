"""End-to-end tests for the public API scan_codebase."""

import json
from pathlib import Path

import pytest

from parser import scan_codebase

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def graph() -> dict:
    return scan_codebase(FIXTURES)


# ---- contract -------------------------------------------------------------


def test_five_top_level_keys(graph):
    assert set(graph.keys()) == {"modules", "ports", "edges", "externalModules", "diagnostics"}


def test_serializable(graph):
    json.dumps(graph)


# ---- modules --------------------------------------------------------------


def test_modules_exclude_venv(graph):
    ids = [m["id"] for m in graph["modules"]]
    assert "sample_pkg/core.py" in ids
    assert "venv/fake.py" not in ids  # F6 exclusion


def test_broken_syntax_not_a_module(graph):
    ids = [m["id"] for m in graph["modules"]]
    assert "broken_syntax.py" not in ids
    parse_errors = [d for d in graph["diagnostics"] if d["kind"] == "parse_error"]
    assert any(d["moduleId"] == "broken_syntax.py" for d in parse_errors)


def test_core_ports_present(graph):
    core = next(m for m in graph["modules"] if m["id"] == "sample_pkg/core.py")
    names = {p["name"] for p in core["ports"]}
    assert {"save_user", "User", "no_return_annotation"} <= names
    assert "_private_helper" not in names  # private excluded


# ---- ports ----------------------------------------------------------------


def test_flat_ports_carry_module_id(graph):
    by_name = {p["name"]: p for p in graph["ports"]}
    assert by_name["save_user"]["moduleId"] == "sample_pkg/core.py"


def test_init_all_exports(graph):
    # re-exported names (save_user, User) still appear as exports (Q4/F18)
    exports = [p for p in graph["ports"] if p["kind"] == "export"]
    names = {p["name"] for p in exports}
    assert {"save_user", "User", "SOME_CONSTANT"} <= names


# ---- edges ----------------------------------------------------------------


def test_call_edge_to_core(graph):
    edges = [
        e for e in graph["edges"]
        if e["kind"] == "call" and e["source"] == "sample_pkg/main.py" and e["target"] == "sample_pkg/core.py"
    ]
    assert any(e["targetPort"] == "save_user" for e in edges)


def test_inheritance_edge(graph):
    edges = [
        e for e in graph["edges"]
        if e["kind"] == "inheritance"
        and e["source"] == "sample_pkg/main.py"
        and e["target"] == "sample_pkg/core.py"
    ]
    assert any(e["targetPort"] == "User" for e in edges)


def test_decorator_edge(graph):
    edges = [
        e for e in graph["edges"]
        if e["kind"] == "decorator"
        and e["source"] == "sample_pkg/main.py"
        and e["target"] == "sample_pkg/utils.py"
    ]
    assert any(e["targetPort"] == "Formatter" for e in edges)


def test_annotation_edge(graph):
    edges = [
        e for e in graph["edges"]
        if e["kind"] == "annotation"
        and e["source"] == "sample_pkg/main.py"
        and e["target"] == "sample_pkg/core.py"
    ]
    assert any(e["targetPort"] == "User" for e in edges)


def test_import_and_from_import_edges(graph):
    kinds = {(e["kind"], e["source"], e["target"]) for e in graph["edges"]}
    assert ("import", "sample_pkg/main.py", "requests") in kinds
    assert ("from_import", "sample_pkg/main.py", "sample_pkg/utils.py") in kinds
    assert ("from_import", "sample_pkg/main.py", "sample_pkg/core.py") in kinds


def test_attribute_call_to_external(graph):
    edges = [
        e for e in graph["edges"]
        if e["kind"] == "call" and e["source"] == "sample_pkg/main.py" and e["target"] == "requests"
    ]
    assert any(e["targetPort"] == "get" for e in edges)


def test_utils_submodule_attribute_edge(graph):
    # utils.py: core_mod.save_user where core_mod binds the core submodule (F17/F4)
    edges = [
        e for e in graph["edges"]
        if e["source"] == "sample_pkg/utils.py"
        and e["target"] == "sample_pkg/core.py"
        and e["kind"] == "call"
    ]
    assert any(e["targetPort"] == "save_user" for e in edges)


# ---- external / diagnostics -----------------------------------------------


def test_external_modules(graph):
    names = {x["id"] for x in graph["externalModules"]}
    assert "requests" in names
    assert "json" not in names  # stdlib ignored (D17)


def test_dynamic_import_diagnostic(graph):
    dyn = [d for d in graph["diagnostics"] if d["kind"] == "dynamic_import"]
    assert dyn
    assert any("non-literal" in d["message"] for d in dyn)


def test_unresolved_symbol_diagnostics(graph):
    unres = [d for d in graph["diagnostics"] if d["kind"] == "unresolved_symbol"]
    messages = " | ".join(d["message"] for d in unres)
    assert "undefined_symbol" in messages
    assert "mystery_thing" in messages


def test_no_builtin_diagnostics(graph):
    # print/list/map/super must not become unresolved symbols (F3)
    unres = [d for d in graph["diagnostics"] if d["kind"] == "unresolved_symbol"]
    for d in unres:
        for builtin in ("print", "list", "map", "super", "len"):
            assert builtin not in d["message"]
