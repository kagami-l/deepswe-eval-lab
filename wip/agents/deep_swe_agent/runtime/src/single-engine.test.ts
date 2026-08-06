import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

import type {
  AgentRunner,
  EventSink,
  TurnRequest,
  TurnResult,
} from './agent-runner.js';
import type { SingleConfig } from './collaboration-engine.js';
import { SingleWorkflowEngine } from './single-engine.js';

test('min-turn admission records a total-deadline skip in single metadata and trace', async (t) => {
  const root = await mkdtemp(join(tmpdir(), 'single-engine-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const repo = join(root, 'app');
  execFileSync('git', ['init', '-q', '-b', 'main', repo]);
  execFileSync('git', ['-C', repo, 'config', 'user.name', 'test']);
  execFileSync('git', [
    '-C',
    repo,
    'config',
    'user.email',
    'test@example.invalid',
  ]);
  await writeFile(join(repo, 'src.txt'), 'original\n');
  execFileSync('git', ['-C', repo, 'add', 'src.txt']);
  execFileSync('git', ['-C', repo, 'commit', '-q', '-m', 'base']);

  const instructionPath = join(root, 'instruction.md');
  await writeFile(instructionPath, 'Fix src.txt.\n');
  const config: SingleConfig = {
    repoDir: repo,
    instructionPath,
    outputDir: join(root, 'out'),
    workDir: join(root, 'work'),
    modifier: { adapter: 'codex' },
    maxAgentAttempts: 4,
    eventSilenceTimeoutSec: 60,
    totalTimeoutSec: 1,
    minTurnSec: 2,
  };
  const modifier: AgentRunner = {
    describe: () => ({ adapter: 'fake' }),
    runTurn: async (
      _request: TurnRequest,
      _eventSink: EventSink,
    ): Promise<TurnResult> => {
      throw new Error('runTurn must not be called below minTurnSec');
    },
  };

  const result = await new SingleWorkflowEngine(config, modifier).run();

  assert.equal(result.outcome, 'timeout');
  assert.equal(result.deliverable, false);
  const metadata = JSON.parse(
    await readFile(
      join(config.outputDir, 'rounds', '00-modify', 'metadata.json'),
      'utf8',
    ),
  ) as { timeoutKind: string | null; attempts: unknown[] };
  assert.equal(metadata.timeoutKind, 'total_deadline');
  assert.deepEqual(metadata.attempts, []);

  const trace = (await readFile(
    join(config.outputDir, 'orchestrator-trace.jsonl'),
    'utf8',
  ))
    .trim()
    .split('\n')
    .map((line) => JSON.parse(line) as Record<string, unknown>);
  const skipped = trace.find((event) => event.event === 'modifier_turn_skipped');
  assert.ok(skipped);
  assert.equal(skipped.timeoutKind, 'total_deadline');
  assert.equal(skipped.attempt, 1);
});
