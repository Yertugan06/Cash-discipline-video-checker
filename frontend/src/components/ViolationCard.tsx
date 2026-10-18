import type { Violation } from '../contract.ts';
import { timecode, seconds } from '../api.ts';
import { framePosition, words, type Language } from '../messages.ts';
import Icon from './Icon.tsx';
import NormBlock, { CitationBadge } from './NormBlock.tsx';

/** One violation, read top to bottom: when and what, which norm, what the
 * video shows (and cannot show), the evidence frames, then the full legal
 * basis (implementation-plan.md WP4). Results without the structured
 * `observation` fall back to the jury `description` string. */
export default function ViolationCard({
  violation,
  language,
  index,
}: {
  violation: Violation;
  language: Language;
  index?: number;
}) {
  const text = words[language];
  const primary = violation.legal_basis?.[0];
  const start = violation.t_start_sec;
  const end = violation.t_end_sec;
  const hasFragment = typeof start === 'number' && typeof end === 'number' && timecode(start) !== timecode(end);
  return (
    <article className="violation-card">
      <div className="violation-heading">
        {typeof index === 'number' ? <span className="violation-index">{String(index).padStart(2, '0')}</span> : null}
        <div>
          <span className="timecode">
            <Icon name="clock" size={15} />
            {timecode(violation.timecode_sec)} <small>({seconds(violation.timecode_sec)})</small>
            {hasFragment ? (
              <small className="fragment">
                {' · '}
                {text.fragment} {timecode(start)}–{timecode(end)}
              </small>
            ) : null}
          </span>
          <h4>{violation.type}</h4>
        </div>
      </div>
      {primary ? (
        <p className="norm-summary">
          <span className="norm-label">{text.norm}:</span> {primary.act_short_title}, {primary.punkt}
          <CitationBadge status={primary.citation_status} language={language} />
        </p>
      ) : null}
      {violation.observation ? (
        <section className="explanation">
          <h4>{text.seen}</h4>
          <p>{violation.observation}</p>
          {violation.visibility_caveat ? (
            <>
              <h4>{text.cannotConfirm}</h4>
              <p className="caveat">{violation.visibility_caveat}</p>
            </>
          ) : null}
        </section>
      ) : (
        <p className="violation-description">{violation.description}</p>
      )}
      {typeof violation.detection_confidence === 'number' ? (
        <p className="detection-confidence">
          {text.confidence}: {Math.round(violation.detection_confidence * 100)}% ({text.confidenceNote})
        </p>
      ) : null}
      <div className="evidence" aria-label={text.frames}>
        {violation.evidence_frames.map((frame, frameIndex) => (
          <figure key={`${frame.timestamp_sec}-${frameIndex}`}>
            <img
              src={`data:image/jpeg;base64,${frame.image_base64}`}
              alt={`${text.frames} ${timecode(frame.timestamp_sec)}`}
            />
            <figcaption>
              <Icon name="scan" size={13} />
              {timecode(frame.timestamp_sec)} · {framePosition(frame.timestamp_sec, violation.timecode_sec, language)}
            </figcaption>
          </figure>
        ))}
      </div>
      <NormBlock violation={violation} language={language} />
    </article>
  );
}
