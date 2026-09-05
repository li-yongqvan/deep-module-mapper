"""Module-internal function-level call graphs (the v2 ``intra`` key, #24 §14).

Purely additive pass: never touches ``resolve_reference`` or any existing
extraction, so the 5 existing keys keep their content byte-for-byte (golden
tests in ``parser/tests/test_golden.py`` pin this).

Nodes  every module-level ``def``/``async def`` (public and private) plus one
       node per top-level class (V2-D6: a class is a single node, methods are
       not expanded).  Nested defs merge into their host; conditional defs are
       collected as usual.
Edges  ① calls to a same-module function/class inside a host body,
       ② calls in module top-level statements (host ``<module>`` -- the
          prototype dropped these, review F6 forbids repeating that),
       ③ callback references: a function name passed as a bare ``Name``
          argument (``sorted(key=f)``, §13.4-1).

Shadowing disambiguation (review F2, 宁缺勿幻): a name only becomes an edge
when it is *not bound* at the reference point -- module-level assignments,
import bindings and builtins shadow module defs, and any binding (parameter,
assignment, comprehension target) anywhere inside the enclosing function/class
subtree suppresses the edge.  Attribute calls (``obj.method()``) are never
edges even when the attribute name matches a module def.

Attribution (review F6): a nested def's calls belong to its host node; lambda
bodies belong to their enclosing host; class-method bodies belong to the class
node.  Duplicate module-level defs keep the first definition and emit a
``duplicate_def`` diagnostic instead of staying silent.
"""

from __future__ import annotations

import ast
import builtins
from collections import OrderedDict
from typing import Iterator

from ._diagnostics import Collector, Diagnostic
from ._edges import RawImport

MODULE_PSEUDO = "<module>"
_BUILTIN_NAMES = frozenset(dir(builtins))


def extract_intra(tree: ast.AST, imports: list[RawImport], module_id: str, collector: Collector) -> dict:
    """Return ``{"funcs": [{"name", "line"}], "calls": [{"from", "to", "line"}]}``."""
    visitor = _Visitor(
        _collect_def_nodes(tree),
        _import_bound_names(imports),
        _module_bound_names(tree),
        module_id,
        collector,
    )
    visitor.visit(tree)
    return visitor.result()


def _collect_def_nodes(tree: ast.AST) -> "OrderedDict[str, int]":
    """All module-level def/class nodes in document order (first def wins).

    Collected *before* the traversal so forward references (``def a(): b()``
    with ``b`` defined later) still resolve; the nesting rule matches the
    visitor's: defs inside functions/classes are merged hosts, not nodes.
    """
    names: "OrderedDict[str, int]" = OrderedDict()

    def walk_stmts(stmts: list[ast.stmt]) -> None:
        for stmt in stmts:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.setdefault(stmt.name, stmt.lineno)
                continue  # nested defs merge into their host (F6)
            walk_stmts(getattr(stmt, "body", []))
            walk_stmts(getattr(stmt, "orelse", []))
            walk_stmts(getattr(stmt, "finalbody", []))
            if isinstance(stmt, ast.Match):
                for case in stmt.cases:
                    walk_stmts(case.body)

    if isinstance(tree, ast.Module):
        walk_stmts(tree.body)
    return names


def _import_bound_names(imports: list[RawImport]) -> frozenset[str]:
    """Names bound by import statements (they shadow same-named module defs).

    ``import a.b`` binds ``a``, so the root segment is included, mirroring
    ``build_symbol_table``.  ``from x import *`` binds unknowable names and is
    ignored (same stance as the symbol table).
    """
    bound: set[str] = set()
    for imp in imports:
        if imp.kind == "import":
            alias = imp.alias or imp.name
            bound.add(alias.split(".")[0])
            bound.add(alias)
        elif imp.name != "*":
            bound.add(imp.alias or imp.name)
    return frozenset(bound)


def _iter_module_scope(node: ast.AST) -> Iterator[ast.AST]:
    """Yield ``node`` and its descendants without entering def/class/lambda scopes."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return
    yield node
    for child in ast.iter_child_nodes(node):
        yield from _iter_module_scope(child)


def _module_bound_names(tree: ast.AST) -> frozenset[str]:
    """Assignment / loop / with targets bound directly at module level.

    Comprehension targets are included: they do not leak, but shadowing them
    is the conservative (宁缺勿幻) direction.
    """
    bound: set[str] = set()
    for node in _iter_module_scope(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.add(node.id)
    return frozenset(bound)


def _bindings(node: ast.AST) -> frozenset[str]:
    """Every name bound anywhere in ``node``'s subtree (params, stores, comps)."""
    bound: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.arg):
            bound.add(sub.arg)
        elif isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
            bound.add(sub.id)
    return frozenset(bound)


def _arg_names(args: ast.arguments) -> list[str]:
    names = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]
    if args.vararg:
        names.append(args.vararg.arg)
    if args.kwarg:
        names.append(args.kwarg.arg)
    return names


class _Visitor(ast.NodeVisitor):
    """Depth-first visitor carrying a (host, shadow-bindings) stack.

    ``host`` is the intra node name calls attribute to; ``None`` marks a
    transparent scope (methods, nested defs, lambdas, merged classes) whose
    calls attribute to the nearest enclosing host.
    """

    def __init__(self, node_names: "OrderedDict[str, int]", import_bound: frozenset[str],
                 module_bound: frozenset[str], module_id: str, collector: Collector) -> None:
        self._funcs = node_names  # complete up front -> forward references resolve
        self._entered: set[str] = set()
        self._import_bound = import_bound
        self._module_bound = module_bound
        self._module_id = module_id
        self._collector = collector
        self._stack: list[tuple[str | None, frozenset[str]]] = []
        self._calls: set[tuple[str, str, int]] = set()

    # ---- result ---------------------------------------------------------------

    def result(self) -> dict:
        funcs = [{"name": name, "line": line} for name, line in self._funcs.items()]
        if any(call[0] == MODULE_PSEUDO for call in self._calls):
            funcs.append({"name": MODULE_PSEUDO, "line": 0})
        calls = [
            {"from": src, "to": dst, "line": line}
            for src, dst, line in sorted(self._calls)
        ]
        return {"funcs": funcs, "calls": calls}

    # ---- scope handling ---------------------------------------------------------

    def visit_Module(self, node: ast.Module) -> None:
        for stmt in node.body:
            self.visit(stmt)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_def(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_def(node)

    def _visit_def(self, node) -> None:
        # decorators / defaults / annotations evaluate in the ENCLOSING scope
        for expr in [*node.decorator_list, *node.args.defaults,
                     *(d for d in node.args.kw_defaults if d is not None)]:
            self.visit(expr)
        merged = bool(self._stack)  # inside a function or class -> not a node (F6)
        self._enter(None if merged else node.name, node.lineno, _bindings(node))
        for stmt in node.body:
            self.visit(stmt)
        self._leave()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for expr in [*node.decorator_list, *node.bases, *node.keywords]:
            self.visit(expr)
        merged = bool(self._stack)
        self._enter(None if merged else node.name, node.lineno, _bindings(node))
        for stmt in node.body:
            self.visit(stmt)
        self._leave()

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._enter(None, 0, frozenset(_arg_names(node.args)))
        self.visit(node.body)
        self._leave()

    def _enter(self, host: str | None, line: int, bindings: frozenset[str]) -> None:
        if host is not None:
            if host in self._entered:
                self._collector.add(Diagnostic(
                    "duplicate_def", self._module_id, line,
                    f"duplicate module-level def {host!r}; intra graph keeps the first "
                    f"definition (line {self._funcs[host]})",
                ))
                host = None  # calls from both bodies attribute to the first definition
            else:
                self._entered.add(host)
        self._stack.append((host, bindings))

    def _leave(self) -> None:
        self._stack.pop()

    def _shadowed(self, name: str) -> bool:
        if name in self._import_bound or name in self._module_bound or name in _BUILTIN_NAMES:
            return True
        return any(name in bindings for _host, bindings in self._stack)

    # ---- edges ------------------------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        candidates: list[str] = []
        if isinstance(node.func, ast.Name):
            candidates.append(node.func.id)  # edge ① direct call
        for arg in node.args:
            target = arg.value if isinstance(arg, ast.Starred) else arg
            if isinstance(target, ast.Name):
                candidates.append(target.id)  # edge ③ callback reference
        for kw in node.keywords:
            if isinstance(kw.value, ast.Name):
                candidates.append(kw.value.id)  # edge ③ keyword callback
        for name in candidates:
            self._record(name, node.lineno)
        self.generic_visit(node)

    def _record(self, name: str, line: int) -> None:
        if name not in self._funcs or self._shadowed(name):
            return
        host = self._current_host() or MODULE_PSEUDO
        if host == name:  # self-recursion: §14 edge ① says "other functions/classes"
            return
        self._calls.add((host, name, line))

    def _current_host(self) -> str | None:
        for host, _bindings in reversed(self._stack):
            if host is not None:
                return host
        return None
