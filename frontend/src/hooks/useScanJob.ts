/**
 * Scan + polling state machine (design doc §5.4, audit M1).
 *
 * States: idle → scanning → done | error | jobLost | networkError | timeout
 *         scanning may also settle on `empty` when the graph has no modules (M5).
 *
 * Polling is a chained setTimeout (D13): each request schedules the next only
 * after it completes, so slow responses never stack. Transient network/5xx
 * failures are tolerated up to MAX_TRANSIENT_RETRIES; a 404 (job vanished after
 * a backend restart) settles immediately into `jobLost`.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { getGraph, getStatus, startScan, type ScanStatus } from '../api/scan';
import { ApiError } from '../api/client';
import type { Graph } from '../api/types';

export const POLL_INTERVAL_MS = 2000;
/** Tolerated transient failures before settling on networkError. */
export const MAX_TRANSIENT_RETRIES = 3;
/** Hard cap on the total polling window (30 polls × 2s). */
export const POLL_TIMEOUT_MS = 60_000;

export type ScanState =
  | { kind: 'idle' }
  | { kind: 'scanning'; jobId: string; status: ScanStatus; retries: number }
  | { kind: 'done'; jobId: string; graph: Graph }
  | { kind: 'empty'; jobId: string; graph: Graph }
  | { kind: 'error'; jobId: string; error: string; details?: string }
  | { kind: 'jobLost'; jobId: string }
  | { kind: 'networkError'; jobId: string; message: string }
  | { kind: 'timeout'; jobId: string };

export interface UseScanJobResult {
  state: ScanState;
  start: (path: string) => Promise<void>;
  cancel: () => void;
}

export function useScanJob(): UseScanJobResult {
  const [state, setState] = useState<ScanState>({ kind: 'idle' });
  // Keep timers/requests cancelable without stale closures.
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const activeRef = useRef<{ jobId: string; cancelled: boolean } | null>(null);

  const clearTimers = useCallback(() => {
    timersRef.current.forEach((t) => clearTimeout(t));
    timersRef.current = [];
  }, []);

  const schedule = useCallback((fn: () => void, ms: number) => {
    const id = setTimeout(fn, ms);
    timersRef.current.push(id);
  }, []);

  // Cancel any in-flight work on unmount.
  useEffect(() => {
    return () => {
      if (activeRef.current) activeRef.current.cancelled = true;
      clearTimers();
    };
  }, [clearTimers]);

  const cancel = useCallback(() => {
    if (activeRef.current) activeRef.current.cancelled = true;
    clearTimers();
  }, [clearTimers]);

  const start = useCallback(
    async (path: string) => {
      cancel();
      try {
        const { jobId } = await startScan(path);
        const run = { jobId, cancelled: false };
        activeRef.current = run;
        setState({ kind: 'scanning', jobId, status: 'pending', retries: 0 });
        pollOnce(run, 0, 0);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setState({ kind: 'networkError', jobId: '', message });
      }
    },
    [cancel],
  );

  // One polling step. `attempt` = total attempts, `retries` = consecutive
  // transient failures so far.
  function pollOnce(
    run: { jobId: string; cancelled: boolean },
    attempt: number,
    retries: number,
  ) {
    if (run.cancelled) return;
    const { jobId } = run;
    const elapsed = attempt * POLL_INTERVAL_MS;
    if (elapsed >= POLL_TIMEOUT_MS) {
      setState({ kind: 'timeout', jobId });
      return;
    }
    schedule(async () => {
      if (run.cancelled) return;
      try {
        const status = await getStatus(jobId);
        if (run.cancelled) return;
        if (status.status === 'done') {
          setState((s) =>
            s.kind === 'scanning' ? { ...s, status: 'done' } : s,
          );
          // Fetch graph; transient failure here retries the same way.
          try {
            const graph = await getGraph(jobId);
            if (run.cancelled) return;
            if (graph.modules.length === 0) {
              setState({ kind: 'empty', jobId, graph }); // M5
            } else {
              setState({ kind: 'done', jobId, graph });
            }
          } catch (err) {
            if (run.cancelled) return;
            const nextRetries = retries + 1;
            if (nextRetries >= MAX_TRANSIENT_RETRIES) {
              setState({
                kind: 'error',
                jobId,
                error: 'graph_fetch_failed',
                details: err instanceof Error ? err.message : String(err),
              });
            } else {
              setState((s) =>
                s.kind === 'scanning'
                  ? { ...s, status: 'running', retries: nextRetries }
                  : s,
              );
              pollOnce(run, attempt + 1, nextRetries);
            }
          }
        } else if (status.status === 'error') {
          setState({
            kind: 'error',
            jobId,
            error: status.error ?? 'scan_failed',
            details: status.details,
          });
        } else {
          // pending / running → keep polling.
          setState((s) =>
            s.kind === 'scanning'
              ? { ...s, status: status.status, retries: 0 }
              : s,
          );
          pollOnce(run, attempt + 1, 0);
        }
      } catch (err) {
        if (run.cancelled) return;
        if (err instanceof ApiError && err.isJobNotFound) {
          setState({ kind: 'jobLost', jobId }); // backend restarted
          return;
        }
        const nextRetries = retries + 1;
        if (nextRetries >= MAX_TRANSIENT_RETRIES) {
          setState({
            kind: 'networkError',
            jobId,
            message: err instanceof Error ? err.message : String(err),
          });
        } else {
          pollOnce(run, attempt + 1, nextRetries);
        }
      }
    }, POLL_INTERVAL_MS);
  }

  return { state, start, cancel };
}
