"""Internal data models for the Deep Module Mapper Python parser.

These types are private implementation details.  The only public contract is
the JSON shape returned by ``scan_codebase``, documented in ``schema.json``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Port:
    """A module's public connection surface: a function, class or export."""

    kind: str  # "function" | "class" | "export"
    name: str
    line: int
    signature: str
    params: list[str] = field(default_factory=list)
    docstring: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.docstring is None:
            d.pop("docstring")
        return d


@dataclass
class Module:
    """One ``.py`` file = one module (D1)."""

    id: str  # relative path, posix separators (D9)
    path: str
    ports: list[Port] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "path": self.path,
            "ports": [p.to_dict() for p in self.ports],
        }


@dataclass
class Edge:
    """A dependency edge between two modules."""

    source: str
    target: str
    targetPort: str | None  # resolved when possible
    kind: str  # import | from_import | call | inheritance | annotation | decorator
    sites: list[dict] = field(default_factory=list)  # [{"line": n}]

    def to_dict(self) -> dict:
        d = {
            "source": self.source,
            "target": self.target,
            "kind": self.kind,
            "sites": self.sites,
        }
        if self.targetPort is not None:
            d["targetPort"] = self.targetPort
        return d


@dataclass
class ExternalModule:
    """A third-party package that the codebase depends on."""

    id: str
    name: str
    kind: str = "third_party"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Diagnostic:
    """A parser note: dynamic import, unresolved symbol or parse error."""

    kind: str  # dynamic_import | unresolved_symbol | parse_error
    moduleId: str
    line: int
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Graph:
    """The full scan result. Serialised to the issue #2 top-level keys plus
    the v2 ``intra`` key (#24 §14)."""

    modules: list[Module] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    external_modules: list[ExternalModule] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    intra: dict = field(default_factory=dict)  # module_id -> {funcs, calls}

    def to_dict(self) -> dict:
        # F1: issue #2 confirms 5 top-level keys. `ports` is a flat list with
        # per-entry moduleId, generated from the same source as the nested lists.
        # v2 (#24 §14): `intra` is appended as the 6th key; the existing five
        # keep their order and content (pure additive pass, golden-tested).
        return {
            "modules": [m.to_dict() for m in self.modules],
            "ports": [p.to_dict() | {"moduleId": m.id} for m in self.modules for p in m.ports],
            "edges": [e.to_dict() for e in sorted(self.edges, key=_edge_sort_key)],
            "externalModules": [x.to_dict() for x in sorted(self.external_modules, key=lambda x: x.id)],
            "diagnostics": [d.to_dict() for d in sorted(self.diagnostics, key=lambda d: (d.moduleId, d.line))],
            "intra": self.intra,
        }


def _edge_sort_key(e: Edge) -> tuple:
    first_line = e.sites[0]["line"] if e.sites else 0
    return (e.source, e.target, e.kind, first_line)
