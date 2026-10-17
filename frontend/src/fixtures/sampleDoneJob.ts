import type { DoneJob } from '../contract.ts';

/**
 * A tiny, synthetically generated placeholder JPEG (a solid rectangle with a
 * border drawn by Pillow, 160x90px) -- never a frame from the organizer
 * dataset. Used only for fixtures/tests/local dev, per the privacy rule in
 * SHARED_BRIEF.md and implementation-plan.md WP4.
 */
export const PLACEHOLDER_JPEG_BASE64 =
  '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAoHBwgHBgoICAgLCgoLDhgQDg0NDh0VFhEYIx8lJCIfIiEmKzcvJik0' +
  'KSEiMEExNDk7Pj4+JS5ESUM8SDc9Pjv/2wBDAQoLCw4NDhwQEBw7KCIoOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7' +
  'Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozv/wAARCABaAKADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAEC' +
  'AwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2Jy' +
  'ggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWW' +
  'l5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEA' +
  'AwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMi' +
  'MoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0' +
  'dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn' +
  '6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDjKKKK2PfCiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKK' +
  'KKACiiigDpPCXhKPxNFfyy6mthHYqjO7x7hg7skncMAba1f+EC0D/oetO/KP/wCOUeAv+RV8X/8AXiP/AECWuGpa' +
  '3MPflOSUrWO5/wCEC0D/AKHrTvyj/wDjlH/CBaB/0PWnflH/APHK4aiiz7j5J/zfgjuf+EC0D/oetO/KP/45R/wg' +
  'Wgf9D1p35R//AByuGoos+4ck/wCb8Edz/wAIFoH/AEPWnflH/wDHKP8AhAtA/wCh6078o/8A45XDUUWfcOSf834I' +
  '7n/hAtA/6HrTvyj/APjlH/CBaB/0PWnflH/8crhqKLPuHJP+b8Edz/wgWgf9D1p35R//AByj/hAtA/6HrTvyj/8A' +
  'jlcNRRZ9w5J/zfgjuf8AhAtA/wCh6078o/8A45R/wgWgf9D1p35R/wDxyuGoos+4ck/5vwR3P/CBaB/0PWnflH/8' +
  'cqj4l8F2+haHBq1rrUeowzziJTFEAp4YkhgxBwVxXKV3Oq/8kb0T/r+b+c1GqJfPBr3r3fkcNRRRTOgKKKKAO58B' +
  'f8ir4v8A+vEf+gS1w1dz4C/5FXxf/wBeI/8AQJa4akt2Yw+OXy/IKKKKZsFFFFABRRRQAUUUUAFFFFABRRRQAV3O' +
  'q/8AJG9E/wCv5v5zVw1dzqv/ACRvRP8Ar+b+c1JmNXePr/mcNRRRTNgooooA7nwF/wAir4v/AOvEf+gS1w1dz4C/' +
  '5FXxf/14j/0CWuGpLdmMPjl8vyCiiimbBRRRQAUUUUAFFFFABRRRQAUUUUAFdzqv/JG9E/6/m/nNXDV3Oq/8kb0T' +
  '/r+b+c1JmNXePr/mcNRRRTNgooooA7n4dz6f/ZXiGxvtStrH7bAkSPPIq9VkBIBIzjIo/wCEC0D/AKHrTvyj/wDj' +
  'lcNRSsYunLmbUrXO5/4QLQP+h6078o//AI5R/wAIFoH/AEPWnflH/wDHK4aiiz7hyT/m/BHc/wDCBaB/0PWnflH/' +
  'APHKP+EC0D/oetO/KP8A+OVw1FFn3Dkn/N+CO5/4QLQP+h6078o//jlH/CBaB/0PWnflH/8AHK4aiiz7hyT/AJvw' +
  'R3P/AAgWgf8AQ9ad+Uf/AMco/wCEC0D/AKHrTvyj/wDjlcNRRZ9w5J/zfgjuf+EC0D/oetO/KP8A+OUf8IFoH/Q9' +
  'ad+Uf/xyuGoos+4ck/5vwR3P/CBaB/0PWnflH/8AHKP+EC0D/oetO/KP/wCOVw1FFn3Dkn/N+CO5/wCEC0D/AKHr' +
  'Tvyj/wDjlT+LRpen/D3TtGstZtNRktrzcWhkUkgiQ52hjgDcBXn9FFg9nJtOUr2CiiimbBRRRQAUUUUAFFFFABRR' +
  'RQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQB//9k=';

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
