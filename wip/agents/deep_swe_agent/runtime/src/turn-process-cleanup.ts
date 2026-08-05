/** Targeted best-effort cleanup for processes created by one Agent turn. */

import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

export interface ProcessIdentity {
  pid: number;
  ppid: number;
  pgid: number;
  depth: number;
}

export interface TurnProcessScope {
  rootPid: number;
  capturedAtMs: number;
  processes: ProcessIdentity[];
  captureError: string | null;
}

export interface TurnProcessCleanupResult {
  reason: string;
  capturedPids: number[];
  termSignaledPids: number[];
  killSignaledPids: number[];
  zombiePids: number[];
  survivorPids: number[];
  errors: string[];
}

export function mergeTurnProcessScopes(
  first: TurnProcessScope,
  second: TurnProcessScope,
): TurnProcessScope {
  if (first.rootPid !== second.rootPid) {
    throw new Error('Cannot merge turn process scopes with different roots');
  }
  const processes = new Map<number, ProcessIdentity>();
  for (const processIdentity of [...first.processes, ...second.processes]) {
    const existing = processes.get(processIdentity.pid);
    if (existing === undefined || processIdentity.depth > existing.depth) {
      processes.set(processIdentity.pid, processIdentity);
    }
  }
  return {
    rootPid: first.rootPid,
    capturedAtMs: Math.max(first.capturedAtMs, second.capturedAtMs),
    processes: [...processes.values()],
    captureError: [first.captureError, second.captureError]
      .filter((value): value is string => value !== null)
      .join('; ') || null,
  };
}

interface CleanupOptions {
  adapterGraceMs?: number;
  termGraceMs?: number;
  killReapGraceMs?: number;
}

const PS_TIMEOUT_MS = 1000;
const DEFAULT_ADAPTER_GRACE_MS = 1500;
const DEFAULT_TERM_GRACE_MS = 1000;
const DEFAULT_KILL_REAP_GRACE_MS = 100;

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function processTable(): ProcessIdentity[] {
  const stdout = execFileSync('ps', ['-eo', 'pid=,ppid=,pgid='], {
    encoding: 'utf8',
    timeout: PS_TIMEOUT_MS,
  });
  const processes: ProcessIdentity[] = [];
  for (const line of stdout.split('\n')) {
    const fields = line.trim().split(/\s+/);
    if (fields.length !== 3) continue;
    const [pid, ppid, pgid] = fields.map(Number);
    if (
      Number.isInteger(pid) &&
      Number.isInteger(ppid) &&
      Number.isInteger(pgid)
    ) {
      processes.push({ pid, ppid, pgid, depth: 0 });
    }
  }
  return processes;
}

export function selectTurnDescendants(
  rootPid: number,
  table: readonly ProcessIdentity[],
  excludedPids: ReadonlySet<number> = new Set(),
): ProcessIdentity[] {
  const descendants: ProcessIdentity[] = [];
  const depths = new Map<number, number>([[rootPid, 0]]);
  let changed = true;
  while (changed) {
    changed = false;
    for (const candidate of table) {
      if (depths.has(candidate.pid)) continue;
      const parentDepth = depths.get(candidate.ppid);
      if (parentDepth === undefined) continue;
      depths.set(candidate.pid, parentDepth + 1);
      changed = true;
    }
  }
  for (const candidate of table) {
    const depth = depths.get(candidate.pid);
    if (
      depth === undefined ||
      candidate.pid === rootPid ||
      candidate.pid <= 1 ||
      excludedPids.has(candidate.pid)
    ) {
      continue;
    }
    descendants.push({ ...candidate, depth });
  }
  return descendants;
}

export function captureTurnProcessScope(
  rootPid: number = process.pid,
  excludedPids: ReadonlySet<number> = new Set(),
): TurnProcessScope {
  try {
    const table = processTable().filter(({ pid }) => isRunning(pid));
    const descendants = selectTurnDescendants(rootPid, table, excludedPids);
    return {
      rootPid,
      capturedAtMs: Date.now(),
      processes: descendants,
      captureError: null,
    };
  } catch (error) {
    return {
      rootPid,
      capturedAtMs: Date.now(),
      processes: [],
      captureError: errorMessage(error),
    };
  }
}

function isAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return (error as NodeJS.ErrnoException).code === 'EPERM';
  }
}

function isZombie(pid: number): boolean {
  try {
    if (process.platform === 'linux') {
      const stat = readFileSync(`/proc/${pid}/stat`, 'utf8');
      const commandEnd = stat.lastIndexOf(')');
      return commandEnd >= 0 && stat.slice(commandEnd + 2).startsWith('Z ');
    }
    const stat = execFileSync('ps', ['-o', 'stat=', '-p', String(pid)], {
      encoding: 'utf8',
      timeout: PS_TIMEOUT_MS,
    }).trim();
    return stat.startsWith('Z');
  } catch {
    return false;
  }
}

function isRunning(pid: number): boolean {
  return isAlive(pid) && !isZombie(pid);
}

function signalProcess(
  pid: number,
  signal: NodeJS.Signals,
  errors: string[],
): boolean {
  try {
    process.kill(pid, signal);
    return true;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ESRCH') {
      errors.push(`${signal} pid ${pid}: ${errorMessage(error)}`);
    }
    return false;
  }
}

function sleep(milliseconds: number): Promise<void> {
  if (milliseconds <= 0) return Promise.resolve();
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export async function cleanupTurnProcessScope(
  scope: TurnProcessScope,
  reason: string,
  options: CleanupOptions = {},
): Promise<TurnProcessCleanupResult> {
  const errors = scope.captureError ? [scope.captureError] : [];
  const captured = [...scope.processes].sort((left, right) => {
    if (left.depth !== right.depth) return right.depth - left.depth;
    return right.pid - left.pid;
  });
  const capturedPids = captured.map(({ pid }) => pid);
  const result: TurnProcessCleanupResult = {
    reason,
    capturedPids,
    termSignaledPids: [],
    killSignaledPids: [],
    zombiePids: [],
    survivorPids: [],
    errors,
  };
  if (!captured.some(({ pid }) => isRunning(pid))) {
    result.zombiePids = captured
      .map(({ pid }) => pid)
      .filter((pid) => isZombie(pid));
    return result;
  }

  await sleep(options.adapterGraceMs ?? DEFAULT_ADAPTER_GRACE_MS);
  for (const { pid } of captured) {
    if (isRunning(pid) && signalProcess(pid, 'SIGTERM', errors)) {
      result.termSignaledPids.push(pid);
    }
  }

  if (result.termSignaledPids.length > 0) {
    await sleep(options.termGraceMs ?? DEFAULT_TERM_GRACE_MS);
  }
  for (const { pid } of captured) {
    if (isRunning(pid) && signalProcess(pid, 'SIGKILL', errors)) {
      result.killSignaledPids.push(pid);
    }
  }
  if (result.killSignaledPids.length > 0) {
    await sleep(options.killReapGraceMs ?? DEFAULT_KILL_REAP_GRACE_MS);
  }
  result.zombiePids = captured
    .map(({ pid }) => pid)
    .filter((pid) => isZombie(pid));
  result.survivorPids = captured
    .map(({ pid }) => pid)
    .filter((pid) => isRunning(pid));
  return result;
}
