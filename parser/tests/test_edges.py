"""Unit tests for edge extraction internals (_edges)."""

import ast
from pathlib import Path

from parser import _edges, _external

FIXTURES = Path(__file__).parent / "fixtures"
MAIN = FIXTURES / "sample_pkg" / "main.py"
UTILS = FIXTURES / "sample_pkg" / "utils.py"
INIT = FIXTURES / "sample_pkg" / "__init__.py"


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _index() -> dict[str, str]:
    files = [
        Path("sample_pkg/__init__.py"),
        Path("sample_pkg/core.py"),
        Path("sample_pkg/utils.py"),
        Path("sample_pkg/main.py"),
    ]
    return _external.build_module_index(files, FIXTURES)


def test_collect_imports_from_main():
    imports = _edges.collect_imports(_tree(MAIN))
    got = {(i.kind, i.name, i.level) for i in imports}
    assert ("import", "json", 0) in got
    assert ("import", "requests", 0) in got
    assert ("from_import", "utils", 1) in got  # from . import utils
    assert ("from_import", "User", 1) in got
    assert ("from_import", "format_name", 1) in got


def test_from_import_submodule_binding_f17():
    # `from sample_pkg import core as core_mod` binds core as a module, not a port
    table = _edges.build_symbol_table(_edges.collect_imports(_tree(UTILS)), _index(), "sample_pkg")
    assert table["core_mod"] == {"kind": "module", "module": "sample_pkg.core"}


def test_relative_import_base_same_for_init_and_module():
    # Q6: __init__.py uses the same directory base as a regular module
    table = _edges.build_symbol_table(_edges.collect_imports(_tree(INIT)), _index(), "sample_pkg")
    assert table["User"] == {"kind": "symbol", "module": "sample_pkg.core", "port": "User"}


def test_collect_references_kinds():
    refs = _edges.collect_references(_tree(MAIN))
    kinds = {r.kind for r in refs}
    assert {"call", "inheritance", "annotation", "decorator"} <= kinds


def test_local_names_collected():
    locals_ = _edges.collect_local_names(_tree(MAIN))
    assert "admin" in locals_  # assigned in main()
    assert "u" in locals_  # parameter of annotate()


def test_module_defs_collected():
    defs = _edges.collect_module_defs(_tree(MAIN))
    assert "Admin" in defs
    assert "main" in defs
    assert "SOME_CONSTANT" not in defs  # not defined in main.py
