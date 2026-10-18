import type { Violation } from '../contract.ts';
import { citationBadge, words, type Language } from '../messages.ts';
import Icon from './Icon.tsx';

/**
 * The norm block (implementation-plan.md WP4 UI requirements): source
 * (act + punkt), verbatim quote, a link to the source, and a citation-status
 * badge. All fields are optional extras on `Violation` (contracts.py), so
 * each piece renders only when present; an AI-produced result must never be
 * shown as "verified" unless `citation_status === "verified"` (AGENTS.md,
 * architecture.md §7).
 */
export default function NormBlock({ violation, language }: { violation: Violation; language: Language }) {
  const text = words[language];
  const hasSource = Boolean(violation.source || violation.source_url || violation.source_quote);
  if (!hasSource) return null;
  const badge = citationBadge(violation.citation_status, language);
  return (
    <div className="norm-block">
      <p className="norm-source">
        <span className="norm-label"><Icon name="book" size={15} />{text.source}</span>{' '}
        {violation.source_url ? (
          <a href={violation.source_url} rel="noreferrer" target="_blank">
            {violation.source ?? text.openSource}<Icon name="arrowUpRight" size={13} />
          </a>
        ) : (
          <span>{violation.source}</span>
        )}
        {violation.strength ? <span className="norm-strength"> ({violation.strength})</span> : null}
        <span
          className={badge.verified ? 'badge badge-verified' : 'badge badge-needs-review'}
          role="status"
        >
          {badge.label}
        </span>
      </p>
      {violation.source_quote ? (
        <blockquote className="norm-quote">
          <span className="norm-label">{text.quote}</span> «{violation.source_quote}»
        </blockquote>
      ) : null}
    </div>
  );
}
