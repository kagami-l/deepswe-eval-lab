"""Pier adapter for the DeepSWE Modifier/Reviewer collaboration runtime.

Architecture (docs/collab-agent-design.md): this thin host-side adapter
installs a Node runtime bundle into the task container and launches the
TypeScript orchestrator there. The orchestrator drives exactly two LLM
agents through cligent (a Modifier working in ``/app`` and a Reviewer in an
isolated copy) and leaves checkpoint commits for ``pre_artifacts.sh``.

Registry packages (cligent + agent SDKs, optionally Kimi Code) install via
``install_spec()`` so derived images cache them; the orchestrator's built
``dist/`` is uploaded at ``setup()`` time.
"""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pier.agents.installed.base import BaseInstalledAgent, with_prompt_template
from pier.environments.base import BaseEnvironment
from pier.models.agent.context import AgentContext
from pier.models.agent.install import AgentInstallSpec, InstallStep
from pier.models.agent.network import NetworkAllowlist
from pier.utils.env import parse_bool_env_value

RUNTIME_DIR = "/opt/collab-runtime"
OUTPUT_DIR = "/logs/agent/collab"
WORK_DIR = "/tmp/deepswe-collab"

# Credential material stays under /tmp — never under /logs, which is synced
# back to the host as artifacts.
REMOTE_SECRETS_DIR = "/tmp/collab-secrets"
REMOTE_CODEX_HOME = "/tmp/codex-home"
REMOTE_KIMI_HOME = "/tmp/kimi-code-home"

SUPPORTED_ADAPTERS = ("claude", "codex", "kimi")

# Claude has no file-injection path (macOS stores its login in the Keychain);
# the standard host-auth route is `claude setup-token` → CLAUDE_CODE_OAUTH_TOKEN.
CLAUDE_CREDENTIAL_ENVS = ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")

_SAFE_NPM_VERSION = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._+-]*$")


def _as_int(name: str, value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid integer for '{name}': {value!r}") from exc


def _as_float(name: str, value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid number for '{name}': {value!r}") from exc


def _as_bool(name: str, value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return parse_bool_env_value(value, name=name)


def _validated_adapter(name: str, value: Any) -> str:
    adapter = str(value).strip().lower()
    if adapter not in SUPPORTED_ADAPTERS:
        raise ValueError(
            f"Unsupported {name} '{value}'. "
            f"Supported adapters: {', '.join(SUPPORTED_ADAPTERS)} "
            "(gemini/opencode are excluded in the first phase, see "
            "docs/collab-agent-design.md section 6.4)."
        )
    return adapter


def _validated_version(name: str, value: Any) -> str:
    version = str(value)
    if not _SAFE_NPM_VERSION.fullmatch(version):
        raise ValueError(f"Invalid npm version for '{name}': {value!r}")
    return version


class DeepSweCollabAgent(BaseInstalledAgent):
    """Run the modify → review → revise collaboration as one Pier agent."""

    DEFAULT_CLIGENT_VERSION = "0.16.0"
    DEFAULT_KIMI_CODE_VERSION = "0.30.0"
    # cligent's own tested SDK versions (its devDependencies).
    CLAUDE_SDK_VERSION = "0.3.207"
    CODEX_SDK_VERSION = "0.144.5"

    def __init__(
        self,
        *args: Any,
        modifier_adapter: str = "codex",
        reviewer_adapter: str = "claude",
        modifier_model: str | None = None,
        reviewer_model: str | None = None,
        modifier_effort: str | None = None,
        reviewer_effort: str | None = None,
        max_reviews: Any = 3,
        max_agent_attempts: Any = 2,
        modifier_timeout_seconds: Any = 2400.0,
        reviewer_timeout_seconds: Any = 600.0,
        revision_timeout_seconds: Any = 900.0,
        total_timeout_seconds: Any = 5100.0,
        strict: Any = False,
        keep_workspaces: Any = False,
        cligent_version: str = DEFAULT_CLIGENT_VERSION,
        kimi_code_version: str = DEFAULT_KIMI_CODE_VERSION,
        **kwargs: Any,
    ) -> None:
        self.modifier_adapter = _validated_adapter("modifier_adapter", modifier_adapter)
        self.reviewer_adapter = _validated_adapter("reviewer_adapter", reviewer_adapter)
        self.modifier_model = modifier_model
        self.reviewer_model = reviewer_model
        self.modifier_effort = modifier_effort
        self.reviewer_effort = reviewer_effort
        self.max_reviews = _as_int("max_reviews", max_reviews)
        self.max_agent_attempts = _as_int("max_agent_attempts", max_agent_attempts)
        self.modifier_timeout_seconds = _as_float(
            "modifier_timeout_seconds", modifier_timeout_seconds
        )
        self.reviewer_timeout_seconds = _as_float(
            "reviewer_timeout_seconds", reviewer_timeout_seconds
        )
        self.revision_timeout_seconds = _as_float(
            "revision_timeout_seconds", revision_timeout_seconds
        )
        self.total_timeout_seconds = _as_float(
            "total_timeout_seconds", total_timeout_seconds
        )
        self.strict = _as_bool("strict", strict)
        self.keep_workspaces = _as_bool("keep_workspaces", keep_workspaces)
        self.cligent_version = _validated_version("cligent_version", cligent_version)
        self.kimi_code_version = _validated_version(
            "kimi_code_version", kimi_code_version
        )
        if self.max_reviews < 0:
            raise ValueError("max_reviews must be >= 0")
        super().__init__(*args, version=self.cligent_version, **kwargs)

    @staticmethod
    def name() -> str:
        return "deep-swe-collab"

    @property
    def adapters_in_use(self) -> set[str]:
        return {self.modifier_adapter, self.reviewer_adapter}

    # --- install -----------------------------------------------------------

    def runtime_dependencies(self) -> dict[str, str]:
        """npm dependencies for the in-container runtime.

        Must stay in sync with ``runtime/package.json``; the unit tests
        enforce the match so the derived image and the host build cannot
        drift apart.
        """
        return {
            "@anthropic-ai/claude-agent-sdk": self.CLAUDE_SDK_VERSION,
            "@openai/codex-sdk": self.CODEX_SDK_VERSION,
            "@sublang/cligent": self.cligent_version,
        }

    def install_spec(self) -> AgentInstallSpec:
        package_json = json.dumps(
            {
                "name": "deep-swe-collab-runtime",
                "private": True,
                "type": "module",
                "dependencies": self.runtime_dependencies(),
            },
            indent=2,
            sort_keys=True,
        )
        root_install = f"""
set -euo pipefail
if ! command -v git >/dev/null 2>&1 || [ ! -f /etc/ssl/certs/ca-certificates.crt ]; then
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y --no-install-recommends ca-certificates curl git
    rm -rf /var/lib/apt/lists/*
  else
    echo "Unsupported package manager for collab runtime installation" >&2
    exit 1
  fi
fi
install -d -m 0777 {RUNTIME_DIR}
""".strip()

        kimi_install = ""
        if "kimi" in self.adapters_in_use:
            kimi_package = shlex.quote(
                f"@moonshot-ai/kimi-code@{self.kimi_code_version}"
            )
            # The new Kimi Code CLI and the legacy Python kimi-cli share the
            # binary name `kimi`; probe for the ACP subcommand cligent needs.
            kimi_install = f"""
npm install --global {kimi_package}
kimi --version
kimi --help 2>&1 | grep -q acp || {{
  echo "installed kimi binary has no 'acp' subcommand (legacy kimi-cli on PATH?)" >&2
  exit 1
}}
"""
        agent_install = f"""
set -euo pipefail
node -e 'const [a,b]=process.versions.node.split(".").map(Number); process.exit(a > 22 || (a === 22 && b >= 19) ? 0 : 1)' || {{
  echo "Node >= 22.19 required (task images ship Node 24)" >&2
  exit 1
}}
cd {RUNTIME_DIR}
cat > package.json <<'PACKAGE_JSON'
{package_json}
PACKAGE_JSON
npm install --omit=dev --no-audit --no-fund
{kimi_install}
npm cache clean --force
""".strip()

        return AgentInstallSpec(
            agent_name=self.name(),
            version=self.cligent_version,
            steps=[
                InstallStep(
                    user="root",
                    env={"DEBIAN_FRONTEND": "noninteractive"},
                    run=root_install,
                ),
                InstallStep(user="agent", run=agent_install),
            ],
            verification_command=self.get_version_command(),
            metadata={
                "package": "@sublang/cligent",
                "adapters": "+".join(sorted(self.adapters_in_use)),
                "interface": "collab-runtime",
            },
        )

    def get_version_command(self) -> str | None:
        return (
            f"cd {RUNTIME_DIR} && node --input-type=module "
            "-e \"await import('@sublang/cligent'); console.log('cligent-ok')\""
        )

    def parse_version(self, stdout: str) -> str:
        del stdout
        return self.cligent_version

    async def setup(self, environment: BaseEnvironment) -> None:
        await super().setup(environment)
        dist_dir = Path(__file__).parent / "runtime" / "dist"
        if not (dist_dir / "main.js").exists():
            raise RuntimeError(
                "Collab runtime is not built. Run `npm ci && npm run build` in "
                "wip/agents/deep_swe_collab/runtime first."
            )
        await environment.upload_dir(dist_dir, f"{RUNTIME_DIR}/dist")

    # --- auth --------------------------------------------------------------

    def _resolve_codex_auth_json_path(self) -> Path | None:
        """Which host auth.json to inject for Codex, if any.

        Mirrors pier's built-in Codex agent:
          - CODEX_AUTH_JSON_PATH=<path> → use that specific file;
          - CODEX_FORCE_AUTH_JSON=<truthy> → use ~/.codex/auth.json
            (the `codex login` OAuth credential);
          - neither → None (OPENAI_API_KEY / CODEX_API_KEY auth).
        """
        explicit = self._get_env("CODEX_AUTH_JSON_PATH")
        if explicit:
            path = Path(explicit)
            if not path.is_file():
                raise ValueError(
                    f"CODEX_AUTH_JSON_PATH points to non-existent file: {explicit}"
                )
            return path
        if parse_bool_env_value(
            self._get_env("CODEX_FORCE_AUTH_JSON"),
            name="CODEX_FORCE_AUTH_JSON",
            default=False,
        ):
            default = Path.home() / ".codex" / "auth.json"
            if not default.is_file():
                raise ValueError(
                    f"CODEX_FORCE_AUTH_JSON is set but {default} does not exist; "
                    "run `codex login` first"
                )
            return default
        return None

    def _resolve_kimi_auth_home(self) -> Path | None:
        """Which host Kimi Code home to inject, if any.

        cligent drives Kimi Code over ACP, which requires the OAuth
        credential created by `kimi login` (`credentials/kimi-code.json`):
          - KIMI_AUTH_HOME_PATH=<dir> → use that Kimi Code home;
          - KIMI_FORCE_AUTH_HOME=<truthy> → use ~/.kimi-code;
          - neither → None (KIMI_MODEL_* provider-config passthrough only).
        """
        explicit = self._get_env("KIMI_AUTH_HOME_PATH")
        home: Path | None = None
        if explicit:
            home = Path(explicit)
            if not home.is_dir():
                raise ValueError(
                    f"KIMI_AUTH_HOME_PATH points to non-existent directory: {explicit}"
                )
        elif parse_bool_env_value(
            self._get_env("KIMI_FORCE_AUTH_HOME"),
            name="KIMI_FORCE_AUTH_HOME",
            default=False,
        ):
            home = Path.home() / ".kimi-code"
            if not home.is_dir():
                raise ValueError(
                    f"KIMI_FORCE_AUTH_HOME is set but {home} does not exist; "
                    "run `kimi login` first"
                )
        if home is not None and not (home / "credentials" / "kimi-code.json").is_file():
            raise ValueError(
                f"Kimi Code home {home} has no credentials/kimi-code.json; "
                "run `kimi login` first"
            )
        return home

    async def _configure_codex_auth(
        self, environment: BaseEnvironment, env: dict[str, str]
    ) -> None:
        """Materialize ``$CODEX_HOME/auth.json`` the same way pier's built-in
        Codex agent does: from an injected host auth.json, or from
        OPENAI_API_KEY. cligent's codex adapter spawns the ``codex`` binary,
        which inherits CODEX_HOME from the runtime process."""
        env["CODEX_HOME"] = REMOTE_CODEX_HOME
        remote_auth = f"{REMOTE_SECRETS_DIR}/codex-auth.json"
        await self.exec_as_agent(
            environment,
            command=f'mkdir -p "$CODEX_HOME" {shlex.quote(REMOTE_SECRETS_DIR)}',
            env=env,
        )
        auth_json_path = self._resolve_codex_auth_json_path()
        if auth_json_path is not None:
            self.logger.debug("Codex auth: injecting %s", auth_json_path)
            await environment.upload_file(auth_json_path, remote_auth)
            if environment.default_user is not None:
                await self.exec_as_root(
                    environment,
                    command=f"chown {environment.default_user} {shlex.quote(remote_auth)}",
                )
            await self.exec_as_agent(
                environment,
                command=(
                    f"chmod 600 {shlex.quote(remote_auth)} && "
                    f'ln -sf {shlex.quote(remote_auth)} "$CODEX_HOME/auth.json"'
                ),
                env=env,
            )
        elif self._has_env("OPENAI_API_KEY"):
            self.logger.debug("Codex auth: materializing auth.json from OPENAI_API_KEY")
            await self.exec_as_agent(
                environment,
                command=(
                    f"umask 077 && cat >{shlex.quote(remote_auth)} <<EOF\n"
                    '{\n  "OPENAI_API_KEY": "${OPENAI_API_KEY}"\n}\nEOF\n'
                    f'ln -sf {shlex.quote(remote_auth)} "$CODEX_HOME/auth.json"'
                ),
                env=env,
            )
        # CODEX_API_KEY-only setups rely on plain env passthrough.

    async def _configure_kimi_auth(
        self, environment: BaseEnvironment, env: dict[str, str]
    ) -> None:
        """Reconstruct an owner-only Kimi Code home in the container from the
        host login (config.toml + credentials/), following cligent's own CI
        harness. Without an injected home, only KIMI_MODEL_* provider config
        is passed through — note ACP mode still expects a `kimi login`
        credential."""
        env["KIMI_CODE_HOME"] = REMOTE_KIMI_HOME
        env.setdefault("KIMI_DISABLE_TELEMETRY", "1")
        env.setdefault("KIMI_CODE_NO_AUTO_UPDATE", "1")
        env.setdefault("KIMI_DISABLE_CRON", "1")
        await self.exec_as_agent(
            environment,
            command='mkdir -p "$KIMI_CODE_HOME/credentials"',
            env=env,
        )
        home = self._resolve_kimi_auth_home()
        if home is None:
            return
        self.logger.debug("Kimi auth: injecting home from %s", home)
        await environment.upload_dir(
            home / "credentials", f"{REMOTE_KIMI_HOME}/credentials"
        )
        if (home / "config.toml").is_file():
            await environment.upload_file(
                home / "config.toml", f"{REMOTE_KIMI_HOME}/config.toml"
            )
        if environment.default_user is not None:
            await self.exec_as_root(
                environment,
                command=f"chown -R {environment.default_user} {REMOTE_KIMI_HOME}",
            )
        await self.exec_as_agent(
            environment,
            command=f"chmod -R go-rwx {REMOTE_KIMI_HOME}",
            env=env,
        )

    # --- run ---------------------------------------------------------------

    def _require_credentials(self) -> None:
        missing: list[str] = []
        if "claude" in self.adapters_in_use and not any(
            self._has_env(key) for key in CLAUDE_CREDENTIAL_ENVS
        ):
            missing.append(f"claude: one of {' / '.join(CLAUDE_CREDENTIAL_ENVS)}")
        if "codex" in self.adapters_in_use:
            if self._resolve_codex_auth_json_path() is None and not (
                self._has_env("OPENAI_API_KEY") or self._has_env("CODEX_API_KEY")
            ):
                missing.append(
                    "codex: OPENAI_API_KEY / CODEX_API_KEY, or host auth via "
                    "CODEX_FORCE_AUTH_JSON=1 / CODEX_AUTH_JSON_PATH"
                )
        if "kimi" in self.adapters_in_use:
            if self._resolve_kimi_auth_home() is None and not self._has_env(
                "KIMI_MODEL_API_KEY"
            ):
                missing.append(
                    "kimi: host auth via KIMI_FORCE_AUTH_HOME=1 / "
                    "KIMI_AUTH_HOME_PATH, or KIMI_MODEL_API_KEY"
                )
        if missing:
            raise ValueError(
                "Missing adapter credentials (pass via `pier run --ae` or host env): "
                + "; ".join(missing)
            )

    def build_runtime_config(self) -> dict[str, Any]:
        return {
            "repoDir": "/app",
            "instructionPath": f"{OUTPUT_DIR}/instruction.md",
            "outputDir": OUTPUT_DIR,
            "workDir": WORK_DIR,
            "modifier": {
                "adapter": self.modifier_adapter,
                "model": self.modifier_model,
                "effort": self.modifier_effort,
            },
            "reviewer": {
                "adapter": self.reviewer_adapter,
                "model": self.reviewer_model,
                "effort": self.reviewer_effort,
            },
            "maxReviews": self.max_reviews,
            "maxAgentAttempts": self.max_agent_attempts,
            "modifierTimeoutSec": self.modifier_timeout_seconds,
            "reviewerTimeoutSec": self.reviewer_timeout_seconds,
            "revisionTimeoutSec": self.revision_timeout_seconds,
            "totalTimeoutSec": self.total_timeout_seconds,
            "strict": self.strict,
            "keepWorkspaces": self.keep_workspaces,
        }

    def _runtime_env(self) -> dict[str, str]:
        return self.build_process_env({"CI": "1", "NO_COLOR": "1"})

    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        del context  # Populated from summary.json after the run.
        self._require_credentials()
        env = self._runtime_env()
        if "codex" in self.adapters_in_use:
            await self._configure_codex_auth(environment, env)
        if "kimi" in self.adapters_in_use:
            await self._configure_kimi_auth(environment, env)

        staging = self.logs_dir / "collab-input"
        staging.mkdir(parents=True, exist_ok=True)
        (staging / "instruction.md").write_text(instruction)
        (staging / "config.json").write_text(
            json.dumps(self.build_runtime_config(), indent=2)
        )

        await self.exec_as_agent(environment, command=f"mkdir -p {OUTPUT_DIR}")
        await environment.upload_file(
            staging / "instruction.md", f"{OUTPUT_DIR}/instruction.md"
        )
        await environment.upload_file(
            staging / "config.json", f"{OUTPUT_DIR}/config.json"
        )

        command = (
            f"cd {RUNTIME_DIR} && "
            f"node dist/main.js --config {OUTPUT_DIR}/config.json"
        )
        await self.exec_as_agent(environment, command=command, env=env)

    # --- context -----------------------------------------------------------

    def _read_summary(self) -> dict[str, Any] | None:
        path = self.logs_dir / "collab" / "summary.json"
        if not path.exists():
            return None
        try:
            summary = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            self.logger.exception("Failed to read collab summary.json")
            return None
        return summary if isinstance(summary, dict) else None

    def populate_context_post_run(self, context: AgentContext) -> None:
        summary = self._read_summary()
        if summary is None:
            return
        result = summary.get("result")
        if not isinstance(result, dict):
            return
        usage = result.get("usage")
        roles = ("modifier", "reviewer")
        if isinstance(usage, dict):

            def total(field: str) -> int:
                return sum(int(usage.get(role, {}).get(field) or 0) for role in roles)

            context.n_input_tokens = total("inputTokens")
            context.n_output_tokens = total("outputTokens")
            context.n_agent_steps = total("turns")
            costs = [
                usage.get(role, {}).get("costUsd")
                for role in roles
                if usage.get(role, {}).get("costUsd") is not None
            ]
            if costs:
                context.cost_usd = float(sum(costs))
        context.metadata = {
            "collab": {
                "engine": summary.get("engine"),
                "outcome": result.get("outcome"),
                "degraded_reason": result.get("degradedReason"),
                "deliverable": result.get("deliverable"),
                "review_count": result.get("reviewCount"),
                "revision_count": result.get("revisionCount"),
                "no_change_revision": result.get("noChangeRevision"),
                "findings_total": result.get("findingsTotal"),
                "blocking_findings_total": result.get("blockingFindingsTotal"),
                "checkpoints": result.get("checkpoints"),
                "protocol_violations": result.get("protocolViolations"),
                "usage": usage,
                "modifier": summary.get("modifier"),
                "reviewer": summary.get("reviewer"),
            }
        }

    # --- network -----------------------------------------------------------

    @staticmethod
    def _hostname(value: str | None) -> str | None:
        if not value:
            return None
        parsed = urlparse(value if "://" in value else f"https://{value}")
        return parsed.hostname

    def network_allowlist(self) -> NetworkAllowlist:
        """Minimal egress set; only enforced when the task environment runs
        with ``allow_internet=False`` (pier enables its proxy solely in that
        combination — see docs/collab-agent-design.md section 11)."""
        domains: set[str] = {"registry.npmjs.org"}
        if "claude" in self.adapters_in_use:
            domains.add("api.anthropic.com")
        if "codex" in self.adapters_in_use:
            domains.update({"api.openai.com", "auth.openai.com", "chatgpt.com"})
        if "kimi" in self.adapters_in_use:
            base = self._hostname(self._get_env("KIMI_MODEL_BASE_URL"))
            domains.add(base or "api.kimi.com")
            domains.add("api.moonshot.ai")
        return NetworkAllowlist(domains=sorted(domains))
