import assert from 'node:assert/strict';
import { mkdtemp, readFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

import { CligentRunner, createEventFileSink } from './agent-runner.js';

test('headless runner aborts instead of waiting on a permission request', async () => {
  let abortSignal: AbortSignal | undefined;
  const fakeCligent = {
    async *run(
      _prompt: string,
      overrides?: Record<string, unknown>,
    ): AsyncGenerator<Record<string, unknown>> {
      abortSignal = overrides?.abortSignal as AbortSignal | undefined;
      yield {
        type: 'init',
        payload: { model: 'deepseek/test' },
      };
      yield {
        type: 'permission_request',
        payload: {
          toolName: 'external_directory',
          toolUseId: 'permission-1',
        },
      };
    },
  };
  const runner = new CligentRunner('modifier', {
    adapter: 'opencode',
    model: 'deepseek/test',
    permissions: 'auto',
  });
  Object.assign(runner, { cligent: fakeCligent });
  const events: Record<string, unknown>[] = [];

  const result = await runner.runTurn(
    {
      prompt: 'test',
      cwd: '/app',
      resumeSession: false,
      timeoutMs: 1000,
      inactivityTimeoutMs: 1000,
      diagnosticDir: '/tmp/unused-diagnostics',
      label: 'modify-a1',
    },
    (event) => events.push(event),
  );

  assert.equal(result.ok, false);
  assert.equal(result.status, 'error');
  assert.equal(result.timedOut, false);
  assert.match(result.error ?? '', /external_directory/);
  assert.match(result.error ?? '', /permission-1/);
  assert.equal(abortSignal?.aborted, true);
  assert.ok(events.some((event) => event.type === 'permission_request'));
  assert.ok(
    events.some((event) => event.type === 'runtime:turn_process_cleanup'),
  );
});

test('permission observability events from other adapters keep their native flow', async () => {
  let abortSignal: AbortSignal | undefined;
  const fakeCligent = {
    async *run(
      _prompt: string,
      overrides?: Record<string, unknown>,
    ): AsyncGenerator<Record<string, unknown>> {
      abortSignal = overrides?.abortSignal as AbortSignal | undefined;
      yield {
        type: 'permission_request',
        payload: {
          toolName: 'shell',
          toolUseId: 'permission-2',
        },
      };
      yield {
        type: 'done',
        payload: {
          status: 'success',
          result: 'continued',
        },
      };
    },
  };
  const runner = new CligentRunner('modifier', {
    adapter: 'kimi',
    model: 'kimi-code/k3',
    permissions: 'auto',
  });
  Object.assign(runner, { cligent: fakeCligent });

  const result = await runner.runTurn(
    {
      prompt: 'test',
      cwd: '/app',
      resumeSession: false,
      timeoutMs: 1000,
      inactivityTimeoutMs: 1000,
      diagnosticDir: '/tmp/unused-diagnostics',
      label: 'modify-a1',
    },
    () => {},
  );

  assert.equal(result.ok, true);
  assert.equal(result.finalText, 'continued');
  assert.equal(abortSignal?.aborted, false);
});

test('a replayed prompt is re-typed and kept out of the final text', async () => {
  const prompt = 'Review this change.\n\nRespond with ONLY a JSON object:\n{\n  "verdict": "approve" | "revise"\n}';
  const fakeCligent = {
    async *run(): AsyncGenerator<Record<string, unknown>> {
      // OpenCode replays the submitted prompt as the session's first text part.
      yield { type: 'text', payload: { content: `${prompt}\n` } };
      yield { type: 'text', payload: { content: 'Checked the diff.' } };
      yield {
        type: 'text',
        payload: { content: '{"verdict":"revise","findings":[]}' },
      };
      yield { type: 'done', payload: { status: 'success' } };
    },
  };
  const runner = new CligentRunner('reviewer', {
    adapter: 'opencode',
    model: 'deepseek/test',
    permissions: 'auto',
  });
  Object.assign(runner, { cligent: fakeCligent });
  const events: Record<string, unknown>[] = [];

  const result = await runner.runTurn(
    {
      prompt,
      cwd: '/app',
      resumeSession: false,
      timeoutMs: 1000,
      inactivityTimeoutMs: 1000,
      diagnosticDir: '/tmp/unused-diagnostics',
      label: 'review-1-a1',
    },
    (event) => events.push(event),
  );

  assert.equal(result.ok, true);
  assert.equal(
    result.finalText,
    'Checked the diff.{"verdict":"revise","findings":[]}',
  );
  // The echo stays in the stream for auditing, under a non-output type.
  assert.equal(
    events.filter((event) => event.type === 'runtime:prompt_echo').length,
    1,
  );
  assert.equal(events.filter((event) => event.type === 'text').length, 2);
});

test('later OpenCode output that equals the prompt is preserved', async () => {
  const fakeCligent = {
    async *run(): AsyncGenerator<Record<string, unknown>> {
      yield { type: 'text', payload: { content: 'review this change, done' } };
      yield { type: 'text', payload: { content: 'review this change' } };
      yield { type: 'done', payload: { status: 'success' } };
    },
  };
  const runner = new CligentRunner('reviewer', {
    adapter: 'opencode',
    model: 'deepseek/test',
    permissions: 'auto',
  });
  Object.assign(runner, { cligent: fakeCligent });

  const result = await runner.runTurn(
    {
      prompt: 'review this change',
      cwd: '/app',
      resumeSession: false,
      timeoutMs: 1000,
      inactivityTimeoutMs: 1000,
      diagnosticDir: '/tmp/unused-diagnostics',
      label: 'review-1-a1',
    },
    () => {},
  );

  assert.equal(
    result.finalText,
    'review this change, donereview this change',
  );
});

test('non-OpenCode output that equals the prompt is preserved', async () => {
  const fakeCligent = {
    async *run(): AsyncGenerator<Record<string, unknown>> {
      yield { type: 'text', payload: { content: 'repeat this exactly' } };
      yield { type: 'done', payload: { status: 'success' } };
    },
  };
  const runner = new CligentRunner('reviewer', {
    adapter: 'codex',
    model: 'test',
    permissions: 'bypass',
  });
  Object.assign(runner, { cligent: fakeCligent });
  const events: Record<string, unknown>[] = [];

  const result = await runner.runTurn(
    {
      prompt: 'repeat this exactly',
      cwd: '/app',
      resumeSession: false,
      timeoutMs: 1000,
      inactivityTimeoutMs: 1000,
      diagnosticDir: '/tmp/unused-diagnostics',
      label: 'review-1-a1',
    },
    (event) => events.push(event),
  );

  assert.equal(result.finalText, 'repeat this exactly');
  assert.equal(
    events.filter((event) => event.type === 'runtime:prompt_echo').length,
    0,
  );
  assert.equal(events.filter((event) => event.type === 'text').length, 1);
});

test('the event file sink drops only OpenCode token deltas', async (t) => {
  const tempDir = await mkdtemp(join(tmpdir(), 'deep-swe-sink-'));
  t.after(() => rm(tempDir, { recursive: true, force: true }));
  const roundEvents = join(tempDir, 'round.jsonl');
  const globalEvents = join(tempDir, 'global.jsonl');

  const sink = createEventFileSink([roundEvents, globalEvents]);
  sink({ type: 'text_delta', agent: 'opencode', payload: { delta: 'Let' } });
  sink({
    type: 'thinking',
    agent: 'opencode',
    payload: { summary: 'Let me check the diff.' },
  });
  sink({ type: 'text_delta', agent: 'opencode', payload: { delta: ' me' } });
  sink({ type: 'text_delta', agent: 'kimi', payload: { delta: 'Kept.' } });
  sink({ type: 'text', agent: 'opencode', payload: { content: 'Done.' } });

  for (const path of [roundEvents, globalEvents]) {
    const written = (await readFile(path, 'utf8'))
      .trim()
      .split('\n')
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    assert.deepEqual(
      written.map((event) => event.type),
      ['thinking', 'text_delta', 'text'],
    );
    assert.equal(
      (
        written.find((event) => event.type === 'text_delta')?.payload as {
          delta?: string;
        }
      ).delta,
      'Kept.',
    );
  }
});

test('event silence captures diagnostics before aborting the turn', async (t) => {
  const tempDir = await mkdtemp(join(tmpdir(), 'deep-swe-watchdog-'));
  t.after(() => rm(tempDir, { recursive: true, force: true }));
  const diagnosticDir = join(tempDir, 'diagnostics');
  const fakeCligent = {
    async *run(
      _prompt: string,
      overrides?: Record<string, unknown>,
    ): AsyncGenerator<Record<string, unknown>> {
      const signal = overrides?.abortSignal as AbortSignal;
      yield {
        type: 'init',
        agent: 'opencode',
        payload: { model: 'deepseek/test' },
      };
      await new Promise<void>((resolve) => {
        signal.addEventListener('abort', () => resolve(), { once: true });
      });
      yield {
        type: 'done',
        agent: 'opencode',
        payload: { status: 'interrupted' },
      };
    },
  };
  const runner = new CligentRunner('modifier', {
    adapter: 'opencode',
    model: 'deepseek/test',
    permissions: 'auto',
  });
  Object.assign(runner, { cligent: fakeCligent });
  const events: Record<string, unknown>[] = [];

  const result = await runner.runTurn(
    {
      prompt: 'test',
      cwd: tempDir,
      resumeSession: false,
      timeoutMs: 2000,
      inactivityTimeoutMs: 20,
      diagnosticDir,
      label: 'modify-a1',
    },
    (event) => events.push(event),
  );

  assert.equal(result.status, 'interrupted');
  assert.equal(result.timedOut, true);
  assert.match(result.error ?? '', /No opencode event/);
  const watchdog = events.find(
    (event) => event.type === 'runtime:event_silence_timeout',
  );
  assert.ok(watchdog);
  const watchdogPayload = watchdog.payload as Record<string, unknown>;
  assert.equal(watchdogPayload.captureError, null);
  assert.equal(
    Number(watchdogPayload.triggeredAt) - Number(watchdogPayload.lastEventAt),
    watchdogPayload.silenceMs,
  );
  assert.match(
    result.error ?? '',
    new RegExp(`for ${String(watchdogPayload.silenceMs)}ms`),
  );
  assert.ok(
    events.some((event) => event.type === 'runtime:turn_process_cleanup'),
  );
  const files = await readdir(diagnosticDir);
  const snapshotName = files.find((name) => name.endsWith('.json'));
  const patchName = files.find((name) => name.endsWith('.patch'));
  assert.ok(snapshotName);
  assert.ok(patchName);
  const snapshot = JSON.parse(
    await readFile(join(diagnosticDir, snapshotName), 'utf8'),
  ) as Record<string, unknown>;
  assert.equal(snapshot.reason, 'event_silence_timeout');
});
