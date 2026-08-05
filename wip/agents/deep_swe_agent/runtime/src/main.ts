/** Container entrypoint for the unified single/collab workflow runtime. */

import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { parseArgs } from 'node:util';

import { CligentRunner } from './agent-runner.js';
import type {
  AdapterName,
  CollabConfig,
  CollaborationResult,
  RoleConfig,
  SingleConfig,
} from './collaboration-engine.js';
import { DirectCollaborationEngine } from './direct-engine.js';
import { SingleWorkflowEngine } from './single-engine.js';

const SUPPORTED_ADAPTERS: ReadonlySet<string> = new Set([
  'claude',
  'codex',
  'gemini',
  'kimi',
  'opencode',
]);
const RUNTIME_VERSION = '0.1.0';

interface ParsedRuntimeConfig {
  topology: 'single' | 'collab';
  plan: Record<string, unknown>;
  single?: SingleConfig;
  collab?: CollabConfig;
}

function record(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error(`${path} must be an object`);
  }
  return value as Record<string, unknown>;
}

function stringValue(raw: Record<string, unknown>, key: string, path = 'config'): string {
  const value = raw[key];
  if (typeof value !== 'string' || value.length === 0) {
    throw new Error(`${path}.${key} must be a non-empty string`);
  }
  return value;
}

function positiveNumber(
  raw: Record<string, unknown>,
  key: string,
  fallback?: number,
): number {
  const value = raw[key] ?? fallback;
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) {
    throw new Error(`config.${key} must be a positive number`);
  }
  return value;
}

function positiveInteger(
  raw: Record<string, unknown>,
  key: string,
  fallback?: number,
): number {
  const value = raw[key] ?? fallback;
  if (typeof value !== 'number' || !Number.isInteger(value) || value < 1) {
    throw new Error(`config.${key} must be a positive integer`);
  }
  return value;
}

function parseRole(value: unknown, path: string): RoleConfig {
  const raw = record(value, path);
  const adapter = stringValue(raw, 'adapter', path);
  if (!SUPPORTED_ADAPTERS.has(adapter)) {
    throw new Error(
      `${path}.adapter must be one of ${[...SUPPORTED_ADAPTERS].join('|')}`,
    );
  }
  const permissions = raw.permissions;
  if (
    permissions !== undefined &&
    permissions !== 'auto' &&
    permissions !== 'bypass'
  ) {
    throw new Error(`${path}.permissions must be auto or bypass`);
  }
  return {
    adapter: adapter as AdapterName,
    model: typeof raw.model === 'string' ? raw.model : undefined,
    effort: typeof raw.effort === 'string' ? raw.effort : undefined,
    permissions: permissions as 'auto' | 'bypass' | undefined,
    profileName: typeof raw.name === 'string' ? raw.name : undefined,
  };
}

export function parseConfig(raw: Record<string, unknown>): ParsedRuntimeConfig {
  const plan = record(raw.executionPlan, 'config.executionPlan');
  if (plan.schemaVersion !== 1) {
    throw new Error('config.executionPlan.schemaVersion must be 1');
  }
  const topology = plan.topology;
  if (topology !== 'single' && topology !== 'collab') {
    throw new Error('config.executionPlan.topology must be single or collab');
  }
  const roles = record(plan.roles, 'config.executionPlan.roles');
  const budget = record(plan.budget, 'config.executionPlan.budget');
  const workflow = record(
    plan.workflowConfig,
    'config.executionPlan.workflowConfig',
  );
  const common = {
    repoDir: stringValue(raw, 'repoDir'),
    instructionPath: stringValue(raw, 'instructionPath'),
    outputDir: stringValue(raw, 'outputDir'),
    workDir: stringValue(raw, 'workDir'),
    modifier: parseRole(roles.modifier, 'config.executionPlan.roles.modifier'),
    maxAgentAttempts: positiveInteger(workflow, 'maxAgentAttempts', 2),
    totalTimeoutSec: positiveNumber(budget, 'soft_deadline_seconds'),
    eventSilenceTimeoutSec: positiveNumber(
      workflow,
      'eventSilenceTimeoutSeconds',
      600,
    ),
    minTurnSec: positiveNumber(workflow, 'minTurnSeconds', 120),
  };
  if (topology === 'single') {
    if (roles.reviewer !== null && roles.reviewer !== undefined) {
      throw new Error('single execution plan must not define a reviewer');
    }
    return {
      topology,
      plan,
      single: {
        ...common,
        modifierTimeoutSec: common.totalTimeoutSec,
      },
    };
  }
  const reviewer = parseRole(
    roles.reviewer,
    'config.executionPlan.roles.reviewer',
  );
  return {
    topology,
    plan,
    collab: {
      ...common,
      reviewer,
      maxReviews: positiveInteger(workflow, 'maxReviews', 3),
      modifierTimeoutSec: common.totalTimeoutSec,
      reviewerTimeoutSec: positiveNumber(
        workflow,
        'reviewerTimeoutSeconds',
        600,
      ),
      revisionTimeoutSec: positiveNumber(
        workflow,
        'revisionTimeoutSeconds',
        900,
      ),
      strict: workflow.strict === true,
      keepWorkspaces: workflow.keepWorkspaces === true,
    },
  };
}

function emptyFailure(error: unknown): CollaborationResult {
  return {
    outcome: 'infrastructure_failed',
    degradedReason: null,
    deliverable: false,
    error: error instanceof Error ? (error.stack ?? error.message) : String(error),
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
        inputTokens: 0,
        outputTokens: 0,
        toolUses: 0,
        costUsd: null,
        turns: 0,
        wallMs: 0,
      },
    },
    actualModels: { modifier: null },
  };
}

async function main(): Promise<number> {
  const { values } = parseArgs({ options: { config: { type: 'string' } } });
  if (!values.config) {
    process.stderr.write('usage: main.js --config <config.json>\n');
    return 1;
  }
  const raw = JSON.parse(await readFile(values.config, 'utf8')) as Record<
    string,
    unknown
  >;
  const parsed = parseConfig(raw);
  const outputDir = stringValue(raw, 'outputDir');
  const runManifestDigest = stringValue(raw, 'runManifestDigest');
  await mkdir(outputDir, { recursive: true });
  await writeFile(
    join(outputDir, 'resolved-config.json'),
    JSON.stringify(
      {
        ...parsed.plan,
        runManifest: {
          sha256: runManifestDigest,
          artifactPath: 'run-manifest.json',
        },
      },
      null,
      2,
    ),
  );

  const modifierConfig =
    parsed.topology === 'single'
      ? parsed.single!.modifier
      : parsed.collab!.modifier;
  const modifier = new CligentRunner('modifier', modifierConfig);
  const reviewer =
    parsed.topology === 'collab'
      ? new CligentRunner('reviewer', parsed.collab!.reviewer)
      : null;
  const engine =
    parsed.topology === 'single'
      ? new SingleWorkflowEngine(parsed.single!, modifier)
      : new DirectCollaborationEngine(parsed.collab!, modifier, reviewer!);

  let result: CollaborationResult;
  try {
    result = await engine.run();
  } catch (error) {
    result = emptyFailure(error);
  }
  const summary = {
    schemaVersion: 1,
    engine: 'direct',
    workflow: parsed.topology === 'single' ? 'single' : 'review-loop',
    runtimeVersion: RUNTIME_VERSION,
    generatedAt: new Date().toISOString(),
    roles: {
      modifier: {
        ...modifier.describe(),
        actualModel: result.actualModels.modifier,
      },
      ...(reviewer
        ? {
            reviewer: {
              ...reviewer.describe(),
              actualModel: result.actualModels.reviewer ?? null,
            },
          }
        : {}),
    },
    result,
  };
  await writeFile(join(outputDir, 'summary.json'), JSON.stringify(summary, null, 2));
  process.stderr.write(
    `agent workflow finished: topology=${parsed.topology} ` +
      `outcome=${result.outcome} deliverable=${result.deliverable}\n`,
  );
  return result.deliverable ? 0 : 2;
}

const isDirectRun =
  process.argv[1] !== undefined &&
  import.meta.url === new URL(`file://${process.argv[1]}`).href;

if (isDirectRun) {
  main().then(
    (code) => process.exit(code),
    (error) => {
      process.stderr.write(
        `fatal: ${error instanceof Error ? error.stack : String(error)}\n`,
      );
      process.exit(3);
    },
  );
}
