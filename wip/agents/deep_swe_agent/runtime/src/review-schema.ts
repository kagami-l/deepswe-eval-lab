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

/**
 * Every balanced `{...}` region in `text`, ordered by closing position.
 *
 * Agents rarely obey "respond with ONLY a JSON object": the answer arrives
 * after progress notes, sometimes inside a ```json fence, and the text ahead of
 * it may hold unrelated objects (code fragments, type sketches). Picking the
 * first fence or the first `{` therefore selects the wrong candidate. Callers
 * walk this list backwards and take the last region that actually validates, so
 * the answer wins over anything quoted before it.
 *
 * Quotes only toggle string state inside a region, keeping stray prose quotes
 * from masking a later object. Regions are reported on each closing brace, so
 * an object nested under an unterminated `{` is still found.
 */
function jsonObjectCandidates(text: string): string[] {
  const candidates: string[] = [];
  const opens: number[] = [];
  let inString = false;
  let escaped = false;
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (opens.length === 0) {
      if (char === '{') opens.push(i);
      continue;
    }
    if (inString) {
      // A JSON string cannot hold a raw newline, so one proves the quote came
      // from prose or code rather than from the object being scanned. Ending
      // the string at the line break stops a single stray quote from masking
      // every brace after it.
      if (char === '\n') {
        inString = false;
        escaped = false;
      } else if (escaped) escaped = false;
      else if (char === '\\') escaped = true;
      else if (char === '"') inString = false;
      continue;
    }
    if (char === '"') inString = true;
    else if (char === '{') opens.push(i);
    else if (char === '}') {
      candidates.push(text.slice(opens.pop() as number, i + 1));
    }
  }
  return candidates;
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
  const candidates = jsonObjectCandidates(text);
  if (candidates.length === 0) {
    throw new ReviewParseError('no JSON object found in reviewer output');
  }
  // Last valid region wins. The first failure met walking backwards is the one
  // reported: it comes from the candidate nearest the end, which is almost
  // always the answer the reviewer meant to give.
  let nearestError: ReviewParseError | null = null;
  for (let index = candidates.length - 1; index >= 0; index--) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(candidates[index]);
    } catch (err) {
      nearestError ??= new ReviewParseError(
        `invalid JSON: ${err instanceof Error ? err.message : String(err)}`,
      );
      continue;
    }
    try {
      return buildReview(parsed as Record<string, unknown>);
    } catch (err) {
      if (!(err instanceof ReviewParseError)) throw err;
      nearestError ??= err;
    }
  }
  throw nearestError ?? new ReviewParseError('no JSON object found in reviewer output');
}

function buildReview(record: Record<string, unknown>): Review {
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
  const candidates = jsonObjectCandidates(text);
  for (let index = candidates.length - 1; index >= 0; index--) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(candidates[index]);
    } catch {
      continue;
    }
    if (typeof parsed !== 'object' || parsed === null) continue;
    const list = (parsed as Record<string, unknown>).resolutions;
    if (!Array.isArray(list)) continue;
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
    if (resolutions.length > 0) return resolutions;
  }
  return null;
}
