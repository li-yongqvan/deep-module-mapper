"""Orchestration of AI aggregation (S5) — the single highest seam.

scan → digest → api provider (DeepSeek, **sole authority**) → validate →
compare → write → report. Failure is explicit and retryable (exit 2,
:data:`RETRYABLE_MESSAGE`); the hand-maintained manifest is never a fallback
and **no manifest is written** on failure (D9/U1, INV5).

The local model's learning role (S6, D14/U6) plugs into the authoritative flow
below and never blocks or replaces it (INV16).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

from parser import scan_codebase

from . import digest, prompt
from .compare import compare_to_ground_truth
from .config import EnvConfig
from .providers import (
    Provider,
    get_api_provider,
    retry_with_repair,
)
from .report import build_report, write_report
from .validate import (
    FeatureAtomManifest,
    is_production_module,
    validate_manifest,
)

# Exit codes (§5.8): 0 = authoritative manifest written; 1 = fatal config or
# input error (bad path, scan failure, missing LLM_API_KEY); 2 = AI aggregation
# failed after retries (retryable, no fallback).
EXIT_OK = 0
EXIT_FATAL = 1
EXIT_AGGREGATION_FAILED = 2

# Explicit, non-silent failure text (U5/D13, INV15).
RETRYABLE_MESSAGE = "AI 聚合失败，可重试"


class FatalError(Exception):
    """Fatal config/input error → exit 1 (not retryable, no degradation)."""


class AggregationFailed(Exception):
    """AI aggregation failed after retries → exit 2. Never falls back to the
    hand-maintained manifest and never writes any manifest (U1/D9, INV5)."""


def _make_validator(module_ids: list[str]) -> Callable[[str], str | None]:
    """Strong check for :func:`providers.retry_with_repair` (S4 swap-in):
    ``None`` when the text is a valid drop-in manifest, else a human-readable
    failure description that becomes the repair prompt's error text."""

    def check(text: str) -> str | None:
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as exc:
            return f"输出不是合法 JSON: {exc}"
        if not isinstance(obj, dict):
            return "输出必须是 JSON 对象"
        result = validate_manifest(obj, module_ids)
        return None if result.ok else "；".join(result.errors)

    return check


def _resolve_output(repo: Path, output: str | Path | None) -> Path:
    # R6: the default output lives inside the scanned repo, at the same place
    # the hand-written manifest lived (drop-in).
    if output is not None:
        return Path(output)
    return repo / "frontend/src/manifest/feature-atoms.json"


def _resolve_report(output_path: Path, report: str | Path | None) -> Path:
    return Path(report) if report is not None else output_path.parent / "feature-atoms.report.json"


def _load_ground_truth(
    compare: str | Path | None,
    output_path: Path,
    dry_run: bool,
    warnings: list[str],
) -> tuple[FeatureAtomManifest | None, str | None]:
    """Ground truth for the quality comparison (D11/U2). ``--compare`` wins;
    otherwise the existing ``--output`` content (i.e. the current hand-written
    manifest) is used. Unreadable/broken GT is a warning, never a crash.
    """
    candidates: list[tuple[str, Path]] = []
    if compare is not None:
        candidates.append(("--compare", Path(compare)))
    elif not dry_run and output_path.exists():
        candidates.append(("--output 既有内容", output_path))

    for label, path in candidates:
        if not path.exists():
            warnings.append(f"ground truth（{label}）不存在: {path}")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            gt = FeatureAtomManifest.model_validate(data)
            return gt, str(path)
        except Exception as exc:  # noqa: BLE001 — malformed GT is a warning
            warnings.append(f"ground truth（{label}）无法解析: {exc}")
    return None, None


def _write_manifest(manifest: FeatureAtomManifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)  # F9: repo may lack the dir
    path.write_text(
        json.dumps(manifest.model_dump(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _quality_dict(comparison: Any, gt_source: str) -> dict:
    return {
        "groundTruthPath": gt_source,
        "accuracy": comparison.accuracy,
        "correctCount": comparison.correct_count,
        "gtProductionTotal": comparison.gt_production_total,
        "aiMissed": comparison.ai_missed,
        "aiExtra": comparison.ai_extra,
        "gtAtoms": comparison.gt_atoms,
        "aiAtoms": comparison.ai_atoms,
        "matches": [
            {
                "gtAtomId": m.gt_atom_id,
                "aiAtomId": m.ai_atom_id,
                "intersection": m.intersection,
                "correctCount": m.correct_count,
            }
            for m in comparison.matches
        ],
    }


def _manifest_dict(
    manifest: FeatureAtomManifest | None,
    *,
    written: bool,
    path: Path | None,
    coverage: Any = None,
) -> dict:
    if manifest is None:
        return {"written": written}
    return {
        "written": written,
        "source": "ai",
        "path": str(path) if path is not None else None,
        "atomCount": len(manifest.atoms),
        "coverage": {
            "productionFiles": len(coverage.production_files),
            "assigned": len(coverage.assigned),
            "missing": coverage.missing,
            "duplicated": coverage.duplicated,
            "noiseFiles": coverage.noise_files,
            "unknownFiles": coverage.unknown_files,
        },
    }


def _repo_dict(repo: Path, module_ids: list[str]) -> dict:
    return {
        "path": str(repo),
        "modulesScanned": len(module_ids),
        "productionModules": sum(1 for m in module_ids if is_production_module(m)),
    }


def run_aggregation(
    repo_path: str | Path,
    config: EnvConfig,
    *,
    api_provider: Provider | None = None,
    local_provider: Provider | None = None,
    output: str | Path | None = None,
    compare: str | Path | None = None,
    dry_run: bool = False,
    skip_local: bool = False,
    training_log: str | Path | None = None,
    report: str | Path | None = None,
) -> int:
    """Run AI aggregation and return an exit code per §5.8.

    ``api_provider``/``local_provider`` are the injection seam (tests inject
    fakes; production uses :func:`get_api_provider`/:func:`get_local_provider`).
    Raises :class:`FatalError` (exit 1) on config/input errors and
    :class:`AggregationFailed` (exit 2) when the AI path fails.
    """
    repo = Path(repo_path)
    if not repo.is_dir():
        raise FatalError(f"仓库路径不存在或不是目录: {repo}")
    if not config.has_api_key:
        raise FatalError(
            "缺少 LLM_API_KEY 环境变量——DeepSeek 是唯一权威聚合来源，无法继续（退出码 1，不降级）"
        )

    output_path = _resolve_output(repo, output)
    report_path = _resolve_report(output_path, report)
    warnings: list[str] = []

    api = api_provider if api_provider is not None else get_api_provider(config)

    # 1. scan — a scan failure is a fatal input error (exit 1), not retryable.
    try:
        graph = scan_codebase(str(repo))
    except Exception as exc:  # noqa: BLE001 — parser failures are input errors
        raise FatalError(f"扫描失败: {exc}") from exc
    module_ids = [m["id"] for m in graph.get("modules", [])]

    # 2. digest for the API — far larger budget than the local one (R2/F3):
    #    the authority must not be limited by the local 8B window.
    api_digest = digest.build_digest(
        graph, repo, total_chars=digest.API_TOTAL_DIGEST_CHARS
    )
    if api_digest.truncation != digest.TRUNCATION_NONE:
        warnings.append(f"API digest 截断级别: {api_digest.truncation}")  # INV14

    # 3. authoritative call with retry/repair (D8). The validator doubles as
    #    the repair check so any invalid output is repaired once.
    api_result = retry_with_repair(
        api,
        prompt.SYSTEM_PROMPT,
        prompt.build_user_prompt(api_digest.text),
        check=_make_validator(module_ids),
        repair_user=prompt.render_repair_prompt,
    )
    api_info = {"ok": api_result.ok, "attempts": api_result.attempts, "error": api_result.error}

    if not api_result.ok or api_result.text is None:
        _fail_and_raise(
            repo_path=repo,
            module_ids=module_ids,
            report_path=report_path,
            api_info=api_info,
            local_info=None,
            warnings=warnings,
            error=api_result.error or "未知错误",
            dry_run=dry_run,
        )

    # 4. validate (belt-and-braces: the repair check already validated it).
    manifest = json.loads(api_result.text)
    validation = validate_manifest(manifest, module_ids)
    if not validation.ok or validation.manifest is None:
        _fail_and_raise(
            repo_path=repo,
            module_ids=module_ids,
            report_path=report_path,
            api_info=api_info,
            local_info=None,
            warnings=warnings,
            error="；".join(validation.errors),
            dry_run=dry_run,
        )
    authoritative = validation.manifest

    # 5. quality comparison vs ground truth (core deliverable, D11/U2).
    gt_manifest, gt_source = _load_ground_truth(compare, output_path, dry_run, warnings)
    comparison = (
        compare_to_ground_truth(authoritative, gt_manifest) if gt_manifest is not None else None
    )

    # 6. write the authoritative manifest (unless dry-run) — only the API
    #    result ever lands here (INV4: the local model never writes it).
    written = False
    if not dry_run:
        try:
            _write_manifest(authoritative, output_path)
        except OSError as exc:
            raise FatalError(f"无法写入 manifest: {exc}") from exc
        written = True

    # 7. report (status=ok).
    report_dict = build_report(
        status="ok",
        repo=_repo_dict(repo, module_ids),
        manifest=_manifest_dict(
            authoritative, written=written, path=output_path, coverage=validation.coverage
        ),
        quality=_quality_dict(comparison, gt_source) if comparison else None,
        providers={"api": api_info, "local": None},
        warnings=warnings,
    )
    if not dry_run:
        try:
            write_report(report_dict, report_path)
        except OSError as exc:  # report is best-effort; don't mask success
            print(f"警告：无法写入报告 {report_path}: {exc}", file=sys.stderr)

    _print_summary(authoritative, output_path, comparison, dry_run)
    return EXIT_OK


def _fail_and_raise(
    *,
    repo_path: Path,
    module_ids: list[str],
    report_path: Path,
    api_info: dict,
    local_info: dict | None,
    warnings: list[str],
    error: str,
    dry_run: bool,
) -> None:
    """Write a ``status=failed`` report (when not dry-run) and raise
    :class:`AggregationFailed` with the retryable message (D13, INV15).
    """
    report_dict = build_report(
        status="failed",
        repo=_repo_dict(repo_path, module_ids),
        manifest={"written": False},
        providers={"api": api_info, "local": local_info},
        warnings=warnings,
        error=error,
    )
    location = ""
    if not dry_run:
        try:
            write_report(report_dict, report_path)
            location = f"（报告: {report_path}）"
        except OSError as exc:
            location = f"（报告写入失败: {exc}）"
    raise AggregationFailed(f"{error}{location}")


def _print_summary(manifest: FeatureAtomManifest, output_path: Path, comparison: Any, dry_run: bool) -> None:
    """Human-readable stdout summary (dry-run prints the full manifest)."""
    if dry_run:
        print(json.dumps(manifest.model_dump(), ensure_ascii=False, indent=2))
    else:
        print(f"功能原子 manifest 已写入: {output_path}（{len(manifest.atoms)} 个原子）")
    if comparison is not None:
        print(
            f"质量对拍 accuracy={comparison.accuracy:.4f} "
            f"（{comparison.correct_count}/{comparison.gt_production_total} 正确归入）"
        )
