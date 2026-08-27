"""AI aggregation package (issue #11).

Public surface: :func:`run_aggregation` — the single orchestration seam.
S1 skeleton: input validation + failure semantics only. The real pipeline
(scan → digest → providers → validate → compare → write → report) lands in S5.

Design contract (U1/D5/D9): aggregation is pure AI. The cloud API is the sole
authority for the manifest; the local model is a learning role only. On AI
failure the CLI reports explicitly and never falls back to the hand-maintained
manifest.
"""

from __future__ import annotations

from pathlib import Path

from .config import EnvConfig
from .providers import Provider, ProviderResult

# Exit codes (§5.8): 0 = authoritative manifest written; 1 = fatal config or
# input error (bad path, scan failure, missing LLM_API_KEY); 2 = AI aggregation
# failed after retries (retryable, no fallback to the hand-maintained manifest).
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


def run_aggregation(
    repo_path: str | Path,
    config: EnvConfig,
    *,
    api_provider: Provider | None = None,
    local_provider: Provider | None = None,
) -> int:
    """Validate inputs and run AI aggregation (skeleton in S1).

    Returns an exit code per §5.8. ``api_provider``/``local_provider`` are the
    injection seam — the highest seam of the whole feature (S5 wires real
    providers via ``get_provider()``; tests inject fakes).
    """
    repo = Path(repo_path)
    if not repo.is_dir():
        raise FatalError(f"仓库路径不存在或不是目录: {repo}")
    if not config.has_api_key:
        raise FatalError(
            "缺少 LLM_API_KEY 环境变量——DeepSeek 是唯一权威聚合来源，无法继续（退出码 1，不降级）"
        )

    # S1 骨架：真实聚合（scan → digest → providers → validate → compare →
    # write → report）在 S5 接入。此处显式失败，保持退出码语义诚实——
    # 不给假成功，也不回退手写 manifest。
    raise AggregationFailed("聚合流程尚未实现（S1 骨架阶段）")
