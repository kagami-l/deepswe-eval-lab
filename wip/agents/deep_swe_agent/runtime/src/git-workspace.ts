/**
 * Git checkpointing and Reviewer isolation for the collab loop
 * (docs/collab-agent-design.md section 7).
 *
 * - Checkpoints stage tracked modifications plus NEW untracked files only;
 *   files that were already untracked at the base commit (environment files
 *   shipped in the task image) never enter history or the final patch.
 * - Reviewer isolation uses a full directory copy (`cp -a`), not a git
 *   worktree, so untracked environment files (node_modules, venvs, build
 *   artifacts) survive and the public test suite still runs.
 */

import { execFile } from 'node:child_process';
import { mkdir, rm, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);

const MAX_BUFFER = 256 * 1024 * 1024;

const COMMIT_IDENTITY = [
  '-c',
  'user.name=collab-harness',
  '-c',
  'user.email=collab-harness@deep-swe.invalid',
];

export class GitWorkspace {
  constructor(readonly repoDir: string) {}

  private async git(...args: string[]): Promise<string> {
    const { stdout } = await execFileAsync('git', ['-C', this.repoDir, ...args], {
      maxBuffer: MAX_BUFFER,
    });
    return stdout;
  }

  async head(): Promise<string> {
    return (await this.git('rev-parse', 'HEAD')).trim();
  }

  /** Untracked, non-ignored files (NUL-separated to survive odd names). */
  async untrackedFiles(): Promise<string[]> {
    const out = await this.git(
      'ls-files',
      '--others',
      '--exclude-standard',
      '-z',
    );
    return out.split('\0').filter((path) => path.length > 0);
  }

  async hasStagedChanges(): Promise<boolean> {
    try {
      await this.git('diff', '--cached', '--quiet');
      return false;
    } catch {
      return true;
    }
  }

  /**
   * Stage every tracked modification plus untracked files that are NOT in
   * the baseline set. Returns the newly staged untracked paths.
   */
  async stageAllExcept(baseline: ReadonlySet<string>): Promise<string[]> {
    await this.git('add', '-u');
    const untracked = await this.untrackedFiles();
    const fresh = untracked.filter((path) => !baseline.has(path));
    if (fresh.length > 0) {
      await this.git('add', '--', ...fresh);
    }
    return fresh;
  }

  /**
   * Commit staged changes with the fixed harness identity. Returns the new
   * HEAD, or null when there was nothing to commit.
   */
  async commitCheckpoint(message: string): Promise<string | null> {
    if (!(await this.hasStagedChanges())) return null;
    await this.git(...COMMIT_IDENTITY, 'commit', '--no-verify', '-m', message);
    return this.head();
  }

  async diffBinary(from: string, to = 'HEAD'): Promise<string> {
    return this.git('diff', '--binary', from, to);
  }

  /**
   * Roll back to a checkpoint after a failed turn: hard-reset tracked state
   * and delete untracked files that were not part of the baseline.
   */
  async resetTo(commit: string, baseline: ReadonlySet<string>): Promise<void> {
    await this.git('reset', '--hard', commit);
    const untracked = await this.untrackedFiles();
    for (const path of untracked) {
      if (!baseline.has(path)) {
        await rm(join(this.repoDir, path), { recursive: true, force: true });
      }
    }
  }

  /** Full copy of the repo (including untracked/ignored files) at `dst`. */
  async copyTo(dst: string): Promise<void> {
    await rm(dst, { recursive: true, force: true });
    await mkdir(dirname(dst), { recursive: true });
    await execFileAsync('cp', ['-a', this.repoDir, dst], {
      maxBuffer: MAX_BUFFER,
    });
  }

  async removeCopy(dst: string): Promise<void> {
    await rm(dst, { recursive: true, force: true });
  }

  /**
   * Terminal sanity check (section 7 step 7): the base→HEAD patch must apply
   * cleanly onto a pristine base checkout. Uses a temporary detached
   * worktree, which is safe here because apply --check only needs tracked
   * file contents.
   */
  async applyCheckAgainstBase(
    baseCommit: string,
    patchText: string,
    scratchDir: string,
  ): Promise<void> {
    if (!patchText.trim()) return;
    const worktree = join(scratchDir, 'apply-check');
    const patchFile = join(scratchDir, 'apply-check.patch');
    await mkdir(scratchDir, { recursive: true });
    await writeFile(patchFile, patchText);
    await rm(worktree, { recursive: true, force: true });
    await this.git('worktree', 'add', '--detach', worktree, baseCommit);
    try {
      await execFileAsync(
        'git',
        ['-C', worktree, 'apply', '--check', '--binary', patchFile],
        { maxBuffer: MAX_BUFFER },
      );
    } finally {
      await this.git('worktree', 'remove', '--force', worktree).catch(() => {});
      await rm(patchFile, { force: true });
    }
  }

  async statusPorcelain(): Promise<string> {
    return this.git('status', '--porcelain');
  }
}
