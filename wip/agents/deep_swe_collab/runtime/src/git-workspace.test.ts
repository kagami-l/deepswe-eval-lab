import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtemp, readFile, rm, stat, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

import { GitWorkspace } from './git-workspace.js';

function git(repo: string, ...args: string[]): string {
  return execFileSync('git', ['-C', repo, ...args], { encoding: 'utf8' });
}

async function makeRepo(): Promise<{ repo: string; ws: GitWorkspace }> {
  const repo = await mkdtemp(join(tmpdir(), 'collab-git-'));
  execFileSync('git', ['init', '-q', '-b', 'main', repo]);
  git(repo, 'config', 'user.name', 'test');
  git(repo, 'config', 'user.email', 'test@example.invalid');
  await writeFile(join(repo, 'base.txt'), 'base\n');
  git(repo, 'add', 'base.txt');
  git(repo, 'commit', '-q', '-m', 'base');
  // Environment file shipped in the image: untracked at base commit.
  await writeFile(join(repo, 'env.log'), 'preexisting\n');
  return { repo, ws: new GitWorkspace(repo) };
}

test('checkpoint stages tracked edits and new files but not baseline untracked', async (t) => {
  const { repo, ws } = await makeRepo();
  t.after(() => rm(repo, { recursive: true, force: true }));
  const base = await ws.head();
  const baseline = new Set(await ws.untrackedFiles());
  assert.deepEqual([...baseline], ['env.log']);

  await writeFile(join(repo, 'base.txt'), 'modified\n');
  await writeFile(join(repo, 'new-file.txt'), 'created\n');
  const stagedNew = await ws.stageAllExcept(baseline);
  assert.deepEqual(stagedNew, ['new-file.txt']);

  const commit = await ws.commitCheckpoint('collab: initial implementation');
  assert.ok(commit);
  const patch = await ws.diffBinary(base);
  assert.match(patch, /new-file\.txt/);
  assert.match(patch, /base\.txt/);
  assert.doesNotMatch(patch, /env\.log/);
  // Baseline file still on disk, still untracked.
  assert.equal((await readFile(join(repo, 'env.log'), 'utf8')), 'preexisting\n');
});

test('commitCheckpoint returns null when nothing is staged', async (t) => {
  const { repo, ws } = await makeRepo();
  t.after(() => rm(repo, { recursive: true, force: true }));
  const baseline = new Set(await ws.untrackedFiles());
  await ws.stageAllExcept(baseline);
  assert.equal(await ws.commitCheckpoint('collab: noop'), null);
});

test('resetTo removes new untracked files but preserves baseline ones', async (t) => {
  const { repo, ws } = await makeRepo();
  t.after(() => rm(repo, { recursive: true, force: true }));
  const base = await ws.head();
  const baseline = new Set(await ws.untrackedFiles());

  await writeFile(join(repo, 'base.txt'), 'broken edit\n');
  await writeFile(join(repo, 'junk.txt'), 'partial\n');
  await ws.resetTo(base, baseline);

  assert.equal(await readFile(join(repo, 'base.txt'), 'utf8'), 'base\n');
  await assert.rejects(stat(join(repo, 'junk.txt')));
  assert.equal(await readFile(join(repo, 'env.log'), 'utf8'), 'preexisting\n');
});

test('copyTo copies untracked environment files too', async (t) => {
  const { repo, ws } = await makeRepo();
  t.after(() => rm(repo, { recursive: true, force: true }));
  const dst = join(await mkdtemp(join(tmpdir(), 'collab-copy-')), 'snapshot');
  t.after(() => rm(dst, { recursive: true, force: true }));
  await ws.copyTo(dst);
  assert.equal(await readFile(join(dst, 'env.log'), 'utf8'), 'preexisting\n');
  assert.equal(await readFile(join(dst, 'base.txt'), 'utf8'), 'base\n');
});

test('applyCheckAgainstBase accepts a valid patch and rejects a corrupt one', async (t) => {
  const { repo, ws } = await makeRepo();
  t.after(() => rm(repo, { recursive: true, force: true }));
  const base = await ws.head();
  const baseline = new Set(await ws.untrackedFiles());
  await writeFile(join(repo, 'base.txt'), 'modified\n');
  await ws.stageAllExcept(baseline);
  await ws.commitCheckpoint('collab: change');
  const patch = await ws.diffBinary(base);
  const scratch = await mkdtemp(join(tmpdir(), 'collab-scratch-'));
  t.after(() => rm(scratch, { recursive: true, force: true }));

  await ws.applyCheckAgainstBase(base, patch, scratch);
  // Corrupt the removal line so the context no longer matches base.txt@base.
  await assert.rejects(
    ws.applyCheckAgainstBase(base, patch.replace('-base', '-mismatch'), scratch),
  );
});
