import assert from 'node:assert/strict';
import test from 'node:test';

import { parseConfig } from './main.js';

function baseRaw(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    repoDir: '/app',
    instructionPath: '/logs/agent/collab/instruction.md',
    outputDir: '/logs/agent/collab',
    workDir: '/tmp/deepswe-collab',
    modifier: { adapter: 'codex' },
    reviewer: { adapter: 'claude' },
    ...overrides,
  };
}

test('applies documented defaults', () => {
  const config = parseConfig(baseRaw());
  assert.equal(config.maxReviews, 3);
  assert.equal(config.maxAgentAttempts, 2);
  assert.equal(config.totalTimeoutSec, 5100);
  assert.equal(config.strict, false);
});

test('maxReviews=0 is accepted (modifier-only control arm)', () => {
  const config = parseConfig(baseRaw({ maxReviews: 0 }));
  assert.equal(config.maxReviews, 0);
});

test('negative or fractional maxReviews is rejected', () => {
  assert.throws(() => parseConfig(baseRaw({ maxReviews: -1 })), /non-negative/);
  assert.throws(() => parseConfig(baseRaw({ maxReviews: 1.5 })), /non-negative/);
});

test('unsupported adapters are rejected', () => {
  assert.throws(
    () => parseConfig(baseRaw({ reviewer: { adapter: 'gemini' } })),
    /reviewer\.adapter/,
  );
});

test('zero or negative timeouts are rejected', () => {
  assert.throws(
    () => parseConfig(baseRaw({ totalTimeoutSec: 0 })),
    /positive number/,
  );
});
