import assert from "node:assert/strict";
import test from "node:test";

import { ensureImage, isRateLimitError } from "./pull-task-images.mjs";

const quietLogger = { log() {}, warn() {} };

test("skips pulling an image that already exists", async () => {
  const calls = [];
  const result = await ensureImage({
    image: "example/image:tag",
    logger: quietLogger,
    runCommand: async (command, args, options) => {
      calls.push({ command, args, options });
      return { code: 0, signal: null, output: "" };
    },
  });

  assert.equal(result, "skipped");
  assert.deepEqual(calls, [
    {
      command: "docker",
      args: ["image", "inspect", "example/image:tag"],
      options: { silent: true },
    },
  ]);
});

test("retries ECR rate limits with 30, 60, and 120 second backoff", async () => {
  let pullAttempts = 0;
  const sleeps = [];
  const result = await ensureImage({
    image: "example/image:tag",
    logger: quietLogger,
    sleepFn: async (milliseconds) => sleeps.push(milliseconds),
    runCommand: async (_command, args) => {
      if (args[0] === "image") {
        return { code: 1, signal: null, output: "" };
      }

      pullAttempts += 1;
      return pullAttempts <= 3
        ? { code: 1, signal: null, output: "toomanyrequests: Rate exceeded" }
        : { code: 0, signal: null, output: "" };
    },
  });

  assert.equal(result, "pulled");
  assert.equal(pullAttempts, 4);
  assert.deepEqual(sleeps, [30_000, 60_000, 120_000]);
});

test("does not retry unrelated pull errors", async () => {
  let pullAttempts = 0;

  await assert.rejects(
    ensureImage({
      image: "example/image:tag",
      logger: quietLogger,
      sleepFn: async () => assert.fail("sleep should not be called"),
      runCommand: async (_command, args) => {
        if (args[0] === "image") {
          return { code: 1, signal: null, output: "" };
        }

        pullAttempts += 1;
        return { code: 1, signal: null, output: "manifest unknown" };
      },
    }),
    /docker exited with code 1/,
  );

  assert.equal(pullAttempts, 1);
});

test("recognizes common registry rate-limit messages", () => {
  assert.equal(isRateLimitError("toomanyrequests: Rate exceeded"), true);
  assert.equal(isRateLimitError("429 Too Many Requests"), true);
  assert.equal(isRateLimitError("manifest unknown"), false);
});
