import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { Cligent, type DoneUsage } from '@sublang/cligent';
import { CligentRunner } from './agent-runner.js';
import { emptyRoleUsage } from './collaboration-engine.js';
import { DirectCollaborationEngine } from './direct-engine.js';
import { SingleWorkflowEngine } from './single-engine.js';
import { accumulateUsage, normalizeUsage } from './usage.js';

const measured: DoneUsage = {
  toolUses: 2,
  tokens: {
    coverage: 'complete',
    totals: { input: { total: 100, uncached: 30, cacheRead: 60, cacheWrite: 10 }, output: { total: 20, visible: 5, reasoning: 15 } },
    records: [
      { model: 'main', tokens: { input: { total: 70 }, output: { total: 12 } } },
      { model: 'child', tokens: { input: { total: 30 }, output: { total: 8 } } },
    ],
  },
  cost: { amount: 0.125, currency: 'USD', source: 'agent-estimate' },
};

test('missing turns retain observed subtotals and cost provenance without claiming completeness', () => {
  const bucket = emptyRoleUsage();
  accumulateUsage(bucket, normalizeUsage(measured), 10);
  accumulateUsage(bucket, null, 20);
  accumulateUsage(bucket, normalizeUsage({ toolUses: 3, tokens: {
    coverage: 'partial', totals: { input: { total: 0 }, output: { total: 0 } },
  } }), 30);
  assert.equal(bucket.tokenAvailability, 'unavailable');
  assert.equal(bucket.inputTokens, null);
  assert.equal(bucket.tokens?.totals.input.total, 100);
  assert.equal(bucket.tokens?.totals.output.total, 20);
  assert.equal(bucket.tokens?.totals.input.cacheRead, undefined);
  assert.equal(bucket.tokenCoverage, 'partial');
  assert.equal(bucket.costCoverage, 'partial');
  assert.equal(bucket.costUsd, 0.125);
  assert.equal(bucket.usageReports?.[0]?.tokens?.records?.[1].model, 'child');
  assert.equal(bucket.usageReports?.[0]?.cost?.source, 'agent-estimate');
  assert.equal(bucket.usageReports?.[1], null);
  assert.equal(bucket.toolUses, 5);
  assert.equal(bucket.turns, 3);
  assert.equal(bucket.wallMs, 60);
});

test('measured zero and cost-only reports keep independently observed values', () => {
  const zero = normalizeUsage({ toolUses: 0, tokens: {
    coverage: 'complete', totals: { input: { total: 0 }, output: { total: 0 } },
  } });
  assert.equal(zero.tokenAvailability, 'reported');
  assert.equal(zero.inputTokens, 0);
  const costOnly = normalizeUsage({ toolUses: 1, cost: { amount: 0, currency: 'USD', source: 'provider-reported' } });
  assert.equal(costOnly.tokenAvailability, 'unavailable');
  assert.equal(costOnly.costUsd, 0);
  assert.equal(costOnly.costCoverage, 'complete');
});

for (const topology of ['single', 'collab'] as const) {
  test(`${topology}: released Cligent events flow through runner, workflow and serialized artifacts`, async (t) => {
    const root = await mkdtemp(join(tmpdir(), 'cligent-upgrade-'));
    t.after(() => rm(root, { recursive: true, force: true }));
    const repo = join(root, 'repo');
    execFileSync('git', ['init', '-q', '-b', 'main', repo]);
    const git = (...args: string[]) => execFileSync('git', ['-C', repo, ...args]);
    git('config', 'user.email', 'test@example.invalid');
    git('config', 'user.name', 'test');
    await writeFile(join(repo, 'file'), 'before\n');
    git('add', 'file'); git('commit', '-qm', 'base');
    const instructionPath = join(root, 'instruction.md');
    await writeFile(instructionPath, 'Fix file.');
    const modifier = new CligentRunner('modifier', { adapter: 'claude' });
    const adapter = {
      name: 'claude-code',
      async *run() {
        await writeFile(join(repo, 'file'), 'after\n');
        yield { type: 'done', agent: 'claude-code', sessionId: 'fixture', timestamp: Date.now(), payload: {
          status: 'success', result: 'fixed', durationMs: 1, usage: measured,
        } };
      },
    };
    Object.assign(modifier, { cligent: new Cligent(adapter as never) });
    const config = {
      repoDir: repo, instructionPath, outputDir: join(root, 'out'), workDir: join(root, 'work'),
      modifier: { adapter: 'claude' as const }, maxAgentAttempts: 1, eventSilenceTimeoutSec: 10,
      totalTimeoutSec: 60, minTurnSec: 1,
    };
    const engine = topology === 'single' ? new SingleWorkflowEngine(config, modifier)
      : new DirectCollaborationEngine({ ...config, reviewer: { adapter: 'claude' }, maxReviews: 0,
        reviewerTimeoutSec: null, revisionTimeoutSec: null, strict: false, keepWorkspaces: false }, modifier, modifier);
    const result = await engine.run();
    assert.equal(result.deliverable, true);
    assert.equal(result.usage.modifier.inputTokens, 100);
    assert.equal(result.usage.modifier.outputTokens, 20);
    assert.equal(result.usage.modifier.tokenCoverage, 'complete');
    assert.equal(result.usage.modifier.costCoverage, 'complete');
    assert.deepEqual(result.usage.modifier.tokens, measured.tokens);
    const serialized = JSON.parse(JSON.stringify(result));
    assert.deepEqual(serialized.usage.modifier.usageReports, [measured]);
    const events = (await readFile(join(config.outputDir, 'events.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    assert.deepEqual(events.find(event => event.type === 'done').payload.usage, measured);
  });
}
