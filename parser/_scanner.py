"""Module discovery and two-pass traversal orchestration.

Public surface: ``scan_codebase``.  Everything else in the package is private
(D14/D15).
"""

from __future__ import annotations

import ast
import tokenize
import warnings
from pathlib import Path

from . import _diagnostics, _edges, _external, _intra, _ports
from ._external import EXCLUDED_DIRS, build_module_index
from ._schema import Diagnostic, Edge, ExternalModule, Graph, Module


def scan_codebase(root_path: Path, exclude_dirs: set[str] | None = None) -> dict:
    """Return a Graph dict: the 5 issue-#2 keys plus the v2 ``intra`` key (#24 §14).

    ``exclude_dirs`` (default None) adds extra directory names (matched at any
    depth) to the always-excluded ``EXCLUDED_DIRS`` set.  Backward compatible:
    not passing it behaves exactly as before (invariant 1, #24 design §7).
    """
    root = Path(root_path).resolve()
    files = _discover_files(root, exclude_dirs)
    module_index = build_module_index(files, root)

    graph = Graph()
    collector = _diagnostics.Collector()
    contexts: list[dict] = []

    # ---- pass 1: parse each file, extract ports + raw imports/references ----
    for rel in sorted(files):
        path = root / rel
        module_id = rel.as_posix()
        try:
            with tokenize.open(path) as fh:  # F5: encoding-safe read
                source = fh.read()
            # #28 C: the scanned code's own compile-time warnings (e.g. SyntaxWarning
            # for invalid escape sequences) must not leak into the caller's stderr.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tree = ast.parse(source)
        except (SyntaxError, ValueError, UnicodeDecodeError) as exc:
            collector.add(
                Diagnostic(
                    "parse_error", module_id, getattr(exc, "lineno", 0) or 0, _parse_error_message(exc)
                )
            )
            continue

        dir_dotted = _dir_dotted(rel)
        extracted = _ports.extract_ports(tree)
        graph.modules.append(Module(id=module_id, path=module_id, ports=extracted.ports))
        imports = _edges.collect_imports(tree)
        # v2 (#24 §14): module-internal call graph -- additive, feeds key 6 only.
        graph.intra[module_id] = _intra.extract_intra(tree, imports, module_id, collector)
        contexts.append(
            {
                "dir_dotted": dir_dotted,
                "tree": tree,
                "imports": imports,
                "refs": _edges.collect_references(tree),
                "locals": _edges.collect_local_names(tree),
            }
        )
        _diagnostics.collect_dynamic_imports(tree, module_id, collector)

    # ---- pass 2: resolve imports and references against the index ----
    module_ports = {m.id: {p.name for p in m.ports} for m in graph.modules}
    for i, ctx in enumerate(contexts):
        source_id = graph.modules[i].id
        symbol_table = _edges.build_symbol_table(ctx["imports"], module_index, ctx["dir_dotted"])
        module_defs = _edges.collect_module_defs(ctx["tree"])
        # #28 B: `from x import *` binds no names, so every unresolvable reference
        # in such a module floods one unresolved_symbol per usage site.  Defer
        # reference diagnostics in star-importing modules and aggregate them per
        # star import below instead.
        star_imports = [imp for imp in ctx["imports"] if imp.kind == "from_import" and imp.name == "*"]
        deferred: list[tuple[str, int]] = []
        for imp in ctx["imports"]:
            res = _edges.resolve_import(imp, module_index, source_id, ctx["dir_dotted"], module_ports)
            _apply(res, graph, collector, source_id)
        for ref in ctx["refs"]:
            res = _edges.resolve_reference(
                ref, symbol_table, module_index, source_id, module_defs, ctx["locals"], module_ports
            )
            if res.unresolved is not None and star_imports:
                deferred.append(res.unresolved)
            else:
                _apply(res, graph, collector, source_id)
        _apply_star_imports(collector, source_id, ctx["dir_dotted"], star_imports, deferred)

    graph.external_modules = _dedupe_external(graph.external_modules)
    graph.edges = _merge_edges(graph.edges)
    graph.diagnostics = collector.finalize()
    return graph.to_dict()


def _apply(res: _edges.Resolution, graph: Graph, collector: _diagnostics.Collector, module_id: str) -> None:
    if res.external is not None:
        graph.external_modules.append(ExternalModule(id=res.external, name=res.external))
    if res.edge is not None:
        graph.edges.append(res.edge)
    if res.unresolved is not None:
        name, line = res.unresolved
        collector.add(Diagnostic("unresolved_symbol", module_id, line, f"unresolved symbol {name!r}"))


def _apply_star_imports(
    collector: _diagnostics.Collector,
    module_id: str,
    dir_dotted: str,
    star_imports: list[_edges.RawImport],
    deferred: list[tuple[str, int]],
) -> None:
    """#28 B: one aggregated diagnostic per star import, not one per usage site.

    A star import binds no names, so a reference it could have provided is
    statically indistinguishable from a genuinely undefined one — attributing
    the count to a specific star import is impossible until #29's two-pass
    resolution.  Until then each star import gets one honest note covering the
    module's whole unresolved set (QuickCut 586 / you-get 1626 site-level
    diagnostics collapse to one line per `import *`).
    """
    if not star_imports or not deferred:
        return
    names = sorted({name for name, _ in deferred})
    sample = ", ".join(repr(n) for n in names[:5])
    more = f" (+{len(names) - 5} more)" if len(names) > 5 else ""
    for imp in star_imports:
        target = _edges._resolve_module(imp.module, imp.level, dir_dotted) or imp.module or "."
        collector.add(
            Diagnostic(
                "star_import_unresolved",
                module_id,
                imp.line,
                f"{len(names)} unresolved symbol(s) in this module may come from star import "
                f"of {target!r} (e.g. {sample}{more}); per-site diagnostics aggregated",
            )
        )


def _discover_files(root: Path, exclude_dirs: set[str] | None = None) -> list[Path]:
    """All ``.py`` files under root, minus excluded directories (D21/F6, #24).

    Caller-supplied ``exclude_dirs`` names are unioned over the always-excluded
    ``EXCLUDED_DIRS``; each name matches any directory at any depth.
    """
    files: list[Path] = []
    excluded = EXCLUDED_DIRS | set(exclude_dirs or [])
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        if any(part in excluded for part in rel.parts):
            continue
        files.append(rel)
    return files


def _dir_dotted(rel: Path) -> str:
    """Dotted module name of the file's *directory* (relative-import base).

    The repo root directory normalises to "" (``Path('main.py').parent`` is
    ``Path('.')``, whose posix form is ".").
    """
    parent = rel.parent
    if str(parent) in (".", ""):
        return ""
    return parent.as_posix().replace("/", ".")


def _dedupe_external(items: list[ExternalModule]) -> list[ExternalModule]:
    seen: dict[str, ExternalModule] = {}
    for x in items:
        seen.setdefault(x.id, x)
    return list(seen.values())


def _merge_edges(edges: list[Edge]) -> list[Edge]:
    """Merge edges on (source, target, targetPort, kind), aggregating sites (S7)."""
    merged: dict[tuple, Edge] = {}
    for e in edges:
        key = (e.source, e.target, e.targetPort, e.kind)
        if key in merged:
            merged[key].sites.extend(e.sites)
        else:
            merged[key] = e
    for e in merged.values():
        seen_lines: set[int] = set()
        sites: list[dict] = []
        for site in sorted(e.sites, key=lambda s: s["line"]):
            if site["line"] not in seen_lines:
                seen_lines.add(site["line"])
                sites.append(site)
        e.sites = sites
    return list(merged.values())


def _parse_error_message(exc: Exception) -> str:
    if isinstance(exc, SyntaxError):
        return f"syntax error: {exc.msg}"
    return f"unable to parse file: {exc}"
