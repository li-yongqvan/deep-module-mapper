"""Tests for aggregate.validate — drop-in validation (S4).

The six rules are asserted one by one; pydantic ``extra="forbid"`` pins the
exact drop-in shape (INV6). Offline.
"""

from __future__ import annotations

from backend.backend.aggregate.validate import (
    FeatureAtomManifest,
    is_init_module,
    is_noise_module,
    is_production_module,
    validate_manifest,
)

# m1..m3 + __init__ are production-ish; tests/ and fixtures/ are noise.
MODULE_IDS = [
    "m1.py",
    "m2.py",
    "m3.py",
    "pkg/__init__.py",
    "backend/tests/test_x.py",
    "backend/tests/fixtures/mini_pkg/lib.py",
]


def _valid_manifest() -> dict:
    return {
        "atoms": [
            {
                "id": "one",
                "name": "原子一",
                "description": "负责功能一",
                "files": ["m1.py", "m2.py"],
            },
            {
                "id": "two",
                "name": "原子二",
                "description": "负责功能二",
                "files": ["m3.py", "pkg/__init__.py"],
            },
        ]
    }


def test_valid_manifest_passes_and_reports_coverage():
    result = validate_manifest(_valid_manifest(), MODULE_IDS)

    assert result.ok
    assert result.manifest is not None
    assert result.coverage.assigned == ["m1.py", "m2.py", "m3.py"]
    assert result.coverage.missing == []
    assert result.coverage.production_files == ["m1.py", "m2.py", "m3.py"]


def test_missing_production_module_fails_coverage():
    manifest = _valid_manifest()
    manifest["atoms"] = [dict(manifest["atoms"][0], files=["m1.py"])]  # m2, m3 gone

    result = validate_manifest(manifest, MODULE_IDS)

    assert not result.ok
    assert any("覆盖缺失" in e and "m2.py" in e and "m3.py" in e for e in result.errors)
    assert result.coverage.missing == ["m2.py", "m3.py"]


def test_noise_file_is_rejected():
    manifest = _valid_manifest()
    manifest["atoms"][0]["files"].append("backend/tests/test_x.py")

    result = validate_manifest(manifest, MODULE_IDS)

    assert not result.ok
    assert any("测试/夹具" in e for e in result.errors)
    assert "backend/tests/test_x.py" in result.coverage.noise_files


def test_fabricated_path_is_rejected():
    manifest = _valid_manifest()
    manifest["atoms"][0]["files"].append("made/up/path.py")

    result = validate_manifest(manifest, MODULE_IDS)

    assert not result.ok
    assert any("非真实模块" in e for e in result.errors)
    assert "made/up/path.py" in result.coverage.unknown_files


def test_file_in_two_atoms_is_rejected():
    manifest = _valid_manifest()
    manifest["atoms"][1]["files"].append("m1.py")  # m1 already in atom one

    result = validate_manifest(manifest, MODULE_IDS)

    assert not result.ok
    assert any("多个原子" in e and "m1.py" in e for e in result.errors)
    assert "m1.py" in result.coverage.duplicated


def test_duplicate_atom_id_is_rejected():
    manifest = _valid_manifest()
    manifest["atoms"].append(dict(manifest["atoms"][0], files=["m1.py"]))

    result = validate_manifest(manifest, MODULE_IDS)

    assert not result.ok
    assert any("id 重复" in e and "one" in e for e in result.errors)


def test_empty_fields_fail_shape():
    manifest = _valid_manifest()
    manifest["atoms"][0]["id"] = ""

    assert not validate_manifest(manifest, MODULE_IDS).ok

    manifest = _valid_manifest()
    manifest["atoms"][0]["files"] = []  # an atom must name at least one file

    assert not validate_manifest(manifest, MODULE_IDS).ok


def test_extra_field_is_forbidden_exact_drop_in():
    manifest = _valid_manifest()
    manifest["atoms"][0]["extraField"] = True

    result = validate_manifest(manifest, MODULE_IDS)

    assert not result.ok
    assert any("形状不合法" in e for e in result.errors)

    # Unknown top-level key is also rejected.
    top = _valid_manifest()
    top["sourceHistory"] = []

    assert not validate_manifest(top, MODULE_IDS).ok


def test_init_py_is_optional_and_allowed():
    without_init = _valid_manifest()
    without_init["atoms"][1]["files"] = ["m3.py"]  # drop pkg/__init__.py

    assert validate_manifest(without_init, MODULE_IDS).ok

    with_init = _valid_manifest()
    with_init["atoms"][0]["files"] = ["m1.py", "m2.py", "pkg/__init__.py"]  # init once
    with_init["atoms"][1]["files"] = ["m3.py"]

    assert validate_manifest(with_init, MODULE_IDS).ok


def test_broken_shape_returns_ok_false_without_manifest():
    result = validate_manifest({"atoms": "not-a-list"}, MODULE_IDS)

    assert not result.ok
    assert result.manifest is None
    assert any("形状不合法" in e for e in result.errors)


def test_shared_predicates_match_frontend_semantics():
    assert is_noise_module("backend/tests/x.py")
    assert is_noise_module("a/fixtures/b.py")
    assert not is_noise_module("m1.py")
    assert is_init_module("pkg/__init__.py")
    assert not is_init_module("pkg/lib.py")
    assert is_production_module("m1.py")
    assert not is_production_module("backend/tests/x.py")
    assert not is_production_module("pkg/__init__.py")
