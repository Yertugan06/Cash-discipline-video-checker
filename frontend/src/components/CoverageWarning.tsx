import type { Coverage } from '../contract.ts';
import { coverageMessages, type Language } from '../messages.ts';
import Icon from './Icon.tsx';

/** Coverage/partial-processing warning, shown whenever coverage.mode is not
 * "full" or the job carries non-empty warnings (implementation-plan.md WP4). */
export default function CoverageWarning({
  coverage,
  warnings,
  language,
}: {
  coverage: Coverage | null | undefined;
  warnings: string[];
  language: Language;
}) {
  const lines = coverageMessages(coverage, warnings, language);
  if (lines.length === 0) return null;
  return (
    <div className="notice coverage-notice" role="status">
      <Icon name="alert" size={18} />
      <div>{lines.map((line, index) => <p key={index}>{line}</p>)}</div>
    </div>
  );
}
