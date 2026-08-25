# Dependency Edge Extraction from Python Code — Research Report

**Project:** Deep Module Mapper  
**Date:** 2026-08-25  
**Scope:** First version focuses on Python only. A module = implementation + port/interface; an interface = public functions / exported symbols; an edge = one module's interface uses another module's interface.

---

## 1. What Constitutes a Dependency Edge in Python?

A dependency edge exists when code in module A references a symbol that is defined in module B and that reference can be resolved statically. In Python the most common carriers of such edges are:

| Edge carrier | Example | Notes for our graph |
|--------------|---------|---------------------|
| **Top-level `import` / `from ... import`** | `import db` or `from db import save_user` | Always an edge from the importing module to the exporter. Even if the imported name is never used, the import statement itself creates a static coupling. |
| **Attribute access on an imported module** | `db.save_user(...)` | Same edge as the underlying import; the call site only adds detail about *which* port is used. |
| **Cross-module function / method calls** | `orders.create_order()` where `orders` is imported | Strong signal of interface use. Requires resolving the callee back to its defining module. |
| **Cross-module class inheritance** | `class PostgresRepo(Repository):` where `Repository` lives in another module | Strong edge to the base class module. |
| **Type annotations** | `def process(repo: Repository) -> Report:` | A static edge to the module defining `Repository` / `Report`. Python ignores these at runtime, but they are explicit design-time couplings. |
| **Decorators from another module** | `@metrics.timed` | Edge to the decorators module; usually treated like a function call. |
| **Dynamic imports** | `__import__(name)`, `importlib.import_module(...)` | Hard to resolve statically. Should be recorded as an *unresolved* edge or ignored in v1. |
| **String-based / config-driven references** | `settings.MY_CLASS`, `getattr(mod, name)` | Generally beyond pure static analysis. |

### What is *not* an edge for our purposes

- Local variable reuse, closures inside the same file.
- Built-ins (`len`, `print`, `dict`) and standard-library calls, unless the user explicitly wants them in the graph.
- Same-module calls (implementation detail, not a port crossing).
- Runtime-only couplings that cannot be seen in source code.

---

## 2. Granularity: Module/Port-Level Graph vs. Too-Fine-Grained Edges

### Keep at module/port level

| Edge type | Rationale |
|-----------|-----------|
| Module → module import | The canonical first-class edge. |
| Public symbol used in another module | This is the "port" crossing: one module's public function/class is referenced by another. |
| Inheritance across modules | A public class from module B becomes part of A's public contract. |
| Type annotations across modules | Design-time contract; useful for architecture diagrams. |

### Too fine-grained for v1 (defer or hide)

| Edge type | Why defer |
|-----------|-----------|
| Function → function call graph | Useful, but it explodes the graph and is not required to show module coupling. |
| Variable-level dataflow | Even more granular; belongs in a code editor, not an architecture mapper. |
| Conditional / lazy import branches | Worth noting as metadata, but the existence of the import is usually enough. |
| Third-party package internals | Treat each external package as one opaque node unless the user expands it. |

### Recommended abstraction

- **Node:** a module (file or directory) with a discoverable public interface.
- **Port:** a public symbol (function, class, or module-level constant) exposed by that module.
- **Edge:** module A uses port X of module B. The edge can carry a list of *use sites* (file, line, kind: import/call/inheritance/annotation) without turning every call into its own edge.

This keeps the graph readable while still allowing drill-down from an edge to the exact call sites.

---

## 3. Existing Tools and Libraries — What We Can Adapt

### 3.1 Python-native tools

#### `pydeps` + `modulegraph` / `modulegraph2`

- **How it works:** Builds a dependency graph by analyzing Python bytecode for import opcodes (`IMPORT_NAME`, `IMPORT_FROM`, `IMPORT_STAR`). Creates a dummy module that imports the target package and walks the resulting tree.
- **Granularity:** Module/package level.
- **Output:** Graphviz DOT, SVG, PNG, and a JSON intermediate with `imports` / `imported_by`.
- **Pattern to adapt:** The JSON intermediate (`--show-deps`) is essentially the data shape we want for module-to-module edges. The bytecode approach is robust against imports hidden in `if` / `try` blocks.
- **Limitation:** It does not tell you *which* public symbol of B is used by A, only that A imports B. Also relies on importability, so it may miss files not reachable from the entry point unless `--include-missing` is used.
- **Sources:** [pydeps GitHub](https://github.com/thebjorn/pydeps), [pydeps docs](https://pydeps.readthedocs.io/), [modulegraph docs](https://modulegraph.readthedocs.io/)

#### `import-linter` (+ `grimp`)

- **How it works:** Uses the `grimp` library to build an import graph across all modules in configured root packages, then checks the graph against architectural contracts (layers, forbidden, independence, etc.).
- **Granularity:** Module / package level.
- **Output:** Pass/fail report with violating import chains.
- **Pattern to adapt:** The contract model (layers, independence, forbidden) is a great reference for how to express *architecture rules* on top of a dependency graph. The underlying graph of `module -> imports -> module` is exactly our first target.
- **Limitation:** Like `pydeps`, it is import-graph only; it does not resolve individual public-symbol usage.
- **Sources:** [import-linter docs](https://import-linter.readthedocs.io/), [Layers contract docs](https://import-linter.readthedocs.io/en/v2.9/contract_types/layers/)

#### Tach

- **How it works:** AST-based static analysis of all Python imports, compared against module boundaries declared in `tach.toml`. Enforces `depends_on` lists, layers, public interfaces, and circular-dependency rules.
- **Granularity:** User-defined modules (can be files or directories) with explicit public interfaces.
- **Output:** Violation reports, `tach show` (DOT / web graph), `tach report` (bidirectional impact analysis).
- **Pattern to adapt:** The explicit **public interface** concept is directly transferable to our "port" idea. Tach's workflow (`tach init` → define boundaries → `tach check`) shows that requiring users to declare module boundaries can dramatically simplify extraction and improve accuracy.
- **Limitation:** Static-only; dynamic imports are missed. Requires upfront configuration.
- **Sources:** [Tach docs](https://docs.gauge.sh/), [Tach overview](https://gauge-sh.github.io/tach/)

#### `jedi`

- **How it works:** A mature static-analysis library that parses Python and resolves names across files. Provides `Script.goto()`, `Script.get_references(scope='project')`, and `Script.infer()`.
- **Granularity:** Symbol level (functions, classes, variables).
- **Output:** Definition / reference locations, inferred types.
- **Pattern to adapt:** Ideal for the **second pass** of our pipeline: after `ast` tells us "module A imports B", use `jedi` to resolve which public symbol of B is actually referenced at each call site.
- **Limitation:** Can stop searching on very complex projects; does not handle dynamic patterns (`getattr`, monkey-patching, decorators/metaclasses reliably).
- **Sources:** [Jedi GitHub](https://github.com/davidhalter/jedi), [Jedi API docs](https://jedi.readthedocs.io/en/latest/_modules/jedi/api.html)

#### PyCG / research-grade call graphs

- **How it works:** Builds an assignment graph and computes inter-procedural call graphs. State-of-the-art for Python static call-graph generation.
- **Granularity:** Function level.
- **Pattern to adapt:** Validates that resolving cross-module calls is feasible, but the complexity is overkill for v1. Keep in mind as the path to function-level drill-down later.
- **Sources:** [PyCG paper](https://arxiv.org/abs/2103.00587), [PyCG ar5iv](https://ar5iv.labs.arxiv.org/html/2103.00587)

### 3.2 Cross-language reference: `dependency-cruiser`

- **How it works:** Static analyzer for JS/TS that parses source, resolves imports through `enhanced-resolve`, and outputs a structured `ICruiseResult` (modules + dependencies + violations).
- **Patterns directly adaptable to Python:**
  - **AST-first analysis** instead of execution (`tsPreCompilationDeps: true`).
  - **Configurable resolution strategy** (`sys.path` / `PYTHONPATH` / nearest `pyproject.toml` for us).
  - **Exclude lists** for `site-packages`, `.venv`, tests.
  - **Reporters** consume a stable intermediate schema; the UI is decoupled from the parser.
  - **Layered architecture rules** and **collapse patterns** for high-level views.
- **Limitation:** It is JS-specific, but its architecture is language-agnostic.
- **Sources:** [dependency-cruiser FAQ](https://github.com/sverweij/dependency-cruiser/blob/main/doc/faq.md), [dependency-cruiser CLI docs](https://github.com/sverweij/dependency-cruiser/blob/main/doc/cli.md)

### 3.3 Parser libraries

| Library | Best for | Trade-off |
|---------|----------|-----------|
| **`ast` (stdlib)** | Fast, read-only extraction of imports, class bases, calls, annotations. No external dependency. | Lossy round-trip; no whitespace/comments; no built-in name resolution. |
| **`symtable` (stdlib)** | Scope analysis: local vs. global vs. imported names. Good complement to `ast`. | No def-use chains or type inference. |
| **`libcst`** | Lossless parse → analyze → rewrite. Preserves comments and formatting. | Slower, more complex tree, extra dependency. Use if we later want to *modify* code, not just read it. |
| **tree-sitter** | Multi-language parsing with fast incremental updates. Good if we later add JS/TS/Go. | Requires grammar + query language; name resolution must be built ourselves. |

For a Python-first v1, **`ast` + `symtable`** is the pragmatic choice. Add `jedi` only for the optional "resolve symbol to defining module" pass.

---

## 4. Recommended First-Version Strategy

### 4.1 Discover modules

1. **User input:** one or more root directories and an optional include/exclude glob list.
2. **Walk the tree:** collect all `.py` files under the roots.
3. **Map file paths to module names:**
   - For a package directory, use the relative path from the root: `src/services/orders.py` → `services.orders`.
   - For an ordinary script directory, treat each file as a standalone module or group by nearest `__init__.py`.
4. **Identify the module boundary:**
   - **Default:** one file = one module. Simple, matches Python's module system.
   - **Optional:** one directory = one module (collapse submodules), useful for bounded contexts.
5. **Ignore:** `.venv`, `site-packages`, `tests/` (configurable), generated files.

### 4.2 Discover ports / interfaces

A module's interface is the set of symbols it intentionally exposes for other modules to use.

| Symbol type | Rule |
|-------------|------|
| **Public functions / async functions** | Names not starting with `_`. Include module-level functions and public class methods only if we later expand ports. |
| **Public classes** | Names not starting with `_`. Include `__init__` as part of the class port. |
| **Module-level public constants / typed variables** | Names not starting with `_`. |
| **Re-exports** | `from .foo import PublicClass as PublicClass` — counts as part of the interface. |
| **`__all__`** | If present, use it as the authoritative interface list. |
| **Private / internal** | Names starting with `_` and submodules not re-exported are excluded by default. |

Implementation: walk the AST, collect `FunctionDef`, `AsyncFunctionDef`, `ClassDef`, and `AnnAssign`/`Assign` at module scope whose `name` does not start with `_`. If `__all__` exists, intersect with it.

### 4.3 Discover edges

Use a **two-pass** design:

#### Pass 1 — Import extraction (AST)

For each module file, parse with `ast.parse()` and record:

- `ast.Import`: each `alias.name` → imported module.
- `ast.ImportFrom`: resolve relative `level` to a dotted module path; record imported names.
- `ast.ClassDef.bases`: record base classes and resolve their module.
- Type annotations on function args / returns and annotated assignments: record referenced names.

Output: raw edges of the form `(source_module, target_module, kind, line, symbol_or_None)`.

#### Pass 2 — Symbol resolution (optional, `jedi`)

For each call site or attribute access that imports a name from another module, ask `jedi`:

- Where is this symbol defined?
- Is it one of the public symbols we recorded as a port?

If resolution succeeds, refine the edge to point to a specific port. If it fails, keep the module-level edge and mark it `unresolved-symbol`.

#### Edge kinds to store

| Kind | Description |
|------|-------------|
| `import` | Top-level import statement. |
| `from-import` | `from X import Y`. |
| `call` | Function/method call across modules. |
| `inheritance` | Class base from another module. |
| `annotation` | Type hint referencing another module. |
| `decorator` | Decorator from another module. |
| `dynamic` | Marked when `__import__` / `importlib` is detected but not resolved. |

### 4.4 Trade-offs and limitations

| Approach | Pros | Cons |
|----------|------|------|
| **AST-only** | Fast, no external deps, works on broken code. | Cannot always resolve re-exports, aliases, or star imports. |
| **AST + jedi** | Better symbol resolution, cross-file references. | Slower, may choke on very large codebases, still misses dynamic code. |
| **Bytecode (modulegraph style)** | Catches imports in conditional branches. | Harder to extract precise ports and line numbers; requires importability. |
| **User-defined boundaries** | Accurate, matches intended architecture. | Manual setup; not zero-config. |

**Recommended v1:** AST-only module-level edges with optional jedi refinement. Do not execute code. Do not chase dynamic imports. Treat third-party packages as opaque external nodes.

---

## 5. Proposed Backend Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Deep Module Mapper Backend                  │
├─────────────────────────────────────────────────────────────────┤
│  Config layer                                                   │
│  - roots, include/exclude globs, module-boundary mode           │
│  - external-package handling (ignore / collapse / expand)       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Discovery                                                      │
│  - FilesystemScanner: list .py files under roots                │
│  - ModuleMapper: file path ↔ logical module name                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Parser (per file)                                              │
│  - AstParser: imports, class bases, annotations, calls          │
│  - InterfaceExtractor: public functions/classes/__all__         │
│  - ScopeHelper (symtable): distinguish imported vs local names  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Resolution (optional)                                          │
│  - JediResolver: map call sites / attributes to defining module │
│  - Fallback: keep module-level edge, mark unresolved            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Graph Builder                                                  │
│  - Aggregate raw edges into module/port graph                   │
│  - Detect cycles, compute stability metrics                     │
│  - Apply collapse rules for directory-level modules             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Output schema (JSON)                                           │
│  - modules, ports, edges, edge-sites, diagnostics               │
└─────────────────────────────────────────────────────────────────┘
```

### Suggested output schema (first cut)

```json
{
  "modules": [
    {
      "id": "services.orders",
      "path": "src/services/orders.py",
      "ports": [
        {"kind": "function", "name": "create_order", "line": 12},
        {"kind": "class", "name": "OrderService", "line": 34}
      ]
    }
  ],
  "edges": [
    {
      "source": "services.orders",
      "target": "db.connection",
      "targetPort": "get_session",
      "kind": "call",
      "sites": [{"path": "src/services/orders.py", "line": 45, "col": 18}],
      "resolved": true
    }
  ],
  "diagnostics": [
    {"severity": "warning", "message": "Dynamic import in src/utils/loader.py:14 could not be resolved"}
  ]
}
```

### Extensibility hooks

- **Parser backend:** define a `Parser` protocol. Start with `AstParser`; later add `LibCstParser` or `TreeSitterParser`.
- **Resolver backend:** define a `Resolver` protocol. Start with no-op; add `JediResolver`; later add a `PyCGResolver` for function-level edges.
- **Module boundary strategy:** `FileModuleStrategy` (default) and `DirectoryModuleStrategy`.
- **Output reporter:** JSON is canonical; add DOT / Graphviz / Cytoscape JSON as separate reporters.

---

## 6. Concrete Recommendations

1. **Start with `ast` only.** It is in the standard library, fast, and sufficient for module-to-module import edges and public-interface discovery.
2. **Model a module as a Python file by default.** It is the least surprising mapping and matches how `import` works.
3. **Define ports as public top-level functions, classes, and `__all__` exports.** Ignore private names (`_`).
4. **Capture imports, inheritance, type annotations, and cross-module calls as edge kinds.** Store line/column sites so the UI can link back to code.
5. **Use `jedi` as an optional resolver** to turn module-level edges into port-level edges, but do not require it.
6. **Do not execute code.** Static analysis keeps the tool safe and fast; accept that dynamic imports will be unresolved.
7. **Borrow patterns from `dependency-cruiser`:** stable intermediate schema, configurable resolution, exclusion lists, and layered architecture rules.
8. **Borrow the public-interface idea from Tach** so users can explicitly designate the official surface of each module.
9. **Plan for multi-language later** by keeping parser/resolver/reporter behind protocols, but implement Python first.
10. **Validate early and visibly:** expose unresolved edges, star imports, and dynamic imports as diagnostics rather than silently dropping them.

---

## Sources

- Python `ast` module documentation: https://docs.python.org/3/library/ast.html
- Python `symtable` / CPython source: https://github.com/python/cpython/blob/main/Python/symtable.c
- LibCST vs AST comparison: https://libcst.readthedocs.io/en/latest/why_libcst.html
- pydeps GitHub and docs: https://github.com/thebjorn/pydeps, https://pydeps.readthedocs.io/
- modulegraph docs: https://modulegraph.readthedocs.io/
- import-linter docs: https://import-linter.readthedocs.io/
- import-linter Layers contract: https://import-linter.readthedocs.io/en/v2.9/contract_types/layers/
- Tach docs: https://docs.gauge.sh/, https://gauge-sh.github.io/tach/
- Jedi GitHub and API docs: https://github.com/davidhalter/jedi, https://jedi.readthedocs.io/en/latest/_modules/jedi/api.html
- PyCG paper: https://arxiv.org/abs/2103.00587
- dependency-cruiser FAQ and CLI docs: https://github.com/sverweij/dependency-cruiser/blob/main/doc/faq.md, https://github.com/sverweij/dependency-cruiser/blob/main/doc/cli.md
- MIT OCW Module Dependence Diagrams: https://ocw.mit.edu/courses/6-170-laboratory-in-software-engineering-fall-2005/db198c4be27061592c1654a72895aff4_lec10.pdf
