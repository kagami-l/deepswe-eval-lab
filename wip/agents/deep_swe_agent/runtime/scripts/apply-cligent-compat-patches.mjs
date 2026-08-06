import { readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const runtimeDir = join(dirname(fileURLToPath(import.meta.url)), '..');
const packageDir = join(
  runtimeDir,
  'node_modules',
  '@sublang',
  'cligent',
);
const packageJsonPath = join(packageDir, 'package.json');
const adapterPath = join(packageDir, 'dist', 'adapters', 'opencode.js');
const expectedVersion = '0.18.0';

const packageJson = JSON.parse(await readFile(packageJsonPath, 'utf8'));
if (packageJson.version !== expectedVersion) {
  throw new Error(
    `CLI-004 compatibility patch requires @sublang/cligent ${expectedVersion}; ` +
      `found ${String(packageJson.version)}`,
  );
}

const replacements = [
  {
    original: "for (const key of ['edit', 'bash', 'webfetch']) {",
    patched:
      "for (const key of ['edit', 'bash', 'webfetch', 'external_directory']) {",
  },
  {
    original:
      "permission: { edit: 'allow', bash: 'allow', webfetch: 'allow' },",
    patched:
      "permission: { edit: 'allow', bash: 'allow', webfetch: 'allow', external_directory: 'allow' },",
  },
];

let source = await readFile(adapterPath, 'utf8');
let changed = false;
for (const { original, patched } of replacements) {
  if (source.includes(patched)) continue;
  const matches = source.split(original).length - 1;
  if (matches !== 1) {
    throw new Error(
      `CLI-004 compatibility patch expected exactly one match in ${adapterPath}; ` +
        `found ${matches}. Refuse to patch an unknown cligent build.`,
    );
  }
  source = source.replace(original, patched);
  changed = true;
}

if (changed) {
  await writeFile(adapterPath, source);
  console.log(
    `Applied CLI-004 OpenCode auto-permission patch to cligent ${expectedVersion}`,
  );
} else {
  console.log(
    `CLI-004 OpenCode auto-permission patch already applied to cligent ${expectedVersion}`,
  );
}
