import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { getJob, uploadVideo } from './api.ts';
import { words, type Language } from './messages.ts';
import type { Job } from './contract.ts';
import { sampleDoneJobViolation } from './fixtures/sampleDoneJob.ts';
import ViolationCard from './components/ViolationCard.tsx';
import CoverageWarning from './components/CoverageWarning.tsx';

export default function App() {
  const [language, setLanguage] = useState<Language>('ru');
  // The API key lives only in this component's state, for the lifetime of
  // the page. It is never written to localStorage, sessionStorage, a
  // cookie, the URL or the frontend bundle (implementation-plan.md WP4).
  const [key, setKey] = useState('');
  const [file, setFile] = useState<File>();
  const [uploading, setUploading] = useState(false);
  const [job, setJob] = useState<Job>();
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const text = words[language];
  const busy = uploading || (job?.status === 'processing' && !error);
  const jobId = job?.status === 'processing' ? job.job_id : undefined;

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  // Explicit processing state with polling (implementation-plan.md WP4).
  useEffect(() => {
    if (!jobId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const current = await getJob(jobId!, key, controller.signal);
        if (controller.signal.aborted) return;
        setJob(current);
        if (current.status === 'processing') timer = setTimeout(poll, 1500);
      } catch (problem) {
        if (!controller.signal.aborted) setError(String(problem));
      }
    }
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
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

  function showDemo() {
    setError('');
    setFile(undefined);
    setJob(sampleDoneJobViolation);
  }

  return (
    <>
      <header className="topbar">
        <a href="/" className="brand" aria-label="Forte">
          forte<span>·</span>
        </a>
        <label className="language">
          {text.language}
          <select value={language} onChange={(event) => setLanguage(event.target.value as Language)}>
            <option value="ru">Русский</option>
            <option value="en">English</option>
          </select>
        </label>
      </header>
      <main>
        <p className="eyebrow">DATATHON 26 / LOCAL REVIEW</p>
        <h1>{text.title}</h1>
        <p className="intro">{text.intro}</p>
        <div className="workspace">
          <section className="upload-panel" aria-label={text.upload}>
            <form onSubmit={(event) => void submit(event)}>
              <label htmlFor="api-key">{text.key}</label>
              <input
                id="api-key"
                type="password"
                value={key}
                required
                disabled={busy}
                autoComplete="off"
                onChange={(event) => setKey(event.target.value)}
              />
              <small className="privacy">{text.keyHelp}</small>
              <label htmlFor="video">{text.file}</label>
              <input
                id="video"
                type="file"
                accept=".mov,video/quicktime"
                required
                disabled={busy}
                onChange={(event) => setFile(event.target.files?.[0])}
              />
              <button type="submit" disabled={busy || !key || !file}>
                {uploading ? text.uploading : text.upload}
              </button>
            </form>
            <p className="privacy">{text.private}</p>
            <button type="button" className="demo-button" onClick={showDemo} disabled={busy}>
              {text.demo}
            </button>
          </section>
          <section className="result-panel" aria-live="polite" aria-busy={busy}>
            <p className="stage">{text.stage}</p>
            <p className="notice">{text.note}</p>
            {error && (
              <div role="alert">
                <h2>{text.error}</h2>
                <p>{error}</p>
                {job?.status === 'processing' && (
                  <button
                    onClick={() => {
                      setError('');
                      setRetry((value) => value + 1);
                    }}
                  >
                    {text.retry}
                  </button>
                )}
              </div>
            )}
            {!job && !error && <p>{uploading ? text.uploading : text.empty}</p>}
            {job?.status === 'processing' && !error && <p role="status">{text.processing}</p>}
            {job?.status === 'failed' && (
              <div role="alert">
                <h2>{text.failed}</h2>
                <p>{job.error}</p>
              </div>
            )}
            {job?.status === 'done' && (
              <>
                <h2>{job.verdict === 'violation' ? text.violation : text.clean}</h2>
                <CoverageWarning coverage={job.coverage} warnings={job.warnings} language={language} />
                {job.violations.map((violation, index) => (
                  <ViolationCard key={`${violation.rule_id ?? violation.type}-${index}`} violation={violation} language={language} />
                ))}
              </>
            )}
          </section>
        </div>
      </main>
    </>
  );
}
