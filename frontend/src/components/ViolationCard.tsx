import type { Violation } from '../contract.ts';
import { timecode, seconds } from '../api.ts';
import { words, type Language } from '../messages.ts';
import Icon from './Icon.tsx';
import NormBlock from './NormBlock.tsx';

/** One violation: type, timecode (mm:ss and seconds), description, 1-3
 * evidence frames, and the norm block (implementation-plan.md WP4). */
export default function ViolationCard({
  violation,
  language,
  index,
}: {
  violation: Violation;
  language: Language;
  index: number;
}) {
  const text = words[language];
  return (
    <article className="violation-card">
      <div className="violation-heading">
        <span className="violation-index">{String(index).padStart(2, '0')}</span>
        <div>
          <span className="timecode">
            <Icon name="clock" size={15} />
            {timecode(violation.timecode_sec)} <small>({seconds(violation.timecode_sec)})</small>
          </span>
          <h4>{violation.type}</h4>
        </div>
      </div>
      <p className="violation-description">{violation.description}</p>
      <div className="evidence" aria-label={text.frames}>
        {violation.evidence_frames.map((frame, index) => (
          <figure key={`${frame.timestamp_sec}-${index}`}>
            <img
              src={`data:image/jpeg;base64,${frame.image_base64}`}
              alt={`${text.frames} ${timecode(frame.timestamp_sec)}`}
            />
            <figcaption>
              <Icon name="scan" size={13} />
              {text.evidenceFrame} · {timecode(frame.timestamp_sec)} ({seconds(frame.timestamp_sec)})
            </figcaption>
          </figure>
        ))}
      </div>
      <NormBlock violation={violation} language={language} />
    </article>
  );
}
