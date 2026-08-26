/**
 * Backend scan flow API (issue #5 contract, backend/backend/app.py).
 * All data transformations happen on the client; the backend API is untouched.
 */
import { api } from './client';
import type { Graph } from './types';

export interface ScanResponse {
  jobId: string;
}

export type ScanStatus = 'pending' | 'running' | 'done' | 'error';

export interface StatusResponse {
  status: ScanStatus;
  error?: string;
  details?: string;
}

/** POST /api/scan — start a background scan. */
export function startScan(path: string): Promise<ScanResponse> {
  return api<ScanResponse>('/api/scan', {
    method: 'POST',
    body: JSON.stringify({ path }),
  });
}

/** GET /api/scan/:jobId/status — poll scan progress. */
export function getStatus(jobId: string): Promise<StatusResponse> {
  return api<StatusResponse>(`/api/scan/${jobId}/status`);
}

/** GET /api/scan/:jobId/graph — fetch the Graph JSON once status is done. */
export function getGraph(jobId: string): Promise<Graph> {
  return api<Graph>(`/api/scan/${jobId}/graph`);
}
