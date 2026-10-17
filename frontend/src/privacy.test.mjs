import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const src = (name) => readFileSync(fileURLToPath(new URL(name, import.meta.url)), 'utf8');

test('the API key is never persisted to browser storage, a cookie or the URL', () => {
  for (const file of ['./App.tsx', './api.ts']) {
    const text = src(file);
    for (const forbidden of [/\blocalStorage\s*[.[]/, /\bsessionStorage\s*[.[]/, /document\.cookie\s*=/]) {
      assert.doesNotMatch(text, forbidden, `${file} must not use ${forbidden}`);
    }
  }
});

test('the upload/job-status requests send the key only in the X-API-Key header, not the URL', () => {
  const text = src('./api.ts');
  assert.match(text, /'X-API-Key':\s*key/);
  assert.doesNotMatch(text, /\/api\/v1\/analyze\?.*key/);
  assert.doesNotMatch(text, /\/api\/v1\/jobs\/.*\?.*key/);
});
