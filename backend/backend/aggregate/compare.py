"""Quality comparison vs the hand-maintained manifest (S4, D11/U2).

The core deliverable: ``accuracy`` = correctly-assigned GT production files /
total GT production files. A GT file is *correctly assigned* when it falls in
the best-match AI atom — the AI atom whose file set has the largest
intersection with the file's own GT atom (tie → first AI atom, deterministic).

AI atom ids/names necessarily differ from the GT's (the AI proposes its own
grouping), so string matching is impossible; set intersection is the objective,
reproducible definition (Appendix A, Q7).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .validate import FeatureAtomManifest, is_production_module


@dataclass(frozen=True)
class AtomMatch:
    """Best-match row for one GT atom."""

    gt_atom_id: str
    ai_atom_id: str | None  # None when no AI atom shares any file
    intersection: list[str]  # shared files (sorted)
    ai_files: list[str]  # full file list of the matched AI atom
    correct_count: int  # GT production files in the intersection


@dataclass(frozen=True)
class ComparisonResult:
    accuracy: float  # correct_count / gt_production_total (0.0 when GT empty)
    correct_count: int
    gt_production_total: int
    ai_missed: list[str]  # GT production files absent from every AI atom
    ai_extra: list[str]  # AI files absent from the GT — NOT counted in accuracy
    gt_atoms: int
    ai_atoms: int
    matches: list[AtomMatch] = field(default_factory=list)


def _best_match(gt_files: set[str], ai_atoms: list) -> tuple:
    """argmax |gt_files ∩ ai.files|; tie → first AI atom (deterministic)."""
    best: tuple[int, int] | None = None  # (intersection size, ai index)
    best_atom = None
    for idx, atom in enumerate(ai_atoms):
        inter = len(gt_files & set(atom.files))
        if best is None or inter > best[0] or (inter == best[0] and idx < best[1]):
            best = (inter, idx)
            best_atom = atom
    return best, best_atom


def compare_to_ground_truth(
    ai_manifest: FeatureAtomManifest, gt_manifest: FeatureAtomManifest
) -> ComparisonResult:
    """Compare the AI-produced manifest to the ground truth (hand-written)."""
    gt_atoms = gt_manifest.atoms
    ai_atoms = ai_manifest.atoms
    gt_all = {f for atom in gt_atoms for f in atom.files}
    ai_all = {f for atom in ai_atoms for f in atom.files}

    gt_production = [
        f for atom in gt_atoms for f in atom.files if is_production_module(f)
    ]
    gt_production_set = set(gt_production)

    matches: list[AtomMatch] = []
    for gt in gt_atoms:
        gt_files = set(gt.files)
        best, best_atom = _best_match(gt_files, ai_atoms)
        if best is None or best[0] == 0:
            matches.append(
                AtomMatch(
                    gt_atom_id=gt.id,
                    ai_atom_id=None,
                    intersection=[],
                    ai_files=[],
                    correct_count=0,
                )
            )
            continue
        intersection = sorted(gt_files & set(best_atom.files))
        correct = sum(1 for f in intersection if f in gt_production_set)
        matches.append(
            AtomMatch(
                gt_atom_id=gt.id,
                ai_atom_id=best_atom.id,
                intersection=intersection,
                ai_files=list(best_atom.files),
                correct_count=correct,
            )
        )

    correct_count = sum(m.correct_count for m in matches)
    gt_total = len(gt_production)
    accuracy = (correct_count / gt_total) if gt_total else 0.0
    return ComparisonResult(
        accuracy=accuracy,
        correct_count=correct_count,
        gt_production_total=gt_total,
        ai_missed=sorted(f for f in gt_production_set if f not in ai_all),
        ai_extra=sorted(f for f in ai_all if f not in gt_all),
        gt_atoms=len(gt_atoms),
        ai_atoms=len(ai_atoms),
        matches=matches,
    )
