import assert from 'node:assert/strict';
import { test } from 'node:test';
import { getJob, timecode, seconds, uploadVideo } from './api.ts';

test('uses the jury endpoints and API key; preserves multipart field and HTTP errors', async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return new Response(
      JSON.stringify(
        url.endsWith('/analyze') ? { job_id: 'a' } : { job_id: 'a', status: 'processing' },
      ),
      { headers: { 'Content-Type': 'application/json' } },
    );
  };
  try {
    const file = new File(['video'], 'Х-1.mov');
    assert.deepEqual(await uploadVideo(file, 'key'), { job_id: 'a' });
    assert.equal(calls[0].url, '/api/v1/analyze');
    assert.equal(calls[0].init.body.get('file').name, 'Х-1.mov');
    assert.equal(calls[0].init.headers['X-API-Key'], 'key');
    assert.equal(calls[0].init.redirect, 'error');
    assert.equal((await getJob('a', 'key')).status, 'processing');
    assert.equal(calls[1].url, '/api/v1/jobs/a');
    // The key never appears in the URL, only in the X-API-Key header.
    assert.ok(!calls[1].url.includes('key'));
    globalThis.fetch = async () => new Response('{"detail":"Invalid key"}', { status: 401 });
    await assert.rejects(() => getJob('a', 'wrong'), /HTTP 401: Invalid key/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('formats timecodes with minute rollover and raw seconds', () => {
  assert.equal(timecode(0), '0:00');
  assert.equal(timecode(68.2), '1:08');
  assert.equal(timecode(59.99), '0:59');
  assert.equal(seconds(44.2), '44.2 s');
});
