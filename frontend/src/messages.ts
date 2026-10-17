import type { Coverage } from './contract.ts';

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
    file: 'Видео .mov',
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
    needsReview: 'требует проверки',
    failed: 'Обработка завершилась ошибкой',
    language: 'Язык / Language',
    empty: 'Выберите видео, чтобы начать проверку.',
    wrongFile: 'Выберите непустой файл .mov.',
    coverageIntro: 'Покрытие видео неполное:',
    coveragePartial: 'обработано кадров: {done}/{planned} (пропущено {failed}); дедлайн достигнут.',
    coverageCoarse: 'использован только грубый шаг разметки, часть событий короче шага могла быть пропущена.',
    demo: 'Пример (демо-данные)',
  },
  en: {
    title: 'Cash-discipline video checker',
    intro: 'Upload a video for a local review.',
    private: 'Video is processed locally on the server.',
    key: 'API key',
    file: 'Video .mov',
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
    needsReview: 'needs review',
    failed: 'Processing failed',
    language: 'Language / Язык',
    empty: 'Select a video to start.',
    wrongFile: 'Choose a non-empty .mov file.',
    coverageIntro: 'Video coverage is incomplete:',
    coveragePartial: 'frames processed: {done}/{planned} (failed {failed}); the deadline was reached.',
    coverageCoarse: 'only the coarse sampling step was used; events shorter than the step may have been missed.',
    demo: 'Sample (demo data)',
  },
} as const;

/** Verdict text to render for a DoneJob.verdict, verbatim from task.md §4. */
export function verdictText(verdict: 'violation' | 'no_violation', language: Language): string {
  return verdict === 'violation' ? words[language].violation : words[language].clean;
}

/**
 * Citation badge for a violation's `citation_status`. Anything other than
 * exactly "verified" is shown as "needs review" ("требует проверки") --
 * an AI must never present an unverified norm as confirmed (AGENTS.md,
 * SHARED_BRIEF rule 6; architecture.md §7).
 */
export function citationBadge(
  status: string | null | undefined,
  language: Language,
): { label: string; verified: boolean } {
  const verified = status === 'verified';
  return { label: verified ? words[language].verified : words[language].needsReview, verified };
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
