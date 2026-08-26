"""Unit tests for diagnostics (_diagnostics)."""

import ast
from pathlib import Path

from parser import _diagnostics
from parser._schema import Diagnostic

MAIN = Path(__file__).parent / "fixtures" / "sample_pkg" / "main.py"


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_dynamic_import_detected_non_literal():
    collector = _diagnostics.Collector()
    _diagnostics.collect_dynamic_imports(_tree(MAIN), "sample_pkg/main.py", collector)
    items = collector.finalize()
    assert len(items) == 1
    assert items[0].kind == "dynamic_import"
    assert "non-literal" in items[0].message


def test_dynamic_import_literal_message():
    tree = ast.parse('def f():\n    return __import__("os")\n')
    collector = _diagnostics.Collector()
    _diagnostics.collect_dynamic_imports(tree, "m.py", collector)
    items = collector.finalize()
    assert items[0].message == "dynamic import of 'os'"


def test_dedup_by_kind_module_line():
    collector = _diagnostics.Collector()
    collector.add(Diagnostic("unresolved_symbol", "m.py", 5, "first"))
    collector.add(Diagnostic("unresolved_symbol", "m.py", 5, "duplicate"))
    collector.add(Diagnostic("unresolved_symbol", "m.py", 7, "later"))
    items = collector.finalize()
    assert [(d.line, d.message) for d in items] == [(5, "first"), (7, "later")]


def test_sort_by_module_then_line():
    collector = _diagnostics.Collector()
    collector.add(Diagnostic("unresolved_symbol", "b.py", 1, "b"))
    collector.add(Diagnostic("unresolved_symbol", "a.py", 2, "a2"))
    collector.add(Diagnostic("unresolved_symbol", "a.py", 1, "a1"))
    items = collector.finalize()
    assert [(d.moduleId, d.line) for d in items] == [("a.py", 1), ("a.py", 2), ("b.py", 1)]
