import assert from 'node:assert/strict';
import test from 'node:test';

import {
  parseResolutions,
  parseReview,
  ReviewParseError,
} from './review-schema.js';

test('parses a plain approve review', () => {
  const review = parseReview(
    JSON.stringify({ verdict: 'approve', summary: 'ok', findings: [] }),
  );
  assert.equal(review.verdict, 'approve');
  assert.equal(review.hasBlockingFindings, false);
  assert.equal(review.verdictMismatch, false);
});

test('parses a fenced revise review with findings', () => {
  const body = JSON.stringify({
    verdict: 'revise',
    summary: 'two problems',
    findings: [
      {
        id: 'R1-F1',
        severity: 'major',
        file: 'src/foo.ts',
        line: 84,
        issue: 'handler is dropped',
        evidence: 'register() overwrites entry',
        required_change: 'compose handlers',
      },
      { id: 'R1-F2', severity: 'suggestion', issue: 'rename variable' },
    ],
  });
  const review = parseReview('Here is my review:\n```json\n' + body + '\n```\n');
  assert.equal(review.verdict, 'revise');
  assert.equal(review.findings.length, 2);
  assert.equal(review.findings[0].severity, 'major');
  assert.equal(review.findings[0].line, 84);
  assert.equal(review.findings[1].file, null);
  assert.equal(review.hasBlockingFindings, true);
  assert.equal(review.verdictMismatch, false);
});

test('findings drive the decision; contradictory verdict is flagged', () => {
  const review = parseReview(
    JSON.stringify({
      verdict: 'approve',
      summary: 'fine',
      findings: [{ id: 'F1', severity: 'critical', issue: 'crashes on start' }],
    }),
  );
  assert.equal(review.hasBlockingFindings, true);
  assert.equal(review.verdictMismatch, true);
});

test('minor-only findings do not block', () => {
  const review = parseReview(
    JSON.stringify({
      verdict: 'approve',
      summary: 'nits only',
      findings: [{ id: 'F1', severity: 'minor', issue: 'typo' }],
    }),
  );
  assert.equal(review.hasBlockingFindings, false);
  assert.equal(review.verdictMismatch, false);
});

test('rejects invalid severity, missing findings, and non-JSON', () => {
  assert.throws(
    () =>
      parseReview(
        JSON.stringify({
          verdict: 'revise',
          findings: [{ severity: 'blocker', issue: 'x' }],
        }),
      ),
    ReviewParseError,
  );
  assert.throws(
    () => parseReview(JSON.stringify({ verdict: 'approve' })),
    ReviewParseError,
  );
  assert.throws(() => parseReview('no json here'), ReviewParseError);
  assert.throws(() => parseReview(''), ReviewParseError);
});

test('extracts the JSON object embedded in surrounding prose', () => {
  const review = parseReview(
    'Summary first.\n{"verdict":"approve","summary":"s","findings":[]}\nthanks',
  );
  assert.equal(review.verdict, 'approve');
});

test('parses modifier resolutions and ignores malformed entries', () => {
  const resolutions = parseResolutions(
    'Done.\n```json\n' +
      JSON.stringify({
        resolutions: [
          { id: 'R1-F1', status: 'accepted', note: 'fixed' },
          { id: 'R1-F2', status: 'REBUTTED' },
          { id: 'R1-F3', status: 'bogus' },
          { status: 'accepted' },
        ],
      }) +
      '\n```',
  );
  assert.ok(resolutions);
  assert.equal(resolutions.length, 2);
  assert.equal(resolutions[0].status, 'accepted');
  assert.equal(resolutions[1].status, 'rebutted');
});

test('resolutions parse returns null on absent or unrelated JSON', () => {
  assert.equal(parseResolutions('all done, no JSON'), null);
  assert.equal(parseResolutions('{"verdict":"approve","findings":[]}'), null);
});
