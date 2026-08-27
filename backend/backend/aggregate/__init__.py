"""AI aggregation package (issue #11).

Public surface: :func:`run_aggregation` — the single orchestration seam
(implemented in :mod:`aggregate.runner`). Design contract (U1/D5/D9):
aggregation is pure AI — the cloud API is the sole authority for the manifest;
the local model is a learning role only; on AI failure the CLI reports
explicitly and never falls back to the hand-maintained manifest.
"""

from .runner import (
    EXIT_AGGREGATION_FAILED,
    EXIT_FATAL,
    EXIT_OK,
    RETRYABLE_MESSAGE,
    AggregationFailed,
    FatalError,
    run_aggregation,
)

__all__ = [
    "EXIT_OK",
    "EXIT_FATAL",
    "EXIT_AGGREGATION_FAILED",
    "RETRYABLE_MESSAGE",
    "FatalError",
    "AggregationFailed",
    "run_aggregation",
]
