#!/usr/bin/env node

import { readFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "..");

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

function run(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: "inherit" });
    child.once("error", reject);
    child.once("exit", (code, signal) => {
      if (code === 0) {
        resolve();
      } else {
        reject(
          new Error(
            signal
              ? `${command} terminated by signal ${signal}`
              : `${command} exited with code ${code}`,
          ),
        );
      }
    });
  });
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
    console.log(`docker pull ${[...platformArgs, image].join(" ")}`);
    await run("docker", ["pull", ...platformArgs, image]);
  }

  console.log(`\nPulled ${taskIds.length} task image(s).`);
}

main().catch((error) => {
  console.error(`\nError: ${error.message}`);
  process.exitCode = 1;
});
