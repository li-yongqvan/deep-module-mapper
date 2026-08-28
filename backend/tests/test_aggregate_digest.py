"""Tests for aggregate.digest — the lightweight input digest (S3, D12/U3).

Pure function, fully offline. The truncation ladder is asserted behaviorally:
the boundary lengths between levels are measured by feeding the digest
*input-graph variants* (docstring present/absent, etc.) at an unlimited budget,
so the test never replicates the ladder's serialization logic.
"""

from __future__ import annotations

import json

from backend.backend.aggregate import digest


def _graph(
    *,
    docstring: str | None = "Doc of f.",
    params: list[str] | None = ["x"],
    signature: str | None = "(x) -> int",
    noise: bool = True,
) -> dict:
    """A minimal graph: a.py (one port) + b.py + pkg/__init__.py + noise."""
    modules = [
        {"id": "a.py", "path": "a.py", "ports": []},
        {"id": "b.py", "path": "b.py", "ports": []},
        {"id": "pkg/__init__.py", "path": "pkg/__init__.py", "ports": []},
    ]
    if noise:
        # Real noise ids are nested (backend/tests/..., .../fixtures/...) so they
        # contain the `/tests/` marker — same predicate as the frontend (T13).
        modules.append(
            {"id": "backend/tests/test_a.py", "path": "backend/tests/test_a.py", "ports": []}
        )
    port: dict = {"kind": "function", "name": "f", "moduleId": "a.py"}
    if signature is not None:
        port["signature"] = signature
    if docstring is not None:
        port["docstring"] = docstring
    if params is not None:
        port["params"] = params
    edges = [
        {"source": "a.py", "target": "b.py", "kind": "import"},
        {"source": "a.py", "target": "b.py", "kind": "import"},  # duplicate
        {"source": "a.py", "target": "os", "kind": "import"},  # external target
        {"source": "a.py", "target": "b.py", "kind": "call"},  # not an import
        {"source": "backend/tests/test_a.py", "target": "a.py", "kind": "from_import"},
    ]
    return {"modules": modules, "ports": [port], "edges": edges}


def _module(text: str, module_id: str) -> dict:
    parsed = json.loads(text)
    return next(m for m in parsed["modules"] if m["id"] == module_id)


# --- content & filtering ---------------------------------------------------


def test_noise_filtered_init_kept_external_imports_kept():
    text = digest.build_digest(_graph(), "repo", total_chars=10**9).text

    assert digest.build_digest(_graph(), "repo", total_chars=10**9).truncation == "none"
    assert "backend/tests/test_a.py" not in text
    ids = [m["id"] for m in json.loads(text)["modules"]]
    assert "a.py" in ids and "b.py" in ids and "pkg/__init__.py" in ids


def test_imports_extracted_deduped_order_preserved():
    a = _module(digest.build_digest(_graph(), "repo", total_chars=10**9).text, "a.py")

    # b.py duplicated in edges but listed once; external `os` kept; `call` edge
    # is not an import and must be excluded (T16).
    assert a["imports"] == ["b.py", "os"]


def test_full_digest_keeps_docstring_params_signature():
    a = _module(digest.build_digest(_graph(), "repo", total_chars=10**9).text, "a.py")

    port = a["ports"][0]
    assert port["docstring"] == "Doc of f."
    assert port["params"] == ["x"]
    assert port["signature"] == "(x) -> int"


def test_repo_name_from_root():
    text = digest.build_digest(_graph(), "some/path/deep-module-mapper", total_chars=10**9).text

    assert json.loads(text)["repo"] == "deep-module-mapper"


def test_default_budget_is_api_budget():
    # The constructor default is the API budget (R2/F3), not the local one.
    assert digest.API_TOTAL_DIGEST_CHARS > digest.TOTAL_DIGEST_CHARS
    assert (
        digest.build_digest(_graph(), "repo").truncation == "none"
    )  # small graph fits 40K


# --- deterministic truncation ladder (INV8/INV12) --------------------------


def test_ladder_levels_observed_via_budget():
    def text(graph: dict) -> str:
        return digest.build_digest(graph, "repo", total_chars=10**9).text

    full = text(_graph())
    no_doc = text(_graph(docstring=None))  # what level-1 rendering looks like
    no_param = text(_graph(docstring=None, params=None))  # level-2 shape
    bare = text(_graph(docstring=None, params=None, signature=None))  # level-3

    assert len(no_doc) < len(full)
    assert len(no_param) < len(no_doc)
    assert len(bare) < len(no_param)

    # Budget == full text → no truncation.
    assert digest.build_digest(_graph(), "repo", total_chars=len(full)).truncation == "none"

    # Budget forces docstring out but keeps params.
    d = digest.build_digest(_graph(), "repo", total_chars=len(no_doc))
    assert d.truncation == digest.TRUNCATION_NO_DOCSTRINGS
    port = _module(d.text, "a.py")["ports"][0]
    assert "docstring" not in port and port["params"] == ["x"]

    # Budget forces params out too, signature survives.
    d = digest.build_digest(_graph(), "repo", total_chars=len(no_doc) - 1)
    assert d.truncation == digest.TRUNCATION_NO_PARAMS
    port = _module(d.text, "a.py")["ports"][0]
    assert "params" not in port and port["signature"] == "(x) -> int"

    # Budget forces ports down to {kind, name}.
    d = digest.build_digest(_graph(), "repo", total_chars=len(no_param) - 1)
    assert d.truncation == digest.TRUNCATION_BARE_PORTS
    assert _module(d.text, "a.py")["ports"] == [{"kind": "function", "name": "f"}]

    # Budget below bare-ports → longest ports dropped, id/imports never dropped.
    d = digest.build_digest(_graph(), "repo", total_chars=len(bare) - 1)
    assert d.truncation == digest.TRUNCATION_DROPPED_PORTS
    a = _module(d.text, "a.py")
    assert a.get("ports") in (None, [])  # every port entry dropped
    assert a["imports"] == ["b.py", "os"]  # INV12


def test_budget_zero_keeps_id_and_imports():
    d = digest.build_digest(_graph(), "repo", total_chars=0)

    assert d.truncation == digest.TRUNCATION_DROPPED_PORTS
    a = _module(d.text, "a.py")
    assert a["imports"] == ["b.py", "os"]
    assert json.loads(d.text)["repo"] == "repo"


def test_digest_is_deterministic():
    g = _graph()

    assert digest.build_digest(g, "repo", total_chars=10**9).text == digest.build_digest(
        g, "repo", total_chars=10**9
    ).text


# --- defensive parsing (INV9) ---------------------------------------------


def test_missing_or_malformed_graph_keys_do_not_crash():
    empty = digest.build_digest({}, "repo", total_chars=10**9)
    assert empty.truncation == "none"
    assert json.loads(empty.text) == {"repo": "repo", "modules": []}

    malformed = {
        "modules": [{"id": "a.py"}, "not-a-dict", 42],
        "edges": [{"source": "a.py"}, "junk", {"source": "a.py", "target": "b.py", "kind": "call"}],
        "ports": "not a list",
    }
    d = digest.build_digest(malformed, "repo", total_chars=10**9)
    assert d.truncation == "none"
    assert "a.py" in d.text  # survived without crashing


def test_self_import_and_unknown_edge_kind_ignored():
    g = {
        "modules": [{"id": "a.py", "path": "a.py", "ports": []}],
        "edges": [
            {"source": "a.py", "target": "a.py", "kind": "import"},  # self
            {"source": "a.py", "target": "b.py", "kind": "weird_kind"},  # unknown
        ],
        "ports": [],
    }

    d = digest.build_digest(g, "repo", total_chars=10**9)

    a = _module(d.text, "a.py")
    assert "imports" not in a or a["imports"] == []
