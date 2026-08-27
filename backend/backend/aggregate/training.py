"""Local-model learning flow (S6, D14/U6).

The local model is a **learning role only**: it produces its own attempt from
the local (12K) digest, compares it against the API's authoritative answer, and
reflects on the difference. Its answer never becomes the authoritative manifest
(INV4), and any local failure never blocks or changes the authoritative path or
exit code (INV16).

Training artifacts (INV10): a sidecar ``feature-atoms.local.json`` (authoritative
path never reads it) and an append-only JSONL ``--training-log`` with three
roles per run — ``api`` (the authoritative answer), ``local`` (the local attempt
with the digest it actually saw, F3), ``learn`` (the reflection, only when both
sides succeeded).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import digest, prompt
from .providers import Provider
from .validate import validate_manifest


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_manifest(text: str, module_ids: list[str]) -> tuple[dict | None, str | None]:
    """Parse + validate local output → (parsed manifest dict, error string)."""
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"输出不是合法 JSON: {exc}"
    if not isinstance(obj, dict):
        return None, "输出必须是 JSON 对象"
    result = validate_manifest(obj, module_ids)
    if not result.ok:
        return None, "；".join(result.errors)
    return result.manifest.model_dump(), None


def api_record(
    *,
    run_id: str,
    repo: str,
    model: str,
    prompt_text: str,
    raw_output: str,
    parsed: dict | None,
    ok: bool,
) -> dict:
    """The authoritative answer — the training log's reference row."""
    return {
        "ts": _now(),
        "run_id": run_id,
        "repo": repo,
        "role": "api",
        "model": model,
        "prompt": prompt_text,
        "raw_output": raw_output,
        "parsed": parsed,
        "ok": ok,
    }


def local_record(
    *,
    run_id: str,
    repo: str,
    model: str,
    prompt_text: str,
    raw_output: str,
    parsed: dict | None,
    ok: bool,
    api_reference: str,
) -> dict:
    """The local attempt — ``prompt_text`` carries the digest it actually saw."""
    return {
        "ts": _now(),
        "run_id": run_id,
        "repo": repo,
        "role": "local",
        "model": model,
        "prompt": prompt_text,
        "raw_output": raw_output,
        "parsed": parsed,
        "ok": ok,
        "api_reference": api_reference,
    }


def learn_record(
    *,
    run_id: str,
    repo: str,
    model: str,
    prompt_text: str,
    local_output: str,
    api_output: str,
    raw_output: str,
    ok: bool,
) -> dict:
    """The compare-and-reflect learning step (D14)."""
    return {
        "ts": _now(),
        "run_id": run_id,
        "repo": repo,
        "role": "learn",
        "model": model,
        "prompt": prompt_text,
        "input": {"local_output": local_output, "api_output": api_output},
        "raw_output": raw_output,
        "ok": ok,
    }


@dataclass
class LocalLearningResult:
    ok: bool  # local attempt produced a valid manifest
    local_ok: bool
    learn_ok: bool | None  # None when no learn step ran
    local_error: str | None
    local_attempts: int
    sidecar_path: str | None
    records: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def append_training_log(path: Path, records: list[dict]) -> None:
    """Append JSONL records (UTF-8, never clobbers existing content, INV10)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_local_sidecar(path: Path, data: dict) -> None:
    """Persist the sidecar (authoritative path never reads it, INV4)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def run_local_learning(
    *,
    repo: str,
    graph: dict,
    module_ids: list[str],
    local: Provider,
    api_raw: str,
    run_id: str,
    training_log: Path | None,
    sidecar: Path,
    dry_run: bool,
    api_record_row: dict | None,
) -> LocalLearningResult:
    """Best-effort local attempt + optional learn reflection (D14/U6).

    Always runs the local attempt and records it; the learn reflection runs
    only when the local attempt is usable AND the API answer exists. Returns a
    result the runner folds into the report; never raises on local failure.
    """
    warnings: list[str] = []
    records = [api_record_row] if api_record_row is not None else []

    local_digest = digest.build_digest(graph, None, total_chars=digest.TOTAL_DIGEST_CHARS)
    if local_digest.truncation != digest.TRUNCATION_NONE:
        warnings.append(f"local digest 截断级别: {local_digest.truncation}")

    user_prompt = prompt.build_user_prompt(local_digest.text)
    result = local.generate(prompt.SYSTEM_PROMPT, user_prompt)
    local_ok = result.ok and result.text is not None
    text = result.text or ""
    parsed, parse_err = _parse_manifest(text, module_ids) if text else (None, "无输出")

    records.append(
        local_record(
            run_id=run_id,
            repo=repo,
            model=local.name,
            prompt_text=user_prompt,
            raw_output=text,
            parsed=parsed,
            ok=local_ok and parse_err is None,
            api_reference=api_raw,
        )
    )

    # Learn reflection — only when both sides produced usable output.
    learn_ok: bool | None = None
    if local_ok and parse_err is None and api_raw:
        learn_user = prompt.render_learn_prompt(text, api_raw)
        learn = local.generate(prompt.SYSTEM_PROMPT, learn_user)
        learn_ok = learn.ok and learn.text is not None
        records.append(
            learn_record(
                run_id=run_id,
                repo=repo,
                model=local.name,
                prompt_text=learn_user,
                local_output=text,
                api_output=api_raw,
                raw_output=learn.text or "",
                ok=bool(learn_ok),
            )
        )

    sidecar_path: str | None = None
    if not dry_run:
        sidecar_path = str(sidecar)
        try:
            write_local_sidecar(
                sidecar,
                {
                    "ok": bool(local_ok and parse_err is None),
                    "manifest": parsed,
                    "error": parse_err,
                    "raw_output": text,
                },
            )
        except OSError as exc:
            warnings.append(f"本地 sidecar 写入失败: {exc}")
            sidecar_path = None

    if training_log is not None and not dry_run:
        try:
            append_training_log(training_log, records)
        except OSError as exc:
            warnings.append(f"训练日志写入失败: {exc}")

    return LocalLearningResult(
        ok=bool(local_ok and parse_err is None),
        local_ok=bool(local_ok),
        learn_ok=learn_ok,
        local_error=parse_err or result.error,
        local_attempts=result.attempts,
        sidecar_path=sidecar_path,
        records=records,
        warnings=warnings,
    )
