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
