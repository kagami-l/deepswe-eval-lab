/**
 * cligent-backed turn execution.
 *
 * `AgentRunner` is the seam the engine depends on; tests inject fakes.
 * `CligentRunner` wraps one `Cligent` per role with the adapter-specific
 * headless configuration from docs/archive/collab-agent-design.md section 6.4:
 * Claude/Codex run with `mode: 'bypass'` (the task container is the
 * isolation boundary), Gemini/OpenCode use headless auto mode, and Kimi gets
 * no permission policy because its ACP adapter rejects capability policies.
 */

import type { DonePayload } from '@sublang/cligent';
import { normalizeUsage, type Accounting } from './usage.js';


import { appendFileSync } from 'node:fs';

import type { AdapterName, RoleConfig } from './collaboration-engine.js';
import { captureTurnDiagnostics } from './turn-diagnostics.js';
import {
  captureTurnProcessScope,
  cleanupTurnProcessScope,
  mergeTurnProcessScopes,
  type TurnProcessScope,
} from './turn-process-cleanup.js';

export interface TurnRequest {
  prompt: string;
  cwd: string;
  /** false forces a fresh session (Reviewer rounds); true continues. */
  resumeSession: boolean;
  timeoutMs: number;
  /** The wall-clock budget that produced timeoutMs. */
  wallClockTimeoutKind: 'total_deadline' | 'stage_timeout';
  /** Abort after this long without any adapter event. */
  inactivityTimeoutMs: number;
  /** Directory for pre-abort process/Git diagnostics. */
  diagnosticDir: string;
  /** Git base used to preserve a tracked pre-abort patch. */
  diagnosticBaseCommit?: string;
  label: string;
}

export interface TurnUsage extends Accounting {
  tokenAvailability: 'reported' | 'unavailable';
  inputTokens: number | null;
  outputTokens: number | null;
  toolUses: number;
  costUsd: number | null;
}

export interface TurnResult {
  ok: boolean;
  status: string;
  timedOut: boolean;
  timeoutKind: TimeoutKind | null;
  finalText: string;
  usage: TurnUsage | null;
  durationMs: number;
  error: string | null;
  errorCode?: string;
  /** Provider-resolved model reported by the adapter's init event. */
  actualModel: string | null;
}

export type TimeoutKind =
  | 'total_deadline'
  | 'stage_timeout'
  | 'event_silence';

export type EventSink = (event: Record<string, unknown>) => void;

export function createEventFileSink(paths: readonly string[]): EventSink {
  return (event) => {
    const line = JSON.stringify(event) + '\n';
    for (const path of paths) appendFileSync(path, line);
  };
}

export interface AgentRunner {
  describe(): Record<string, unknown>;
  runTurn(request: TurnRequest, eventSink: EventSink): Promise<TurnResult>;
}

type CligentLike = {
  run(
    prompt: string,
    overrides?: Record<string, unknown>,
  ): AsyncGenerator<Record<string, unknown>, void, void>;
};

async function createAdapter(name: AdapterName): Promise<unknown> {
  switch (name) {
    case 'claude': {
      const { ClaudeCodeAdapter } = await import(
        '@sublang/cligent/adapters/claude-code'
      );
      return new ClaudeCodeAdapter();
    }
    case 'codex': {
      const { CodexAdapter } = await import('@sublang/cligent/adapters/codex');
      return new CodexAdapter();
    }
    case 'gemini': {
      const { GeminiAdapter } = await import(
        '@sublang/cligent/adapters/gemini'
      );
      return new GeminiAdapter();
    }
    case 'kimi': {
      const { KimiAdapter } = await import('@sublang/cligent/adapters/kimi');
      return new KimiAdapter();
    }
    case 'opencode': {
      const { OpenCodeAdapter } = await import(
        '@sublang/cligent/adapters/opencode'
      );
      return new OpenCodeAdapter();
    }
    default: {
      const exhaustive: never = name;
      throw new Error(`unsupported adapter: ${String(exhaustive)}`);
    }
  }
}

function permissionsFor(
  name: AdapterName,
  configured?: 'auto' | 'bypass',
): Record<string, unknown> | undefined {
  if (configured) return { mode: configured };
  if (name === 'kimi') return undefined;
  switch (name) {
    case 'claude':
    case 'codex':
      return { mode: 'bypass' };
    case 'gemini':
    case 'opencode':
      return { mode: 'auto' };
  }
}

export class CligentRunner implements AgentRunner {
  private cligent: CligentLike | null = null;

  constructor(
    private readonly role: string,
    private readonly config: RoleConfig,
  ) {}

  describe(): Record<string, unknown> {
    return {
      role: this.role,
      adapter: this.config.adapter,
      model: this.config.model ?? null,
      effort: this.config.effort ?? null,
    };
  }

  private async instance(): Promise<CligentLike> {
    if (this.cligent === null) {
      const { Cligent } = await import('@sublang/cligent');
      const adapter = await createAdapter(this.config.adapter);
      const options: Record<string, unknown> = { role: this.role };
      if (this.config.model) options.model = this.config.model;
      if (this.config.effort) options.effort = this.config.effort;
      const permissions = permissionsFor(
        this.config.adapter,
        this.config.permissions,
      );
      if (permissions) options.permissions = permissions;
      this.cligent = new Cligent(
        adapter as never,
        options as never,
      ) as unknown as CligentLike;
    }
    return this.cligent;
  }

  async runTurn(request: TurnRequest, eventSink: EventSink): Promise<TurnResult> {
    const agent = await this.instance();
    const controller = new AbortController();
    const processBaseline = captureTurnProcessScope();
    const baselinePids = new Set(
      processBaseline.processes.map(({ pid }) => pid),
    );
    const started = Date.now();
    let lastEventAt = started;
    let lastEventType: string | null = null;
    let lastEventAgent: string | null = null;
    let lastEventSessionId: string | null = null;
    let inactivityTimer: NodeJS.Timeout | null = null;
    let abortReason: string | null = null;
    let timeoutKind: TimeoutKind | null = null;
    let diagnosticPromise: Promise<void> | null = null;
    let processCleanupPromise: Promise<void> | null = null;
    const textParts: string[] = [];
    let doneStatus: string | null = null;
    let doneResult: string | undefined;
    let usage: TurnUsage | null = null;
    let errorMessage: string | null = null;
    let errorCode: string | undefined;
    let actualModel: string | null = null;

    const claimAbort = (reason: string, kind: TimeoutKind | null): boolean => {
      if (abortReason !== null) return false;
      abortReason = reason;
      timeoutKind = kind;
      return true;
    };

    const beginAbortCleanup = (earlierScope?: TurnProcessScope): void => {
      if (processCleanupPromise !== null || abortReason === null) {
        controller.abort();
        return;
      }
      const latestScope = captureTurnProcessScope(process.pid, baselinePids);
      const scope = earlierScope
        ? mergeTurnProcessScopes(earlierScope, latestScope)
        : latestScope;
      controller.abort();
      const claimedReason = abortReason;
      const claimedTimeoutKind = timeoutKind;
      processCleanupPromise = cleanupTurnProcessScope(scope, claimedReason).then(
        (cleanup) => {
          try {
            eventSink({
              label: request.label,
              type: 'runtime:turn_process_cleanup',
              agent: this.config.adapter,
              timestamp: Date.now(),
              role: this.role,
              payload: { ...cleanup, timeoutKind: claimedTimeoutKind },
            });
          } catch {
            // Cleanup must remain independent of the event sink.
          }
        },
      );
    };

    const startAbortCleanup = (
      reason: string,
      earlierScope?: TurnProcessScope,
    ): void => {
      if (!claimAbort(reason, null)) {
        controller.abort();
        return;
      }
      beginAbortCleanup(earlierScope);
    };

    const timer = setTimeout(() => {
      if (
        !claimAbort(
          request.wallClockTimeoutKind,
          request.wallClockTimeoutKind,
        )
      ) {
        return;
      }
      errorMessage = `Turn exceeded its ${request.wallClockTimeoutKind} budget`;
      beginAbortCleanup();
    }, request.timeoutMs);

    const armInactivityTimer = (): void => {
      if (inactivityTimer !== null) clearTimeout(inactivityTimer);
      inactivityTimer = setTimeout(() => {
        if (!claimAbort('event_silence', 'event_silence')) return;
        const triggeredAt = Date.now();
        const frozenLastEventAt = lastEventAt;
        const frozenLastEventType = lastEventType;
        const frozenLastEventAgent = lastEventAgent;
        const frozenLastEventSessionId = lastEventSessionId;
        const processScope = captureTurnProcessScope(
          process.pid,
          baselinePids,
        );
        diagnosticPromise = (async () => {
          let snapshotPath: string | null = null;
          let patchPath: string | null = null;
          let captureError: string | null = null;
          try {
            const diagnostic = await captureTurnDiagnostics({
              adapter: this.config.adapter,
              role: this.role,
              model: this.config.model ?? null,
              label: request.label,
              cwd: request.cwd,
              diagnosticDir: request.diagnosticDir,
              baseCommit: request.diagnosticBaseCommit,
              turnStartedAtMs: started,
              triggeredAtMs: triggeredAt,
              lastEventAtMs: frozenLastEventAt,
              lastEventType: frozenLastEventType,
              lastEventAgent: frozenLastEventAgent,
              lastEventSessionId: frozenLastEventSessionId,
              silenceTimeoutMs: request.inactivityTimeoutMs,
            });
            snapshotPath = diagnostic.snapshotPath;
            patchPath = diagnostic.patchPath;
          } catch (error) {
            captureError = error instanceof Error ? error.message : String(error);
          }
          const silenceMs = triggeredAt - frozenLastEventAt;
          errorMessage =
            `No ${this.config.adapter} event for ${silenceMs}ms; ` +
            'aborting the headless turn';
          try {
            eventSink({
              label: request.label,
              type: 'runtime:event_silence_timeout',
              agent: this.config.adapter,
              timestamp: triggeredAt,
              role: this.role,
              payload: {
                silenceMs,
                timeoutMs: request.inactivityTimeoutMs,
                triggeredAt,
                lastEventAt: frozenLastEventAt,
                lastEventType: frozenLastEventType,
                lastEventAgent: frozenLastEventAgent,
                lastEventSessionId: frozenLastEventSessionId,
                snapshotPath,
                patchPath,
                captureError,
                timeoutKind: 'event_silence',
              },
            });
          } catch {
            // A failed diagnostic sink must not prevent the watchdog abort.
          }
          beginAbortCleanup(processScope);
        })();
      }, request.inactivityTimeoutMs);
    };
    armInactivityTimer();

    try {
      const overrides: Record<string, unknown> = {
        cwd: request.cwd,
        abortSignal: controller.signal,
      };
      if (!request.resumeSession) overrides.resume = false;

      for await (const event of agent.run(request.prompt, overrides)) {
        lastEventAt = Date.now();
        lastEventType = typeof event.type === 'string' ? event.type : null;
        lastEventAgent = typeof event.agent === 'string' ? event.agent : null;
        lastEventSessionId =
          typeof event.sessionId === 'string' ? event.sessionId : null;
        armInactivityTimer();
        const type = event.type as string;
        const textContent =
          type === 'text'
            ? (event.payload as { content?: string } | undefined)?.content
            : undefined;
        const textDelta =
          type === 'text_delta'
            ? (event.payload as { delta?: string } | undefined)?.delta
            : undefined;
        eventSink({ label: request.label, ...event });
        if (type === 'init') {
          const payload = event.payload as { model?: string } | undefined;
          if (payload?.model && actualModel === null) actualModel = payload.model;
        } else if (type === 'text') {
          if (textContent) textParts.push(textContent);
        } else if (type === 'text_delta') {
          if (textDelta) textParts.push(textDelta);
        } else if (
          type === 'permission_request' &&
          this.config.adapter === 'opencode'
        ) {
          const payload = event.payload as
            | {
                toolName?: string;
                toolUseId?: string;
              }
            | undefined;
          const permission = payload?.toolName ?? 'unknown';
          const requestId = payload?.toolUseId ?? 'unknown';
          errorMessage =
            `Headless ${this.config.adapter} run cannot answer permission ` +
            `request ${permission} (${requestId}); aborting instead of waiting`;
          doneStatus = 'error';
          startAbortCleanup('permission_request');
          break;
        } else if (type === 'error') {
          const payload = event.payload as { message?: string; code?: string } | undefined;
          if (abortReason === null) {
            errorMessage = payload?.message ?? 'unknown adapter error';
            errorCode = payload?.code;
          }
        } else if (type === 'done') {
          const payload = event.payload as DonePayload;
          doneStatus = payload.status ?? 'error';
          doneResult = payload.result;
          if (payload.usage) usage = normalizeUsage(payload.usage);
        }
      }
    } catch (err) {
      if (errorMessage === null) {
        errorMessage = err instanceof Error ? err.message : String(err);
      }
    } finally {
      clearTimeout(timer);
      if (inactivityTimer !== null) clearTimeout(inactivityTimer);
      if (diagnosticPromise !== null) await diagnosticPromise;
      if (processCleanupPromise !== null) await processCleanupPromise;
    }

    const durationMs = Date.now() - started;
    const status = doneStatus ?? 'error';
    const timedOut = timeoutKind !== null;
    return {
      ok: status === 'success' && abortReason === null,
      status,
      timedOut,
      timeoutKind,
      finalText: doneResult ?? textParts.join(''),
      usage,
      durationMs,
      error: errorMessage,
      ...(errorCode ? { errorCode } : {}),
      actualModel,
    };
  }
}
