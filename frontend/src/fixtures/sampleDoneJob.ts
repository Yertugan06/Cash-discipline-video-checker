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
 * under partial coverage. Built from the contract, not from organizer video.
 * The violations were produced by backend/serialize.py from the real Knowledge
 * Pack (real norm quotes); only the first one's "verified" status is staged
 * for the demo -- every real norm is still pending review. */
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
      type: 'Наличные/ценности оставлены без присмотра: кассир покинул рабочее место',
      timecode_sec: 44.2,
      description: 'Что видно: С 0:44 по 0:49 кассир отсутствует на рабочем месте; на столе видны денежные купюры. Возможное нарушение: Наличные/ценности оставлены без присмотра: кассир покинул рабочее место. Норма: Правила осуществления кассовых операций и операций по инкассации банкнот, монет и ценностей, п. 20 ч. 2 (Правление Национального Банка Республики Казахстан, № 231 от 29.11.2019).',
      evidence_frames: [
        {
          timestamp_sec: 42.2,
          image_base64: PLACEHOLDER_JPEG_BASE64,
        },
        {
          timestamp_sec: 44.2,
          image_base64: PLACEHOLDER_JPEG_BASE64,
        },
        {
          timestamp_sec: 46.2,
          image_base64: PLACEHOLDER_JPEG_BASE64,
        },
      ],
      rule_id: 'L-NO-CASH-ON-LEAVE',
      source: '231, п. 20 ч. 2',
      source_url: 'https://adilet.zan.kz/rus/docs/V1900019680#z112:~:text=%D0%9D%D0%B0%20%D1%80%D0%B0%D0%B1%D0%BE%D1%87%D0%B5%D0%BC%20%D0%BC%D0%B5%D1%81%D1%82%D0%B5%20%D0%BA%D0%B0%D1%81%D1%81%D0%BE%D0%B2%D0%BE%D0%B3%D0%BE',
      source_quote: 'На рабочем месте кассового работника находятся наличные деньги клиента.',
      strength: 'direct',
      citation_status: 'verified',
      jurisdiction: 'KZ',
      document_title: 'Об утверждении Правил осуществления кассовых операций и операций по инкассации банкнот, монет и ценностей в банках второго уровня, филиалах банков-нерезидентов Республики Казахстан, Национальном операторе почты и юридических лицах, исключительной деятельностью которых является инкассация банкнот, монет и ценностей',
      issuing_authority: 'Правление Национального Банка Республики Казахстан',
      act_number: '231',
      adopted_on: '2019-11-29',
      detection_confidence: 0.94,
      business_status: 'confirmed',
      implementation_status: 'implemented',
      observation: 'С 0:44 по 0:49 кассир отсутствует на рабочем месте; на столе видны денежные купюры.',
      t_start_sec: 44.2,
      t_end_sec: 49.6,
      visibility_caveat: 'Видео не показывает номинал и принадлежность купюр, только их визуальное присутствие на столе.',
      legal_basis: [
        {
          norm_id: '231-20-2',
          citation: 'Правила осуществления кассовых операций и операций по инкассации банкнот, монет и ценностей, п. 20 ч. 2 (Правление Национального Банка Республики Казахстан, № 231 от 29.11.2019)',
          act_short_title: 'Правила осуществления кассовых операций и операций по инкассации банкнот, монет и ценностей',
          punkt: 'п. 20 ч. 2',
          quote: 'На рабочем месте кассового работника находятся наличные деньги клиента.',
          url: 'https://adilet.zan.kz/rus/docs/V1900019680#z112:~:text=%D0%9D%D0%B0%20%D1%80%D0%B0%D0%B1%D0%BE%D1%87%D0%B5%D0%BC%20%D0%BC%D0%B5%D1%81%D1%82%D0%B5%20%D0%BA%D0%B0%D1%81%D1%81%D0%BE%D0%B2%D0%BE%D0%B3%D0%BE',
          strength: 'direct',
          citation_status: 'verified',
          document_title: 'Об утверждении Правил осуществления кассовых операций и операций по инкассации банкнот, монет и ценностей в банках второго уровня, филиалах банков-нерезидентов Республики Казахстан, Национальном операторе почты и юридических лицах, исключительной деятельностью которых является инкассация банкнот, монет и ценностей',
          issuing_authority: 'Правление Национального Банка Республики Казахстан',
          act_number: '231',
          adopted_on: '2019-11-29',
        },
        {
          norm_id: '231-22',
          citation: 'Правила осуществления кассовых операций и операций по инкассации банкнот, монет и ценностей, п. 22 (Правление Национального Банка Республики Казахстан, № 231 от 29.11.2019)',
          act_short_title: 'Правила осуществления кассовых операций и операций по инкассации банкнот, монет и ценностей',
          punkt: 'п. 22',
          quote: 'Кассовому работнику не допускается покидать рабочее место до окончания обслуживания клиента.',
          url: 'https://adilet.zan.kz/rus/docs/V1900019680#z114:~:text=%D0%9A%D0%B0%D1%81%D1%81%D0%BE%D0%B2%D0%BE%D0%BC%D1%83%20%D1%80%D0%B0%D0%B1%D0%BE%D1%82%D0%BD%D0%B8%D0%BA%D1%83%20%D0%BD%D0%B5%20%D0%B4%D0%BE%D0%BF%D1%83%D1%81%D0%BA%D0%B0%D0%B5%D1%82%D1%81%D1%8F',
          strength: 'direct',
          citation_status: 'verified',
          document_title: 'Об утверждении Правил осуществления кассовых операций и операций по инкассации банкнот, монет и ценностей в банках второго уровня, филиалах банков-нерезидентов Республики Казахстан, Национальном операторе почты и юридических лицах, исключительной деятельностью которых является инкассация банкнот, монет и ценностей',
          issuing_authority: 'Правление Национального Банка Республики Казахстан',
          act_number: '231',
          adopted_on: '2019-11-29',
        },
      ],
    },
    {
      type: 'Ключ оставлен в замке сейфа',
      timecode_sec: 78.6,
      description: 'Что видно: С 1:16 по 1:20, после выхода кассира из комнаты, ключ виден в замке сейфа. Возможное нарушение: Ключ оставлен в замке сейфа. Норма: Правила осуществления кассовых операций и операций по инкассации банкнот, монет и ценностей, п. 80 (Правление Национального Банка Республики Казахстан, № 231 от 29.11.2019).',
      evidence_frames: [
        {
          timestamp_sec: 78.6,
          image_base64: PLACEHOLDER_JPEG_BASE64,
        },
      ],
      rule_id: 'L-SAFE-LOCKED-ON-LEAVE',
      source: '231, п. 80',
      source_url: 'https://adilet.zan.kz/rus/docs/V1900019680#z226:~:text=%D0%BA%D0%BB%D1%8E%D1%87%D0%B5%D0%B9%20%D0%BE%D1%82%20%D1%81%D0%BF%D0%B5%D1%86%D0%B8%D0%B0%D0%BB%D1%8C%D0%BD%D1%8B%D1%85%20%D1%83%D1%81%D1%82%D1%80%D0%BE%D0%B9%D1%81%D1%82%D0%B2%2C',
      source_quote: 'ключей от специальных устройств, находящихся на рабочем месте кассового работника, предназначенных для хранения наличных денег (металлический шкаф, сейф, тележка, ящики стола), определяется внутренними документами банка, обеспечивающими исключение их несанкционированного использования',
      strength: 'indirect',
      citation_status: 'pending',
      jurisdiction: 'KZ',
      document_title: 'Об утверждении Правил осуществления кассовых операций и операций по инкассации банкнот, монет и ценностей в банках второго уровня, филиалах банков-нерезидентов Республики Казахстан, Национальном операторе почты и юридических лицах, исключительной деятельностью которых является инкассация банкнот, монет и ценностей',
      issuing_authority: 'Правление Национального Банка Республики Казахстан',
      act_number: '231',
      adopted_on: '2019-11-29',
      detection_confidence: 0.61,
      business_status: 'candidate',
      implementation_status: 'unimplemented',
      observation: 'С 1:16 по 1:20, после выхода кассира из комнаты, ключ виден в замке сейфа.',
      t_start_sec: 76.1,
      t_end_sec: 80.4,
      visibility_caveat: 'По видео не подтверждается, заперт ли сейф механически, только положение ключа в замке.',
      legal_basis: [
        {
          norm_id: '231-80-1',
          citation: 'Правила осуществления кассовых операций и операций по инкассации банкнот, монет и ценностей, п. 80 (Правление Национального Банка Республики Казахстан, № 231 от 29.11.2019)',
          act_short_title: 'Правила осуществления кассовых операций и операций по инкассации банкнот, монет и ценностей',
          punkt: 'п. 80',
          quote: 'ключей от специальных устройств, находящихся на рабочем месте кассового работника, предназначенных для хранения наличных денег (металлический шкаф, сейф, тележка, ящики стола), определяется внутренними документами банка, обеспечивающими исключение их несанкционированного использования',
          url: 'https://adilet.zan.kz/rus/docs/V1900019680#z226:~:text=%D0%BA%D0%BB%D1%8E%D1%87%D0%B5%D0%B9%20%D0%BE%D1%82%20%D1%81%D0%BF%D0%B5%D1%86%D0%B8%D0%B0%D0%BB%D1%8C%D0%BD%D1%8B%D1%85%20%D1%83%D1%81%D1%82%D1%80%D0%BE%D0%B9%D1%81%D1%82%D0%B2%2C',
          strength: 'indirect',
          citation_status: 'pending',
          document_title: 'Об утверждении Правил осуществления кассовых операций и операций по инкассации банкнот, монет и ценностей в банках второго уровня, филиалах банков-нерезидентов Республики Казахстан, Национальном операторе почты и юридических лицах, исключительной деятельностью которых является инкассация банкнот, монет и ценностей',
          issuing_authority: 'Правление Национального Банка Республики Казахстан',
          act_number: '231',
          adopted_on: '2019-11-29',
        },
      ],
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
