import type { CitationStrength, Coverage } from './contract.ts';

export type Language = 'ru' | 'en';

/**
 * UI vocabulary. Both verdict strings are verbatim from task.md §4
 * ("Обязательный пользовательский сценарий"): "Нарушение не обнаружено" and
 * "Обнаружены признаки возможных нарушений". Do not reword them.
 */
export const words = {
  ru: {
    title: 'Проверка кассовой дисциплины',
    intro: 'Загрузите видео для локальной проверки.',
    private: 'Видео обрабатывается локально на сервере.',
    key: 'API-ключ',
    file: 'Видео .mov, .mp4 или .mkv',
    keyHelp: 'Ключ хранится только в памяти этой страницы и не сохраняется.',
    upload: 'Проверить видео',
    uploading: 'Загрузка…',
    processing: 'Обработка видео…',
    error: 'Не удалось выполнить проверку',
    retry: 'Повторить запрос статуса',
    clean: 'Нарушение не обнаружено',
    violation: 'Обнаружены признаки возможных нарушений',
    note: 'Результат основан на видимых видеосигналах и требует проверки человеком.',
    stage: 'Локальный анализ',
    frames: 'Кадры',
    source: 'Правило и источник',
    quote: 'Цитата нормы',
    openSource: 'Открыть источник',
    verified: 'проверено',
    pending: 'ожидает проверки',
    invalid: 'ссылка или трактовка недействительна',
    jurisdiction: 'Юрисдикция',
    authority: 'Орган',
    adoptedOn: 'Дата принятия',
    confidence: 'Уверенность обнаружения',
    confidenceNote: 'Оценка модели, не калиброванная вероятность.',
    failed: 'Обработка завершилась ошибкой',
    language: 'Язык / Language',
    empty: 'Выберите видео, чтобы начать проверку.',
    wrongFile: 'Выберите непустой файл .mov, .mp4 или .mkv.',
    coverageIntro: 'Покрытие видео неполное:',
    coveragePartial: 'обработано кадров: {done}/{planned} (пропущено {failed}); дедлайн достигнут.',
    coverageCoarse: 'использован только грубый шаг разметки, часть событий короче шага могла быть пропущена.',
    demo: 'Пример (демо-данные)',
    seen: 'Что видно на видео',
    cannotConfirm: 'Что видео не подтверждает',
    norm: 'Норма',
    legalBasis: 'Правовое основание',
    primaryNorm: 'Основная норма',
    extraNorm: 'Дополнительная норма',
    fragment: 'Фрагмент',
    actNumber: '№ {number} от {date}',
    openAdilet: 'Открыть текст на adilet.zan.kz',
    strength: { direct: 'прямое основание', indirect: 'косвенное основание', weak: 'слабое основание' },
    framePosition: { before: 'до', moment: 'момент', after: 'после' },
  },
  en: {
    title: 'Cash-discipline video checker',
    intro: 'Upload a video for a local review.',
    private: 'Video is processed locally on the server.',
    key: 'API key',
    file: 'Video .mov, .mp4 or .mkv',
    keyHelp: 'The key stays only in this page’s memory and is never saved.',
    upload: 'Analyze video',
    uploading: 'Uploading…',
    processing: 'Processing video…',
    error: 'Analysis could not be completed',
    retry: 'Retry status request',
    clean: 'No violation detected',
    violation: 'Signs of possible violations detected',
    note: 'The result uses visible video signals and requires human review.',
    stage: 'Local analysis',
    frames: 'Frames',
    source: 'Rule and source',
    quote: 'Norm quote',
    openSource: 'Open source',
    verified: 'verified',
    pending: 'pending review',
    invalid: 'invalid source or interpretation',
    jurisdiction: 'Jurisdiction',
    authority: 'Issuing authority',
    adoptedOn: 'Adopted',
    confidence: 'Detection confidence',
    confidenceNote: 'Model score, not a calibrated probability.',
    failed: 'Processing failed',
    language: 'Language / Язык',
    empty: 'Select a video to start.',
    wrongFile: 'Choose a non-empty .mov, .mp4 or .mkv file.',
    coverageIntro: 'Video coverage is incomplete:',
    coveragePartial: 'frames processed: {done}/{planned} (failed {failed}); the deadline was reached.',
    coverageCoarse: 'only the coarse sampling step was used; events shorter than the step may have been missed.',
    demo: 'Sample (demo data)',
    seen: 'What the video shows',
    cannotConfirm: 'What the video cannot confirm',
    norm: 'Norm',
    legalBasis: 'Legal basis',
    primaryNorm: 'Primary norm',
    extraNorm: 'Additional norm',
    fragment: 'Fragment',
    actNumber: 'No. {number} of {date}',
    openAdilet: 'Open the text on adilet.zan.kz',
    strength: { direct: 'direct basis', indirect: 'indirect basis', weak: 'weak basis' },
    framePosition: { before: 'before', moment: 'moment', after: 'after' },
  },
} as const;

/** Verdict text to render for a DoneJob.verdict, verbatim from task.md §4. */
export function verdictText(verdict: 'violation' | 'no_violation', language: Language): string {
  return verdict === 'violation' ? words[language].violation : words[language].clean;
}

/**
 * Citation badge for a violation's `citation_status`. Anything other than
 * exactly "verified" is shown as verified. Pending or invalid sources retain
 * distinct labels so a human can distinguish review from a known conflict --
 * an AI must never present an unverified norm as confirmed (AGENTS.md,
 * SHARED_BRIEF rule 6; architecture.md §7).
 */
export function citationBadge(
  status: string | null | undefined,
  language: Language,
): { label: string; verified: boolean; invalid: boolean } {
  const verified = status === 'verified';
  const invalid = status === 'invalid';
  const label = verified
    ? words[language].verified
    : invalid
      ? words[language].invalid
      : words[language].pending;
  return { label, verified, invalid };
}

/** Plain-language label for a citation strength. */
export function strengthText(strength: CitationStrength, language: Language): string {
  return words[language].strength[strength];
}

/** Where an evidence frame sits relative to the reported timecode (backend/evidence.py). */
export function framePosition(frameSec: number, timecodeSec: number, language: Language): string {
  const position = frameSec < timecodeSec ? 'before' : frameSec > timecodeSec ? 'after' : 'moment';
  return words[language].framePosition[position];
}

/** "№ 231 от 29.11.2019" from an act number and an ISO date. */
export function actNumberText(number: string, isoDate: string, language: Language): string {
  const [year, month, day] = isoDate.split('-');
  return words[language].actNumber.replace('{number}', number).replace('{date}', `${day}.${month}.${year}`);
}

/**
 * Human-readable coverage/partial-processing warning lines. Shown whenever
 * `coverage.mode !== "full"` or the job carries non-empty `warnings`
 * (implementation-plan.md WP4 UI requirements).
 */
export function coverageMessages(
  coverage: Coverage | null | undefined,
  warnings: string[],
  language: Language,
): string[] {
  const w = words[language];
  const lines: string[] = [];
  if (coverage && coverage.mode !== 'full') {
    const detail =
      coverage.mode === 'partial'
        ? w.coveragePartial
            .replace('{done}', String(coverage.done))
            .replace('{planned}', String(coverage.planned))
            .replace('{failed}', String(coverage.failed))
        : w.coverageCoarse;
    lines.push(`${w.coverageIntro} ${detail}`);
  }
  for (const warning of warnings) lines.push(warning);
  return lines;
}
