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
 * Quotes are tracked everywhere, so a brace quoted in prose (`the "{" token`)
 * does not open a bogus region and mask the answer behind it. A raw newline
 * ends the string: real JSON strings escape their newlines, so meeting one
 * proves the quote came from prose, and a single unbalanced quote can only
 * disturb its own line. Regions are reported on each closing brace, so an
 * object nested under an unterminated `{` is still found.
 */
interface Candidate {
  raw: string;
  start: number;
  end: number;
  /** Null when the region is not a JSON object — quoted code, a type sketch. */
  value: Record<string, unknown> | null;
}

function jsonObjectCandidates(text: string): Candidate[] {
  const candidates: Candidate[] = [];
  const opens: number[] = [];
  let inString = false;
  let escaped = false;
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (inString) {
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
    else if (char === '}' && opens.length > 0) {
      const start = opens.pop() as number;
      const raw = text.slice(start, i + 1);
      let value: Record<string, unknown> | null = null;
      try {
        const parsed: unknown = JSON.parse(raw);
        if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
          value = parsed as Record<string, unknown>;
        }
      } catch {
        // Left unparsed; callers decide whether the region still means something.
      }
      candidates.push({ raw, start, end: i + 1, value });
    }
  }
  return candidates;
}

/**
 * Candidates that can stand on their own, ordered by closing position.
 *
 * A region enclosed by another region that parsed is part of that object — a
 * finding, or a `payload` inside a log line — and must never be mistaken for
 * the reviewer's own answer. Enclosure by an *unparsed* region carries no such
 * meaning: quoted code with stray braces routinely swallows the real answer,
 * so those inner regions stay eligible.
 */
function eligibleCandidates(text: string): Candidate[] {
  const candidates = jsonObjectCandidates(text);
  return candidates.filter(
    (candidate) =>
      !candidates.some(
        (other) =>
          other.value !== null &&
          other.start < candidate.start &&
          candidate.end <= other.end,
      ),
  );
}

/** Whether an unparsed region still declares `key`, e.g. a truncated answer. */
function declaresKey(raw: string, key: string): boolean {
  return new RegExp(`"${key}"\\s*:`).test(raw);
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
  const candidates = eligibleCandidates(text);

  // Stating a verdict is how a reviewer signs its decision, so the last
  // candidate that states one is authoritative. It must validate: falling
  // further back would resurrect a verdict the reviewer already superseded,
  // while failing here surfaces `invalid_review_output` and retries the turn.
  // A truncated answer counts too — losing its closing brace must not hand the
  // decision back to an earlier one.
  for (let index = candidates.length - 1; index >= 0; index--) {
    const { raw, value } = candidates[index];
    if (value !== null && Object.hasOwn(value, 'verdict')) {
      return buildReview(value);
    }
    if (value === null && declaresKey(raw, 'verdict')) {
      throw new ReviewParseError(
        'the reviewer output nearest the end states a verdict but is not valid JSON',
      );
    }
  }

  // No verdict anywhere. The schema accepts a verdict-less review because
  // findings alone decide the outcome, but only an unambiguous one: with more
  // than one candidate there is no way to tell the answer from a trailing log
  // line, and guessing wrong would approve past blocking findings.
  const objects = candidates.map((candidate) => candidate.value).filter((value) => value !== null);
  if (objects.length === 1) return buildReview(objects[0]);
  if (objects.length === 0) {
    throw new ReviewParseError('no JSON object found in reviewer output');
  }
  throw new ReviewParseError(
    `reviewer output has ${objects.length} candidate objects and none states a verdict`,
  );
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
  const candidates = eligibleCandidates(text);
  for (let index = candidates.length - 1; index >= 0; index--) {
    const { raw, value } = candidates[index];
    // The nearest report is the current one, whether or not it survived. If it
    // resolves nothing — empty, all-invalid, or too damaged to parse — that is
    // the answer; searching further back would hand a superseded round's
    // resolutions to the next reviewer as if they applied to this one.
    if (value === null) {
      if (declaresKey(raw, 'resolutions')) return null;
      continue;
    }
    const list = value.resolutions;
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
    return resolutions.length > 0 ? resolutions : null;
  }
  return null;
}
