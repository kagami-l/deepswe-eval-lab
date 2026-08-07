/**
 * Prompt builders for the Modifier and Reviewer roles.
 *
 * The Pier harness submits the task instruction exactly once; every prompt
 * here is derived from that instruction plus intermediate artifacts — never
 * from new user input (docs/archive/collab-agent-design.md section 5.1).
 */

import type { FindingResolution, Review } from './review-schema.js';

const MODIFIER_RULES = `
Ground rules:
- Work ONLY inside the current working directory (the repository checkout).
- Do NOT commit; leave all modifications in the working tree. The harness
  creates checkpoint commits itself.
- Do not create branches, do not fetch or pull, and do not inspect commits
  that are not reachable from the current HEAD.
- Keep the change minimal and focused on the task.
- You may run the repository's own test suite to validate your work.
`.trim();

const REVIEW_OUTPUT_SPEC = `
Respond with ONLY a JSON object (no prose before or after) of this shape:

{
  "verdict": "approve" | "revise",
  "summary": "<one or two sentences>",
  "findings": [
    {
      "id": "R<round>-F<n>",
      "severity": "critical" | "major" | "minor" | "suggestion",
      "file": "<repo-relative path or null>",
      "line": <number or null>,
      "issue": "<what is wrong>",
      "evidence": "<why you believe it is wrong>",
      "required_change": "<what must change>"
    }
  ]
}

Severity rules:
- "critical" and "major" are blocking: the change must be revised.
- "minor" and "suggestion" are recorded but never block delivery.
- Use "approve" with an empty findings list when the change is acceptable.
- Findings decide the outcome; make the verdict consistent with them.
`.trim();

export function buildModifierInitialPrompt(task: string): string {
  return `${task.trim()}

${MODIFIER_RULES}`;
}

function formatFindings(review: Review): string {
  const lines: string[] = [];
  for (const finding of review.findings) {
    const location = finding.file
      ? `${finding.file}${finding.line !== null ? `:${finding.line}` : ''}`
      : '(no location)';
    lines.push(
      `- [${finding.severity}] ${finding.id ?? '(no id)'} ${location}\n` +
        `  issue: ${finding.issue}\n` +
        (finding.evidence ? `  evidence: ${finding.evidence}\n` : '') +
        (finding.requiredChange ? `  required change: ${finding.requiredChange}` : ''),
    );
  }
  return lines.join('\n');
}

function formatResolutions(resolutions: FindingResolution[]): string {
  return resolutions
    .map(
      (resolution) =>
        `- ${resolution.id}: ${resolution.status}` +
        (resolution.note ? ` — ${resolution.note}` : ''),
    )
    .join('\n');
}

export function buildRevisionPrompt(options: {
  task: string;
  review: Review;
  round: number;
  maxReviews: number;
  finalRound: boolean;
}): string {
  const { task, review, round, maxReviews, finalRound } = options;
  const finalNote = finalRound
    ? '\nThis is the FINAL revision: there will be no further review, so ' +
      'prioritize the blocking findings you agree with and leave the code in ' +
      'a deliverable state.'
    : '';
  return `You previously implemented the task below in this repository.
An independent reviewer examined your change (review ${round} of ${maxReviews}) and requests a revision.

<original-task>
${task.trim()}
</original-task>

Reviewer summary: ${review.summary || '(none)'}

Findings:
${formatFindings(review)}

Address every blocking (critical/major) finding: either fix it, or rebut it
with concrete evidence if you believe it is wrong. Non-blocking findings are
optional.${finalNote}

${MODIFIER_RULES}

After finishing, end your reply with ONLY a JSON object reporting how you
handled each finding:

{
  "resolutions": [
    { "id": "<finding id>", "status": "accepted" | "rebutted" | "unresolved", "note": "<short reason>" }
  ]
}`;
}

const PATCH_INLINE_LIMIT = 200_000;

export function buildReviewerPrompt(options: {
  task: string;
  patch: string;
  baseCommit: string;
  round: number;
  maxReviews: number;
  previousReview: Review | null;
  previousResolutions: FindingResolution[] | null;
  retryNote: string | null;
}): string {
  const {
    task,
    patch,
    baseCommit,
    round,
    maxReviews,
    previousReview,
    previousResolutions,
    retryNote,
  } = options;

  const truncated = patch.length > PATCH_INLINE_LIMIT;
  const patchBlock = truncated
    ? patch.slice(0, PATCH_INLINE_LIMIT) +
      `\n... [patch truncated at ${PATCH_INLINE_LIMIT} bytes — run the git ` +
      'command above for the full diff]'
    : patch;

  const history =
    previousReview !== null
      ? `

Previous review (round ${round - 1}) findings:
${formatFindings(previousReview)}

Modifier's reported handling of those findings:
${previousResolutions ? formatResolutions(previousResolutions) : '(no resolution report provided)'}

Do not re-raise a finding that was rebutted with valid evidence; verify the
rebuttal instead. Focus on whether blocking findings were actually resolved
and on any new problems the revision introduced.`
      : '';

  const retry = retryNote ? `\n\nIMPORTANT: ${retryNote}` : '';

  return `You are an independent code reviewer. This is review round ${round} of ${maxReviews}.

A coding agent implemented the following task in this repository checkout
(you are in an isolated copy — you may read anything and run the test suite,
but your edits are discarded):

<original-task>
${task.trim()}
</original-task>

The change under review is the diff from base commit ${baseCommit} to HEAD.
You can reproduce it locally with:

    git diff ${baseCommit} HEAD

<patch>
${patchBlock}
</patch>

Judge ONLY whether the change correctly and completely implements the task
without breaking existing behavior. Style preferences are at most "suggestion".
${history}

${REVIEW_OUTPUT_SPEC}${retry}`;
}

export const REVIEW_FORMAT_RETRY_NOTE =
  'Your previous response could not be parsed as the required JSON object. ' +
  'Respond with ONLY the JSON object described above — no markdown fences, ' +
  'no explanation, no other text.';
