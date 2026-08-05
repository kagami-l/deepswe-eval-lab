import assert from 'node:assert/strict';
import test from 'node:test';

import { parseConfig } from './main.js';

function role(adapter: string): Record<string, unknown> {
  return {
    name: adapter,
    adapter,
    model: `${adapter}-model`,
    effort: 'high',
    permissions: adapter === 'codex' ? 'bypass' : 'auto',
  };
}

function basePlan(
  topology: 'single' | 'collab',
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    repoDir: '/app',
    instructionPath: '/logs/agent/system/instruction.md',
    outputDir: '/logs/agent/system',
    workDir: '/tmp/deep-swe-agent',
    executionPlan: {
      schemaVersion: 1,
      topology,
      workflow: topology === 'single' ? 'single' : 'review-loop',
      engine: 'direct',
      roles: {
        modifier: role('codex'),
        reviewer: topology === 'collab' ? role('gemini') : null,
      },
      budget: {
        soft_deadline_seconds: 5100,
      },
      workflowConfig: {
        maxReviews: 3,
        maxAgentAttempts: 2,
        reviewerTimeoutSeconds: 600,
        revisionTimeoutSeconds: 900,
        eventSilenceTimeoutSeconds: 600,
        minTurnSeconds: 120,
      },
      ...overrides,
    },
  };
}

test('parses a single plan without a reviewer', () => {
  const parsed = parseConfig(basePlan('single'));
  assert.equal(parsed.topology, 'single');
  assert.equal(parsed.single?.modifier.adapter, 'codex');
  assert.equal(parsed.single?.modifierTimeoutSec, 5100);
  assert.equal(parsed.single?.eventSilenceTimeoutSec, 600);
  assert.equal(parsed.collab, undefined);
});

test('parses all supported reviewer adapters', () => {
  for (const adapter of ['claude', 'codex', 'gemini', 'kimi', 'opencode']) {
    const raw = basePlan('collab');
    const plan = raw.executionPlan as Record<string, unknown>;
    const roles = plan.roles as Record<string, unknown>;
    roles.reviewer = role(adapter);
    assert.equal(parseConfig(raw).collab?.reviewer.adapter, adapter);
  }
});

test('single rejects a reviewer', () => {
  const raw = basePlan('single');
  const plan = raw.executionPlan as Record<string, unknown>;
  const roles = plan.roles as Record<string, unknown>;
  roles.reviewer = role('claude');
  assert.throws(() => parseConfig(raw), /must not define a reviewer/);
});

test('collab rejects zero reviews', () => {
  const raw = basePlan('collab');
  const plan = raw.executionPlan as Record<string, unknown>;
  const workflow = plan.workflowConfig as Record<string, unknown>;
  workflow.maxReviews = 0;
  assert.throws(() => parseConfig(raw), /positive integer/);
});
