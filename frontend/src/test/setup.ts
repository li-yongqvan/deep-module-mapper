/**
 * Vitest setup (design doc §5.2 M6 / audit m3).
 *  - Extends Jest-DOM matchers.
 *  - Manages the MSW node server lifecycle so every network request is mocked.
 */
import '@testing-library/jest-dom/vitest';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

// Default handlers used across tests; individual tests can extend with
// `server.use(...)`. `onUnhandledRequest: 'error'` guarantees every request is
// explicitly handled (audit m3).
export const server = setupServer(
  // POST /api/scan
  http.post('*/api/scan', () => HttpResponse.json({ jobId: 'test-job' })),
  // GET /api/scan/:jobId/status — default: done immediately.
  http.get('*/api/scan/:jobId/status', () =>
    HttpResponse.json({ status: 'done' }),
  ),
  // GET /api/scan/:jobId/graph — default: minimal empty graph (M5).
  http.get('*/api/scan/:jobId/graph', () =>
    HttpResponse.json({
      modules: [],
      ports: [],
      edges: [],
      externalModules: [],
      diagnostics: [],
    }),
  ),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
