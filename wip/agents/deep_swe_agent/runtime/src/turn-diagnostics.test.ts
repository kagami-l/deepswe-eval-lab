import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { promisify } from 'node:util';

import { captureTurnDiagnostics } from './turn-diagnostics.js';

const execFileAsync = promisify(execFile);

async function git(cwd: string, ...args: string[]): Promise<string> {
  const { stdout } = await execFileAsync('git', args, { cwd, encoding: 'utf8' });
  return stdout.trim();
}

test('minimal snapshot preserves frozen timing, process shape, and tracked patch', async (t) => {
  const root = await mkdtemp(join(tmpdir(), 'deep-swe-diagnostic-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  await git(root, 'init');
  await git(root, 'config', 'user.name', 'Deep SWE Test');
  await git(root, 'config', 'user.email', 'deep-swe-test@example.invalid');
  const tracked = join(root, 'tracked.txt');
  await writeFile(tracked, 'before\n');
  await git(root, 'add', 'tracked.txt');
  await git(root, 'commit', '-m', 'baseline');
  const baseCommit = await git(root, 'rev-parse', 'HEAD');
  await writeFile(tracked, 'after\n');

  const triggeredAtMs = Date.now();
  const lastEventAtMs = triggeredAtMs - 600_123;
  const result = await captureTurnDiagnostics({
    adapter: 'opencode',
    role: 'modifier',
    model: 'deepseek/test',
    label: 'modify-a1',
    cwd: root,
    diagnosticDir: join(root, 'diagnostics'),
    baseCommit,
    turnStartedAtMs: triggeredAtMs - 900_000,
    triggeredAtMs,
    lastEventAtMs,
    lastEventType: 'tool_use',
    lastEventAgent: 'opencode',
    lastEventSessionId: 'session-1',
    silenceTimeoutMs: 600_000,
  });

  const snapshot = JSON.parse(
    await readFile(result.snapshotPath, 'utf8'),
  ) as Record<string, unknown>;
  assert.equal(snapshot.schemaVersion, 1);
  assert.equal(snapshot.reason, 'event_silence_timeout');
  assert.equal(snapshot.triggeredAt, new Date(triggeredAtMs).toISOString());
  assert.ok(Number(snapshot.captureDelayMs) >= 0);

  const inactivity = snapshot.inactivity as Record<string, unknown>;
  assert.equal(inactivity.silenceMs, 600_123);
  assert.equal(inactivity.lastEventType, 'tool_use');
  assert.equal(inactivity.lastEventSessionId, 'session-1');

  const processes = snapshot.processes as Record<string, unknown>;
  assert.deepEqual(processes.command, [
    'ps',
    '-eo',
    'pid=,ppid=,pgid=,stat=,etime=,pcpu=,pmem=,comm=,args=',
  ]);
  assert.equal(typeof processes.stdout, 'string');
  assert.ok('error' in processes);

  const gitSnapshot = snapshot.git as Record<string, unknown>;
  assert.equal(gitSnapshot.baseCommit, baseCommit);
  const status = gitSnapshot.status as Record<string, unknown>;
  assert.match(String(status.stdout), /tracked\.txt/);
  const trackedPatch = gitSnapshot.trackedPatch as Record<string, unknown>;
  assert.ok(Number(trackedPatch.bytes) > 0);
  assert.match(await readFile(result.patchPath, 'utf8'), /after/);
});
