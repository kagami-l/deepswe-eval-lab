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

test('the answer wins over objects quoted ahead of it', () => {
  // The shape that produced 18 false parse errors in the 12-task collab run:
  // a replayed prompt carrying pseudo-JSON and patch code, then the answer.
  const answer = {
    verdict: 'revise',
    summary: 'nested modules lose the module path',
    findings: [
      {
        id: 'R1-F1',
        severity: 'major',
        file: 'evaluator/modules.go',
        line: 257,
        issue: 'child environments do not inherit ABS_MODULE_PATH',
        evidence: 'a nested require resolves against an empty path',
        required_change: 'carry the resolution config through nested loads',
      },
    ],
  };
  const review = parseReview(
    [
      'You are an independent code reviewer.',
      'Respond with ONLY a JSON object of this shape:',
      '{',
      '  "verdict": "approve" | "revise",',
      '  "line": <number or null>',
      '}',
      '',
      'Patch under review:',
      '+func init() {',
      '+\tcounts := map[string]int{"deprecated_hits": 1}',
      '+\tcfg := map[string]bool{"enabled": True}',
      '+}',
      '',
      'I verified the nested-graph case and found a blocking issue.',
      JSON.stringify(answer),
    ].join('\n'),
  );

  assert.equal(review.verdict, 'revise');
  assert.equal(review.findings.length, 1);
  assert.equal(review.findings[0].id, 'R1-F1');
  assert.equal(review.hasBlockingFindings, true);
});

test('a fenced answer wins over an earlier fenced code block', () => {
  const review = parseReview(
    [
      'The current config object is:',
      '```json',
      '{"enabled": True, "retries": 3}',
      '```',
      'That is invalid JSON, but my review is:',
      '```json',
      '{"verdict":"approve","summary":"looks right","findings":[]}',
      '```',
    ].join('\n'),
  );

  assert.equal(review.verdict, 'approve');
  assert.equal(review.summary, 'looks right');
});

test('prose quotes and braces inside strings do not hide the answer', () => {
  const review = parseReview(
    'I first thought the fix was "wrong" — see the `{` handling below.\n' +
      '{"verdict":"revise","summary":"s","findings":[{"severity":"major",' +
      '"issue":"unbalanced } in the error message","file":null,"line":null}]}',
  );

  assert.equal(review.verdict, 'revise');
  assert.equal(review.findings[0].issue, 'unbalanced } in the error message');
});

test('an unmatched brace and a stray quote ahead do not mask the answer', () => {
  // The Cliffy shape: a quoted patch left 9 unmatched `{` and an odd number of
  // quotes ahead of the review, which used to swallow every later brace.
  const review = parseReview(
    [
      'The patch adds:',
      '+func load(path string) error {',
      '+\tif cfg.Has("name) {',
      '+\treturn &ConfigError{',
      '',
      'My review:',
      '{"verdict":"revise","summary":"s","findings":[]}',
    ].join('\n'),
  );

  assert.equal(review.verdict, 'revise');
});

test('an unterminated brace ahead of the answer is skipped', () => {
  const review = parseReview(
    'Consider the block starting at {\n' +
      '{"verdict":"approve","summary":"s","findings":[]}',
  );

  assert.equal(review.verdict, 'approve');
});

test('an invalid latest verdict fails instead of reviving the earlier one', () => {
  // Falling back here would deliver a verdict the reviewer explicitly retracted.
  // Throwing surfaces invalid_review_output so the turn is retried.
  assert.throws(
    () =>
      parseReview(
        '{"verdict":"approve","summary":"s","findings":[]}\n' +
          'Scratch that, my verdict is:\n' +
          '{"verdict":"maybe","findings":[]}',
      ),
    (err: unknown) =>
      err instanceof ReviewParseError && /maybe/.test(err.message),
  );
});

test('a trailing object without a verdict cannot erase blocking findings', () => {
  // `{"findings":[]}` passes the schema on its own, and the engine approves on
  // hasBlockingFindings === false — so preferring it would ship an unrevised
  // blocking review.
  const review = parseReview(
    '{"verdict":"revise","summary":"s","findings":[' +
      '{"severity":"major","issue":"nested modules lose the module path"}]}\n' +
      'Log: {"findings":[]}',
  );

  assert.equal(review.verdict, 'revise');
  assert.equal(review.findings.length, 1);
  assert.equal(review.hasBlockingFindings, true);
});

test('a verdict-less review is still accepted when no verdict is stated', () => {
  const review = parseReview(
    'Nothing blocking here.\n{"summary":"s","findings":[]}',
  );

  assert.equal(review.verdict, null);
  assert.equal(review.hasBlockingFindings, false);
});

test('a quoted brace on the answer line does not mask the answer', () => {
  const review = parseReview(
    'The token "{" is special; answer: {"verdict":"approve","summary":"s","findings":[]}',
  );

  assert.equal(review.verdict, 'approve');
});

test('when nothing validates, the error comes from the nearest candidate', () => {
  assert.throws(
    () =>
      parseReview(
        '{"verdict":"approve"}\nActually:\n{"verdict":"maybe","findings":[]}',
      ),
    (err: unknown) =>
      err instanceof ReviewParseError && /maybe/.test(err.message),
  );
});

test('an empty latest resolutions report does not revive an earlier one', () => {
  assert.equal(
    parseResolutions(
      'Earlier {"resolutions":[{"id":"R1-F1","status":"accepted"}]}\n' +
        'Final {"resolutions":[]}',
    ),
    null,
  );
});

test('modifier resolutions also come from the last valid object', () => {
  const resolutions = parseResolutions(
    'The prompt listed {"resolutions": []} as the required shape.\n' +
      JSON.stringify({
        resolutions: [{ id: 'R1-F1', status: 'accepted', note: 'fixed' }],
      }),
  );

  assert.ok(resolutions);
  assert.equal(resolutions.length, 1);
  assert.equal(resolutions[0].id, 'R1-F1');
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
