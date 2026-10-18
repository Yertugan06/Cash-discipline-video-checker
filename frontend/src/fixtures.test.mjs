import assert from 'node:assert/strict';
import { test } from 'node:test';
import { PLACEHOLDER_JPEG_BASE64, sampleDoneJobClean, sampleDoneJobViolation } from './fixtures/sampleDoneJob.ts';

test('the placeholder evidence image decodes as a real JPEG (SOI/EOI markers)', () => {
  const bytes = Buffer.from(PLACEHOLDER_JPEG_BASE64, 'base64');
  assert.equal(bytes.length > 100, true);
  assert.deepEqual(bytes.subarray(0, 3), Buffer.from([0xff, 0xd8, 0xff]));
  assert.deepEqual(bytes.subarray(-2), Buffer.from([0xff, 0xd9]));
});

test('sample DoneJob fixtures match the contract shape used by the UI', () => {
  for (const job of [sampleDoneJobViolation, sampleDoneJobClean]) {
    assert.equal(job.status, 'done');
    assert.ok(Array.isArray(job.violations));
    assert.equal(job.verdict, job.violations.length > 0 ? 'violation' : 'no_violation');
    for (const violation of job.violations) {
      assert.ok(violation.type.length > 0);
      assert.ok(violation.description.length > 0);
      assert.ok(violation.evidence_frames.length >= 1 && violation.evidence_frames.length <= 3);
      for (const frame of violation.evidence_frames) {
        assert.equal(typeof frame.image_base64, 'string');
        assert.equal(frame.image_base64, PLACEHOLDER_JPEG_BASE64);
      }
    }
  }
  assert.equal(sampleDoneJobViolation.violations[0].citation_status, 'verified');
  assert.equal(sampleDoneJobViolation.violations[1].citation_status, 'pending');
  assert.equal(sampleDoneJobViolation.coverage?.mode, 'partial');
  assert.equal(sampleDoneJobClean.coverage?.mode, 'full');
});
