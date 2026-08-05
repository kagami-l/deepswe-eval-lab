/** Best-effort diagnostics captured before an event-silence abort. */

import { execFile } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

interface CommandSnapshot {
  command: string[];
  stdout: string;
  stderr: string;
  error: string | null;
}

export interface TurnDiagnosticRequest {
  adapter: string;
  role: string;
  model: string | null;
  label: string;
  cwd: string;
  diagnosticDir: string;
  baseCommit?: string;
  turnStartedAtMs: number;
  triggeredAtMs: number;
  lastEventAtMs: number;
  lastEventType: string | null;
  lastEventAgent: string | null;
  lastEventSessionId: string | null;
  silenceTimeoutMs: number;
}

export interface TurnDiagnosticResult {
  snapshotPath: string;
  patchPath: string;
  snapshot: Record<string, unknown>;
}

const COMMAND_TIMEOUT_MS = 3000;
const MAX_BUFFER_BYTES = 16 * 1024 * 1024;

function runCommand(
  command: string,
  args: string[],
  cwd?: string,
): Promise<CommandSnapshot> {
  return new Promise((resolve) => {
    try {
      execFile(
        command,
        args,
        {
          cwd,
          encoding: 'utf8',
          maxBuffer: MAX_BUFFER_BYTES,
          timeout: COMMAND_TIMEOUT_MS,
        },
        (error, stdout, stderr) => {
          resolve({
            command: [command, ...args],
            stdout,
            stderr,
            error: error instanceof Error ? error.message : null,
          });
        },
      );
    } catch (error) {
      resolve({
        command: [command, ...args],
        stdout: '',
        stderr: '',
        error: error instanceof Error ? error.message : String(error),
      });
    }
  });
}

function safeLabel(label: string): string {
  const normalized = label.replace(/[^A-Za-z0-9_.-]+/g, '-');
  return normalized.length > 0 ? normalized : 'turn';
}

export async function captureTurnDiagnostics(
  request: TurnDiagnosticRequest,
): Promise<TurnDiagnosticResult> {
  const capturedAtMs = Date.now();
  const stamp = new Date(capturedAtMs).toISOString().replace(/[:.]/g, '-');
  const prefix = `${safeLabel(request.label)}-event-silence-${stamp}`;
  await mkdir(request.diagnosticDir, { recursive: true });

  const diffTarget = request.baseCommit ?? 'HEAD';
  const [processes, head, status, diffStat, patch] = await Promise.all([
    runCommand('ps', [
      '-eo',
      'pid=,ppid=,pgid=,stat=,etime=,pcpu=,pmem=,comm=,args=',
    ]),
    runCommand('git', ['rev-parse', 'HEAD'], request.cwd),
    runCommand('git', ['status', '--short', '--branch'], request.cwd),
    runCommand('git', ['diff', '--stat', diffTarget], request.cwd),
    runCommand('git', ['diff', '--binary', diffTarget], request.cwd),
  ]);

  const patchPath = join(request.diagnosticDir, `${prefix}.patch`);
  await writeFile(patchPath, patch.stdout);
  const snapshotPath = join(request.diagnosticDir, `${prefix}.json`);
  const snapshot: Record<string, unknown> = {
    schemaVersion: 1,
    reason: 'event_silence_timeout',
    capturedAt: new Date(capturedAtMs).toISOString(),
    triggeredAt: new Date(request.triggeredAtMs).toISOString(),
    captureDelayMs: capturedAtMs - request.triggeredAtMs,
    turn: {
      label: request.label,
      role: request.role,
      adapter: request.adapter,
      model: request.model,
      cwd: request.cwd,
      elapsedMs: capturedAtMs - request.turnStartedAtMs,
    },
    inactivity: {
      timeoutMs: request.silenceTimeoutMs,
      silenceMs: request.triggeredAtMs - request.lastEventAtMs,
      lastEventAt: new Date(request.lastEventAtMs).toISOString(),
      lastEventType: request.lastEventType,
      lastEventAgent: request.lastEventAgent,
      lastEventSessionId: request.lastEventSessionId,
    },
    processes,
    git: {
      baseCommit: diffTarget,
      head,
      status,
      diffStat,
      trackedPatch: {
        path: patchPath,
        bytes: Buffer.byteLength(patch.stdout),
        error: patch.error,
        stderr: patch.stderr,
      },
    },
  };
  await writeFile(snapshotPath, JSON.stringify(snapshot, null, 2));
  return { snapshotPath, patchPath, snapshot };
}
