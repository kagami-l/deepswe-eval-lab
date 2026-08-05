import assert from 'node:assert/strict';
import { mkdtemp, readFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

import { CligentRunner } from './agent-runner.js';

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
  assert.equal(events.at(-1)?.type, 'permission_request');
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
