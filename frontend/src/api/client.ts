/**
 * Backend base URL. Vite auto-exposes `VITE_`-prefixed env vars via
 * `import.meta.env`; the `??` fallback keeps local dev working with zero config.
 * (Audit m7: no extra vite.config.ts wiring is needed for this.)
 */
const BASE_URL: string =
  import.meta.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8123';

/** Error raised when the backend returns a non-2xx response. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: string;

  constructor(status: number, code: string, details?: string) {
    super(details ? `${code}: ${details}` : code);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** True when the backend reports the scan job no longer exists (e.g. restart). */
  get isJobNotFound(): boolean {
    return this.status === 404 && this.code === 'job_not_found';
  }
}

/**
 * Thin fetch wrapper: sets JSON headers, parses the unified `{error, details}`
 * error envelope (backend/app.py `_error_response`), and surfaces network
 * failures as readable ApiErrors.
 */
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    });
  } catch (err) {
    throw new ApiError(0, 'network_error', String(err));
  }

  if (!res.ok) {
    let code = `http_${res.status}`;
    let details: string | undefined;
    try {
      const body = await res.json();
      if (typeof body?.error === 'string') code = body.error;
      if (typeof body?.details === 'string') details = body.details;
    } catch {
      // non-JSON error body; keep the http_* fallback code
    }
    throw new ApiError(res.status, code, details);
  }
  return (await res.json()) as T;
}
