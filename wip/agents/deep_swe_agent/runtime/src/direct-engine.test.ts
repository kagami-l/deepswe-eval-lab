import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

import type { AgentRunner, TurnRequest, TurnResult } from './agent-runner.js';
import type { CollabConfig } from './collaboration-engine.js';
import { DirectCollaborationEngine } from './direct-engine.js';

function git(repo: string, ...args: string[]): string {
  return execFileSync('git', ['-C', repo, ...args], { encoding: 'utf8' });
}

type TurnScript = (request: TurnRequest) => Promise<TurnResult> | TurnResult;

class FakeRunner implements AgentRunner {
  readonly requests: TurnRequest[] = [];
  private index = 0;

  constructor(
    private readonly role: string,
    private readonly script: TurnScript[],
  ) {}

  describe(): Record<string, unknown> {
    return { role: this.role, adapter: 'fake' };
  }

  async runTurn(request: TurnRequest): Promise<TurnResult> {
    this.requests.push(request);
    const step = this.script[this.index];
    if (!step) throw new Error(`FakeRunner(${this.role}): script exhausted`);
    this.index += 1;
    return step(request);
  }
}

function ok(finalText: string): TurnResult {
  return {
    ok: true,
    status: 'success',
    timedOut: false,
    timeoutKind: null,
    finalText,
    usage: { inputTokens: 100, outputTokens: 50, toolUses: 3, costUsd: 0.01 },
    durationMs: 10,
    error: null,
    actualModel: 'fake-model-v1',
  };
}

function processFailure(): TurnResult {
  return {
    ok: false,
    status: 'error',
    timedOut: false,
    timeoutKind: null,
    finalText: '',
    usage: null,
    durationMs: 5,
    error: 'boom',
    actualModel: null,
  };
}

function timeoutFailure(
  timeoutKind: 'total_deadline' | 'stage_timeout' | 'event_silence',
): TurnResult {
  return {
    ok: false,
    status: 'error',
    timedOut: true,
    timeoutKind,
    finalText: '',
    usage: null,
    durationMs: 5,
    error: timeoutKind,
    actualModel: null,
  };
}

const APPROVE = JSON.stringify({ verdict: 'approve', summary: 'ok', findings: [] });
const REVISE = JSON.stringify({
  verdict: 'revise',
  summary: 'needs work',
  findings: [
    {
      id: 'R1-F1',
      severity: 'major',
      file: 'src.txt',
      line: 1,
      issue: 'wrong value',
      evidence: 'observed',
      required_change: 'fix it',
    },
  ],
});
const RESOLUTIONS =
  '{"resolutions":[{"id":"R1-F1","status":"accepted","note":"fixed"}]}';

interface Fixture {
  repo: string;
  config: CollabConfig;
}

async function makeFixture(
  t: { after(fn: () => unknown): void },
  overrides: Partial<CollabConfig> = {},
): Promise<Fixture> {
  const root = await mkdtemp(join(tmpdir(), 'collab-engine-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const repo = join(root, 'app');
  execFileSync('git', ['init', '-q', '-b', 'main', repo]);
  git(repo, 'config', 'user.name', 'test');
  git(repo, 'config', 'user.email', 'test@example.invalid');
  await writeFile(join(repo, 'src.txt'), 'original\n');
  git(repo, 'add', 'src.txt');
  git(repo, 'commit', '-q', '-m', 'base');
  await writeFile(join(repo, 'env.log'), 'baseline untracked\n');

  const instructionPath = join(root, 'instruction.md');
  await writeFile(instructionPath, 'Fix the value in src.txt.\n');

  const config: CollabConfig = {
    repoDir: repo,
    instructionPath,
    outputDir: join(root, 'out'),
    workDir: join(root, 'work'),
    modifier: { adapter: 'codex' },
    reviewer: { adapter: 'claude' },
    maxReviews: 3,
    maxAgentAttempts: 2,
    reviewerTimeoutSec: null,
    revisionTimeoutSec: null,
    eventSilenceTimeoutSec: 60,
    totalTimeoutSec: 1200,
    minTurnSec: 1,
    strict: false,
    keepWorkspaces: false,
    ...overrides,
  };
  return { repo, config };
}

function editFile(repo: string, name: string, content: string): TurnScript {
  return async () => {
    await writeFile(join(repo, name), content);
    return ok('done');
  };
}

test('approve on first review delivers with outcome approved', async (t) => {
  const { repo, config } = await makeFixture(t);
  const modifier = new FakeRunner('modifier', [
    editFile(repo, 'src.txt', 'fixed\n'),
  ]);
  const reviewer = new FakeRunner('reviewer', [() => ok(APPROVE)]);
  const engine = new DirectCollaborationEngine(config, modifier, reviewer);
  const result = await engine.run();

  assert.equal(result.outcome, 'approved');
  assert.equal(result.deliverable, true);
  assert.equal(result.reviewCount, 1);
  assert.equal(result.revisionCount, 0);
  assert.equal(result.checkpoints.length, 1);
  assert.match(git(repo, 'log', '-1', '--format=%s'), /collab: initial implementation/);

  const patch = await readFile(join(config.outputDir, 'final', 'patch.diff'), 'utf8');
  assert.match(patch, /src\.txt/);
  assert.doesNotMatch(patch, /env\.log/);

  // Reviewer ran against an isolated copy, fresh session.
  assert.equal(reviewer.requests[0].resumeSession, false);
  assert.notEqual(reviewer.requests[0].cwd, repo);
  assert.equal(reviewer.requests[0].wallClockTimeoutKind, 'total_deadline');
  assert.ok(reviewer.requests[0].timeoutMs > 600_000);
  const summaryUsage = result.usage;
  assert.equal(summaryUsage.modifier.turns, 1);
  assert.equal(summaryUsage.reviewer?.turns, 1);
  // Provider-resolved models are captured from the init events.
  assert.equal(result.actualModels.modifier, 'fake-model-v1');
  assert.equal(result.actualModels.reviewer, 'fake-model-v1');
});

test('revise then approve counts one revision and passes findings context', async (t) => {
  const { repo, config } = await makeFixture(t);
  const modifier = new FakeRunner('modifier', [
    editFile(repo, 'src.txt', 'first attempt\n'),
    async () => {
      await writeFile(join(repo, 'src.txt'), 'revised\n');
      return ok(`done\n${RESOLUTIONS}`);
    },
  ]);
  const reviewer = new FakeRunner('reviewer', [() => ok(REVISE), () => ok(APPROVE)]);
  const engine = new DirectCollaborationEngine(config, modifier, reviewer);
  const result = await engine.run();

  assert.equal(result.outcome, 'approved');
  assert.equal(result.reviewCount, 2);
  assert.equal(result.revisionCount, 1);
  assert.equal(result.findingsTotal, 1);
  assert.equal(result.blockingFindingsTotal, 1);
  assert.equal(result.checkpoints.length, 2);

  // Round-2 reviewer prompt carries round-1 findings and the resolutions.
  const round2Prompt = reviewer.requests[1].prompt;
  assert.match(round2Prompt, /R1-F1/);
  assert.match(round2Prompt, /accepted/);
  // Revision prompt carried the finding to the modifier.
  assert.match(modifier.requests[1].prompt, /wrong value/);
  assert.equal(modifier.requests[1].resumeSession, true);
  assert.equal(modifier.requests[1].wallClockTimeoutKind, 'total_deadline');
  assert.ok(modifier.requests[1].timeoutMs > 900_000);
});

test('explicit reviewer cap is classified as a stage timeout budget', async (t) => {
  const { repo, config } = await makeFixture(t, { reviewerTimeoutSec: 60 });
  const modifier = new FakeRunner('modifier', [
    editFile(repo, 'src.txt', 'fixed\n'),
  ]);
  const reviewer = new FakeRunner('reviewer', [() => ok(APPROVE)]);
  const engine = new DirectCollaborationEngine(config, modifier, reviewer);
  const result = await engine.run();

  assert.equal(result.outcome, 'approved');
  assert.equal(reviewer.requests[0].timeoutMs, 60_000);
  assert.equal(reviewer.requests[0].wallClockTimeoutKind, 'stage_timeout');
});

test('explicit revision cap is classified as a stage timeout budget', async (t) => {
  const { repo, config } = await makeFixture(t, {
    maxReviews: 1,
    revisionTimeoutSec: 60,
  });
  const modifier = new FakeRunner('modifier', [
    editFile(repo, 'src.txt', 'attempt\n'),
    editFile(repo, 'src.txt', 'final fix\n'),
  ]);
  const reviewer = new FakeRunner('reviewer', [() => ok(REVISE)]);
  const engine = new DirectCollaborationEngine(config, modifier, reviewer);
  const result = await engine.run();

  assert.equal(result.outcome, 'max_reviews_reached');
  assert.equal(modifier.requests[1].timeoutMs, 60_000);
  assert.equal(modifier.requests[1].wallClockTimeoutKind, 'stage_timeout');
});

test('reviewer timeout retries up to maxAgentAttempts and reports timeout', async (t) => {
  const { repo, config } = await makeFixture(t, {
    reviewerTimeoutSec: 60,
    maxAgentAttempts: 3,
  });
  const modifier = new FakeRunner('modifier', [
    editFile(repo, 'src.txt', 'fixed\n'),
  ]);
  const reviewer = new FakeRunner('reviewer', [
    () => timeoutFailure('stage_timeout'),
    () => timeoutFailure('stage_timeout'),
    () => timeoutFailure('stage_timeout'),
  ]);
  const engine = new DirectCollaborationEngine(config, modifier, reviewer);
  const result = await engine.run();

  assert.equal(result.outcome, 'degraded');
  assert.equal(result.degradedReason, 'timeout');
  assert.equal(result.deliverable, true);
  assert.equal(reviewer.requests.length, 3);
  const metadata = JSON.parse(
    await readFile(join(config.outputDir, 'rounds', '01-review', 'metadata.json'), 'utf8'),
  ) as {
    timeoutKind: string | null;
    attempts: { timeoutKind: string | null }[];
  };
  assert.equal(metadata.timeoutKind, 'stage_timeout');
  assert.deepEqual(
    metadata.attempts.map((attempt) => attempt.timeoutKind),
    ['stage_timeout', 'stage_timeout', 'stage_timeout'],
  );
});

test('min-turn admission stops retries and records total deadline exhaustion', async (t) => {
  const { config } = await makeFixture(t, {
    totalTimeoutSec: 1,
    minTurnSec: 2,
    maxAgentAttempts: 4,
  });
  const modifier = new FakeRunner('modifier', []);
  const reviewer = new FakeRunner('reviewer', []);
  const engine = new DirectCollaborationEngine(config, modifier, reviewer);
  const result = await engine.run();

  assert.equal(result.outcome, 'timeout');
  assert.equal(result.deliverable, false);
  assert.equal(modifier.requests.length, 0);
  const metadata = JSON.parse(
    await readFile(join(config.outputDir, 'rounds', '00-modify', 'metadata.json'), 'utf8'),
  ) as { timeoutKind: string | null; attempts: unknown[] };
  assert.equal(metadata.timeoutKind, 'total_deadline');
  assert.deepEqual(metadata.attempts, []);
});

test('invalid review JSON retries once then degrades but still delivers', async (t) => {
  const { repo, config } = await makeFixture(t);
  const modifier = new FakeRunner('modifier', [
    editFile(repo, 'src.txt', 'fixed\n'),
  ]);
  const reviewer = new FakeRunner('reviewer', [
    () => ok('not json at all'),
    () => ok('still not json'),
  ]);
  const engine = new DirectCollaborationEngine(config, modifier, reviewer);
  const result = await engine.run();

  assert.equal(result.outcome, 'degraded');
  assert.equal(result.degradedReason, 'invalid_review_output');
  assert.equal(result.deliverable, true);
  // Second attempt got the format retry note.
  assert.match(reviewer.requests[1].prompt, /could not be parsed/);
});

test('a retracted verdict retries instead of delivering the retracted approval', async (t) => {
  const { repo, config } = await makeFixture(t);
  const modifier = new FakeRunner('modifier', [
    editFile(repo, 'src.txt', 'fixed\n'),
  ]);
  const reviewer = new FakeRunner('reviewer', [
    () =>
      ok(
        '{"verdict":"approve","summary":"s","findings":[]}\n' +
          'Scratch that, my verdict is:\n' +
          '{"verdict":"maybe","findings":[]}',
      ),
    () => ok('still not a verdict'),
  ]);
  const engine = new DirectCollaborationEngine(config, modifier, reviewer);
  const result = await engine.run();

  // Reading the retracted approval would have ended the loop at "approved".
  assert.notEqual(result.outcome, 'approved');
  assert.equal(result.degradedReason, 'invalid_review_output');
  assert.equal(reviewer.requests.length, 2);
  assert.match(reviewer.requests[1].prompt, /could not be parsed/);
});

test('a trailing log object never approves past blocking findings', async (t) => {
  const { repo, config } = await makeFixture(t);
  const modifier = new FakeRunner('modifier', [
    editFile(repo, 'src.txt', 'fixed\n'),
    editFile(repo, 'src.txt', 'revised\n'),
  ]);
  const reviewer = new FakeRunner('reviewer', [
    () =>
      ok(
        '{"verdict":"revise","summary":"s","findings":[' +
          '{"id":"R1-F1","severity":"major","issue":"x"}]}\n' +
          'Log: {"findings":[]}',
      ),
    () => ok('{"verdict":"approve","summary":"s","findings":[]}'),
  ]);
  const engine = new DirectCollaborationEngine(config, modifier, reviewer);
  const result = await engine.run();

  assert.equal(result.outcome, 'approved');
  // The blocking finding drove a revision before the approval.
  assert.equal(modifier.requests.length, 2);
  assert.match(modifier.requests[1].prompt, /R1-F1/);
});

test('strict mode turns degraded into non-deliverable', async (t) => {
  const { repo, config } = await makeFixture(t, { strict: true });
  const modifier = new FakeRunner('modifier', [
    editFile(repo, 'src.txt', 'fixed\n'),
  ]);
  const reviewer = new FakeRunner('reviewer', [processFailure, processFailure]);
  const engine = new DirectCollaborationEngine(config, modifier, reviewer);
  const result = await engine.run();

  assert.equal(result.outcome, 'degraded');
  assert.equal(result.degradedReason, 'reviewer_failed');
  assert.equal(result.deliverable, false);
});

test('initial modifier producing no change fails with empty_patch', async (t) => {
  const { config } = await makeFixture(t);
  const modifier = new FakeRunner('modifier', [() => ok('did nothing'), () => ok('again nothing')]);
  const reviewer = new FakeRunner('reviewer', []);
  const engine = new DirectCollaborationEngine(config, modifier, reviewer);
  const result = await engine.run();

  assert.equal(result.outcome, 'empty_patch');
  assert.equal(result.deliverable, false);
  assert.equal(result.reviewCount, 0);
});

test('initial modifier process failure rolls back partial edits and fails', async (t) => {
  const { repo, config } = await makeFixture(t);
  const modifier = new FakeRunner('modifier', [
    async () => {
      await writeFile(join(repo, 'src.txt'), 'half-done\n');
      await writeFile(join(repo, 'partial.txt'), 'junk\n');
      return processFailure();
    },
    processFailure,
  ]);
  const reviewer = new FakeRunner('reviewer', []);
  const engine = new DirectCollaborationEngine(config, modifier, reviewer);
  const result = await engine.run();

  assert.equal(result.outcome, 'modifier_failed');
  assert.equal(result.deliverable, false);
  // Rollback restored the tree and removed the partial untracked file.
  assert.equal(await readFile(join(repo, 'src.txt'), 'utf8'), 'original\n');
  assert.equal(git(repo, 'status', '--porcelain').includes('partial.txt'), false);
  assert.equal(await readFile(join(repo, 'env.log'), 'utf8'), 'baseline untracked\n');
});

test('no-change revision stops the loop without another review', async (t) => {
  const { repo, config } = await makeFixture(t);
  const modifier = new FakeRunner('modifier', [
    editFile(repo, 'src.txt', 'attempt\n'),
    () => ok('I disagree with the finding.\n{"resolutions":[{"id":"R1-F1","status":"rebutted","note":"works as intended"}]}'),
  ]);
  const reviewer = new FakeRunner('reviewer', [() => ok(REVISE)]);
  const engine = new DirectCollaborationEngine(config, modifier, reviewer);
  const result = await engine.run();

  assert.equal(result.outcome, 'max_reviews_reached');
  assert.equal(result.noChangeRevision, true);
  assert.equal(result.reviewCount, 1);
  assert.equal(result.revisionCount, 1);
  assert.equal(result.deliverable, true);
});

test('final round revision delivers as max_reviews_reached without extra review', async (t) => {
  const { repo, config } = await makeFixture(t, { maxReviews: 1 });
  const modifier = new FakeRunner('modifier', [
    editFile(repo, 'src.txt', 'attempt\n'),
    editFile(repo, 'src.txt', 'final fix\n'),
  ]);
  const reviewer = new FakeRunner('reviewer', [() => ok(REVISE)]);
  const engine = new DirectCollaborationEngine(config, modifier, reviewer);
  const result = await engine.run();

  assert.equal(result.outcome, 'max_reviews_reached');
  assert.equal(result.reviewCount, 1);
  assert.equal(result.revisionCount, 1);
  assert.match(git(repo, 'log', '-1', '--format=%s'), /collab: final revision/);
  assert.match(modifier.requests[1].prompt, /FINAL revision/);
});

test('maxReviews=0 delivers modifier-only through the same pipeline', async (t) => {
  const { repo, config } = await makeFixture(t, { maxReviews: 0 });
  const modifier = new FakeRunner('modifier', [
    editFile(repo, 'src.txt', 'fixed without review\n'),
  ]);
  const reviewer = new FakeRunner('reviewer', []);
  const engine = new DirectCollaborationEngine(config, modifier, reviewer);
  const result = await engine.run();

  assert.equal(result.outcome, 'max_reviews_reached');
  assert.equal(result.deliverable, true);
  assert.equal(result.reviewCount, 0);
  assert.equal(reviewer.requests.length, 0);
  const patch = await readFile(join(config.outputDir, 'final', 'patch.diff'), 'utf8');
  assert.match(patch, /fixed without review/);
});

test('infrastructure exception after a trusted checkpoint degrades but delivers', async (t) => {
  const { repo, config } = await makeFixture(t);
  const modifier = new FakeRunner('modifier', [
    editFile(repo, 'src.txt', 'fixed\n'),
  ]);
  // Empty script: the reviewer runner THROWS (infrastructure failure), which
  // is different from a TurnResult process failure.
  const reviewer = new FakeRunner('reviewer', []);
  const engine = new DirectCollaborationEngine(config, modifier, reviewer);
  const result = await engine.run();

  assert.equal(result.outcome, 'degraded');
  assert.equal(result.degradedReason, 'infrastructure');
  assert.equal(result.deliverable, true);
  assert.match(result.error ?? '', /script exhausted/);
  // The trusted checkpoint and real usage survive into the summary.
  assert.equal(result.checkpoints.length, 1);
  assert.equal(result.usage.modifier.turns, 1);
  const patch = await readFile(join(config.outputDir, 'final', 'patch.diff'), 'utf8');
  assert.match(patch, /src\.txt/);
});

test('infrastructure exception before any checkpoint fails but keeps context', async (t) => {
  const { config } = await makeFixture(t);
  const modifier = new FakeRunner('modifier', []); // throws on first turn
  const reviewer = new FakeRunner('reviewer', []);
  const engine = new DirectCollaborationEngine(config, modifier, reviewer);
  const result = await engine.run();

  assert.equal(result.outcome, 'checkpoint_failed');
  assert.equal(result.deliverable, false);
  assert.match(result.error ?? '', /script exhausted/);
  // The engine finalized itself: base commit is recorded, not blanked.
  assert.notEqual(result.baseCommit, '');
});

test('modifier committing by itself is tolerated and recorded', async (t) => {
  const { repo, config } = await makeFixture(t);
  const modifier = new FakeRunner('modifier', [
    async () => {
      await writeFile(join(repo, 'src.txt'), 'fixed by agent\n');
      git(repo, 'add', 'src.txt');
      git(repo, 'commit', '-q', '-m', 'agent did this itself');
      return ok('done');
    },
  ]);
  const reviewer = new FakeRunner('reviewer', [() => ok(APPROVE)]);
  const engine = new DirectCollaborationEngine(config, modifier, reviewer);
  const result = await engine.run();

  assert.equal(result.outcome, 'approved');
  assert.equal(result.protocolViolations.length, 1);
  const patch = await readFile(join(config.outputDir, 'final', 'patch.diff'), 'utf8');
  assert.match(patch, /fixed by agent/);
});
