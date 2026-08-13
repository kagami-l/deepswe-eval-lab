/**
 * Container entrypoint: `node dist/main.js --config <path>`.
 *
 * Reads the JSON config written by the Pier agent, runs the direct engine,
 * writes `<outputDir>/summary.json`, and exits 0 only when the result is
 * deliverable (the Pier agent turns a non-zero exit into a failed trial).
 */

import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { parseArgs } from 'node:util';

import { CligentRunner } from './agent-runner.js';
import type {
  AdapterName,
  CollabConfig,
  CollaborationResult,
  RoleConfig,
} from './collaboration-engine.js';
import { DirectCollaborationEngine } from './direct-engine.js';

const SUPPORTED_ADAPTERS: ReadonlySet<string> = new Set([
  'claude',
  'codex',
  'kimi',
]);

const RUNTIME_VERSION = '0.1.0';

function requireString(raw: Record<string, unknown>, key: string): string {
  const value = raw[key];
  if (typeof value !== 'string' || value.length === 0) {
    throw new Error(`config.${key} must be a non-empty string`);
  }
  return value;
}

function optionalNumber(
  raw: Record<string, unknown>,
  key: string,
  fallback: number,
): number {
  const value = raw[key];
  if (value === undefined || value === null) return fallback;
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) {
    throw new Error(`config.${key} must be a positive number`);
  }
  return value;
}

/** Non-negative integer: maxReviews=0 runs the modifier-only control arm. */
function optionalCount(
  raw: Record<string, unknown>,
  key: string,
  fallback: number,
): number {
  const value = raw[key];
  if (value === undefined || value === null) return fallback;
  if (typeof value !== 'number' || !Number.isInteger(value) || value < 0) {
    throw new Error(`config.${key} must be a non-negative integer`);
  }
  return value;
}

function parseRole(raw: Record<string, unknown>, key: string): RoleConfig {
  const value = raw[key];
  if (typeof value !== 'object' || value === null) {
    throw new Error(`config.${key} must be an object`);
  }
  const record = value as Record<string, unknown>;
  const adapter = requireString(record, 'adapter');
  if (!SUPPORTED_ADAPTERS.has(adapter)) {
    throw new Error(
      `config.${key}.adapter must be one of ${[...SUPPORTED_ADAPTERS].join('|')}, got "${adapter}"`,
    );
  }
  return {
    adapter: adapter as AdapterName,
    model: typeof record.model === 'string' ? record.model : undefined,
    effort: typeof record.effort === 'string' ? record.effort : undefined,
  };
}

export function parseConfig(raw: Record<string, unknown>): CollabConfig {
  return {
    repoDir: requireString(raw, 'repoDir'),
    instructionPath: requireString(raw, 'instructionPath'),
    outputDir: requireString(raw, 'outputDir'),
    workDir: requireString(raw, 'workDir'),
    modifier: parseRole(raw, 'modifier'),
    reviewer: parseRole(raw, 'reviewer'),
    maxReviews: optionalCount(raw, 'maxReviews', 3),
    maxAgentAttempts: optionalNumber(raw, 'maxAgentAttempts', 2),
    modifierTimeoutSec: optionalNumber(raw, 'modifierTimeoutSec', 2400),
    reviewerTimeoutSec: optionalNumber(raw, 'reviewerTimeoutSec', 600),
    revisionTimeoutSec: optionalNumber(raw, 'revisionTimeoutSec', 900),
    totalTimeoutSec: optionalNumber(raw, 'totalTimeoutSec', 5100),
    minTurnSec: optionalNumber(raw, 'minTurnSec', 120),
    strict: raw.strict === true,
    keepWorkspaces: raw.keepWorkspaces === true,
  };
}

async function main(): Promise<number> {
  const { values } = parseArgs({
    options: { config: { type: 'string' } },
  });
  if (!values.config) {
    process.stderr.write('usage: main.js --config <config.json>\n');
    return 1;
  }

  const raw = JSON.parse(await readFile(values.config, 'utf8')) as Record<
    string,
    unknown
  >;
  const config = parseConfig(raw);
  await mkdir(config.outputDir, { recursive: true });

  const modifier = new CligentRunner('modifier', config.modifier);
  const reviewer = new CligentRunner('reviewer', config.reviewer);
  const engine = new DirectCollaborationEngine(config, modifier, reviewer);

  let result: CollaborationResult;
  try {
    result = await engine.run();
  } catch (err) {
    result = {
      outcome: 'checkpoint_failed',
      degradedReason: null,
      deliverable: false,
      error: err instanceof Error ? (err.stack ?? err.message) : String(err),
      baseCommit: '',
      finalCommit: null,
      checkpoints: [],
      reviewCount: 0,
      revisionCount: 0,
      noChangeRevision: false,
      findingsTotal: 0,
      blockingFindingsTotal: 0,
      protocolViolations: [],
      usage: {
        modifier: {
          tokenAvailability: 'unavailable',
          inputTokens: null,
          outputTokens: null,
          toolUses: 0,
          costUsd: null,
          turns: 0,
          wallMs: 0,
        },
        reviewer: {
          tokenAvailability: 'unavailable',
          inputTokens: null,
          outputTokens: null,
          toolUses: 0,
          costUsd: null,
          turns: 0,
          wallMs: 0,
        },
      },
      actualModels: { modifier: null, reviewer: null },
    };
  }

  const summary = {
    engine: 'direct',
    runtimeVersion: RUNTIME_VERSION,
    generatedAt: new Date().toISOString(),
    modifier: { ...modifier.describe(), actualModel: result.actualModels.modifier },
    reviewer: { ...reviewer.describe(), actualModel: result.actualModels.reviewer },
    config: {
      maxReviews: config.maxReviews,
      maxAgentAttempts: config.maxAgentAttempts,
      modifierTimeoutSec: config.modifierTimeoutSec,
      reviewerTimeoutSec: config.reviewerTimeoutSec,
      revisionTimeoutSec: config.revisionTimeoutSec,
      totalTimeoutSec: config.totalTimeoutSec,
      strict: config.strict,
    },
    result,
  };
  await writeFile(
    join(config.outputDir, 'summary.json'),
    JSON.stringify(summary, null, 2),
  );

  process.stderr.write(
    `collab finished: outcome=${result.outcome}` +
      (result.degradedReason ? ` (${result.degradedReason})` : '') +
      ` deliverable=${result.deliverable}\n`,
  );
  return result.deliverable ? 0 : 2;
}

const isDirectRun =
  process.argv[1] !== undefined &&
  import.meta.url === new URL(`file://${process.argv[1]}`).href;

if (isDirectRun) {
  main().then(
    (code) => process.exit(code),
    (err) => {
      process.stderr.write(`fatal: ${err instanceof Error ? err.stack : err}\n`);
      process.exit(3);
    },
  );
}
