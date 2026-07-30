/**
 * DirectCollaborationEngine — the first-phase deterministic control loop
 * (docs/collab-agent-design.md sections 5.1, 7, 8, 13).
 *
 *   initial_modify → checkpoint → [review → (approve | revise → revision →
 *   checkpoint)] * maxReviews → deliver
 *
 * Once a trusted checkpoint exists, reviewer/revision/timeout failures
 * degrade to delivering that checkpoint (outcome "degraded", reason
 * recorded) instead of discarding the work; `strict` restores fail-hard.
 */

import { appendFileSync } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

import type {
  AgentRunner,
  EventSink,
  TurnResult,
  TurnUsage,
} from './agent-runner.js';
import {
  emptyRoleUsage,
  isDeliverable,
  type CollabConfig,
  type CollaborationEngine,
  type CollaborationResult,
  type DegradedReason,
  type Outcome,
  type RoleUsage,
} from './collaboration-engine.js';
import { GitWorkspace } from './git-workspace.js';
import {
  buildModifierInitialPrompt,
  buildReviewerPrompt,
  buildRevisionPrompt,
  REVIEW_FORMAT_RETRY_NOTE,
} from './prompts.js';
import {
  BLOCKING_SEVERITIES,
  parseResolutions,
  parseReview,
  ReviewParseError,
  type FindingResolution,
  type Review,
} from './review-schema.js';

interface ModifierTurnOutcome {
  ok: boolean;
  changed: boolean;
  finalText: string;
  failKind: 'timeout' | 'process' | 'empty' | null;
}

interface ReviewTurnOutcome {
  review: Review | null;
  failReason: Extract<DegradedReason, 'reviewer_failed' | 'invalid_review_output' | 'timeout'> | null;
}

export class DirectCollaborationEngine implements CollaborationEngine {
  private readonly ws: GitWorkspace;
  private deadline = 0;
  private sequence = 0;
  private baseline: ReadonlySet<string> = new Set();
  private baseCommit = '';
  private lastCheckpoint = '';
  private readonly checkpoints: { label: string; commit: string }[] = [];
  private readonly protocolViolations: string[] = [];
  private readonly usage = {
    modifier: emptyRoleUsage(),
    reviewer: emptyRoleUsage(),
  };
  private findingsTotal = 0;
  private blockingFindingsTotal = 0;

  constructor(
    private readonly config: CollabConfig,
    private readonly modifier: AgentRunner,
    private readonly reviewer: AgentRunner,
  ) {
    this.ws = new GitWorkspace(config.repoDir);
  }

  // --- infrastructure -----------------------------------------------------

  private remainingSec(): number {
    return Math.max(0, (this.deadline - Date.now()) / 1000);
  }

  private expired(): boolean {
    return Date.now() >= this.deadline;
  }

  private trace(event: string, data: Record<string, unknown> = {}): void {
    const line = JSON.stringify({
      ts: new Date().toISOString(),
      event,
      ...data,
    });
    appendFileSync(join(this.config.outputDir, 'orchestrator-trace.jsonl'), line + '\n');
  }

  private makeEventSink(roundDir: string): EventSink {
    const roundEvents = join(roundDir, 'events.jsonl');
    const globalEvents = join(this.config.outputDir, 'cligent-events.jsonl');
    return (event) => {
      const line = JSON.stringify(event) + '\n';
      appendFileSync(roundEvents, line);
      appendFileSync(globalEvents, line);
    };
  }

  private addUsage(role: 'modifier' | 'reviewer', result: TurnResult): void {
    const bucket: RoleUsage = this.usage[role];
    bucket.turns += 1;
    bucket.wallMs += result.durationMs;
    const usage: TurnUsage | null = result.usage;
    if (!usage) return;
    bucket.inputTokens += usage.inputTokens;
    bucket.outputTokens += usage.outputTokens;
    bucket.toolUses += usage.toolUses;
    if (usage.costUsd !== null) {
      bucket.costUsd = (bucket.costUsd ?? 0) + usage.costUsd;
    }
  }

  private async newRoundDir(kind: string): Promise<string> {
    const label = `${String(this.sequence).padStart(2, '0')}-${kind}`;
    this.sequence += 1;
    const dir = join(this.config.outputDir, 'rounds', label);
    await mkdir(dir, { recursive: true });
    return dir;
  }

  private turnTimeoutMs(roleTimeoutSec: number): number {
    return Math.floor(Math.min(roleTimeoutSec, this.remainingSec()) * 1000);
  }

  // --- turns --------------------------------------------------------------

  /**
   * One Modifier phase (initial implementation or a revision) with per-turn
   * retries. Every failed attempt rolls the tree back to `resetCommit` and
   * removes non-baseline untracked files before retrying (section 6.1).
   */
  private async modifierTurn(options: {
    kind: 'modify' | 'revise' | 'final-revision';
    prompt: string;
    timeoutSec: number;
    resetCommit: string;
    requireChange: boolean;
  }): Promise<ModifierTurnOutcome> {
    const roundDir = await this.newRoundDir(options.kind);
    await writeFile(join(roundDir, 'prompt.md'), options.prompt);
    const sink = this.makeEventSink(roundDir);
    const attempts: Record<string, unknown>[] = [];
    let failKind: ModifierTurnOutcome['failKind'] = null;
    let outcome: ModifierTurnOutcome = {
      ok: false,
      changed: false,
      finalText: '',
      failKind: null,
    };

    for (let attempt = 1; attempt <= this.config.maxAgentAttempts; attempt++) {
      if (this.remainingSec() < this.config.minTurnSec) {
        failKind = 'timeout';
        break;
      }
      this.trace('modifier_turn_start', { kind: options.kind, attempt });
      const result = await this.modifier.runTurn(
        {
          prompt: options.prompt,
          cwd: this.config.repoDir,
          resumeSession: true,
          timeoutMs: this.turnTimeoutMs(options.timeoutSec),
          label: `${options.kind}-a${attempt}`,
        },
        sink,
      );
      this.addUsage('modifier', result);
      attempts.push({
        attempt,
        status: result.status,
        timedOut: result.timedOut,
        durationMs: result.durationMs,
        usage: result.usage,
        error: result.error,
      });

      if (!result.ok) {
        failKind = result.timedOut ? 'timeout' : 'process';
        this.trace('modifier_turn_failed', { kind: options.kind, attempt, failKind });
        await this.ws.resetTo(options.resetCommit, this.baseline);
        continue;
      }

      const headNow = await this.ws.head();
      if (headNow !== options.resetCommit) {
        this.protocolViolations.push(
          `${options.kind}: modifier moved HEAD to ${headNow} (tolerated)`,
        );
      }
      const stagedNew = await this.ws.stageAllExcept(this.baseline);
      const hasStaged = await this.ws.hasStagedChanges();
      const changed = hasStaged || headNow !== options.resetCommit;
      if (options.requireChange && !changed) {
        failKind = 'empty';
        this.trace('modifier_turn_empty', { kind: options.kind, attempt });
        continue;
      }
      attempts[attempts.length - 1].stagedNewFiles = stagedNew.length;
      outcome = { ok: true, changed, finalText: result.finalText, failKind: null };
      break;
    }

    if (!outcome.ok) outcome.failKind = failKind ?? 'process';
    await writeFile(
      join(roundDir, 'metadata.json'),
      JSON.stringify({ role: 'modifier', kind: options.kind, attempts }, null, 2),
    );
    return outcome;
  }

  /** One review round: isolated full copy, fresh session, strict JSON. */
  private async reviewTurn(options: {
    round: number;
    task: string;
    previousReview: Review | null;
    previousResolutions: FindingResolution[] | null;
  }): Promise<ReviewTurnOutcome> {
    const roundDir = await this.newRoundDir('review');
    const sink = this.makeEventSink(roundDir);
    const attempts: Record<string, unknown>[] = [];
    const patch = await this.ws.diffBinary(this.baseCommit);
    await writeFile(join(roundDir, 'patch.diff'), patch);

    let retryNote: string | null = null;
    let failReason: ReviewTurnOutcome['failReason'] = 'reviewer_failed';
    let review: Review | null = null;

    for (let attempt = 1; attempt <= this.config.maxAgentAttempts; attempt++) {
      if (this.remainingSec() < this.config.minTurnSec) {
        failReason = 'timeout';
        break;
      }
      const copyDir = join(
        this.config.workDir,
        `review-${options.round}-a${attempt}`,
      );
      await this.ws.copyTo(copyDir);
      const prompt = buildReviewerPrompt({
        task: options.task,
        patch,
        baseCommit: this.baseCommit,
        round: options.round,
        maxReviews: this.config.maxReviews,
        previousReview: options.previousReview,
        previousResolutions: options.previousResolutions,
        retryNote,
      });
      await writeFile(join(roundDir, `prompt-a${attempt}.md`), prompt);
      this.trace('review_turn_start', { round: options.round, attempt });
      const result = await this.reviewer.runTurn(
        {
          prompt,
          cwd: copyDir,
          resumeSession: false,
          timeoutMs: this.turnTimeoutMs(this.config.reviewerTimeoutSec),
          label: `review-${options.round}-a${attempt}`,
        },
        sink,
      );
      if (!this.config.keepWorkspaces) await this.ws.removeCopy(copyDir);
      this.addUsage('reviewer', result);
      attempts.push({
        attempt,
        status: result.status,
        timedOut: result.timedOut,
        durationMs: result.durationMs,
        usage: result.usage,
        error: result.error,
      });

      if (!result.ok) {
        failReason = 'reviewer_failed';
        this.trace('review_turn_failed', { round: options.round, attempt });
        continue;
      }
      await writeFile(join(roundDir, `review-raw-a${attempt}.txt`), result.finalText);
      try {
        review = parseReview(result.finalText);
      } catch (err) {
        if (!(err instanceof ReviewParseError)) throw err;
        attempts[attempts.length - 1].parseError = err.message;
        failReason = 'invalid_review_output';
        retryNote = `${REVIEW_FORMAT_RETRY_NOTE} (${err.message})`;
        this.trace('review_parse_error', { round: options.round, attempt });
        continue;
      }
      await writeFile(
        join(roundDir, 'review.json'),
        JSON.stringify(
          {
            verdict: review.verdict,
            summary: review.summary,
            findings: review.findings,
            verdictMismatch: review.verdictMismatch,
          },
          null,
          2,
        ),
      );
      break;
    }

    await writeFile(
      join(roundDir, 'metadata.json'),
      JSON.stringify({ role: 'reviewer', round: options.round, attempts }, null, 2),
    );
    return review !== null
      ? { review, failReason: null }
      : { review: null, failReason };
  }

  // --- main loop ----------------------------------------------------------

  async run(): Promise<CollaborationResult> {
    await mkdir(join(this.config.outputDir, 'rounds'), { recursive: true });
    await mkdir(join(this.config.outputDir, 'final'), { recursive: true });
    await mkdir(this.config.workDir, { recursive: true });

    const task = await readFile(this.config.instructionPath, 'utf8');
    this.baseCommit = await this.ws.head();
    this.lastCheckpoint = this.baseCommit;
    this.baseline = new Set(await this.ws.untrackedFiles());
    this.deadline = Date.now() + this.config.totalTimeoutSec * 1000;
    this.trace('start', {
      baseCommit: this.baseCommit,
      baselineUntracked: this.baseline.size,
      config: {
        maxReviews: this.config.maxReviews,
        maxAgentAttempts: this.config.maxAgentAttempts,
        totalTimeoutSec: this.config.totalTimeoutSec,
        strict: this.config.strict,
      },
    });

    let outcome: Outcome;
    let degradedReason: DegradedReason | null = null;
    let error: string | null = null;
    let reviewCount = 0;
    let revisionCount = 0;
    let noChangeRevision = false;

    // --- initial implementation ------------------------------------------
    const initial = await this.modifierTurn({
      kind: 'modify',
      prompt: buildModifierInitialPrompt(task),
      timeoutSec: this.config.modifierTimeoutSec,
      resetCommit: this.baseCommit,
      requireChange: true,
    });

    if (!initial.ok) {
      outcome =
        initial.failKind === 'timeout'
          ? 'timeout'
          : initial.failKind === 'empty'
            ? 'empty_patch'
            : 'modifier_failed';
      error = `initial implementation failed (${initial.failKind})`;
      this.trace('initial_failed', { failKind: initial.failKind });
      return this.finalize(outcome, degradedReason, error, {
        reviewCount,
        revisionCount,
        noChangeRevision,
      });
    }

    await this.checkpoint('collab: initial implementation');

    // --- review / revise loop --------------------------------------------
    let previousReview: Review | null = null;
    let previousResolutions: FindingResolution[] | null = null;
    outcome = 'degraded'; // overwritten on every exit path below

    for (let round = 1; ; round++) {
      if (round > this.config.maxReviews) {
        // All reviews consumed and the last revision was a non-final one
        // (only reachable when maxReviews is 0).
        outcome = 'max_reviews_reached';
        break;
      }
      if (this.expired()) {
        degradedReason = 'timeout';
        outcome = 'degraded';
        break;
      }

      const reviewOutcome = await this.reviewTurn({
        round,
        task,
        previousReview,
        previousResolutions,
      });
      if (reviewOutcome.review === null) {
        degradedReason = reviewOutcome.failReason ?? 'reviewer_failed';
        outcome = 'degraded';
        break;
      }
      reviewCount += 1;
      const review = reviewOutcome.review;
      this.findingsTotal += review.findings.length;
      const blocking = review.findings.filter((finding) =>
        BLOCKING_SEVERITIES.has(finding.severity),
      ).length;
      this.blockingFindingsTotal += blocking;
      this.trace('review_done', {
        round,
        findings: review.findings.length,
        blocking,
        verdict: review.verdict,
        verdictMismatch: review.verdictMismatch,
      });

      if (!review.hasBlockingFindings) {
        outcome = 'approved';
        break;
      }
      if (this.expired()) {
        degradedReason = 'timeout';
        outcome = 'degraded';
        break;
      }

      const finalRound = round === this.config.maxReviews;
      const revision = await this.modifierTurn({
        kind: finalRound ? 'final-revision' : 'revise',
        prompt: buildRevisionPrompt({
          task,
          review,
          round,
          maxReviews: this.config.maxReviews,
          finalRound,
        }),
        timeoutSec: this.config.revisionTimeoutSec,
        resetCommit: this.lastCheckpoint,
        requireChange: false,
      });
      if (!revision.ok) {
        degradedReason = revision.failKind === 'timeout' ? 'timeout' : 'revision_failed';
        outcome = 'degraded';
        break;
      }
      revisionCount += 1;
      await this.checkpoint(
        finalRound ? 'collab: final revision' : `collab: revision ${round}`,
      );

      if (!revision.changed) {
        // No-change revision: do not burn another review (section 8).
        noChangeRevision = true;
        outcome = 'max_reviews_reached';
        this.trace('no_change_revision', { round });
        break;
      }
      if (finalRound) {
        outcome = 'max_reviews_reached';
        break;
      }
      previousReview = review;
      previousResolutions = parseResolutions(revision.finalText);
    }

    if (outcome === 'degraded') {
      error = `collab degraded: ${degradedReason}`;
    }
    return this.finalize(outcome, degradedReason, error, {
      reviewCount,
      revisionCount,
      noChangeRevision,
    });
  }

  private async checkpoint(message: string): Promise<void> {
    try {
      const committed = await this.ws.commitCheckpoint(message);
      const head = await this.ws.head();
      this.lastCheckpoint = head;
      if (committed !== null) {
        this.checkpoints.push({ label: message, commit: head });
        this.trace('checkpoint', { message, commit: head });
      }
    } catch (err) {
      throw new CheckpointError(err instanceof Error ? err.message : String(err));
    }
  }

  private async finalize(
    outcome: Outcome,
    degradedReason: DegradedReason | null,
    error: string | null,
    counters: {
      reviewCount: number;
      revisionCount: number;
      noChangeRevision: boolean;
    },
  ): Promise<CollaborationResult> {
    let finalOutcome = outcome;
    let finalError = error;
    let finalCommit: string | null = null;

    try {
      finalCommit = await this.ws.head();
      const patch = await this.ws.diffBinary(this.baseCommit);
      await writeFile(join(this.config.outputDir, 'final', 'patch.diff'), patch);
      await writeFile(
        join(this.config.outputDir, 'final', 'git-status.txt'),
        await this.ws.statusPorcelain(),
      );

      if (isDeliverable(finalOutcome, this.config.strict)) {
        if (!patch.trim()) {
          finalOutcome = 'empty_patch';
          finalError = 'final patch is empty';
        } else {
          try {
            await this.ws.applyCheckAgainstBase(
              this.baseCommit,
              patch,
              this.config.workDir,
            );
          } catch (err) {
            finalOutcome = 'checkpoint_failed';
            finalError = `final patch failed apply --check: ${
              err instanceof Error ? err.message : String(err)
            }`;
          }
        }
      }
    } catch (err) {
      finalOutcome = 'checkpoint_failed';
      finalError = err instanceof Error ? err.message : String(err);
    }

    const result: CollaborationResult = {
      outcome: finalOutcome,
      degradedReason,
      deliverable: isDeliverable(finalOutcome, this.config.strict),
      error: finalError,
      baseCommit: this.baseCommit,
      finalCommit,
      checkpoints: this.checkpoints,
      reviewCount: counters.reviewCount,
      revisionCount: counters.revisionCount,
      noChangeRevision: counters.noChangeRevision,
      findingsTotal: this.findingsTotal,
      blockingFindingsTotal: this.blockingFindingsTotal,
      protocolViolations: this.protocolViolations,
      usage: this.usage,
    };
    this.trace('finalized', {
      outcome: result.outcome,
      degradedReason: result.degradedReason,
      deliverable: result.deliverable,
      error: result.error,
    });
    return result;
  }
}

export class CheckpointError extends Error {}
