import type { CitationStrength, Coverage } from './contract.ts';

export type Language = 'ru' | 'en';

/**
 * UI vocabulary. Both verdict strings are verbatim from task.md §4
 * ("Обязательный пользовательский сценарий"). Do not reword them.
 */
export const words = {
  ru: {
    navigation: 'Основная навигация', navAnalyze: 'Анализ', navHow: 'Как это работает', navPrivacy: 'Приватность',
    startReview: 'Начать проверку', lightTheme: 'Включить светлую тему', darkTheme: 'Включить тёмную тему',
    eyebrow: 'Локальная система видеоаналитики', heroTitle: 'Замечайте риск.', heroAccent: 'Проверяйте каждый момент.',
    intro: 'Интеллектуальная проверка кассовых операций по видео — с таймкодами, доказательными кадрами и ссылками на нормы.',
    capabilities: 'Возможности системы', local: 'Локальная обработка', evidence: 'Доказательные кадры', norms: 'Ссылки на нормы',
    workspace: 'Рабочая область проверки', analyzeKicker: 'Проверка', analyzeTitle: 'Загрузите видео для анализа', secureSession: 'Защищённая сессия',
    key: 'API-ключ', required: 'Обязательно', keyPlaceholder: 'Введите ключ доступа', keyHelp: 'Ключ хранится только в памяти этой страницы и не сохраняется.',
    file: 'Видео кассовой операции', maxSize: 'до 500 МБ', dropTitle: 'Перетащите видео сюда', dropHelp: 'или выберите файл с устройства',
    browse: 'Выбрать', replace: 'Заменить', ready: 'Готово к анализу', upload: 'Запустить анализ', uploading: 'Защищённая загрузка…',
    processing: 'Система анализирует видимые события и формирует проверяемый результат.',
    privateTitle: 'Ваши данные остаются закрытыми.', private: 'Видео обрабатывается локально на сервере и не передаётся внешним AI-сервисам.',
    demo: 'Посмотреть пример результата', stage: 'Система готова', analysisRunning: 'Анализ выполняется',
    error: 'Ошибка анализа', tryAgain: 'Не удалось завершить проверку', retry: 'Повторить запрос статуса',
    readyLabel: 'Готово к работе', emptyTitle: 'Результат появится здесь', empty: 'Добавьте API-ключ и видео слева. Система покажет события, кадры и связанные нормы.',
    metricUpload: 'Загрузка', metricAnalyze: 'Анализ', metricReview: 'Проверка',
    secureUpload: 'Видео загружается локально', processingTitle: 'Ищем значимые события', stepSecure: 'Защищено', stepFrames: 'Кадры', stepVerdict: 'Вердикт',
    completed: 'Проверка завершена', findings: 'события', coverage: 'покрытие',
    clean: 'Нарушение не обнаружено', violation: 'Обнаружены признаки возможных нарушений',
    note: 'Результат основан на видимых видеосигналах и требует проверки человеком.',
    failed: 'Обработка завершилась ошибкой', language: 'Язык / Language', wrongFile: 'Выберите непустой файл .mov, .mp4 или .mkv.',
    frames: 'Доказательные кадры', evidenceFrame: 'Кадр', source: 'Правило и источник', quote: 'Цитата нормы', openSource: 'Открыть источник',
    verified: 'проверено', needsReview: 'требует проверки', coverageIntro: 'Покрытие видео неполное:',
    coveragePartial: 'обработано кадров: {done}/{planned} (пропущено {failed}); дедлайн достигнут.',
    coverageCoarse: 'использован только грубый шаг разметки, часть событий короче шага могла быть пропущена.',
    howKicker: 'Метод', howTitle: 'От видео до проверяемого решения', howIntro: 'Три прозрачных шага. Никаких скрытых выводов — каждый результат можно перепроверить.',
    featureUploadTitle: 'Безопасная загрузка', featureUploadText: 'Видео и ключ остаются внутри защищённого контура во время всей проверки.', featureUploadDetail: 'Без внешней передачи данных',
    featureVisionTitle: 'Анализ событий', featureVisionText: 'Система отслеживает роли, действия и объекты в контексте рабочей зоны.', featureVisionDetail: 'Точные таймкоды и кадры',
    featureReviewTitle: 'Решение с контекстом', featureReviewText: 'Каждое наблюдение связано с описанием и релевантным нормативным источником.', featureReviewDetail: 'Финальное решение принимает человек',
    footer: 'Локальная система анализа кассовой дисциплины · Datathon 2026', backToTop: 'Наверх',
    organizers: 'Организаторы', team: 'Команда',
    // Contract fields from main: legal-basis details and before/moment/after frame labels.
    title: 'Проверка кассовой дисциплины',
    pending: 'ожидает проверки',
    invalid: 'ссылка или трактовка недействительна',
    jurisdiction: 'Юрисдикция',
    authority: 'Орган',
    adoptedOn: 'Дата принятия',
    confidence: 'Уверенность обнаружения',
    confidenceNote: 'Оценка модели, не калиброванная вероятность.',
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
    navigation: 'Main navigation', navAnalyze: 'Analyze', navHow: 'How it works', navPrivacy: 'Privacy',
    startReview: 'Start review', lightTheme: 'Switch to light theme', darkTheme: 'Switch to dark theme',
    eyebrow: 'Local video intelligence', heroTitle: 'See the risk.', heroAccent: 'Verify every moment.',
    intro: 'Intelligent cash-operation video review with exact timecodes, evidence frames, and traceable policy references.',
    capabilities: 'System capabilities', local: 'Local processing', evidence: 'Evidence frames', norms: 'Policy references',
    workspace: 'Review workspace', analyzeKicker: 'Review', analyzeTitle: 'Upload a video for analysis', secureSession: 'Secure session',
    key: 'API key', required: 'Required', keyPlaceholder: 'Enter access key', keyHelp: 'The key stays only in this page’s memory and is never saved.',
    file: 'Cash-operation video', maxSize: 'up to 500 MB', dropTitle: 'Drop your video here', dropHelp: 'or choose a file from your device',
    browse: 'Browse', replace: 'Replace', ready: 'Ready to analyze', upload: 'Run analysis', uploading: 'Secure upload…',
    processing: 'The system is analyzing visible events and preparing a reviewable result.',
    privateTitle: 'Your data stays private.', private: 'Video is processed locally on the server and is never sent to external AI services.',
    demo: 'Preview a sample result', stage: 'System ready', analysisRunning: 'Analysis in progress',
    error: 'Analysis error', tryAgain: 'The review could not be completed', retry: 'Retry status request',
    readyLabel: 'Ready when you are', emptyTitle: 'Your result will appear here', empty: 'Add an API key and video on the left. The system will surface events, evidence, and relevant policy.',
    metricUpload: 'Upload', metricAnalyze: 'Analyze', metricReview: 'Review',
    secureUpload: 'Uploading video locally', processingTitle: 'Finding meaningful events', stepSecure: 'Secured', stepFrames: 'Frames', stepVerdict: 'Verdict',
    completed: 'Review complete', findings: 'findings', coverage: 'coverage',
    clean: 'No violation detected', violation: 'Signs of possible violations detected',
    note: 'The result uses visible video signals and requires human review.',
    failed: 'Processing failed', language: 'Language / Язык', wrongFile: 'Choose a non-empty .mov, .mp4 or .mkv file.',
    frames: 'Evidence frames', evidenceFrame: 'Frame', source: 'Rule and source', quote: 'Policy quote', openSource: 'Open source',
    verified: 'verified', needsReview: 'needs review', coverageIntro: 'Video coverage is incomplete:',
    coveragePartial: 'frames processed: {done}/{planned} (failed {failed}); the deadline was reached.',
    coverageCoarse: 'only the coarse sampling step was used; events shorter than the step may have been missed.',
    howKicker: 'Method', howTitle: 'From video to a reviewable decision', howIntro: 'Three transparent steps. No hidden conclusions—every result can be independently checked.',
    featureUploadTitle: 'Secure upload', featureUploadText: 'Your video and access key remain inside the protected environment throughout the review.', featureUploadDetail: 'No external data transfer',
    featureVisionTitle: 'Event analysis', featureVisionText: 'The system tracks roles, actions, and objects in the context of the cash desk.', featureVisionDetail: 'Exact timecodes and frames',
    featureReviewTitle: 'Context-rich decision', featureReviewText: 'Every observation is connected to an explanation and a relevant policy source.', featureReviewDetail: 'A human makes the final decision',
    footer: 'Local cash-discipline intelligence · Datathon 2026', backToTop: 'Back to top',
    organizers: 'Organizers', team: 'Team',
    // Contract fields from main: legal-basis details and before/moment/after frame labels.
    title: 'Cash-discipline video checker',
    pending: 'pending review',
    invalid: 'invalid source or interpretation',
    jurisdiction: 'Jurisdiction',
    authority: 'Issuing authority',
    adoptedOn: 'Adopted',
    confidence: 'Detection confidence',
    confidenceNote: 'Model score, not a calibrated probability.',
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

export function coverageMessages(
  coverage: Coverage | null | undefined,
  warnings: string[],
  language: Language,
): string[] {
  const w = words[language];
  const lines: string[] = [];
  if (coverage && coverage.mode !== 'full') {
    const detail = coverage.mode === 'partial'
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
