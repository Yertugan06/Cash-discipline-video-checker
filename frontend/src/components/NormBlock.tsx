import type { LegalBasis, Violation } from '../contract.ts';
import { actNumberText, citationBadge, strengthText, words, type Language } from '../messages.ts';
import Icon from './Icon.tsx';

/**
 * The legal basis (implementation-plan.md WP4 UI requirements): every norm
 * the rule cites, primary first, each with its act and punkt, verbatim quote,
 * who adopted it, a link to adilet.zan.kz and a citation-status badge. An
 * AI-produced result must never be shown as "verified" unless
 * `citation_status === "verified"` (AGENTS.md, architecture.md §7).
 *
 * `legal_basis` is an optional extra on `Violation` (contracts.py); a result
 * without it shows the flat primary-norm fields instead.
 */
export default function NormBlock({ violation, language }: { violation: Violation; language: Language }) {
  const text = words[language];
  if (violation.legal_basis?.length) {
    return (
      <section className="norm-block">
        <h4>{text.legalBasis}</h4>
        <ol className="norm-list">
          {violation.legal_basis.map((norm, index) => (
            <NormItem key={norm.norm_id} norm={norm} primary={index === 0} language={language} />
          ))}
        </ol>
      </section>
    );
  }
  if (!violation.source && !violation.source_url && !violation.source_quote) return null;
  return (
    <section className="norm-block">
      <h4>{text.legalBasis}</h4>
      <p className="norm-source">
        <span className="norm-label"><Icon name="book" size={15} />{text.source}</span>{' '}
        {violation.source_url ? (
          <a href={violation.source_url} rel="noreferrer" target="_blank">
            {violation.document_title ?? violation.source ?? text.openSource}<Icon name="arrowUpRight" size={13} />
          </a>
        ) : (
          <span>{violation.document_title ?? violation.source}</span>
        )}
        <CitationBadge status={violation.citation_status} language={language} />
      </p>
      {violation.source_quote ? (
        <blockquote className="norm-quote">
          <span className="norm-label">{text.quote}</span> «{violation.source_quote}»
        </blockquote>
      ) : null}
    </section>
  );
}

function NormItem({ norm, primary, language }: { norm: LegalBasis; primary: boolean; language: Language }) {
  const text = words[language];
  // Some quotes are cut from the middle of a sentence; mark the cut.
  const quote = /^[a-zа-яё]/.test(norm.quote) ? `…${norm.quote}` : norm.quote;
  return (
    <li className={primary ? 'norm-item norm-primary' : 'norm-item'}>
      <p className="norm-kind">
        {primary ? text.primaryNorm : text.extraNorm} · {strengthText(norm.strength, language)}
        <CitationBadge status={norm.citation_status} language={language} />
      </p>
      <p className="norm-title">
        {norm.act_short_title}, <strong>{norm.punkt}</strong>
      </p>
      <blockquote className="norm-quote">«{quote}»</blockquote>
      <p className="norm-meta">
        {norm.issuing_authority}, {actNumberText(norm.act_number, norm.adopted_on, language)} ·{' '}
        <a href={norm.url} rel="noreferrer" target="_blank" title={norm.document_title}>
          {text.openAdilet}<Icon name="arrowUpRight" size={13} />
        </a>
      </p>
    </li>
  );
}

export function CitationBadge({ status, language }: { status: string | null | undefined; language: Language }) {
  const badge = citationBadge(status, language);
  return (
    <span
      className={`badge ${badge.verified ? 'badge-verified' : badge.invalid ? 'badge-invalid' : 'badge-needs-review'}`}
      role="status"
    >
      {badge.label}
    </span>
  );
}
