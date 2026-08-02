#!/usr/bin/env node

import { open, readFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';

function fail(message) {
  process.stderr.write(`opencode-watchdog: ${message}\n`);
  process.exit(2);
}

function parseArgs(argv) {
  const options = {
    output: '/logs/agent/opencode.txt',
    stateLog: '/logs/agent/opencode-watchdog.jsonl',
    terminalGraceMs: 10_000,
    terminateGraceMs: 5_000,
    pollIntervalMs: 100,
  };
  let index = 0;
  for (; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--') break;
    const value = argv[++index];
    if (value === undefined) fail(`missing value for ${arg}`);
    if (arg === '--output') options.output = value;
    else if (arg === '--state-log') options.stateLog = value;
    else if (arg === '--terminal-grace-ms') options.terminalGraceMs = Number(value);
    else if (arg === '--terminate-grace-ms') options.terminateGraceMs = Number(value);
    else if (arg === '--poll-interval-ms') options.pollIntervalMs = Number(value);
    else fail(`unknown option ${arg}`);
  }
  const command = argv.slice(index + 1);
  for (const [name, value] of Object.entries({
    terminalGraceMs: options.terminalGraceMs,
    terminateGraceMs: options.terminateGraceMs,
    pollIntervalMs: options.pollIntervalMs,
  })) {
    if (!Number.isFinite(value) || value < 0) fail(`${name} must be non-negative`);
  }
  if (command.length === 0) fail('missing command after --');
  return { options, command };
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function main() {
  const { options, command } = parseArgs(process.argv.slice(2));
  const output = await open(options.output, 'w');
  const stateLog = await open(options.stateLog, 'w');
  let child = null;
  let childExited = false;
  let childExitCode = null;
  let childSignal = null;
  let mainSessionId = null;
  let terminalSeen = false;
  let terminalAt = null;
  let readOffset = 0;
  let partialLine = '';
  let forcedAfterTerminal = false;
  let forwardedSignal = null;

  const record = async (state, extra = {}) => {
    const entry = {
      timestamp: new Date().toISOString(),
      state,
      pid: child?.pid ?? null,
      mainSessionId,
      ...extra,
    };
    await stateLog.appendFile(`${JSON.stringify(entry)}\n`);
  };

  const groupExists = () => {
    if (!child) return false;
    try {
      process.kill(-child.pid, 0);
      return true;
    } catch (error) {
      if (error?.code === 'ESRCH') return false;
      // macOS can report EPERM briefly after the group leader exits and its
      // descendants are being reparented. There is no useful retry in that
      // state; Linux containers normally return ESRCH instead.
      if (error?.code === 'EPERM') return false;
      throw error;
    }
  };

  const signalGroup = async (signal, includeDescendantsAfterExit = false) => {
    if (!child || (childExited && !includeDescendantsAfterExit)) return;
    try {
      process.kill(-child.pid, signal);
      await record('signal_sent', { signal });
    } catch (error) {
      if (error?.code === 'ESRCH' || error?.code === 'EPERM') return;
      throw error;
    }
  };

  const processLine = async (line) => {
    if (!line.trim()) return;
    let event;
    try {
      event = JSON.parse(line);
    } catch {
      return;
    }
    if (event?.type === 'step_start' && mainSessionId === null && event.sessionID) {
      mainSessionId = event.sessionID;
      await record('main_session_identified');
    }
    if (
      !terminalSeen &&
      mainSessionId !== null &&
      event?.sessionID === mainSessionId &&
      event?.type === 'step_finish' &&
      event?.part?.reason === 'stop'
    ) {
      terminalSeen = true;
      terminalAt = Date.now();
      await record('terminal_grace');
    }
  };

  const readNewLines = async () => {
    let data;
    try {
      data = await readFile(options.output, 'utf8');
    } catch (error) {
      if (error?.code === 'ENOENT') return;
      throw error;
    }
    const fresh = data.slice(readOffset);
    readOffset = data.length;
    if (!fresh) return;
    const lines = (partialLine + fresh).split('\n');
    partialLine = lines.pop() ?? '';
    for (const line of lines) await processLine(line);
  };

  const handleParentSignal = (signal) => {
    if (forwardedSignal !== null) return;
    forwardedSignal = signal;
    void record('parent_signal', { signal }).then(() => signalGroup(signal));
  };
  process.on('SIGTERM', () => handleParentSignal('SIGTERM'));
  process.on('SIGINT', () => handleParentSignal('SIGINT'));

  try {
    child = spawn(command[0], command.slice(1), {
      detached: true,
      stdio: ['ignore', output.fd, output.fd],
      env: process.env,
    });
    child.once('error', (error) => {
      childExited = true;
      childExitCode = 127;
      void record('spawn_error', { error: error.message });
    });
    child.once('exit', (code, signal) => {
      childExited = true;
      childExitCode = code;
      childSignal = signal;
    });
    await record('running');

    while (!childExited) {
      await readNewLines();
      if (forwardedSignal !== null) {
        await sleep(options.terminateGraceMs);
        if (!childExited) await signalGroup('SIGKILL');
      } else if (
        terminalSeen &&
        terminalAt !== null &&
        Date.now() - terminalAt >= options.terminalGraceMs
      ) {
        forcedAfterTerminal = true;
        await record('terminating');
        await signalGroup('SIGTERM');
        const deadline = Date.now() + options.terminateGraceMs;
        while (!childExited && Date.now() < deadline) await sleep(options.pollIntervalMs);
        if (!childExited) {
          await record('killing');
          await signalGroup('SIGKILL');
        }
      }
      if (!childExited) await sleep(options.pollIntervalMs);
    }
    await readNewLines();
    if (partialLine) await processLine(partialLine);
    await record('process_exited', { exitCode: childExitCode, signal: childSignal });

    // A regular-file stdout prevents inherited descriptors from blocking this
    // runner, but descendants in the OpenCode process group may still be alive.
    if (terminalSeen && groupExists()) {
      await record('descendant_cleanup');
      await signalGroup('SIGTERM', true);
      const deadline = Date.now() + options.terminateGraceMs;
      while (groupExists() && Date.now() < deadline) await sleep(options.pollIntervalMs);
      if (groupExists()) await signalGroup('SIGKILL', true);
    }

    if (forcedAfterTerminal) return 0;
    if (forwardedSignal === 'SIGINT') return 130;
    if (forwardedSignal === 'SIGTERM') return 143;
    if (childExitCode !== null) return childExitCode;
    return 1;
  } finally {
    await output.close();
    await stateLog.close();
  }
}

process.exitCode = await main();
