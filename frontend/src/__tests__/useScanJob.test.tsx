/**
 * Integration-style tests for the scan + polling state machine (design doc
 * §5.4 / §8.2, audit M1). MSW (from src/test/setup.ts) mocks the backend.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { server } from '../test/setup';
import {
  useScanJob,
  POLL_INTERVAL_MS,
  MAX_TRANSIENT_RETRIES,
  type ScanState,
} from '../hooks/useScanJob';
import type { Graph } from '../api/types';

const API = 'http://127.0.0.1:8123';

function sampleGraph(): Graph {
  return {
    modules: [
      { id: 'pkg/a.py', path: 'pkg/a.py', ports: [{ kind: 'function', name: 'fa', line: 30, signature: 'fa()', params: [] }] },
    ],
    ports: [{ kind: 'function', name: 'fa', line: 30, signature: 'fa()', params: [], moduleId: 'pkg/a.py' }],
    edges: [],
    externalModules: [],
    diagnostics: [],
  };
}

/** Drive the state machine forward one poll interval (chained setTimeout). */
async function advancePoll(): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS);
  });
}

describe('useScanJob', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('reaches done with the graph on the happy path', async () => {
    // First status poll returns running, then done.
    let calls = 0;
    server.use(
      http.post(`${API}/api/scan`, () => HttpResponse.json({ jobId: 'job-1' })),
      http.get(`${API}/api/scan/:jobId/status`, () => {
        calls += 1;
        return HttpResponse.json({ status: calls === 1 ? 'running' : 'done' });
      }),
      http.get(`${API}/api/scan/:jobId/graph`, () =>
        HttpResponse.json(sampleGraph()),
      ),
    );

    const { result } = renderHook(() => useScanJob());
    await act(async () => {
      await result.current.start('pkg');
    });
    expect(result.current.state.kind).toBe('scanning');

    await advancePoll(); // running -> schedules next
    expect(result.current.state.kind).toBe('scanning');
    await advancePoll(); // done -> fetch graph
    await waitFor(() => expect(result.current.state.kind).toBe('done'));
    const state = result.current.state as Extract<ScanState, { kind: 'done' }>;
    expect(state.graph.modules).toHaveLength(1);
  });

  it('settles on error with details when the scan fails', async () => {
    server.use(
      http.post(`${API}/api/scan`, () => HttpResponse.json({ jobId: 'job-2' })),
      http.get(`${API}/api/scan/:jobId/status`, () =>
        HttpResponse.json({ status: 'error', error: 'scan_failed', details: 'boom' }),
      ),
    );
    const { result } = renderHook(() => useScanJob());
    await act(async () => {
      await result.current.start('pkg');
    });
    await advancePoll();
    await waitFor(() => expect(result.current.state.kind).toBe('error'));
    const state = result.current.state as Extract<ScanState, { kind: 'error' }>;
    expect(state.error).toBe('scan_failed');
    expect(state.details).toBe('boom');
  });

  it('settles on jobLost when the backend reports 404 job_not_found (M1)', async () => {
    server.use(
      http.post(`${API}/api/scan`, () => HttpResponse.json({ jobId: 'job-3' })),
      http.get(`${API}/api/scan/:jobId/status`, () =>
        HttpResponse.json({ error: 'job_not_found', details: 'Job gone.' }, { status: 404 }),
      ),
    );
    const { result } = renderHook(() => useScanJob());
    await act(async () => {
      await result.current.start('pkg');
    });
    await advancePoll();
    await waitFor(() => expect(result.current.state.kind).toBe('jobLost'));
  });

  it('retries a graph fetch that fails, then settles on error (M1)', async () => {
    let graphCalls = 0;
    server.use(
      http.post(`${API}/api/scan`, () => HttpResponse.json({ jobId: 'job-4' })),
      http.get(`${API}/api/scan/:jobId/status`, () =>
        HttpResponse.json({ status: 'done' }),
      ),
      http.get(`${API}/api/scan/:jobId/graph`, () => {
        graphCalls += 1;
        if (graphCalls < MAX_TRANSIENT_RETRIES) {
          return HttpResponse.json({ error: 'scan_failed', details: 'boom' }, { status: 500 });
        }
        return HttpResponse.json({ error: 'scan_failed', details: 'boom' }, { status: 500 });
      }),
    );
    const { result } = renderHook(() => useScanJob());
    await act(async () => {
      await result.current.start('pkg');
    });
    // One status poll -> done; then MAX_TRANSIENT_RETRIES graph polls all fail.
    for (let i = 0; i < 1 + MAX_TRANSIENT_RETRIES; i++) {
      await advancePoll();
    }
    await waitFor(() => expect(result.current.state.kind).toBe('error'));
    const state = result.current.state as Extract<ScanState, { kind: 'error' }>;
    expect(state.error).toBe('graph_fetch_failed');
  });

  it('survives transient status failures and still reaches done', async () => {
    let statusCalls = 0;
    server.use(
      http.post(`${API}/api/scan`, () => HttpResponse.json({ jobId: 'job-5' })),
      http.get(`${API}/api/scan/:jobId/status`, () => {
        statusCalls += 1;
        if (statusCalls <= 2) {
          return HttpResponse.json({ error: 'boom' }, { status: 502 });
        }
        return HttpResponse.json({ status: 'done' });
      }),
      http.get(`${API}/api/scan/:jobId/graph`, () =>
        HttpResponse.json(sampleGraph()),
      ),
    );
    const { result } = renderHook(() => useScanJob());
    await act(async () => {
      await result.current.start('pkg');
    });
    // Two failed polls (retried), then a successful done poll.
    for (let i = 0; i < 3; i++) {
      await advancePoll();
    }
    await waitFor(() => expect(result.current.state.kind).toBe('done'));
  });

  it('settles on empty when the graph has no modules (M5)', async () => {
    server.use(
      http.post(`${API}/api/scan`, () => HttpResponse.json({ jobId: 'job-6' })),
      http.get(`${API}/api/scan/:jobId/status`, () =>
        HttpResponse.json({ status: 'done' }),
      ),
      http.get(`${API}/api/scan/:jobId/graph`, () =>
        HttpResponse.json({ modules: [], ports: [], edges: [], externalModules: [], diagnostics: [] }),
      ),
    );
    const { result } = renderHook(() => useScanJob());
    await act(async () => {
      await result.current.start('pkg');
    });
    await advancePoll();
    await waitFor(() => expect(result.current.state.kind).toBe('empty'));
  });
});
