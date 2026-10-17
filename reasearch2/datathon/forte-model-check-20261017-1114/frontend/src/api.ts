import type { AcceptedJob, Job } from './contract.ts';

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
      const body = await response.json() as { detail?: unknown };
      if (typeof body.detail === 'string') detail = body.detail;
    } catch {
      // Proxies may return HTML errors; preserve the HTTP status in that case.
    }
    throw new Error(`HTTP ${response.status}: ${detail}`);
  }
  return response.json() as Promise<T>;
}

export function uploadVideo(file: File, key: string, signal?: AbortSignal): Promise<AcceptedJob> {
  const body = new FormData();
  body.append('file', file);
  return request('/api/v1/analyze', key, { method: 'POST', body, signal });
}

export function getJob(jobId: string, key: string, signal?: AbortSignal): Promise<Job> {
  return request(`/api/v1/jobs/${encodeURIComponent(jobId)}`, key, { signal });
}

export function timecode(seconds: number): string {
  const tenths = Math.round(seconds * 10);
  return `${Math.floor(tenths / 600)}:${((tenths % 600) / 10).toFixed(1).padStart(4, '0')}`;
}
