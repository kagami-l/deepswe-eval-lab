/** Deterministic one-turn workflow for the unified single-Agent baseline. */

import { appendFileSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

import {
  createEventFileSink,
  type AgentRunner,
  type EventSink,
  type TimeoutKind,
  type TurnResult,
} from './agent-runner.js';
import {
  emptyRoleUsage,
  type CollaborationEngine,
  type CollaborationResult,
  type RoleUsage,
  type SingleConfig,
} from './collaboration-engine.js';
import { GitWorkspace } from './git-workspace.js';
import { buildModifierInitialPrompt } from './prompts.js';

export class SingleWorkflowEngine implements CollaborationEngine {
  private readonly ws: GitWorkspace;
  private readonly usage: RoleUsage = emptyRoleUsage();
  private actualModel: string | null = null;
  private baseCommit = '';
  private lastCheckpoint = '';
  private deadline = 0;
  private baseline = new Set<string>();
  private readonly protocolViolations: string[] = [];

  constructor(
    private readonly config: SingleConfig,
    private readonly modifier: AgentRunner,
  ) {
    this.ws = new GitWorkspace(config.repoDir);
  }

  private trace(event: string, data: Record<string, unknown> = {}): void {
    try {
      appendFileSync(
        join(this.config.outputDir, 'orchestrator-trace.jsonl'),
        JSON.stringify({ ts: new Date().toISOString(), event, ...data }) + '\n',
      );
    } catch {
      // Observability must not change the workflow result.
    }
  }

  private remainingSec(): number {
    return Math.max(0, (this.deadline - Date.now()) / 1000);
  }

  private addUsage(result: TurnResult): void {
    if (this.actualModel === null && result.actualModel !== null) {
      this.actualModel = result.actualModel;
    }
    const previousTurns = this.usage.turns;
    this.usage.turns += 1;
    this.usage.wallMs += result.durationMs;
    if (result.usage === null) {
      this.usage.tokenAvailability = 'unavailable';
      this.usage.inputTokens = null;
      this.usage.outputTokens = null;
      return;
    }
    if (
      result.usage.tokenAvailability === 'reported' &&
      previousTurns === 0
    ) {
      this.usage.tokenAvailability = 'reported';
      this.usage.inputTokens = result.usage.inputTokens;
      this.usage.outputTokens = result.usage.outputTokens;
    } else if (
      result.usage.tokenAvailability === 'reported' &&
      this.usage.tokenAvailability === 'reported' &&
      this.usage.inputTokens !== null &&
      this.usage.outputTokens !== null
    ) {
      this.usage.inputTokens += result.usage.inputTokens;
      this.usage.outputTokens += result.usage.outputTokens;
    } else {
      this.usage.tokenAvailability = 'unavailable';
      this.usage.inputTokens = null;
      this.usage.outputTokens = null;
    }
    this.usage.toolUses += result.usage.toolUses;
    if (result.usage.costUsd !== null) {
      this.usage.costUsd = (this.usage.costUsd ?? 0) + result.usage.costUsd;
    }
  }

  async run(): Promise<CollaborationResult> {
    try {
      return await this.execute();
    } catch (error) {
      return this.finalize(
        'infrastructure_failed',
        error instanceof Error ? (error.stack ?? error.message) : String(error),
      );
    }
  }

  private async execute(): Promise<CollaborationResult> {
    const roundDir = join(this.config.outputDir, 'rounds', '00-modify');
    await mkdir(roundDir, { recursive: true });
    await mkdir(join(this.config.outputDir, 'final'), { recursive: true });
    await mkdir(this.config.workDir, { recursive: true });
    const instruction = await readFile(this.config.instructionPath, 'utf8');
    const prompt = buildModifierInitialPrompt(instruction);
    await writeFile(join(roundDir, 'prompt.md'), prompt);

    this.baseCommit = await this.ws.head();
    this.lastCheckpoint = this.baseCommit;
    this.baseline = new Set(await this.ws.untrackedFiles());
    this.deadline = Date.now() + this.config.totalTimeoutSec * 1000;
    this.trace('start', {
      topology: 'single',
      baseCommit: this.baseCommit,
      totalTimeoutSec: this.config.totalTimeoutSec,
    });

    const attempts: Record<string, unknown>[] = [];
    let failure: 'modifier_failed' | 'timeout' | 'empty_patch' =
      'modifier_failed';
    let terminalTimeoutKind: TimeoutKind | null = null;
    let succeeded = false;
    const sink: EventSink = createEventFileSink([
      join(roundDir, 'events.jsonl'),
      join(this.config.outputDir, 'events.jsonl'),
    ]);

    for (let attempt = 1; attempt <= this.config.maxAgentAttempts; attempt++) {
      if (this.remainingSec() < this.config.minTurnSec) {
        failure = 'timeout';
        terminalTimeoutKind = 'total_deadline';
        this.trace('modifier_turn_skipped', {
          attempt,
          timeoutKind: terminalTimeoutKind,
          remainingSec: this.remainingSec(),
        });
        break;
      }
      this.trace('modifier_turn_start', { attempt });
      const timeoutMs = Math.floor(this.remainingSec() * 1000);
      const result = await this.modifier.runTurn(
        {
          prompt,
          cwd: this.config.repoDir,
          resumeSession: true,
          timeoutMs,
          wallClockTimeoutKind: 'total_deadline',
          inactivityTimeoutMs: Math.floor(
            this.config.eventSilenceTimeoutSec * 1000,
          ),
          diagnosticDir: join(roundDir, 'diagnostics'),
          diagnosticBaseCommit: this.baseCommit,
          label: `modify-a${attempt}`,
        },
        sink,
      );
      this.addUsage(result);
      attempts.push({
        attempt,
        status: result.status,
        timedOut: result.timedOut,
        timeoutKind: result.timeoutKind,
        durationMs: result.durationMs,
        usage: result.usage,
        error: result.error,
      });
      if (!result.ok) {
        failure = result.timedOut ? 'timeout' : 'modifier_failed';
        terminalTimeoutKind = result.timeoutKind;
        await this.ws.resetTo(this.baseCommit, this.baseline);
        continue;
      }

      const head = await this.ws.head();
      if (head !== this.baseCommit) {
        this.protocolViolations.push(
          `modifier moved HEAD to ${head} (tolerated)`,
        );
      }
      await this.ws.stageAllExcept(this.baseline);
      const changed =
        (await this.ws.hasStagedChanges()) || head !== this.baseCommit;
      if (!changed) {
        failure = 'empty_patch';
        continue;
      }
      const checkpoint = await this.ws.commitCheckpoint(
        'agent: single implementation',
      );
      this.lastCheckpoint = await this.ws.head();
      this.trace('checkpoint', {
        commit: this.lastCheckpoint,
        harnessCommit: checkpoint !== null,
      });
      succeeded = true;
      break;
    }

    await writeFile(
      join(roundDir, 'metadata.json'),
      JSON.stringify(
        {
          role: 'modifier',
          attempts,
          timeoutKind:
            !succeeded && failure === 'timeout' ? terminalTimeoutKind : null,
        },
        null,
        2,
      ),
    );
    return succeeded
      ? this.finalize('completed', null)
      : this.finalize(failure, `single modifier failed (${failure})`);
  }

  private async finalize(
    outcome: CollaborationResult['outcome'],
    error: string | null,
  ): Promise<CollaborationResult> {
    let finalOutcome = outcome;
    let finalError = error;
    let finalCommit: string | null = null;
    let patch = '';
    try {
      if (this.baseCommit) {
        finalCommit = await this.ws.head();
        patch = await this.ws.diffBinary(this.baseCommit);
      }
      await mkdir(join(this.config.outputDir, 'final'), { recursive: true });
      await writeFile(join(this.config.outputDir, 'final', 'patch.diff'), patch);
      await writeFile(
        join(this.config.outputDir, 'final', 'git-status.txt'),
        this.baseCommit ? await this.ws.statusPorcelain() : '',
      );
      if (finalOutcome === 'completed') {
        if (!patch.trim()) {
          finalOutcome = 'empty_patch';
          finalError = 'final patch is empty';
        } else {
          await this.ws.applyCheckAgainstBase(
            this.baseCommit,
            patch,
            this.config.workDir,
          );
        }
      }
    } catch (finalizeError) {
      finalOutcome = 'checkpoint_failed';
      finalError =
        finalizeError instanceof Error
          ? finalizeError.message
          : String(finalizeError);
    }
    const deliverable = finalOutcome === 'completed';
    const result: CollaborationResult = {
      outcome: finalOutcome,
      degradedReason: null,
      deliverable,
      error: finalError,
      baseCommit: this.baseCommit,
      finalCommit,
      checkpoints:
        this.lastCheckpoint && this.lastCheckpoint !== this.baseCommit
          ? [{ label: 'agent: single implementation', commit: this.lastCheckpoint }]
          : [],
      reviewCount: 0,
      revisionCount: 0,
      noChangeRevision: false,
      findingsTotal: 0,
      blockingFindingsTotal: 0,
      protocolViolations: this.protocolViolations,
      usage: { modifier: this.usage },
      actualModels: { modifier: this.actualModel },
    };
    this.trace('finalized', {
      outcome: result.outcome,
      deliverable: result.deliverable,
      error: result.error,
    });
    return result;
  }
}
