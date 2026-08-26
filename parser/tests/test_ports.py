"""Unit tests for port extraction (_ports)."""

import ast
from pathlib import Path

from parser import _ports

CORE = Path(__file__).parent / "fixtures" / "sample_pkg" / "core.py"
INIT = Path(__file__).parent / "fixtures" / "sample_pkg" / "__init__.py"


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_core_ports_are_public_only():
    result = _ports.extract_ports(_tree(CORE))
    names = {p.name for p in result.ports}
    assert {"save_user", "User", "no_return_annotation"} <= names
    assert "_private_helper" not in names


def test_no_return_annotation_does_not_crash():
    # F2: functions without a return annotation must not crash signature building.
    by_name = {p.name: p for p in _ports.extract_ports(_tree(CORE)).ports}
    assert by_name["no_return_annotation"].signature == "(x)"


def test_save_user_signature_and_params():
    by_name = {p.name: p for p in _ports.extract_ports(_tree(CORE)).ports}
    port = by_name["save_user"]
    assert port.params == ["name", "email", "active"]
    # D12: signature carries names + defaults (no type annotations); types are in params only
    assert port.signature == "(name, email, *, active=True) -> User"


def test_class_port_docstring_first_sentence():
    by_name = {p.name: p for p in _ports.extract_ports(_tree(CORE)).ports}
    assert by_name["User"].kind == "class"
    assert by_name["User"].docstring == "A user account."


def test_all_exports():
    result = _ports.extract_ports(_tree(INIT))
    exports = [(p.name, p.kind) for p in result.ports if p.kind == "export"]
    assert exports == [("save_user", "export"), ("User", "export"), ("SOME_CONSTANT", "export")]
