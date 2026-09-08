/**
 * cligent-backed turn execution.
 *
 * `AgentRunner` is the seam the engine depends on; tests inject fakes.
 * `CligentRunner` wraps one `Cligent` per role with the adapter-specific
 * headless configuration from docs/archive/collab-agent-design.md section 6.4:
 * Claude/Codex run with `mode: 'bypass'` (the task container is the
 * isolation boundary; Codex's OS sandbox cannot start in Docker), Kimi gets
 * no permission policy because it rejects capability policies.
 */

import type { DonePayload } from '@sublang/cligent';
import { normalizeUsage, type Accounting } from './usage.js';


import type { AdapterName, RoleConfig } from './collaboration-engine.js';

export interface TurnRequest {
  prompt: string;
  cwd: string;
  /** false forces a fresh session (Reviewer rounds); true continues. */
  resumeSession: boolean;
  timeoutMs: number;
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
  finalText: string;
  usage: TurnUsage | null;
  durationMs: number;
  error: string | null;
  errorCode?: string;
  /** Provider-resolved model reported by the adapter's init event. */
  actualModel: string | null;
}

export type EventSink = (event: Record<string, unknown>) => void;

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
    case 'kimi': {
      const { KimiAdapter } = await import('@sublang/cligent/adapters/kimi');
      return new KimiAdapter();
    }
    default: {
      const exhaustive: never = name;
      throw new Error(`unsupported adapter: ${String(exhaustive)}`);
    }
  }
}

function permissionsFor(name: AdapterName): Record<string, unknown> | undefined {
  switch (name) {
    case 'claude':
    case 'codex':
      return { mode: 'bypass' };
    case 'kimi':
      return undefined;
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
      const permissions = permissionsFor(this.config.adapter);
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
    let timerFired = false;
    const timer = setTimeout(() => {
      timerFired = true;
      controller.abort();
    }, request.timeoutMs);

    const started = Date.now();
    const textParts: string[] = [];
    let doneStatus: string | null = null;
    let doneResult: string | undefined;
    let usage: TurnUsage | null = null;
    let errorMessage: string | null = null;
    let errorCode: string | undefined;
    let actualModel: string | null = null;

    try {
      const overrides: Record<string, unknown> = {
        cwd: request.cwd,
        abortSignal: controller.signal,
      };
      if (!request.resumeSession) overrides.resume = false;

      for await (const event of agent.run(request.prompt, overrides)) {
        eventSink({ label: request.label, ...event });
        const type = event.type as string;
        if (type === 'init') {
          const payload = event.payload as { model?: string } | undefined;
          if (payload?.model && actualModel === null) actualModel = payload.model;
        } else if (type === 'text') {
          const payload = event.payload as { content?: string } | undefined;
          if (payload?.content) textParts.push(payload.content);
        } else if (type === 'text_delta') {
          const payload = event.payload as { delta?: string } | undefined;
          if (payload?.delta) textParts.push(payload.delta);
        } else if (type === 'error') {
          const payload = event.payload as { message?: string; code?: string } | undefined;
          errorMessage = payload?.message ?? 'unknown adapter error';
            errorCode = payload?.code;
        } else if (type === 'done') {
          const payload = event.payload as DonePayload;
          doneStatus = payload.status ?? 'error';
          doneResult = payload.result;
          if (payload.usage) usage = normalizeUsage(payload.usage);
        }
      }
    } catch (err) {
      errorMessage = err instanceof Error ? err.message : String(err);
    } finally {
      clearTimeout(timer);
    }

    const durationMs = Date.now() - started;
    const status = doneStatus ?? 'error';
    const timedOut = timerFired && status === 'interrupted';
    return {
      ok: status === 'success',
      status,
      timedOut,
      finalText: doneResult ?? textParts.join(''),
      usage,
      durationMs,
      error: errorMessage,
      ...(errorCode ? { errorCode } : {}),
      actualModel,
    };
  }
}
