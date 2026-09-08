# Agent SDK compatibility notes — 2026-09-08

The selected versions are now installed. Final changes and validation are recorded
in the [SDK upgrade implementation record](./20260908-agent-sdk-upgrade.md).

## Published 0.26.0 follow-up and proposed baseline

The implementation investigation subsequently obtained the published npm package
`@sublang/cligent` **0.26.0** in `/tmp/deep-swe-sdk-upgrade/package`. Its
`docs/releases/0.26.0-preparation.md` identifies additive model discovery as the
release feature and states that existing execution, dependency ranges, and
compatibility floors are unchanged. That preparation document records local
release checks, with CI/tag steps delegated; it is not independent evidence of
the eventual CI result.

Direct artifact comparison against this project's installed npm 0.25.0 confirms:

- All JavaScript under `dist/adapters/` is byte-identical. The only adapter
  declaration difference is reordered enum members in `acp-schema.d.ts`, retaining
  identical names and types.
- `dist/cligent.js`, `dist/runtime-version.js`, and `dist/runtime-targets.js` are
  byte-identical.
- `dist/index.js` adds the `discoverAgentModels` export. Its new module defines
  discovery functions and constants; importing the export does not itself launch
  a provider process. These consumers do not call the new API.

**Recommended formal baseline: published cligent 0.26.0 plus its exact tested
targets in the table below.** This upgrades the wrapper to its newly published
release and the vendor runtimes to the newest combination this wrapper release
has already verified, without an identified additional caller migration.

The main upgrade investigation separately queried npm and found newer vendor
versions (Claude SDK 0.3.263, Codex SDK/CLI 0.153.4, Gemini 0.58.0, Kimi 0.41.0,
OpenCode SDK/CLI 1.18.29). Those are all above the unchanged tested targets. They
are admitted as `untested`, not declared incompatible. This review found no
specific required fix or model route in those unexamined vendor releases that
justifies adopting them before compatibility verification. OpenCode has the
concrete partial-accounting consequence described below. Selecting tested
versions is therefore an evidence-based baseline choice, **not a claim that
newer versions cannot work or that these are npm's latest releases**.

Final dependency installation and validation remain the responsibility of the
implementation record. The source analysis below is retained as the 0.25.0
static snapshot; the unchanged 0.26.0 execution artifacts confirm its gate and
accounting conclusions also apply to the proposed baseline.

## Local 0.25.0 source snapshot

Read-only source review of `@sublang/cligent` 0.25.0, local checkout commit
`6b97fed86d4271e7ff94af5a3b24483e4cad3a19`. The checkout is evidence only;
production dependencies must continue to come from published npm packages.
This note does not establish npm's latest versions or replace installed-package,
container, authentication, or real-model verification.

## Declared targets and upgrade boundary

| Runtime | Supported from | Cligent's exact tested version |
| --- | --- | --- |
| `@anthropic-ai/claude-agent-sdk` | 0.3.219 | 0.3.251 |
| `@openai/codex-sdk` / SDK-selected `@openai/codex` | 0.144.0 | 0.151.0 |
| `@google/gemini-cli` | 0.45.1 | 0.57.0 |
| `@moonshot-ai/kimi-code` | 0.28.1 | 0.39.1 |
| `@opencode-ai/sdk` and `opencode-ai` | 1.18.12 | 1.18.25 |

Source: [runtime-targets.ts](/Users/kgm/Projects/merico/cligent/src/runtime-targets.ts:102).
Cligent pins its own ACP protocol dependency to `@agentclientprotocol/sdk` 1.4.0,
paired with Kimi 0.39.1; consumers need not independently override that protocol
dependency ([package-23](/Users/kgm/Projects/merico/cligent/specs/packages/package.md:98)).

Versions above `tested` load and classify as `untested`; `run()` rejects only
readable versions below `supportedFrom`. Unknown versions are admitted. Thus
“newer than tested” is neither a hard upper bound nor evidence that the newer
vendor release has been verified. The published peer range intentionally has no
upper bound. Codex version resolution checks the executable package selected by
the SDK's own declared dependency tree, not an unrelated global CLI. Claude's
compatibility authority is its SDK, so upgrading a separate global Claude CLI
does not satisfy that dependency.

Evidence: [package-201](/Users/kgm/Projects/merico/cligent/specs/packages/package.md:263),
[runtime gate](/Users/kgm/Projects/merico/cligent/src/runtime-version.ts:217),
[readiness classification](/Users/kgm/Projects/merico/cligent/src/runtime-version.ts:270),
and [DR-013](/Users/kgm/Projects/merico/cligent/specs/decisions/013-cligent-owned-runtime-compatibility.md).

OpenCode has a material additional constraint: complete usage accounting requires
`global.health` to report healthy **and exactly 1.18.25**. Another version leaves
execution unblocked but forces partial accounting. Keep the SDK and CLI paired
at 1.18.25 while using cligent 0.25.0 if preserving the newly repaired accounting
is the priority. This is an accounting-proof rule, not a general refusal to run
newer OpenCode.

Evidence: [opencode-49](/Users/kgm/Projects/merico/cligent/specs/packages/adapters/opencode.md:659),
[health check](/Users/kgm/Projects/merico/cligent/src/adapters/opencode.ts:1405).

## Existing consumer calls and authentication

Both runtime runners call cligent's public adapters and unified `run()` surface.
No additional caller API migration was identified for upgrading Claude, Codex,
Gemini, or Kimi to the above tested targets after the existing cligent 0.25.0
migration. Keep the current watchdog, event diagnostics, cancellation containment,
and residual-permission failure handling; dependency versions alone do not prove
those protections redundant.

- Claude: the existing API-key/OAuth-token environment forwarding remains within
  the adapter contract. Cligent clones the inherited environment and only removes
  `CLAUDECODE`; no new consumer authentication field is required by that contract.
  See [claude-code-34](/Users/kgm/Projects/merico/cligent/specs/packages/adapters/claude-code.md:359).
- Codex: the adapter supplies the modern permission controls itself. A supplied
  permission policy adds `--ignore-user-config` while retaining `CODEX_HOME`
  authentication and session state. Existing injected `auth.json` and forwarded
  credential environment routes do not require a consumer migration indicated by
  this contract. See [codex-4 and codex-31](/Users/kgm/Projects/merico/cligent/specs/packages/adapters/codex.md:170).
- Gemini: the consumer uses the CLI adapter with inherited credentials and
  `GEMINI_CLI_TRUST_WORKSPACE`; per-run policies, effort defaults, telemetry,
  and their cleanup are already handled by cligent. No additional required
  consumer setting was identified in the pinned-target adapter specification.
  This is not a live verification of Google OAuth or service credentials.
  See [Gemini adapter specification](/Users/kgm/Projects/merico/cligent/specs/packages/adapters/gemini.md).
- Kimi: 0.39.1 explicitly admits stored OAuth, a configured default model with
  non-OAuth credentials, and the pair `KIMI_MODEL_NAME` + `KIMI_MODEL_API_KEY`.
  A bare `MOONSHOT_API_KEY` or `KIMI_API_KEY` does not establish the default-model
  alias needed by ACP. See [kimi-21](/Users/kgm/Projects/merico/cligent/specs/packages/adapters/kimi.md:152).

The two consumer entry points currently impose a narrower Kimi OAuth policy.
The unified entry point also generates a `managed:kimi-code` model configuration
with OAuth storage; simply removing its credential check would not establish a
correct provider-key route. The legacy collab entry point explicitly retains the
OAuth route. These policies do **not** prevent upgrading the CLI to 0.39.1, so an
authentication feature expansion is not a required upgrade migration. However,
text claiming that Kimi ACP universally requires OAuth or cannot accept the
model/key pair is stale and should identify the restriction as this project's
current policy instead.

Consumer evidence: [unified Kimi config](/Users/kgm/Projects/merico/deep-swe/wip/agents/deep_swe_agent/pier_agent.py:110),
[unified credential gate](/Users/kgm/Projects/merico/deep-swe/wip/agents/deep_swe_agent/pier_agent.py:324),
[collab credential gate](/Users/kgm/Projects/merico/deep-swe/wip/agents/deep_swe_collab/pier_agent.py:423),
and [collab Kimi documentation](/Users/kgm/Projects/merico/deep-swe/wip/agents/deep_swe_collab/README.md:71).

For any package selected above cligent's tested version, verify the installed
package's actual runtime/declaration surfaces and record the `untested` status;
this local cligent review cannot establish unpublished or unexamined vendor
changes. Final installed versions and validation results belong in the upgrade
implementation record.
