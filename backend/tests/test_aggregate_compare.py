"""Tests for aggregate.compare — quality vs ground truth (S4, D11/U2).

Known GT + known AI inputs yield exact accuracy/missed/extra numbers, plus the
per-atom best-match table. Offline, deterministic.
"""

from __future__ import annotations

from backend.backend.aggregate.compare import compare_to_ground_truth
from backend.backend.aggregate.validate import FeatureAtomManifest


def _manifest(atoms: list[dict]) -> FeatureAtomManifest:
    return FeatureAtomManifest.model_validate({"atoms": atoms})


def _atom(atom_id: str, files: list[str]) -> dict:
    return {"id": atom_id, "name": atom_id, "description": atom_id, "files": files}


GT = _manifest([_atom("gt-a", ["m1.py", "m2.py", "m3.py"]), _atom("gt-b", ["m4.py", "m5.py"])])
AI = _manifest(
    [
        _atom("ai-x", ["m1.py", "m2.py", "m6.py", "m7.py"]),
        _atom("ai-y", ["m4.py", "m5.py"]),
        _atom("ai-z", ["m8.py"]),
    ]
)


def test_accuracy_is_correctly_assigned_gt_production_files():
    result = compare_to_ground_truth(AI, GT)

    # m1,m2 correctly placed (in gt-a's best match ai-x); m3 missed; m4,m5 in
    # ai-y. 4 correct out of 5 GT production files.
    assert result.correct_count == 4
    assert result.gt_production_total == 5
    assert result.accuracy == 0.8


def test_ai_missed_and_ai_extra_reported():
    result = compare_to_ground_truth(AI, GT)

    assert result.ai_missed == ["m3.py"]  # GT production file absent from AI
    assert result.ai_extra == ["m6.py", "m7.py", "m8.py"]  # new files, not counted
    assert result.gt_atoms == 2
    assert result.ai_atoms == 3


def test_per_atom_best_match_table():
    result = compare_to_ground_truth(AI, GT)

    first, second = result.matches
    assert first.gt_atom_id == "gt-a" and first.ai_atom_id == "ai-x"
    assert first.intersection == ["m1.py", "m2.py"]
    assert first.correct_count == 2
    assert second.gt_atom_id == "gt-b" and second.ai_atom_id == "ai-y"
    assert second.intersection == ["m4.py", "m5.py"]
    assert second.correct_count == 2


def test_empty_ai_gives_zero_accuracy_and_all_missed():
    result = compare_to_ground_truth(_manifest([_atom("nothing", ["m9.py"])]), GT)

    assert result.accuracy == 0.0
    assert result.ai_missed == ["m1.py", "m2.py", "m3.py", "m4.py", "m5.py"]


def test_best_match_tie_goes_to_first_ai_atom():
    ai = _manifest([_atom("ai-1", ["m1.py", "m9.py"]), _atom("ai-2", ["m2.py", "m9.py"])])
    gt = _manifest([_atom("gt-a", ["m1.py", "m2.py"])])

    result = compare_to_ground_truth(ai, gt)

    # Both AI atoms intersect gt-a in exactly 1 file; the first wins, so only
    # m1.py counts as correctly assigned (m2.py is in ai-2, not the matched atom).
    assert result.matches[0].ai_atom_id == "ai-1"
    assert result.matches[0].intersection == ["m1.py"]
    assert result.accuracy == 0.5


def test_gt_atom_with_zero_overlap_has_no_match():
    ai = _manifest([_atom("ai-x", ["m9.py"])])
    gt = _manifest([_atom("gt-a", ["m1.py"])])

    result = compare_to_ground_truth(ai, gt)

    assert result.matches[0].ai_atom_id is None
    assert result.matches[0].intersection == []
    assert result.accuracy == 0.0


def test_init_and_noise_files_excluded_from_accuracy():
    gt = _manifest([_atom("gt-a", ["m1.py", "pkg/__init__.py"])])
    ai = _manifest([_atom("ai-x", ["m1.py", "pkg/__init__.py"])])

    result = compare_to_ground_truth(ai, gt)

    assert result.gt_production_total == 1  # __init__ not production
    assert result.accuracy == 1.0  # m1.py correctly placed
    assert result.ai_extra == []  # __init__.py also present in GT


def test_empty_gt_guard():
    gt = _manifest([_atom("gt-a", ["pkg/__init__.py"])])  # no production files
    ai = _manifest([_atom("ai-x", ["m1.py"])])

    result = compare_to_ground_truth(ai, gt)

    assert result.gt_production_total == 0
    assert result.accuracy == 0.0
    assert result.correct_count == 0
