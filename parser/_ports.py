"""Port extraction: module-level public functions, classes and ``__all__`` exports.

Only module-level public symbols are ports (D2).  Public methods of a public
class are *not* listed as separate ports (F16): the class port carries them.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from ._schema import Port


@dataclass
class ExtractedPorts:
    ports: list[Port] = field(default_factory=list)
    exported_names: list[str] = field(default_factory=list)


def _param_names(args: ast.arguments) -> list[str]:
    """Parameter names in declaration order, ignoring defaults/annotations."""
    names: list[str] = []
    for a in args.posonlyargs:
        names.append(a.arg)
    for a in args.args:
        names.append(a.arg)
    if args.vararg is not None:
        names.append(args.vararg.arg)
    for a in args.kwonlyargs:
        names.append(a.arg)
    if args.kwarg is not None:
        names.append(args.kwarg.arg)
    return names


def _unparse_type(node: ast.AST) -> str:
    """Unwrap Subscript and string annotations (F18) for signatures."""
    while isinstance(node, ast.Subscript):
        node = node.value
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ast.unparse(node)


def _args_signature(args: ast.arguments) -> str:
    """Render parameter names + defaults + varargs, WITHOUT type annotations.

    D12: signature is a compact form like ``(name, email, *, active=True)``;
    typed parameter names are carried separately in ``Port.params``.
    """
    pieces: list[str] = []
    positional = list(args.posonlyargs) + list(args.args)
    n_defaults = len(args.defaults)
    offset = len(positional) - n_defaults
    for i, a in enumerate(positional):
        text = a.arg
        if i >= offset:
            default = args.defaults[i - offset]
            if default is not None:
                text += "=" + ast.unparse(default)
        pieces.append(text)
    if args.posonlyargs:
        pieces.insert(len(args.posonlyargs), "/")
    if args.vararg is not None:
        pieces.append("*" + args.vararg.arg)
    elif args.kwonlyargs:
        pieces.append("*")
    for a, default in zip(args.kwonlyargs, args.kw_defaults):
        text = a.arg
        if default is not None:
            text += "=" + ast.unparse(default)
        pieces.append(text)
    if args.kwarg is not None:
        pieces.append("**" + args.kwarg.arg)
    return "(" + ", ".join(pieces) + ")"


def _function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    sig = _args_signature(node.args)
    # F2: returns is None for most functions; must not crash.
    if node.returns is not None:
        sig += " -> " + _unparse_type(node.returns)
    return sig


def _class_signature(node: ast.ClassDef) -> str:
    if not node.bases:
        return node.name
    bases = ", ".join(_unparse_type(b) for b in node.bases)
    return f"{node.name}({bases})"


def _first_sentence(docstring: str | None) -> str | None:
    if not docstring:
        return None
    docstring = docstring.strip()
    for sep in (". ", ".\n", "\n"):
        idx = docstring.find(sep)
        if idx != -1:
            return docstring[: idx + 1].strip()
    return docstring


def extract_ports(tree: ast.AST) -> ExtractedPorts:
    """Extract public ports from a parsed module (top-level statements only)."""
    result = ExtractedPorts()

    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and not stmt.name.startswith("_"):
            result.ports.append(
                Port(
                    kind="function",
                    name=stmt.name,
                    line=stmt.lineno,
                    signature=_function_signature(stmt),
                    params=_param_names(stmt.args),
                    docstring=_first_sentence(ast.get_docstring(stmt)),
                )
            )
        elif isinstance(stmt, ast.ClassDef) and not stmt.name.startswith("_"):
            result.ports.append(
                Port(
                    kind="class",
                    name=stmt.name,
                    line=stmt.lineno,
                    signature=_class_signature(stmt),
                    params=[],
                    docstring=_first_sentence(ast.get_docstring(stmt)),
                )
            )
        elif _is_all_assignment(stmt):
            for el in stmt.value.elts:
                if isinstance(el, ast.Constant) and isinstance(el.value, str):
                    result.exported_names.append(el.value)
                    result.ports.append(
                        Port(
                            kind="export",
                            name=el.value,
                            line=el.lineno,
                            signature="",
                            params=[],
                            docstring=None,
                        )
                    )
    return result


def _is_all_assignment(stmt: ast.AST) -> bool:
    if not isinstance(stmt, ast.Assign) or not isinstance(stmt.value, (ast.List, ast.Tuple)):
        return False
    return any(isinstance(t, ast.Name) and t.id == "__all__" for t in stmt.targets)
