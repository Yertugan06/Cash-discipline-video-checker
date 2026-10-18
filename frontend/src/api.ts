import type { AcceptedJob, Job } from './contract.ts';

/**
 * Thin typed API client. The API key is passed in by the caller on every
 * request and is never read from or written to any browser storage here.
 */
async function request<T>(path: string, key: string, init: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { ...init.headers, 'X-API-Key': key },
    credentials: 'omit',
    redirect: 'error',
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === 'string') detail = body.detail;
    } catch {
      // Proxies may return HTML errors; preserve the HTTP status in that case.
    }
    throw new Error(`HTTP ${response.status}: ${detail}`);
  }
  return response.json() as Promise<T>;
}

/** POST /api/v1/analyze (task.md §10). */
export function uploadVideo(file: File, key: string, signal?: AbortSignal): Promise<AcceptedJob> {
  const body = new FormData();
  body.append('file', file);
  return request('/api/v1/analyze', key, { method: 'POST', body, signal });
}

/** GET /api/v1/jobs/{job_id} (task.md §10). */
export function getJob(jobId: string, key: string, signal?: AbortSignal): Promise<Job> {
  return request(`/api/v1/jobs/${encodeURIComponent(jobId)}`, key, { signal });
}

/** m:ss, truncated like a player's clock and like backend/knowledge.py clock(): 68.9 -> "1:08". */
export function timecode(seconds: number): string {
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}

/** Raw seconds, one decimal place, e.g. 68.2 -> "68.2 s". */
export function seconds(value: number): string {
  return `${value.toFixed(1)} s`;
}
