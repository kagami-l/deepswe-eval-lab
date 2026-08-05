import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import test from 'node:test';

import {
  cleanupTurnProcessScope,
  mergeTurnProcessScopes,
  selectTurnDescendants,
  type TurnProcessScope,
} from './turn-process-cleanup.js';

function processIsAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

test('descendant selection includes new children below an excluded baseline process', () => {
  const descendants = selectTurnDescendants(
    100,
    [
      { pid: 100, ppid: 1, pgid: 100, depth: 0 },
      { pid: 110, ppid: 100, pgid: 100, depth: 0 },
      { pid: 111, ppid: 110, pgid: 100, depth: 0 },
      { pid: 200, ppid: 1, pgid: 200, depth: 0 },
    ],
    new Set([110]),
  );
  assert.deepEqual(descendants, [
    { pid: 111, ppid: 110, pgid: 100, depth: 2 },
  ]);
});

test('scope merge preserves processes seen before and after diagnostics', () => {
  const merged = mergeTurnProcessScopes(
    {
      rootPid: 100,
      capturedAtMs: 1,
      captureError: null,
      processes: [{ pid: 110, ppid: 100, pgid: 100, depth: 1 }],
    },
    {
      rootPid: 100,
      capturedAtMs: 2,
      captureError: 'late capture warning',
      processes: [{ pid: 111, ppid: 110, pgid: 100, depth: 2 }],
    },
  );
  assert.deepEqual(
    merged.processes.map(({ pid }) => pid),
    [110, 111],
  );
  assert.equal(merged.captureError, 'late capture warning');
});

test('cleanup terminates the frozen descendant tree without signaling the root', async () => {
  const child = spawn(
    process.execPath,
    [
      '--input-type=module',
      '-e',
      "import {spawn} from 'node:child_process';" +
        "const child=spawn('sleep',['60'],{stdio:'ignore'});" +
        'process.stdout.write(String(child.pid));' +
        'setInterval(()=>{},1000);',
    ],
    { stdio: ['ignore', 'pipe', 'ignore'] },
  );
  assert.ok(child.pid);

  try {
    const grandchildPid = await new Promise<number>((resolve, reject) => {
      child.once('error', reject);
      child.stdout.once('data', (chunk) => resolve(Number(String(chunk))));
    });
    assert.ok(Number.isInteger(grandchildPid));
    const scope: TurnProcessScope = {
      rootPid: process.pid,
      capturedAtMs: Date.now(),
      captureError: null,
      processes: [
        { pid: child.pid, ppid: process.pid, pgid: 0, depth: 1 },
        { pid: grandchildPid, ppid: child.pid, pgid: 0, depth: 2 },
      ],
    };

    const result = await cleanupTurnProcessScope(scope, 'test_abort', {
      adapterGraceMs: 0,
      termGraceMs: 30,
      killReapGraceMs: 30,
    });
    assert.ok(result.termSignaledPids.includes(child.pid));
    assert.ok(result.termSignaledPids.includes(grandchildPid));
    assert.equal(result.survivorPids.length, 0);
    assert.ok(Array.isArray(result.zombiePids));
    assert.equal(processIsAlive(process.pid), true);
  } finally {
    if (processIsAlive(child.pid)) child.kill('SIGKILL');
  }
});
