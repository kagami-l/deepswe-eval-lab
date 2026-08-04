import assert from 'node:assert/strict';
import test from 'node:test';

import {
  mapPermissionsToOpenCodeOptions,
  wrapOpencodeClient,
} from '@sublang/cligent/adapters/opencode';

test('CLI-004 patch maps OpenCode auto to external_directory allow', () => {
  const mapped = mapPermissionsToOpenCodeOptions({ mode: 'auto' }) as unknown as {
    permission: Record<string, string>;
  };
  assert.equal(mapped.permission.external_directory, 'allow');
});

test('CLI-004 patch carries external_directory into the v2 session ruleset', async () => {
  let createInput: Record<string, unknown> | undefined;
  const stream = {
    async *[Symbol.asyncIterator](): AsyncGenerator<Record<string, unknown>> {
      return;
    },
  };
  const client = wrapOpencodeClient(
    {
      event: {
        async subscribe(): Promise<{ stream: typeof stream }> {
          return { stream };
        },
      },
      session: {
        async create(input: Record<string, unknown>): Promise<{ data: { id: string } }> {
          createInput = input;
          return { data: { id: 'session-1' } };
        },
        async promptAsync(): Promise<Record<string, never>> {
          return {};
        },
      },
    },
    { apiVersion: 'v2' },
  );
  const mapped = mapPermissionsToOpenCodeOptions({ mode: 'auto' }) as unknown as {
    permission: Record<string, string>;
  };

  await client.run?.({
    cwd: '/app',
    permission: mapped.permission,
    prompt: 'test',
  });

  const rules = createInput?.permission as
    | Array<{ permission: string; pattern: string; action: string }>
    | undefined;
  assert.ok(rules);
  assert.ok(
    rules.some(
      (rule) =>
        rule.permission === 'external_directory' &&
        rule.pattern === '*' &&
        rule.action === 'allow',
    ),
  );
});
