#!/usr/bin/env node

import { readFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "..");
const retryDelaysMs = [30_000, 60_000, 120_000];

function printUsage() {
  console.error("Usage: node wip/pull-task-images.mjs <task-ids.txt>");
}

function parseTaskIds(contents) {
  const taskIds = [];
  const seen = new Set();

  for (const rawLine of contents.split(/\r?\n/)) {
    const taskId = rawLine.replace(/\s+#.*$/, "").trim();
    if (!taskId || taskId.startsWith("#")) continue;

    if (!/^[a-z0-9][a-z0-9-]*$/.test(taskId)) {
      throw new Error(`Invalid task ID: ${JSON.stringify(taskId)}`);
    }

    if (!seen.has(taskId)) {
      seen.add(taskId);
      taskIds.push(taskId);
    }
  }

  return taskIds;
}

function getDockerImage(taskToml, taskId) {
  let section = "";

  for (const rawLine of taskToml.split(/\r?\n/)) {
    const line = rawLine.trim();
    const sectionMatch = line.match(/^\[([^\]]+)]$/);
    if (sectionMatch) {
      section = sectionMatch[1];
      continue;
    }

    if (section === "environment") {
      const imageMatch = line.match(/^docker_image\s*=\s*["']([^"']+)["']/);
      if (imageMatch) return imageMatch[1];
    }
  }

  throw new Error(`Missing [environment].docker_image for task: ${taskId}`);
}

function run(command, args, { silent = false } = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      stdio: silent ? ["ignore", "ignore", "ignore"] : ["inherit", "pipe", "pipe"],
    });
    let output = "";

    const forwardOutput = (stream, destination) => {
      stream?.on("data", (chunk) => {
        destination.write(chunk);
        output = `${output}${chunk}`.slice(-65_536);
      });
    };

    if (!silent) {
      forwardOutput(child.stdout, process.stdout);
      forwardOutput(child.stderr, process.stderr);
    }

    child.once("error", reject);
    child.once("close", (code, signal) => {
      resolve({ code, signal, output });
    });
  });
}

function commandError(command, result) {
  return new Error(
    result.signal
      ? `${command} terminated by signal ${result.signal}`
      : `${command} exited with code ${result.code}`,
  );
}

export function isRateLimitError(output) {
  return /toomanyrequests|too many requests|rate exceeded/i.test(output);
}

function sleep(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

export async function ensureImage({
  image,
  platformArgs = [],
  runCommand = run,
  sleepFn = sleep,
  delays = retryDelaysMs,
  logger = console,
}) {
  const inspectResult = await runCommand(
    "docker",
    ["image", "inspect", image],
    { silent: true },
  );
  if (inspectResult.code === 0) {
    logger.log("Image already exists; skipping pull.");
    return "skipped";
  }

  const pullArgs = ["pull", ...platformArgs, image];
  for (let attempt = 0; ; attempt += 1) {
    logger.log(`docker ${pullArgs.join(" ")}`);
    const pullResult = await runCommand("docker", pullArgs);
    if (pullResult.code === 0) return "pulled";

    if (!isRateLimitError(pullResult.output) || attempt >= delays.length) {
      throw commandError("docker", pullResult);
    }

    const delayMs = delays[attempt];
    logger.warn(
      `Public ECR rate limit reached; retrying in ${delayMs / 1_000}s `
      + `(${attempt + 1}/${delays.length}).`,
    );
    await sleepFn(delayMs);
  }
}

async function main() {
  const [taskListArg, ...extraArgs] = process.argv.slice(2);
  if (!taskListArg || extraArgs.length > 0) {
    printUsage();
    process.exitCode = 2;
    return;
  }

  const taskListPath = path.resolve(process.cwd(), taskListArg);
  const taskIds = parseTaskIds(await readFile(taskListPath, "utf8"));
  if (taskIds.length === 0) {
    throw new Error(`No task IDs found in ${taskListPath}`);
  }

  const platformArgs = process.arch === "arm64"
    ? ["--platform", "linux/amd64"]
    : [];
  let pulledCount = 0;
  let skippedCount = 0;

  for (const [index, taskId] of taskIds.entries()) {
    const taskTomlPath = path.join(repoRoot, "tasks", taskId, "task.toml");
    let taskToml;
    try {
      taskToml = await readFile(taskTomlPath, "utf8");
    } catch (error) {
      if (error.code === "ENOENT") {
        throw new Error(`Task not found: ${taskId} (${taskTomlPath})`);
      }
      throw error;
    }

    const image = getDockerImage(taskToml, taskId);
    console.log(`\n[${index + 1}/${taskIds.length}] ${taskId}`);
    const result = await ensureImage({ image, platformArgs });
    if (result === "skipped") {
      skippedCount += 1;
    } else {
      pulledCount += 1;
    }
  }

  console.log(
    `\nCompleted ${taskIds.length} task image(s): `
    + `${pulledCount} pulled, ${skippedCount} already present.`,
  );
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(`\nError: ${error.message}`);
    process.exitCode = 1;
  });
}
