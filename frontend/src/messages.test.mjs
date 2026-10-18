import assert from 'node:assert/strict';
import { test } from 'node:test';
import { citationBadge, coverageMessages, verdictText, words } from './messages.ts';

test('verdict texts are verbatim from task.md §4', () => {
  assert.equal(verdictText('no_violation', 'ru'), 'Нарушение не обнаружено');
  assert.equal(verdictText('violation', 'ru'), 'Обнаружены признаки возможных нарушений');
  assert.equal(words.ru.clean, 'Нарушение не обнаружено');
  assert.equal(words.ru.violation, 'Обнаружены признаки возможных нарушений');
});

test('citation badge shows verified only for citation_status === "verified"', () => {
  assert.deepEqual(citationBadge('verified', 'ru'), { label: 'проверено', verified: true, invalid: false });
  assert.deepEqual(citationBadge('pending', 'ru'), { label: 'ожидает проверки', verified: false, invalid: false });
  assert.deepEqual(citationBadge('invalid', 'ru'), { label: 'ссылка или трактовка недействительна', verified: false, invalid: true });
  // Anything unexpected (missing, null, a typo) must fail safe to pending,
  // never be presented as a confirmed citation (AGENTS.md rule 6).
  assert.equal(citationBadge(undefined, 'ru').verified, false);
  assert.equal(citationBadge(null, 'en').verified, false);
  assert.equal(citationBadge('bogus', 'en').verified, false);
  assert.equal(citationBadge('verified', 'en').label, 'verified');
});

test('coverage warning appears for partial/coarse coverage, not for full coverage', () => {
  const full = { step_s: 2, planned: 10, done: 10, failed: 0, deadline_hit: false, mode: 'full' };
  assert.deepEqual(coverageMessages(full, [], 'ru'), []);

  const partial = { step_s: 4, planned: 40, done: 31, failed: 2, deadline_hit: true, mode: 'partial' };
  const lines = coverageMessages(partial, [], 'ru');
  assert.equal(lines.length, 1);
  assert.match(lines[0], /31\/40/);
  assert.match(lines[0], /пропущено 2/);

  const coarse = { step_s: 4, planned: 10, done: 10, failed: 0, deadline_hit: false, mode: 'coarse' };
  assert.match(coverageMessages(coarse, [], 'en')[0], /coarse sampling step/);
});

test('extra pipeline warnings are always surfaced regardless of coverage', () => {
  const full = { step_s: 2, planned: 10, done: 10, failed: 0, deadline_hit: false, mode: 'full' };
  const lines = coverageMessages(full, ['Состояние key_in_safe_lock часто не распознано.'], 'ru');
  assert.deepEqual(lines, ['Состояние key_in_safe_lock часто не распознано.']);
});

test('coverage warning absent when mode is full and no warnings', () => {
  assert.deepEqual(coverageMessages(null, [], 'ru'), []);
  assert.deepEqual(coverageMessages(undefined, [], 'en'), []);
});
