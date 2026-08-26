"""Dependency edge extraction: imports and symbol references.

Two-pass contract (F20): pass 1 collects ``RawImport`` / ``RawReference`` from
the AST; pass 2 resolves them against the global module index and per-module
symbol tables, producing ``Edge`` objects, external-module candidates and
unresolved-symbol diagnostics.
"""

from __future__ import annotations

import ast
import builtins
from dataclasses import dataclass, field

from ._external import classify
from ._schema import Edge

_BUILTIN_NAMES = frozenset(dir(builtins))


# ---- pass-1 intermediate structures (F20) --------------------------------


@dataclass
class RawImport:
    kind: str  # "import" | "from_import"
    module: str | None  # ImportFrom.module (None for plain import / `from . import x`)
    level: int  # relative import level; 0 = absolute
    name: str  # imported symbol / module name
    alias: str | None
    line: int


@dataclass
class RawReference:
    name: str
    kind: str  # call | inheritance | annotation | decorator
    base: str | None  # Attribute root name (e.g. "utils" in utils.fmt()); None for Name
    line: int


@dataclass
class Resolution:
    """Outcome of resolving one import/reference against the index."""

    edge: Edge | None = None
    external: str | None = None  # external module id to record
    unresolved: tuple[str, int] | None = None  # (name, line)


# ---- pass 1: collection ---------------------------------------------------


def collect_imports(tree: ast.AST) -> list[RawImport]:
    imports: list[RawImport] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(RawImport("import", None, 0, alias.name, alias.asname, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.append(
                    RawImport("from_import", node.module, node.level, alias.name, alias.asname, node.lineno)
                )
    return imports


def collect_references(tree: ast.AST) -> list[RawReference]:
    """Collect call / inheritance / annotation / decorator references."""
    refs: list[RawReference] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            _add_ref(refs, node.func, "call", node.lineno)
        elif isinstance(node, ast.ClassDef):
            for base in node.bases:
                _add_ref(refs, base, "inheritance", base.lineno)
            for deco in node.decorator_list:
                _add_ref(refs, deco, "decorator", deco.lineno)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is not None:
                _add_ref(refs, node.returns, "annotation", node.returns.lineno)
            for deco in node.decorator_list:
                _add_ref(refs, deco, "decorator", deco.lineno)
        elif isinstance(node, ast.AnnAssign) and node.annotation is not None:
            _add_ref(refs, node.annotation, "annotation", node.annotation.lineno)
        elif isinstance(node, ast.arg) and node.annotation is not None:
            _add_ref(refs, node.annotation, "annotation", node.annotation.lineno)
    return refs


def _add_ref(refs: list[RawReference], expr: ast.AST, kind: str, line: int) -> None:
    expr = _strip_annotation(expr)
    name, base = _func_name(expr)
    if name is not None:
        refs.append(RawReference(name=name, kind=kind, base=base, line=line))


def _strip_annotation(node: ast.AST) -> ast.AST:
    """Unwrap Subscript and string annotations (F18) before name lookup."""
    while isinstance(node, ast.Subscript):
        node = node.value
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            return ast.parse(node.value, mode="eval").body
        except SyntaxError:
            return node
    return node


def _func_name(expr: ast.AST) -> tuple[str | None, str | None]:
    """Return (name, base) for Name / Attribute expressions."""
    if isinstance(expr, ast.Name):
        return expr.id, None
    if isinstance(expr, ast.Attribute):
        return expr.attr, _base_name(expr.value)
    return None, None


def _base_name(expr: ast.AST) -> str | None:
    """Root receiver name of an expression, following attribute chains and calls.

    ``name.strip().title()`` and ``super().__init__()`` both resolve to their
    root receiver so method chains on locals/builtins are skipped, not flagged.
    """
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return _base_name(expr.value)
    if isinstance(expr, ast.Call):
        return _base_name(expr.func)
    return None


def collect_local_names(tree: ast.AST) -> frozenset[str]:
    """All names bound inside any function body (params, assignments, loop vars)."""
    locals_: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for sub in ast.walk(node):
            if sub is node:
                continue
            if isinstance(sub, ast.arg):
                locals_.add(sub.arg)
            elif isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                locals_.add(sub.id)
    return frozenset(locals_)


def collect_module_defs(tree: ast.AST) -> frozenset[str]:
    """Module-level defined names (functions, classes, assignments)."""
    defs: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs.add(stmt.name)
        elif isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            for t in targets:
                if isinstance(t, ast.Name):
                    defs.add(t.id)
    return frozenset(defs)


# ---- symbol table ---------------------------------------------------------


def _resolve_module(module: str | None, level: int, dir_dotted: str) -> str | None:
    """Resolve a (possibly relative) module reference to a dotted name.

    Q6: the base for a relative import is the current file's *directory*,
    independent of whether the repo root is a package. ``sample_pkg/core.py``
    and ``sample_pkg/__init__.py`` both use ``sample_pkg`` as their base.
    """
    if level == 0:
        return module
    parts = dir_dotted.split(".") if dir_dotted else []
    if level == 1:
        base = dir_dotted
    else:
        base = ".".join(parts[: -(level - 1)])
    if module:
        return f"{base}.{module}" if base else module
    return base


def build_symbol_table(
    imports: list[RawImport],
    module_index: dict[str, str],
    dir_dotted: str,
) -> dict[str, dict]:
    """Map bound names to module/symbol entries.

    Entry shapes:
      {"kind": "module", "module": dotted}      # import a.b / from pkg import core (submodule)
      {"kind": "symbol", "module": dotted, "port": name}  # from pkg.core import User
    """
    table: dict[str, dict] = {}
    for imp in imports:
        if imp.kind == "import":
            alias = imp.alias or imp.name
            table[alias] = {"kind": "module", "module": imp.name}
            root = imp.name.split(".")[0]
            if root != alias:
                table.setdefault(root, {"kind": "module", "module": imp.name})
            continue

        target_module = _resolve_module(imp.module, imp.level, dir_dotted)
        if target_module is None:
            continue
        if imp.name == "*":
            continue
        alias = imp.alias or imp.name
        # F17: `from pkg import core` binds `core` as a submodule, not a port.
        sub = f"{target_module}.{imp.name}" if target_module else imp.name
        if sub in module_index:
            table[alias] = {"kind": "module", "module": sub}
        else:
            table[alias] = {"kind": "symbol", "module": target_module, "port": imp.name}
    return table


# ---- pass 2: resolution ---------------------------------------------------


def resolve_import(
    imp: RawImport,
    module_index: dict[str, str],
    source_id: str,
    dir_dotted: str,
    module_ports: dict[str, set[str]],
) -> Resolution:
    if imp.kind == "import":
        return _resolve_import_stmt(imp, module_index, source_id)
    return _resolve_from_import(imp, module_index, source_id, dir_dotted, module_ports)


def _resolve_import_stmt(imp: RawImport, module_index: dict[str, str], source_id: str) -> Resolution:
    kind, mod_id = classify(imp.name, module_index)
    if kind == "local":
        return Resolution(edge=Edge(source_id, mod_id, None, "import", [{"line": imp.line}]))
    if kind == "stdlib":
        return Resolution()  # D17: stdlib is ignored
    return Resolution(
        edge=Edge(source_id, imp.name, None, "import", [{"line": imp.line}]),
        external=imp.name,
    )


def _resolve_from_import(
    imp: RawImport,
    module_index: dict[str, str],
    source_id: str,
    dir_dotted: str,
    module_ports: dict[str, set[str]],
) -> Resolution:
    target_module = _resolve_module(imp.module, imp.level, dir_dotted)
    if target_module is None:
        return Resolution(unresolved=(imp.name, imp.line))

    # F17: submodule wins over __init__ port: `from pkg import core` -> pkg/core.py
    sub = f"{target_module}.{imp.name}" if target_module else imp.name
    if sub in module_index:
        return Resolution(edge=Edge(source_id, module_index[sub], None, "from_import", [{"line": imp.line}]))

    if target_module in module_index:
        mod_id = module_index[target_module]
        port = imp.name if imp.name in module_ports.get(mod_id, set()) else None
        return Resolution(edge=Edge(source_id, mod_id, port, "from_import", [{"line": imp.line}]))

    kind, mod_id = classify(target_module, module_index)
    if kind == "stdlib":
        return Resolution()
    if kind == "third_party":
        return Resolution(
            edge=Edge(source_id, target_module, imp.name, "from_import", [{"line": imp.line}]),
            external=target_module,
        )
    return Resolution(unresolved=(imp.name, imp.line))


def resolve_reference(
    ref: RawReference,
    symbol_table: dict[str, dict],
    module_index: dict[str, str],
    source_id: str,
    module_defs: frozenset[str],
    locals_: frozenset[str],
    module_ports: dict[str, set[str]],
) -> Resolution:
    """Resolve a call/inheritance/annotation/decorator reference (F3/F4)."""
    name, base = ref.name, ref.base

    if base is not None:
        # Attribute target: obj.method(), @mod.deco(), obj.field: T
        if base in locals_ or base in module_defs:
            return Resolution()  # local var / param / self / member -> skip
        entry = symbol_table.get(base)
        if entry is not None:
            return _edge_from_entry(entry, name, ref.kind, source_id, module_index, ref.line, module_ports)
        if base in _BUILTIN_NAMES:
            return Resolution()
        return Resolution(unresolved=(f"{base}.{name}", ref.line))

    entry = symbol_table.get(name)
    if entry is not None:
        return _edge_from_entry(entry, None, ref.kind, source_id, module_index, ref.line, module_ports)
    if name in module_defs or name in locals_:
        return Resolution()  # module-internal reference, not a cross-module edge
    if name in _BUILTIN_NAMES:
        return Resolution()
    return Resolution(unresolved=(name, ref.line))


def _edge_from_entry(
    entry: dict,
    attr: str | None,
    kind: str,
    source_id: str,
    module_index: dict[str, str],
    line: int,
    module_ports: dict[str, set[str]],
) -> Resolution:
    target_module = entry["module"]
    if entry["kind"] == "symbol":
        attr = attr or entry["port"]

    kind_class, mod_id = classify(target_module, module_index)
    if kind_class == "stdlib":
        return Resolution()
    if kind_class == "third_party":
        return Resolution(
            edge=Edge(source_id, target_module, attr, kind, [{"line": line}]),
            external=target_module,
        )
    # local module
    if attr is None:
        return Resolution(edge=Edge(source_id, mod_id, None, kind, [{"line": line}]))
    port = attr if attr in module_ports.get(mod_id, set()) else None
    return Resolution(edge=Edge(source_id, mod_id, port, kind, [{"line": line}]))
