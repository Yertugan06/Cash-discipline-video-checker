import { useEffect, useState } from 'react';
import type { DragEvent, FormEvent } from 'react';
import { getJob, uploadVideo } from './api.ts';
import Icon from './components/Icon.tsx';
import CoverageWarning from './components/CoverageWarning.tsx';
import ViolationCard from './components/ViolationCard.tsx';
import { VIDEO_SUFFIXES, type Job } from './contract.ts';
import { sampleDoneJobViolation } from './fixtures/sampleDoneJob.ts';
import { words, type Language } from './messages.ts';

type Theme = 'light' | 'dark';

function preferredTheme(): Theme {
  if (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: light)').matches) {
    return 'light';
  }
  return 'dark';
}

function fileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function App() {
  const [language, setLanguage] = useState<Language>('ru');
  const [theme, setTheme] = useState<Theme>(preferredTheme);
  // The API key lives only in this component's state, for the lifetime of
  // the page. It is never written to browser storage, a cookie, the URL or
  // the frontend bundle (implementation-plan.md WP4).
  const [key, setKey] = useState('');
  const [file, setFile] = useState<File>();
  const [dragging, setDragging] = useState(false);
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

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
  }, [theme]);

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

  function selectFile(nextFile: File | undefined) {
    setError('');
    setJob(undefined);
    setFile(nextFile);
  }

  function dropFile(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    if (!busy) selectFile(event.dataTransfer.files[0]);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    const name = file?.name.toLowerCase() ?? '';
    if (!file || !file.size || !VIDEO_SUFFIXES.some((suffix) => name.endsWith(suffix))) {
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
    window.setTimeout(() => document.querySelector('#result')?.scrollIntoView({ behavior: 'smooth' }), 0);
  }

  const coveragePercent =
    job?.status === 'done' && job.coverage?.planned
      ? Math.round((job.coverage.done / job.coverage.planned) * 100)
      : null;

  return (
    <div className="app-shell">
      <header className="site-header">
        <a href="#top" className="brand" aria-label="Forte Vision">
          <span className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          <span className="brand-name">forte</span>
          <span className="brand-product">vision</span>
        </a>

        <nav className="main-nav" aria-label={text.navigation}>
          <a href="#analyzer">{text.navAnalyze}</a>
          <a href="#how-it-works">{text.navHow}</a>
          <a href="#privacy">{text.navPrivacy}</a>
        </nav>

        <div className="header-actions">
          <label className="language-control">
            <span className="sr-only">{text.language}</span>
            <Icon name="globe" size={16} />
            <select
              value={language}
              aria-label={text.language}
              onChange={(event) => setLanguage(event.target.value as Language)}
            >
              <option value="ru">RU</option>
              <option value="en">EN</option>
            </select>
          </label>
          <button
            type="button"
            className="icon-button"
            aria-label={theme === 'dark' ? text.lightTheme : text.darkTheme}
            title={theme === 'dark' ? text.lightTheme : text.darkTheme}
            onClick={() => setTheme((current) => (current === 'dark' ? 'light' : 'dark'))}
          >
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={19} />
          </button>
          <a className="header-cta" href="#analyzer">
            {text.startReview}
            <Icon name="arrowDown" size={16} />
          </a>
        </div>
      </header>

      <main id="top">
        <section className="hero" aria-labelledby="hero-title">
          <div className="hero-glow hero-glow-left" />
          <div className="hero-glow hero-glow-right" />
          <div className="eyebrow">
            <span className="live-dot" />
            {text.eyebrow}
          </div>
          <h1 id="hero-title">
            {text.heroTitle}
            <span>{text.heroAccent}</span>
          </h1>
          <p className="hero-copy">{text.intro}</p>
          <div className="hero-signals" aria-label={text.capabilities}>
            <span><Icon name="shield" size={17} />{text.local}</span>
            <span><Icon name="scan" size={17} />{text.evidence}</span>
            <span><Icon name="book" size={17} />{text.norms}</span>
          </div>
        </section>

        <section className="workspace" id="analyzer" aria-label={text.workspace}>
          <div className="workspace-header">
            <div>
              <p className="section-kicker">01 / {text.analyzeKicker}</p>
              <h2>{text.analyzeTitle}</h2>
            </div>
            <span className="secure-chip"><Icon name="lock" size={15} />{text.secureSession}</span>
          </div>

          <div className="workspace-grid">
            <section className="upload-panel" aria-label={text.upload}>
              <form onSubmit={(event) => void submit(event)}>
                <div className="field-group">
                  <div className="field-heading">
                    <label htmlFor="api-key">{text.key}</label>
                    <span>{text.required}</span>
                  </div>
                  <div className="input-shell">
                    <Icon name="key" size={18} />
                    <input
                      id="api-key"
                      type="password"
                      value={key}
                      required
                      disabled={busy}
                      autoComplete="off"
                      placeholder={text.keyPlaceholder}
                      onChange={(event) => setKey(event.target.value)}
                    />
                    <span className="input-status" aria-hidden="true" />
                  </div>
                  <small>{text.keyHelp}</small>
                </div>

                <div className="field-group">
                  <div className="field-heading">
                    <label htmlFor="video">{text.file}</label>
                    <span>MOV · {text.maxSize}</span>
                  </div>
                  <input
                    className="sr-only"
                    id="video"
                    type="file"
                    accept={VIDEO_SUFFIXES.join(',')}
                    required
                    disabled={busy}
                    onChange={(event) => selectFile(event.target.files?.[0])}
                  />
                  <label
                    htmlFor="video"
                    className={`drop-zone${dragging ? ' is-dragging' : ''}${file ? ' has-file' : ''}`}
                    onDragEnter={(event) => {
                      event.preventDefault();
                      if (!busy) setDragging(true);
                    }}
                    onDragOver={(event) => event.preventDefault()}
                    onDragLeave={() => setDragging(false)}
                    onDrop={dropFile}
                  >
                    <span className="drop-icon"><Icon name={file ? 'video' : 'upload'} size={25} /></span>
                    {file ? (
                      <span className="file-copy">
                        <strong>{file.name}</strong>
                        <small>{fileSize(file.size)} · {text.ready}</small>
                      </span>
                    ) : (
                      <span className="file-copy">
                        <strong>{text.dropTitle}</strong>
                        <small>{text.dropHelp}</small>
                      </span>
                    )}
                    <span className="browse-button">{file ? text.replace : text.browse}</span>
                  </label>
                </div>

                <button className="primary-button" type="submit" disabled={busy || !key || !file}>
                  <span>{uploading ? text.uploading : busy ? text.processing : text.upload}</span>
                  <Icon name={busy ? 'loader' : 'arrowUpRight'} size={19} />
                </button>
              </form>

              <div className="privacy-note" id="privacy">
                <Icon name="shield" size={18} />
                <p><strong>{text.privateTitle}</strong><span>{text.private}</span></p>
              </div>
              <button type="button" className="demo-button" onClick={showDemo} disabled={busy}>
                <Icon name="play" size={16} />
                {text.demo}
              </button>
            </section>

            <section className="result-panel" id="result" aria-live="polite" aria-busy={busy}>
              <div className="result-toolbar">
                <div>
                  <span className={`status-dot${busy ? ' is-active' : ''}`} />
                  {busy ? text.analysisRunning : text.stage}
                </div>
                {job?.status === 'done' && <span className="job-reference">#{job.job_id.slice(0, 8)}</span>}
              </div>

              {error && (
                <div className="state-card error-state" role="alert">
                  <span className="state-icon"><Icon name="alert" size={28} /></span>
                  <p className="state-label">{text.error}</p>
                  <h3>{text.tryAgain}</h3>
                  <p>{error}</p>
                  {job?.status === 'processing' && (
                    <button
                      className="secondary-button"
                      type="button"
                      onClick={() => {
                        setError('');
                        setRetry((value) => value + 1);
                      }}
                    >
                      {text.retry}<Icon name="refresh" size={16} />
                    </button>
                  )}
                </div>
              )}

              {!job && !error && !uploading && (
                <div className="empty-state">
                  <div className="scan-visual" aria-hidden="true">
                    <span className="scan-corner corner-one" />
                    <span className="scan-corner corner-two" />
                    <span className="scan-corner corner-three" />
                    <span className="scan-corner corner-four" />
                    <Icon name="scan" size={42} />
                    <span className="scan-line" />
                  </div>
                  <p className="state-label">{text.readyLabel}</p>
                  <h3>{text.emptyTitle}</h3>
                  <p>{text.empty}</p>
                  <div className="empty-metrics">
                    <span><strong>01</strong>{text.metricUpload}</span>
                    <span><strong>02</strong>{text.metricAnalyze}</span>
                    <span><strong>03</strong>{text.metricReview}</span>
                  </div>
                </div>
              )}

              {(uploading || (job?.status === 'processing' && !error)) && (
                <div className="processing-state" role="status">
                  <div className="processing-orbit" aria-hidden="true">
                    <span /><span /><Icon name="scan" size={35} />
                  </div>
                  <p className="state-label">{uploading ? text.uploading : text.analysisRunning}</p>
                  <h3>{uploading ? text.secureUpload : text.processingTitle}</h3>
                  <p>{text.processing}</p>
                  <div className="progress-track"><span /></div>
                  <div className="processing-steps">
                    <span className="is-complete"><Icon name="check" size={14} />{text.stepSecure}</span>
                    <span className={!uploading ? 'is-complete' : ''}><Icon name="check" size={14} />{text.stepFrames}</span>
                    <span><Icon name="circle" size={9} />{text.stepVerdict}</span>
                  </div>
                </div>
              )}

              {job?.status === 'failed' && !error && (
                <div className="state-card error-state" role="alert">
                  <span className="state-icon"><Icon name="alert" size={28} /></span>
                  <p className="state-label">{text.failed}</p>
                  <h3>{text.tryAgain}</h3>
                  <p>{job.error}</p>
                </div>
              )}

              {job?.status === 'done' && (
                <div className="done-state">
                  <div className={`verdict-banner verdict-${job.verdict}`}>
                    <span className="verdict-icon">
                      <Icon name={job.verdict === 'violation' ? 'alert' : 'check'} size={25} />
                    </span>
                    <div>
                      <p className="state-label">{text.completed}</p>
                      <h3>{job.verdict === 'violation' ? text.violation : text.clean}</h3>
                    </div>
                    <div className="verdict-stats">
                      <span><strong>{job.violations.length}</strong>{text.findings}</span>
                      {coveragePercent !== null && <span><strong>{coveragePercent}%</strong>{text.coverage}</span>}
                    </div>
                  </div>
                  <p className="human-review-note"><Icon name="info" size={16} />{text.note}</p>
                  <CoverageWarning coverage={job.coverage} warnings={job.warnings} language={language} />
                  <div className="findings-list">
                    {job.violations.map((violation, index) => (
                      <ViolationCard
                        key={`${violation.rule_id ?? violation.type}-${index}`}
                        violation={violation}
                        language={language}
                        index={index + 1}
                      />
                    ))}
                  </div>
                </div>
              )}
            </section>
          </div>
        </section>

        <section className="how-section" id="how-it-works" aria-labelledby="how-title">
          <div className="section-intro">
            <p className="section-kicker">02 / {text.howKicker}</p>
            <h2 id="how-title">{text.howTitle}</h2>
            <p>{text.howIntro}</p>
          </div>
          <div className="feature-grid">
            <article className="feature-card">
              <span className="feature-number">01</span>
              <span className="feature-icon"><Icon name="upload" size={26} /></span>
              <h3>{text.featureUploadTitle}</h3>
              <p>{text.featureUploadText}</p>
              <span className="feature-detail"><Icon name="check" size={14} />{text.featureUploadDetail}</span>
            </article>
            <article className="feature-card featured">
              <span className="feature-number">02</span>
              <span className="feature-icon"><Icon name="scan" size={26} /></span>
              <h3>{text.featureVisionTitle}</h3>
              <p>{text.featureVisionText}</p>
              <span className="feature-detail"><Icon name="check" size={14} />{text.featureVisionDetail}</span>
            </article>
            <article className="feature-card">
              <span className="feature-number">03</span>
              <span className="feature-icon"><Icon name="book" size={26} /></span>
              <h3>{text.featureReviewTitle}</h3>
              <p>{text.featureReviewText}</p>
              <span className="feature-detail"><Icon name="check" size={14} />{text.featureReviewDetail}</span>
            </article>
          </div>
        </section>
      </main>

      <footer>
        <a href="#top" className="brand footer-brand" aria-label="Forte Vision">
          <span className="brand-mark" aria-hidden="true"><span /><span /><span /></span>
          <span className="brand-name">forte</span><span className="brand-product">vision</span>
        </a>
        <p>{text.footer}</p>
        <a href="#top" className="back-to-top">{text.backToTop}<Icon name="arrowUp" size={15} /></a>
      </footer>
    </div>
  );
}
