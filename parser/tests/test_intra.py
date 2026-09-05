"""Unit tests for the v2 ``intra`` extraction (#24 §17.1).

Covers: function-level extraction, class-as-single-node, callback references,
top-level calls, cross-module exclusion, shadowing disambiguation (locals /
params / attributes / imports / builtins), attribution rules (nested def,
lambda, conditional def, duplicate def) and schema-shape consistency.
"""

from __future__ import annotations

import ast

from parser._diagnostics import Collector
from parser._edges import collect_imports
from parser._intra import MODULE_PSEUDO, extract_intra


def intra(source: str, module_id: str = "m.py") -> tuple[dict, list[dict]]:
    """Parse ``source`` and return (intra entry, diagnostics as dicts)."""
    tree = ast.parse(source)
    collector = Collector()
    entry = extract_intra(tree, collect_imports(tree), module_id, collector)
    return entry, [d.to_dict() for d in collector.finalize()]


def calls_of(entry: dict) -> set[tuple[str, str]]:
    return {(c["from"], c["to"]) for c in entry["calls"]}


def funcs_of(entry: dict) -> list[str]:
    return [f["name"] for f in entry["funcs"]]


# ---- extraction ---------------------------------------------------------------

class TestExtraction:
    def test_function_nodes_and_direct_call(self):
        entry, _ = intra(
            "def a():\n    b()\n\ndef b():\n    pass\n"
        )
        assert funcs_of(entry) == ["a", "b"]
        assert calls_of(entry) == {("a", "b")}
        assert entry["calls"][0]["line"] == 2

    def test_private_and_async_defs_are_nodes(self):
        entry, _ = intra(
            "async def _hidden():\n    pass\n"
        )
        assert funcs_of(entry) == ["_hidden"]

    def test_class_is_single_node_methods_not_expanded(self):
        entry, _ = intra(
            "def helper():\n    pass\n\n"
            "class Widget:\n"
            "    def __init__(self):\n        helper()\n"
            "    def render(self):\n        helper()\n"
        )
        assert funcs_of(entry) == ["helper", "Widget"]
        # both method bodies attribute to the class node
        assert calls_of(entry) == {("Widget", "helper")}

    def test_class_method_calling_own_method_attributes_to_class(self):
        entry, _ = intra(
            "class Widget:\n"
            "    def a(self):\n        self.b()\n"
            "    def b(self):\n        pass\n"
        )
        # b is not a node (methods are not expanded), and self.b() is an
        # attribute call -> no edge at all
        assert funcs_of(entry) == ["Widget"]
        assert entry["calls"] == []

    def test_callback_reference_makes_edge(self):
        entry, _ = intra(
            "def cmp(a, b):\n    pass\n\n"
            "def run(xs):\n    return sorted(xs, key=cmp)\n"
        )
        assert calls_of(entry) == {("run", "cmp")}

    def test_keyword_and_starred_callback(self):
        entry, _ = intra(
            "def f():\n    pass\n"
            "def g():\n    pass\n"
            "def run(xs):\n"
            "    return sorted(xs, key=f), sum(xs, start=g(0))\n"
        )
        pairs = calls_of(entry)
        assert ("run", "f") in pairs  # key=f callback
        assert ("run", "g") in pairs  # direct call g(0)

    def test_forward_reference_resolves(self):
        entry, _ = intra(
            "def a():\n    b()\n\ndef b():\n    pass\n"
        )
        assert calls_of(entry) == {("a", "b")}

    def test_top_level_call_gets_module_pseudo_host(self):
        entry, _ = intra(
            "def main():\n    pass\n\nmain()\n"
        )
        assert funcs_of(entry) == ["main", MODULE_PSEUDO]
        assert calls_of(entry) == {(MODULE_PSEUDO, "main")}

    def test_no_top_level_calls_no_pseudo_node(self):
        entry, _ = intra("def main():\n    pass\n")
        assert funcs_of(entry) == ["main"]

    def test_cross_module_calls_not_captured(self):
        entry, _ = intra(
            "from utils import fmt\n\n"
            "def run():\n    return fmt('x')\n"
        )
        assert funcs_of(entry) == ["run"]
        assert entry["calls"] == []

    def test_self_recursion_not_an_edge(self):
        entry, _ = intra("def fact(n):\n    return fact(n - 1)\n")
        assert entry["calls"] == []

    def test_calls_sorted_and_deduped_by_line(self):
        entry, _ = intra(
            "def b():\n    pass\n"
            "def a():\n    b(); b(); b()\n"
        )
        assert entry["calls"] == [{"from": "a", "to": "b", "line": 4}]


# ---- shadowing disambiguation (review F2) ---------------------------------------

class TestShadowing:
    def test_local_variable_same_name_no_edge(self):
        entry, _ = intra(
            "def render(x):\n    pass\n\n"
            "def handler():\n    render = get_render()\n    render()\n"
        )
        assert entry["calls"] == []

    def test_parameter_same_name_no_edge(self):
        entry, _ = intra(
            "def f(x):\n    pass\n\n"
            "def g(f):\n    f()\n"
        )
        assert entry["calls"] == []

    def test_attribute_call_never_an_edge(self):
        entry, _ = intra(
            "def write_text(t):\n    pass\n\n"
            "def save(out, t):\n    out.write_text(t)\n"
        )
        assert entry["calls"] == []

    def test_import_binding_shadows_module_def(self):
        entry, _ = intra(
            "from fmt import render\n\n"
            "def render(x):\n    pass\n\n"
            "def run():\n    render(1)\n"
        )
        assert funcs_of(entry) == ["render", "run"]
        assert entry["calls"] == []

    def test_builtin_name_shadows_module_def(self):
        entry, _ = intra(
            "def id(x):\n    pass\n\n"
            "def run(x):\n    return id(x)\n"
        )
        assert entry["calls"] == []

    def test_comprehension_target_shadows(self):
        entry, _ = intra(
            "def f(x):\n    pass\n\n"
            "def run(data):\n    return [f(x) for x in data]\n"
        )
        # the comprehension target is x, f is the module def -> real edge
        assert calls_of(entry) == {("run", "f")}

    def test_enclosing_function_binding_shadows_nested_scope(self):
        entry, _ = intra(
            "def helper():\n    pass\n\n"
            "def outer():\n    helper = 3\n"
            "    def inner():\n        return helper()\n"
            "    return inner\n"
        )
        assert entry["calls"] == []

    def test_class_body_assign_shadows_for_body_calls(self):
        entry, _ = intra(
            "def make():\n    pass\n\n"
            "class A:\n    make = staticmethod(make)\n    other = make()\n"
        )
        assert entry["calls"] == []


# ---- attribution rules (review F6) ----------------------------------------------

class TestAttribution:
    def test_nested_def_merges_into_host(self):
        entry, _ = intra(
            "def helper():\n    pass\n\n"
            "def outer():\n"
            "    def inner():\n        helper()\n"
            "    inner()\n"
        )
        assert funcs_of(entry) == ["helper", "outer"]  # inner is not a node
        assert calls_of(entry) == {("outer", "helper")}

    def test_lambda_calls_belong_to_host(self):
        entry, _ = intra(
            "def transform(x):\n    pass\n\n"
            "def run(xs):\n    return list(map(lambda v: transform(v), xs))\n"
        )
        assert calls_of(entry) == {("run", "transform")}

    def test_conditional_def_still_a_node(self):
        entry, _ = intra(
            "DEBUG = True\n\n"
            "if DEBUG:\n"
            "    def setup():\n        pass\n"
            "else:\n"
            "    def setup():\n        pass\n\n"
            "def run():\n    setup()\n"
        )
        assert funcs_of(entry) == ["setup", "run"]
        assert calls_of(entry) == {("run", "setup")}

    def test_duplicate_def_keeps_first_and_reports(self):
        entry, diags = intra(
            "def f():\n    pass\n\n"
            "def f():\n    pass\n\n"
            "def run():\n    f()\n"
        )
        assert funcs_of(entry) == ["f", "run"]
        dups = [d for d in diags if d["kind"] == "duplicate_def"]
        assert len(dups) == 1
        assert dups[0]["line"] == 4  # the second definition's line
        assert calls_of(entry) == {("run", "f")}

    def test_decorator_evaluated_in_enclosing_scope(self):
        entry, _ = intra(
            "def deco(fn):\n    return fn\n\n"
            "def helper():\n    pass\n\n"
            "@deco(helper)\n"
            "def wrapped():\n    pass\n"
        )
        # @deco(helper) sits at module level -> host is <module>
        assert calls_of(entry) == {(MODULE_PSEUDO, "helper"), (MODULE_PSEUDO, "deco")}

    def test_default_arg_call_evaluated_in_enclosing_scope(self):
        entry, _ = intra(
            "def helper():\n    pass\n\n"
            "def run(x=helper()):\n    pass\n"
        )
        assert calls_of(entry) == {(MODULE_PSEUDO, "helper")}


# ---- scan integration ------------------------------------------------------------

class TestScanIntegration:
    def test_sample_pkg_intra_shape(self):
        from pathlib import Path
        from parser import scan_codebase

        fixture = Path(__file__).parent / "fixtures"
        graph = scan_codebase(fixture)
        intra = graph["intra"]
        assert set(intra.keys()) == {m["id"] for m in graph["modules"]}

        core = intra["sample_pkg/core.py"]
        names = funcs_of(core)
        assert "User" in names and "save_user" in names and "_private_helper" in names
        pairs = calls_of(core)
        assert ("save_user", "User") in pairs  # real constructor call

        # fmt('bob') is an import (shadowed); save_user call is cross-module
        main = intra["sample_pkg/main.py"]
        assert ("main", "save_user") not in calls_of(main)
        assert ("main", "Admin") in calls_of(main)  # local class instantiation
        assert not any(f["name"] == MODULE_PSEUDO for f in main["funcs"])

    def test_intra_survives_parse_errors(self):
        from pathlib import Path
        from parser import scan_codebase

        fixtures = Path(__file__).parent / "fixtures"
        graph = scan_codebase(fixtures)
        assert "broken_syntax.py" not in graph["intra"]
        assert "broken_syntax.py" not in {m["id"] for m in graph["modules"]}
