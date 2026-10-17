import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { getJob, timecode, uploadVideo } from './api.ts';
import { warningText } from './messages.ts';
import type { Job } from './contract.ts';

const words = {
  ru: {
    title: 'Проверка кассовой дисциплины', intro: 'Загрузите видео для локальной проверки.',
    private: 'Видео обрабатывается локально на сервере.', key: 'API-ключ', file: 'Видео .mov',
    keyHelp: 'Пароль этого сервиса: значение API_KEY из .env.',
    upload: 'Проверить видео', uploading: 'Загрузка…', processing: 'Обработка видео…',
    error: 'Не удалось выполнить проверку', retry: 'Повторить запрос статуса',
    clean: 'Нарушение не обнаружено', violation: 'Обнаружены признаки возможных нарушений',
    note: 'Результат основан на видимых видеосигналах и требует проверки человеком.',
    stage: 'Локальный анализ · v1', frames: 'Кадры', source: 'Правило и источник',
    failed: 'Обработка завершилась ошибкой', duration: 'Длительность', runtime: 'Время обработки',
    language: 'Язык / Language', empty: 'Выберите видео, чтобы начать проверку.',
    wrongFile: 'Выберите непустой файл .mov.',
  },
  en: {
    title: 'Cash-discipline video checker', intro: 'Upload a video for a local review.',
    private: 'Video is processed locally on the server.', key: 'API key', file: 'Video .mov',
    keyHelp: 'This service’s password: the API_KEY value from .env.',
    upload: 'Analyze video', uploading: 'Uploading…', processing: 'Processing video…',
    error: 'Analysis could not be completed', retry: 'Retry status request',
    clean: 'No violation detected', violation: 'Signs of possible violations detected',
    note: 'The result uses visible video signals and requires human review.',
    stage: 'Local analysis · v1', frames: 'Frames', source: 'Rule and source',
    failed: 'Processing failed', duration: 'Duration', runtime: 'Processing time',
    language: 'Language / Язык', empty: 'Select a video to start.',
    wrongFile: 'Choose a non-empty .mov file.',
  },
};

export default function App() {
  const [language, setLanguage] = useState<'ru' | 'en'>('ru');
  const [key, setKey] = useState('');
  const [file, setFile] = useState<File>();
  const [uploading, setUploading] = useState(false);
  const [job, setJob] = useState<Job>();
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const text = words[language];
  const busy = uploading || (job?.status === 'processing' && !error);
  const jobId = job?.job_id;

  useEffect(() => { document.documentElement.lang = language; }, [language]);

  useEffect(() => {
    if (!jobId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const current = await getJob(jobId!, key, controller.signal);
        if (controller.signal.aborted) return;
        setJob(current);
        if (current.status === 'processing') timer = setTimeout(poll, 700);
      } catch (problem) {
        if (!controller.signal.aborted) setError(String(problem));
      }
    }
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [jobId, key, retry]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    if (!file || !file.size || !file.name.toLowerCase().endsWith('.mov')) {
      setError(text.wrongFile);
      return;
    }
    setJob(undefined);
    setUploading(true);
    try {
      const accepted = await uploadVideo(file, key);
      setJob({ job_id: accepted.job_id, status: 'processing' });
    } catch (problem) {
      setError(String(problem));
    } finally {
      setUploading(false);
    }
  }

  return <>
    <header className="topbar">
      <a href="/" className="brand" aria-label="Forte">forte<span>·</span></a>
      <label className="language">{text.language}
        <select value={language} onChange={event => setLanguage(event.target.value as 'ru' | 'en')}>
          <option value="ru">Русский</option><option value="en">English</option>
        </select>
      </label>
    </header>
    <main>
      <p className="eyebrow">DATATHON 26 / LOCAL REVIEW</p>
      <h1>{text.title}</h1><p className="intro">{text.intro}</p>
      <div className="workspace">
        <section className="upload-panel" aria-label={text.upload}>
          <form onSubmit={event => { void submit(event); }}>
            <label htmlFor="api-key">{text.key}</label>
            <input id="api-key" type="password" value={key} required disabled={busy}
              autoComplete="off" onChange={event => setKey(event.target.value)} />
            <small className="privacy">{text.keyHelp}</small>
            <label htmlFor="video">{text.file}</label>
            <input id="video" type="file" accept=".mov,video/quicktime" required disabled={busy}
              onChange={event => setFile(event.target.files?.[0])} />
            <button type="submit" disabled={busy || !key || !file}>
              {uploading ? text.uploading : text.upload}
            </button>
          </form>
          <p className="privacy">{text.private}</p>
        </section>
        <section className="result-panel" aria-live="polite" aria-busy={busy}>
          <p className="stage">{text.stage}</p>
          <p className="notice">{text.note}</p>
          {error && <div role="alert"><h2>{text.error}</h2><p>{error}</p>
            {job?.status === 'processing' && <button onClick={() => {
              setError(''); setRetry(value => value + 1);
            }}>{text.retry}</button>}
          </div>}
          {!job && !error && <p>{uploading ? text.uploading : text.empty}</p>}
          {job?.status === 'processing' && !error && <p role="status">{text.processing}</p>}
          {job?.status === 'failed' && <div role="alert"><h2>{text.failed}</h2><p>{job.error}</p></div>}
          {job?.status === 'done' && <>
            <h2>{job.verdict === 'violation' ? text.violation : text.clean}</h2>
            {job.warnings.length > 0 && <div className="notice" role="status">
              {job.warnings.map(warning => <p key={warning}>{warningText(warning,language)}</p>)}
            </div>}
            <p className="metadata">{text.duration}: {timecode(job.video.duration_sec)} · {text.runtime}: {' '}
              {job.runtime_sec.toFixed(2)} s</p>
            {job.violations.map((violation, index) => <article key={`${violation.rule_id}-${index}`}>
              <h3><span className="timecode">{timecode(violation.timecode_sec)}</span>
                {language === 'en' && violation.type_en ? violation.type_en : violation.type}</h3>
              <p>{language === 'en' && violation.description_en ? violation.description_en : violation.description}</p>
              <p>{text.source}: <strong>{violation.rule_id}</strong> · {' '}
                <a href={violation.source_url} rel="noreferrer" target="_blank">{violation.source}</a>
                {' '}({violation.strength})</p>
              <div className="evidence" aria-label={text.frames}>
                {violation.evidence_frames.map(frame => <figure key={frame.timestamp_sec}>
                  <img src={`data:image/jpeg;base64,${frame.image_base64}`}
                    alt={`${text.frames} ${timecode(frame.timestamp_sec)}`} />
                  <figcaption>{timecode(frame.timestamp_sec)}</figcaption>
                </figure>)}
              </div>
            </article>)}
          </>}
        </section>
      </div>
    </main>
  </>;
}
