/**
 * Strict-JSON review protocol (docs/collab-agent-design.md section 8).
 *
 * cligent has no structured-output support, so the Reviewer's final text is
 * parsed and validated locally. Adjudication is driven by blocking findings;
 * the verdict field is only a cross-check.
 */

export const SEVERITIES = ['critical', 'major', 'minor', 'suggestion'] as const;
export type Severity = (typeof SEVERITIES)[number];
export const BLOCKING_SEVERITIES: ReadonlySet<string> = new Set([
  'critical',
  'major',
]);

export interface ReviewFinding {
  id: string | null;
  severity: Severity;
  file: string | null;
  line: number | null;
  issue: string;
  evidence: string | null;
  requiredChange: string | null;
}

export interface Review {
  verdict: 'approve' | 'revise' | null;
  summary: string;
  findings: ReviewFinding[];
  hasBlockingFindings: boolean;
  /** True when the verdict contradicts the findings-derived decision. */
  verdictMismatch: boolean;
  raw: Record<string, unknown>;
}

export class ReviewParseError extends Error {}

export type ResolutionStatus = 'accepted' | 'rebutted' | 'unresolved';

export interface FindingResolution {
  id: string;
  status: ResolutionStatus;
  note: string | null;
}

function extractJsonCandidate(text: string): string {
  const fenced = text.match(/```(?:json)?\s*\n([\s\S]*?)\n\s*```/);
  if (fenced) {
    const inner = fenced[1].trim();
    if (inner.startsWith('{')) return inner;
  }
  const trimmed = text.trim();
  if (trimmed.startsWith('{') && trimmed.endsWith('}')) return trimmed;
  const start = text.indexOf('{');
  const end = text.lastIndexOf('}');
  if (start >= 0 && end > start) return text.slice(start, end + 1);
  throw new ReviewParseError('no JSON object found in reviewer output');
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.length > 0 ? value : null;
}

function parseFinding(value: unknown, index: number): ReviewFinding {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new ReviewParseError(`findings[${index}] is not an object`);
  }
  const record = value as Record<string, unknown>;
  const severity = asString(record.severity)?.toLowerCase();
  if (!severity || !(SEVERITIES as readonly string[]).includes(severity)) {
    throw new ReviewParseError(
      `findings[${index}].severity must be one of ${SEVERITIES.join('|')}, ` +
        `got ${JSON.stringify(record.severity)}`,
    );
  }
  const issue = asString(record.issue) ?? asString(record.summary);
  if (!issue) {
    throw new ReviewParseError(`findings[${index}].issue is required`);
  }
  const line = record.line;
  return {
    id: asString(record.id),
    severity: severity as Severity,
    file: asString(record.file),
    line: typeof line === 'number' && Number.isFinite(line) ? line : null,
    issue,
    evidence: asString(record.evidence),
    requiredChange: asString(record.required_change) ?? asString(record.requiredChange),
  };
}

export function parseReview(text: string): Review {
  if (!text.trim()) throw new ReviewParseError('reviewer output is empty');
  const candidate = extractJsonCandidate(text);
  let parsed: unknown;
  try {
    parsed = JSON.parse(candidate);
  } catch (err) {
    throw new ReviewParseError(
      `invalid JSON: ${err instanceof Error ? err.message : String(err)}`,
    );
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw new ReviewParseError('reviewer output is not a JSON object');
  }
  const record = parsed as Record<string, unknown>;

  const verdictRaw = asString(record.verdict)?.toLowerCase() ?? null;
  if (verdictRaw !== null && verdictRaw !== 'approve' && verdictRaw !== 'revise') {
    throw new ReviewParseError(
      `verdict must be "approve" or "revise", got ${JSON.stringify(record.verdict)}`,
    );
  }
  const findingsRaw = record.findings;
  if (!Array.isArray(findingsRaw)) {
    throw new ReviewParseError('findings must be an array');
  }
  const findings = findingsRaw.map(parseFinding);
  const hasBlockingFindings = findings.some((finding) =>
    BLOCKING_SEVERITIES.has(finding.severity),
  );
  const verdictMismatch =
    verdictRaw !== null && (verdictRaw === 'approve') === hasBlockingFindings;

  return {
    verdict: verdictRaw,
    summary: asString(record.summary) ?? '',
    findings,
    hasBlockingFindings,
    verdictMismatch,
    raw: record,
  };
}

/**
 * Best-effort parse of the Modifier's per-finding resolution report.
 * Returns null when no parseable report is present; a missing report is
 * recorded but never fails the round.
 */
export function parseResolutions(text: string): FindingResolution[] | null {
  let candidate: string;
  try {
    candidate = extractJsonCandidate(text);
  } catch {
    return null;
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(candidate);
  } catch {
    return null;
  }
  if (typeof parsed !== 'object' || parsed === null) return null;
  const list = (parsed as Record<string, unknown>).resolutions;
  if (!Array.isArray(list)) return null;
  const resolutions: FindingResolution[] = [];
  for (const item of list) {
    if (typeof item !== 'object' || item === null) continue;
    const record = item as Record<string, unknown>;
    const id = asString(record.id);
    const status = asString(record.status)?.toLowerCase();
    if (!id) continue;
    if (status !== 'accepted' && status !== 'rebutted' && status !== 'unresolved') {
      continue;
    }
    resolutions.push({ id, status, note: asString(record.note) });
  }
  return resolutions.length > 0 ? resolutions : null;
}
