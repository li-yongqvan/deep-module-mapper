"""Validation of the AI manifest (S4).

Drop-in shape is enforced by pydantic with ``extra="forbid"`` (INV6) plus six
semantic rules that mirror the frontend test invariants (T12/T13):

1. atom ``id`` unique
2. fields non-empty (pydantic ``min_length``)
3. no file appears in more than one atom
4. every ``files`` entry is a real module id (no fabricated paths, INV2)
5. the manifest never names ``/tests/`` or ``/fixtures/`` files (INV3)
6. C2 coverage: every production module (non-noise, non-``__init__``) appears
   exactly once; ``__init__.py`` files are optional.

The shared noise/init predicates live here so digest, validate, compare and the
runner all agree on what counts as production (single source of truth).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]

# Same marker set as the frontend's isNoiseLike (featureAtoms.test.ts:13).
NOISE_MARKERS = ("/tests/", "/fixtures/")


def is_noise_module(module_id: str) -> bool:
    return any(marker in module_id for marker in NOISE_MARKERS)


def is_init_module(module_id: str) -> bool:
    return module_id.endswith("__init__.py")


def is_production_module(module_id: str) -> bool:
    """C2 set: the modules the manifest must cover exactly once."""
    return not is_noise_module(module_id) and not is_init_module(module_id)


class FeatureAtom(BaseModel):
    """One functional atom — the drop-in contract shape (issue #11, INV6)."""

    model_config = ConfigDict(extra="forbid")

    id: NonEmptyStr
    name: NonEmptyStr
    description: NonEmptyStr
    files: list[NonEmptyStr] = Field(min_length=1)


class FeatureAtomManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    atoms: list[FeatureAtom]


@dataclass
class Coverage:
    """Per-file coverage facts over the C2 production set."""

    production_files: list[str]  # sorted C2 set (non-noise, non-init)
    assigned: list[str]  # production files appearing exactly once
    missing: list[str]  # production files in no atom (rule 6 failure)
    duplicated: list[str]  # files appearing in more than one atom
    noise_files: list[str]  # manifest entries that are test/fixture paths
    unknown_files: list[str]  # manifest entries that are not real module ids


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str]
    manifest: FeatureAtomManifest | None  # set only when the shape parses
    coverage: Coverage | None = None  # set only when the shape parses


def validate_manifest(manifest: dict, module_ids: list[str]) -> ValidationResult:
    """Validate an AI-produced manifest against the real module set.

    ``ok=False`` when the shape is broken or any rule fails; ``errors`` is a
    human-readable list that doubles as the repair-feedback text. ``manifest``
    is populated only when the shape is a valid drop-in.
    """
    module_set = set(module_ids)
    try:
        parsed = FeatureAtomManifest.model_validate(manifest)
    except ValidationError as exc:
        return ValidationResult(
            ok=False,
            errors=[f"形状不合法（drop-in 契约）: {exc}"],
            manifest=None,
        )

    errors: list[str] = []

    # Rule 1: unique atom ids.
    seen: dict[str, int] = {}
    for atom in parsed.atoms:
        seen[atom.id] = seen.get(atom.id, 0) + 1
    dup_ids = sorted(i for i, n in seen.items() if n > 1)
    if dup_ids:
        errors.append(f"原子 id 重复: {dup_ids}")

    # Rules 3/4/5: file-level checks over the full file multiset.
    counts: dict[str, int] = {}
    for atom in parsed.atoms:
        for f in atom.files:
            counts[f] = counts.get(f, 0) + 1

    duplicated = sorted(f for f, n in counts.items() if n > 1)
    if duplicated:
        errors.append(f"文件出现在多个原子: {duplicated}")

    unknown_files = sorted(f for f in counts if f not in module_set)
    if unknown_files:
        errors.append(f"manifest 包含非真实模块 id: {unknown_files}")

    noise_files = sorted(f for f in counts if is_noise_module(f))
    if noise_files:
        errors.append(f"manifest 不得命名测试/夹具文件: {noise_files}")

    # Rule 6: C2 coverage — every production module exactly once.
    production = sorted(m for m in module_set if is_production_module(m))
    assigned = sorted(f for f in production if counts.get(f, 0) == 1)
    missing = sorted(f for f in production if f not in counts)
    if missing:
        errors.append(f"C2 覆盖缺失: {missing}")

    coverage = Coverage(
        production_files=production,
        assigned=assigned,
        missing=missing,
        duplicated=duplicated,
        noise_files=noise_files,
        unknown_files=unknown_files,
    )
    return ValidationResult(
        ok=not errors,
        errors=errors,
        manifest=parsed,
        coverage=coverage,
    )
