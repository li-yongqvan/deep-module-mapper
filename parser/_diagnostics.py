"""Diagnostic collection, dedup and dynamic-import detection."""

from __future__ import annotations

import ast

from ._schema import Diagnostic


class Collector:
    """Collects diagnostics during a scan; finalize() dedups and sorts."""

    def __init__(self) -> None:
        self._items: list[Diagnostic] = []

    def add(self, diag: Diagnostic) -> None:
        self._items.append(diag)

    def finalize(self) -> list[Diagnostic]:
        # F19: dedup key (kind, moduleId, line); stable sort by (moduleId, line).
        seen: dict[tuple, Diagnostic] = {}
        for d in self._items:
            seen.setdefault((d.kind, d.moduleId, d.line), d)
        return sorted(seen.values(), key=lambda d: (d.moduleId, d.line))


def _root_name(expr: ast.AST) -> str | None:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return _root_name(expr.value)
    return None


def collect_dynamic_imports(tree: ast.AST, module_id: str, collector: Collector) -> None:
    """Detect ``__import__`` and ``importlib.import_module`` calls (D19/Q5)."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "__import__":
            pass
        elif (
            isinstance(func, ast.Attribute)
            and func.attr in ("import_module",)
            and _root_name(func.value) == "importlib"
        ):
            pass
        else:
            continue
        collector.add(Diagnostic("dynamic_import", module_id, node.lineno, _dynamic_message(node)))


def _dynamic_message(node: ast.Call) -> str:
    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        return f"dynamic import of {node.args[0].value!r}"
    return "dynamic import of non-literal target"
