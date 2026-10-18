import type { DoneJob } from '../contract.ts';

/**
 * A tiny, synthetically generated placeholder JPEG (a scan-frame illustration,
 * 160x90px) -- never a frame from the organizer
 * dataset. Used only for fixtures/tests/local dev, per the privacy rule in
 * SHARED_BRIEF.md and implementation-plan.md WP4.
 */
export const PLACEHOLDER_JPEG_BASE64 =
  '/9j/4AAQSkZJRgABAQAASABIAAD/4QBMRXhpZgAATU0AKgAAAAgAAYdpAAQAAAABAAAAGgAAAAAAA6ABAAMAAAAB' +
  'AAEAAKACAAQAAAABAAAAoKADAAQAAAABAAAAWgAAAAD/7QA4UGhvdG9zaG9wIDMuMAA4QklNBAQAAAAAAAA4QklN' +
  'BCUAAAAAABDUHYzZjwCyBOmACZjs+EJ+/8AAEQgAWgCgAwEiAAIRAQMRAf/EAB8AAAEFAQEBAQEBAAAAAAAAAAAB' +
  'AgMEBQYHCAkKC//EALUQAAIBAwMCBAMFBQQEAAABfQECAwAEEQUSITFBBhNRYQcicRQygZGhCCNCscEVUtHwJDN' +
  'icoIJChYXGBkaJSYnKCkqNDU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6g4SFhoeIiYqSk5' +
  'SVlpeYmZqio6Slpqeoqaqys7S1tre4ubrCw8TFxsfIycrS09TV1tfY2drh4uPk5ebn6Onq8fLz9PX29/j5+v/E' +
  'AB8BAAMBAQEBAQEBAQEAAAAAAAABAgMEBQYHCAkKC//EALURAAIBAgQEAwQHBQQEAAECdwABAgMRBAUhMQYSQVE' +
  'HYXETIjKBCBRCkaGxwQkjM1LwFWJy0QoWJDThJfEXGBkaJicoKSo1Njc4OTpDREVGR0hJSlNUVVZXWFlaY2RlZm' +
  'doaWpzdHV2d3h5eoKDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ' +
  '2uLj5OXm5+jp6vLz9PX29/j5+v/bAEMADAwMDAwMFAwMFB0UFBQdJx0dHR0nMScnJycnMTsxMTExMTE7Ozs7Oz' +
  's7O0dHR0dHR1NTU1NTXV1dXV1dXV1dXf/bAEMBDg8PGBYYKBYWKGFCNkJhYWFhYWFhYWFhYWFhYWFhYWFhYWF' +
  'hYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYf/dAAQACv/aAAwDAQACEQMRAD8A85ooxRimSHailxxSYoAKKMUY' +
  'oAKO1TyW0sS7n2jpxuUnn2BzUOOKAEooxRigAooxRigA7UUuOKmjtpZV3JtPtuUHj2JzQBBRRijFABR2oxS44oAS' +
  'ijFGKAP/0POaKKKZIdqKXtSUAFFFFAD5ZGlcyNjJ9KZ2qxawi4uY4CcB2AP4mrkmpTxuyWu2KNThVCjp7kjJNBn' +
  'KTvyxRl0Vo/2rf/8APX9F/wAKP7Vv/wDnr+i/4UaBep2X3/8AAM6itH+1b/8A56/ov+FH9q3/APz1/Rf8KNAvU' +
  '7L7/wDgGd2p8UjROJFxketaMepTyOqXW2WNjhlKjp7EDINU7qEW9zJADkIxA/A0BGTvyyRXooooNAo7UUvagBKKK' +
  'KAP/9HzmiiimSHail7UlABRRRQBd0z/AJCEH++P51Vk++31NW9N/wCQhB/vj+dVJPvt9TR0M1/Efov1GVqOlpYk' +
  'RTR+dN/ECSFX245J9az4WWOZHbkKwJ/A1a1GJ47yRm5WRiyt2IPII/OmhT1kosmRLS+Jihj8mb+EAkq3tzyD6Vl' +
  '1e06NpL2IrwEYOx9AvJNVZmWSZ3XgMxI/E0MIaScUJH99fqKtan/yEJ/98/zqrH99fqKt6l/yEJ/98/zpdBv+Iv' +
  'R/oUaKKKDQKO1FL2oASiiigD//0vOaKOKOKZIdqKXjFJxQAUUcUcUAXdM/5CEH++P51Vk++31NWLB0jvYZHOFDj' +
  'J/Go7mJ4Z3jkBBDGn0Mv+Xj9Ce1toyhuro7YVOMDqx/uj+pq5Hqwd/Ku4le3zwmPuD/AGTWLRxRcJUlLWX/AAx0' +
  'U19ZW8Zt40SVZPvBAVG3tyeS36Csq5tVjQXFu3mQscA91Pow9f51S4oobuKFHk1ix8f31+oq1qf/ACEJ/wDfP86' +
  'htonmnSOMEksKkv3SS9mkQ5UucH8aOg/+Xi9CpRRxRxSNQo7UcUvGKAEoo4o4oA//0/OaKKKZIdqKXtSUAFFFFA' +
  'CsrKdrAg+hq7HqV9EgRJTtHQHBx+dRTzQzfOEZXOMncCOPbH9ar9qCZRUviRf/ALVv/wDnr/46v+FH9q3/APz0/' +
  'wDHV/wrPoouyfYw/lX3Gh/at/8A89P/AB1f8KP7Vv8A/nr/AOOr/hWfRRdh7GH8q+4vSalfSoUeU7T1AwM/lVJ' +
  'VZjtUEn0FHarEE0MOHKMzjODuAH5Y/rQVGKj8KK1FFFBQUdqKXtQAlFFFAH//1POaKKKZIdqKO1FABRRRQAUdqK' +
  'O1ABRRRQAUUUUAHaijtRQAUUUUAFHaijtQAUUUUAf/2Q==';

/** A job with two findings: one verified citation, one needs-review citation,
 * under partial coverage. Built from the contract, not from organizer video. */
export const sampleDoneJobViolation: DoneJob = {
  job_id: 'sample-violation',
  status: 'done',
  verdict: 'violation',
  warnings: ['Состояние "key_in_safe_lock" часто не распознано; проверки сейфа ограничены.'],
  coverage: {
    step_s: 4,
    planned: 40,
    done: 31,
    failed: 2,
    deadline_hit: true,
    mode: 'partial',
  },
  violations: [
    {
      type: 'Кассир оставил наличные на столе без присмотра',
      timecode_sec: 44.2,
      description:
        'С 41 по 49 с кассир отсутствует на рабочем месте; на столе видны денежные купюры. ' +
        'Признаки возможного нарушения: кассир оставил наличные на столе без присмотра.',
      evidence_frames: [
        { timestamp_sec: 41.0, image_base64: PLACEHOLDER_JPEG_BASE64 },
        { timestamp_sec: 44.2, image_base64: PLACEHOLDER_JPEG_BASE64 },
      ],
      rule_id: 'L-NO-CASH-ON-LEAVE',
      source: 'Постановление НБРК №231, п.20, п.22',
      source_url: 'https://adilet.zan.kz/rus/docs/V1900019680',
      source_quote:
        'Кассовый работник обязан... не оставлять рабочее место с незакрытым сейфом ' +
        'или денежной наличностью на рабочем столе.',
      strength: 'direct',
      citation_status: 'verified',
    },
    {
      type: 'Сейф не закрыт при уходе кассира',
      timecode_sec: 78.6,
      description:
        'С 76 по 80 с кассир уходит от сейфа, ключ остаётся в замке. ' +
        'Признаки возможного нарушения: сейф не закрыт при уходе кассира.',
      evidence_frames: [{ timestamp_sec: 78.6, image_base64: PLACEHOLDER_JPEG_BASE64 }],
      rule_id: 'L-SAFE-LOCKED-ON-LEAVE',
      source: 'Постановление НБРК №231, п.20, п.78',
      source_url: 'https://adilet.zan.kz/rus/docs/V1900019680',
      source_quote: 'Требует подтверждения юристом перед сдачей.',
      strength: 'indirect',
      citation_status: 'needs_review',
    },
  ],
};

/** A clean job with full coverage and no violations. */
export const sampleDoneJobClean: DoneJob = {
  job_id: 'sample-clean',
  status: 'done',
  verdict: 'no_violation',
  warnings: [],
  coverage: { step_s: 2, planned: 70, done: 70, failed: 0, deadline_hit: false, mode: 'full' },
  violations: [],
};
