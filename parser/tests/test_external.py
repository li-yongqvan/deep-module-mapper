"""Unit tests for external/third-party classification (_external)."""

from pathlib import Path

from parser import _external


def test_is_stdlib():
    assert _external.is_stdlib("os")
    assert _external.is_stdlib("json")
    assert not _external.is_stdlib("requests")


def test_classify_local():
    index = {
        "sample_pkg": "sample_pkg/__init__.py",
        "sample_pkg.core": "sample_pkg/core.py",
    }
    kind, mod_id = _external.classify("sample_pkg.core", index)
    assert (kind, mod_id) == ("local", "sample_pkg/core.py")


def test_classify_third_party():
    kind, mod_id = _external.classify("requests", {})
    assert (kind, mod_id) == ("third_party", "requests")


def test_classify_stdlib():
    kind, mod_id = _external.classify("os", {})
    assert (kind, mod_id) == ("stdlib", None)


def test_module_index_maps_package_and_file():
    files = [
        Path("sample_pkg/__init__.py"),
        Path("sample_pkg/core.py"),
        Path("main.py"),
        Path("__init__.py"),
    ]
    index = _external.build_module_index(files, Path("."))
    assert index["sample_pkg"] == "sample_pkg/__init__.py"
    assert index["sample_pkg.core"] == "sample_pkg/core.py"
    assert index["main"] == "main.py"
    assert "" not in index  # root-level __init__ has no dotted name


def test_excluded_dirs_are_stable():
    assert "venv" in _external.EXCLUDED_DIRS
    assert ".git" in _external.EXCLUDED_DIRS
