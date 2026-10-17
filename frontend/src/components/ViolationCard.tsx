import type { Violation } from '../contract.ts';
import { timecode, seconds } from '../api.ts';
import { words, type Language } from '../messages.ts';
import NormBlock from './NormBlock.tsx';

/** One violation: type, timecode (mm:ss and seconds), description, 1-3
 * evidence frames, and the norm block (implementation-plan.md WP4). */
export default function ViolationCard({ violation, language }: { violation: Violation; language: Language }) {
  const text = words[language];
  return (
    <article>
      <h3>
        <span className="timecode">
          {timecode(violation.timecode_sec)} <small>({seconds(violation.timecode_sec)})</small>
        </span>
        {violation.type}
      </h3>
      <p>{violation.description}</p>
      <div className="evidence" aria-label={text.frames}>
        {violation.evidence_frames.map((frame, index) => (
          <figure key={`${frame.timestamp_sec}-${index}`}>
            <img
              src={`data:image/jpeg;base64,${frame.image_base64}`}
              alt={`${text.frames} ${timecode(frame.timestamp_sec)}`}
            />
            <figcaption>
              {timecode(frame.timestamp_sec)} ({seconds(frame.timestamp_sec)})
            </figcaption>
          </figure>
        ))}
      </div>
      <NormBlock violation={violation} language={language} />
    </article>
  );
}
