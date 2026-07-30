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

SUPPORTED_ADAPTERS = ("claude", "codex", "kimi")

# Any-of credential environment variables required per adapter.
ADAPTER_CREDENTIALS: dict[str, tuple[str, ...]] = {
    "claude": ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"),
    "codex": ("OPENAI_API_KEY", "CODEX_API_KEY"),
    "kimi": ("KIMI_CODE_HOME", "KIMI_MODEL_API_KEY"),
}

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

    # --- run ---------------------------------------------------------------

    def _require_credentials(self) -> None:
        missing: list[str] = []
        for adapter in sorted(self.adapters_in_use):
            keys = ADAPTER_CREDENTIALS[adapter]
            if not any(self._has_env(key) for key in keys):
                missing.append(f"{adapter}: one of {' / '.join(keys)}")
        if missing:
            raise ValueError(
                "Missing adapter credentials (pass via `pier run --ae`): "
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
