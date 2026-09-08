import {
  AGENT_RUNTIME_TARGETS,
  classifyRuntime,
  describeRuntimeReadiness,
} from '@sublang/cligent';
import { ClaudeCodeAdapter } from '@sublang/cligent/adapters/claude-code';
import { CodexAdapter } from '@sublang/cligent/adapters/codex';
import { GeminiAdapter } from '@sublang/cligent/adapters/gemini';
import { KimiAdapter } from '@sublang/cligent/adapters/kimi';
import { OpenCodeAdapter } from '@sublang/cligent/adapters/opencode';

// Probe the installed production tree without credentials or model requests.
const adapters = {
  claude: new ClaudeCodeAdapter(),
  codex: new CodexAdapter(),
  gemini: new GeminiAdapter(),
  kimi: new KimiAdapter(),
  opencode: new OpenCodeAdapter(),
};

for (const [name, adapter] of Object.entries(adapters)) {
  const available = await adapter.isAvailable();
  for (const target of AGENT_RUNTIME_TARGETS[name]) {
    const readiness = classifyRuntime(target, available);
    console.log(`${name}: ${describeRuntimeReadiness(readiness)}`);
    // Newer versions remain eligible; cligent reports their untested status.
    if (!available || !['satisfied', 'untested'].includes(readiness.state)) {
      throw new Error(`Runtime unavailable or unverifiable: ${target.package}`);
    }
  }
}
