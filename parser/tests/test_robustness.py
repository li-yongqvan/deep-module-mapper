"""Robustness regressions for #28: star-import aggregation and warning isolation.

Dogfood evidence (2026-09-06): QuickCut produced 586 site-level unresolved_symbol
diagnostics off one PyQt5 star import, you-get 1626 off ``from ..common import *``;
scanned-code SyntaxWarnings (invalid escape sequences) leaked onto the caller's
stderr (QuickCut 12x, you-get 4x).
"""

import warnings
from pathlib import Path

from parser import scan_codebase


def _write(root: Path, rel: str, source: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


# ---- #28 B: star-import aggregation ------------------------------------------


def test_star_import_aggregates_unresolved_into_one_note(tmp_path):
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/core.py", "def helper():\n    return 1\n")
    _write(
        tmp_path,
        "consumer.py",
        "from pkg.core import *\n"
        "\n"
        "def run():\n"
        "    a = helper()\n"
        "    b = helper()\n"
        "    return missing_symbol() + a + b\n",
    )
    graph = scan_codebase(tmp_path)

    # the star import itself is still a real edge
    assert any(
        e["source"] == "consumer.py" and e["target"] == "pkg/core.py" and e["kind"] == "from_import"
        for e in graph["edges"]
    )
    diags = [d for d in graph["diagnostics"] if d["moduleId"] == "consumer.py"]
    # no per-site flood: `helper` x2 + `missing_symbol` collapse into one note
    assert [d["kind"] for d in diags] == ["star_import_unresolved"]
    note = diags[0]
    assert note["line"] == 1  # anchored at the star import, not at usage sites
    assert "2 unresolved symbol(s)" in note["message"]
    assert "pkg.core" in note["message"]


def test_each_star_import_gets_its_own_aggregated_note(tmp_path):
    _write(tmp_path, "a.py", "def fa():\n    return 1\n")
    _write(tmp_path, "b.py", "def fb():\n    return 1\n")
    _write(
        tmp_path,
        "consumer.py",
        "from a import *\nfrom b import *\n\ndef run():\n    return fa() + fb() + gone()\n",
    )
    graph = scan_codebase(tmp_path)
    notes = [
        d for d in graph["diagnostics"]
        if d["moduleId"] == "consumer.py" and d["kind"] == "star_import_unresolved"
    ]
    assert [(n["line"], n["message"].count("unresolved symbol(s)")) for n in notes] == [
        (1, 1),
        (2, 1),
    ]


def test_resolved_refs_in_star_import_module_stay_silent(tmp_path):
    _write(tmp_path, "dep.py", "def known():\n    return 1\n")
    _write(
        tmp_path,
        "consumer.py",
        "from dep import known\nfrom dep import *\n\ndef run():\n    return known()\n",
    )
    graph = scan_codebase(tmp_path)
    assert [
        d for d in graph["diagnostics"] if d["moduleId"] == "consumer.py"
    ] == []


def test_no_star_import_keeps_per_site_unresolved(tmp_path):
    # control: without a star import the per-site diagnostic behaviour is unchanged
    _write(tmp_path, "lone.py", "def run():\n    return missing_symbol()\n")
    graph = scan_codebase(tmp_path)
    diags = graph["diagnostics"]
    assert [(d["kind"], d["line"]) for d in diags] == [("unresolved_symbol", 2)]


# ---- #28 C: scanned-code warnings must not leak --------------------------------


def test_scanned_code_syntax_warning_does_not_escape(tmp_path):
    # invalid escape sequence: SyntaxWarning at scanned-module compile time
    _write(tmp_path, "mod.py", 'X = "a\\.b"\nY = len(X)\n')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        graph = scan_codebase(tmp_path)
    assert [m["id"] for m in graph["modules"]] == ["mod.py"]
    assert not [w for w in caught if issubclass(w.category, SyntaxWarning)]


def test_scanned_code_warning_survives_error_filter(tmp_path):
    # stronger: a caller running with warnings-as-error must not have the scan
    # blow up on the scanned code's own SyntaxWarning
    _write(tmp_path, "mod.py", 'X = "a\\.b"\nY = len(X)\n')
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        graph = scan_codebase(tmp_path)
    assert [m["id"] for m in graph["modules"]] == ["mod.py"]
