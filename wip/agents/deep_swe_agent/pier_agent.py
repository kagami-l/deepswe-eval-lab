"""Thin Pier adapter for the immutable unified DeepSWE Agent runtime."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pier.agents.installed.base import BaseInstalledAgent, with_prompt_template
from pier.environments.base import BaseEnvironment
from pier.models.agent.context import AgentContext
from pier.models.agent.install import AgentInstallSpec
from pier.models.agent.network import NetworkAllowlist
from pier.utils.trajectory_metrics import populate_context_from_final_metrics
from pier.utils.trajectory_utils import format_trajectory_json

from .atif import events_to_trajectory, load_events


DEFAULT_RUNTIME_DIR = "/opt/deep-swe-agent-runtime"
OUTPUT_DIR = "/logs/agent/system"
WORK_DIR = "/tmp/deep-swe-agent-work"
REMOTE_HOME = "/tmp/deep-swe-agent-home"
REMOTE_SECRETS = "/tmp/deep-swe-agent-secrets"
REMOTE_CODEX_HOME = f"{REMOTE_SECRETS}/codex"
REMOTE_KIMI_HOME = f"{REMOTE_SECRETS}/kimi"
REMOTE_OPENCODE_DATA = f"{REMOTE_SECRETS}/opencode-data"
REMOTE_OPENCODE_CONFIG = f"{REMOTE_SECRETS}/opencode-config"

SUPPORTED_ADAPTERS = {"claude", "codex", "gemini", "kimi", "opencode"}
_SAFE_RUNTIME_PATH = re.compile(r"^/[0-9A-Za-z._+/-]+$")
_SAFE_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class ExecutionPlanError(ValueError):
    """The launcher-to-agent execution plan does not satisfy schema v1."""


def _record(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExecutionPlanError(f"{path} must be an object")
    return value


def _validate_plan_json(value: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        # Pier's --agent-kwarg parser JSON-decodes object-valued arguments.
        plan = value
    else:
        try:
            plan = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ExecutionPlanError(
                f"execution_plan_json is invalid JSON: {exc}"
            ) from exc
    plan = _record(plan, "execution plan")
    if plan.get("schemaVersion") != 1:
        raise ExecutionPlanError("execution plan schemaVersion must be 1")
    topology = plan.get("topology")
    expected_workflow = "single" if topology == "single" else "review-loop"
    if topology not in {"single", "collab"}:
        raise ExecutionPlanError("execution plan topology must be single or collab")
    if plan.get("workflow") != expected_workflow:
        raise ExecutionPlanError(
            f"{topology} topology requires workflow={expected_workflow}"
        )
    if plan.get("engine") != "direct":
        raise ExecutionPlanError("only engine=direct is supported by this baseline")
    roles = _record(plan.get("roles"), "execution plan roles")
    modifier = _record(roles.get("modifier"), "execution plan roles.modifier")
    reviewer = roles.get("reviewer")
    if topology == "single" and reviewer is not None:
        raise ExecutionPlanError("single topology must not define a reviewer")
    if topology == "collab":
        reviewer = _record(reviewer, "execution plan roles.reviewer")
    for role_name, role in (("modifier", modifier), ("reviewer", reviewer)):
        if role is None:
            continue
        if role.get("adapter") not in SUPPORTED_ADAPTERS:
            raise ExecutionPlanError(f"unsupported {role_name} adapter")
        if not isinstance(role.get("model"), str) or not role["model"]:
            raise ExecutionPlanError(f"{role_name} model must be non-empty")
    budget = _record(plan.get("budget"), "execution plan budget")
    if not isinstance(budget.get("soft_deadline_seconds"), (int, float)):
        raise ExecutionPlanError("budget.soft_deadline_seconds must be numeric")
    runtime = _record(plan.get("runtime"), "execution plan runtime")
    digest = runtime.get("manifestDigest")
    if not isinstance(digest, str) or not _SAFE_DIGEST.fullmatch(digest):
        raise ExecutionPlanError("runtime.manifestDigest must be a SHA-256 digest")
    _record(plan.get("workflowConfig"), "execution plan workflowConfig")
    return plan


class DeepSweAgent(BaseInstalledAgent):
    """Run either single or review-loop through the same cligent runtime."""

    SUPPORTS_ATIF = True

    def __init__(
        self,
        *args: Any,
        execution_plan_json: str | dict[str, Any],
        run_manifest_path: str,
        runtime_path: str = DEFAULT_RUNTIME_DIR,
        **kwargs: Any,
    ) -> None:
        normalized = runtime_path.rstrip("/")
        if (
            normalized in {"", "/"}
            or not _SAFE_RUNTIME_PATH.fullmatch(normalized)
            or "//" in normalized
            or "/../" in f"{normalized}/"
            or "/./" in f"{normalized}/"
        ):
            raise ValueError("runtime_path must be a safe absolute container path")
        self.runtime_path = normalized
        self.execution_plan = _validate_plan_json(execution_plan_json)
        self.run_manifest_path = Path(run_manifest_path).expanduser().resolve()
        digest = self.execution_plan["runtime"]["manifestDigest"]
        super().__init__(*args, version=f"runtime-{digest[:16]}", **kwargs)

    @staticmethod
    def name() -> str:
        return "deep-swe-agent"

    @property
    def adapters_in_use(self) -> set[str]:
        roles = self.execution_plan["roles"]
        return {
            role["adapter"]
            for role in (roles["modifier"], roles.get("reviewer"))
            if isinstance(role, dict)
        }

    def install_spec(self) -> AgentInstallSpec:  # type: ignore[override]
        """The environment mounts a complete immutable runtime; install nothing."""

        return None  # type: ignore[return-value]

    def get_version_command(self) -> str | None:
        return None

    async def setup(self, environment: BaseEnvironment) -> None:
        digest = self.execution_plan["runtime"]["manifestDigest"]
        runtime = shlex.quote(self.runtime_path)
        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
                f"test -x {runtime}/bin/node; "
                f"test -r {runtime}/dist/main.js; "
                f"test -r {runtime}/runtime-manifest.digest; "
                f'test "$(cat {runtime}/runtime-manifest.digest)" = {shlex.quote(digest)}'
            ),
        )

    # --- credential discovery -------------------------------------------

    def _resolve_file(self, env_name: str, default: Path) -> Path | None:
        explicit = self._get_env(env_name)
        if explicit:
            path = Path(explicit).expanduser()
            if not path.is_file():
                raise ValueError(f"{env_name} points to a missing file: {explicit}")
            return path
        return default if default.is_file() else None

    def _resolve_codex_auth(self) -> Path | None:
        return self._resolve_file(
            "CODEX_AUTH_JSON_PATH", Path.home() / ".codex" / "auth.json"
        )

    def _resolve_opencode_auth(self) -> Path | None:
        return self._resolve_file(
            "OPENCODE_AUTH_JSON_PATH",
            Path.home() / ".local" / "share" / "opencode" / "auth.json",
        )

    def _resolve_gemini_auth(self) -> Path | None:
        return self._resolve_file(
            "GEMINI_OAUTH_CREDS_PATH", Path.home() / ".gemini" / "oauth_creds.json"
        )

    def _resolve_kimi_home(self) -> Path | None:
        explicit = self._get_env("KIMI_AUTH_HOME_PATH")
        home = Path(explicit).expanduser() if explicit else Path.home() / ".kimi-code"
        if explicit and not home.is_dir():
            raise ValueError(
                f"KIMI_AUTH_HOME_PATH points to a missing directory: {explicit}"
            )
        if not home.is_dir():
            return None
        credential_candidates = (
            home / "credentials" / "kimi-code.json",
            home / "oauth" / "kimi-code",
        )
        return home if any(path.is_file() for path in credential_candidates) else None

    def _has_any_env(self, names: tuple[str, ...]) -> bool:
        return any(bool(self._get_env(name)) for name in names)

    def _require_credentials(self) -> None:
        missing: list[str] = []
        if "claude" in self.adapters_in_use and not self._has_any_env(
            ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")
        ):
            missing.append("claude login token or ANTHROPIC_API_KEY")
        if "codex" in self.adapters_in_use and self._resolve_codex_auth() is None:
            if not self._has_any_env(("OPENAI_API_KEY", "CODEX_API_KEY")):
                missing.append("~/.codex/auth.json or an OpenAI API key")
        if "kimi" in self.adapters_in_use and self._resolve_kimi_home() is None:
            missing.append("~/.kimi-code login credential")
        if "opencode" in self.adapters_in_use and self._resolve_opencode_auth() is None:
            if not self._has_any_env(
                (
                    "ANTHROPIC_API_KEY",
                    "DEEPSEEK_API_KEY",
                    "GEMINI_API_KEY",
                    "OPENAI_API_KEY",
                    "OPENROUTER_API_KEY",
                    "OPENCODE_API_KEY",
                )
            ):
                missing.append("~/.local/share/opencode/auth.json or provider API key")
        if "gemini" in self.adapters_in_use and self._resolve_gemini_auth() is None:
            if not self._has_any_env(
                ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS")
            ):
                missing.append("~/.gemini/oauth_creds.json or Google API credential")
        if missing:
            raise ValueError("Missing Agent credentials: " + "; ".join(missing))

    async def _upload_owned_file(
        self, environment: BaseEnvironment, source: Path, target: str
    ) -> None:
        await environment.upload_file(source, target)
        if environment.default_user is not None:
            await self.exec_as_root(
                environment,
                command=(
                    f"chown {shlex.quote(str(environment.default_user))} "
                    f"{shlex.quote(target)}"
                ),
            )
        await self.exec_as_agent(
            environment, command=f"chmod 600 {shlex.quote(target)}"
        )

    async def _configure_credentials(
        self, environment: BaseEnvironment, env: dict[str, str]
    ) -> None:
        env.update(
            {
                "HOME": REMOTE_HOME,
                "CODEX_HOME": REMOTE_CODEX_HOME,
                "KIMI_CODE_HOME": REMOTE_KIMI_HOME,
                "XDG_DATA_HOME": REMOTE_OPENCODE_DATA,
                "XDG_CONFIG_HOME": REMOTE_OPENCODE_CONFIG,
                "OPENCODE_CONFIG_DIR": REMOTE_OPENCODE_CONFIG,
                "KIMI_DISABLE_TELEMETRY": "1",
                "KIMI_CODE_NO_AUTO_UPDATE": "1",
                "KIMI_DISABLE_CRON": "1",
            }
        )
        await self.exec_as_agent(
            environment,
            command=(
                "umask 077; "
                f"mkdir -p {REMOTE_HOME}/.gemini {REMOTE_CODEX_HOME} "
                f"{REMOTE_KIMI_HOME}/credentials {REMOTE_KIMI_HOME}/oauth "
                f"{REMOTE_OPENCODE_DATA}/opencode {REMOTE_OPENCODE_CONFIG}"
            ),
            env=env,
        )
        if "codex" in self.adapters_in_use:
            path = self._resolve_codex_auth()
            if path is not None:
                await self._upload_owned_file(
                    environment, path, f"{REMOTE_CODEX_HOME}/auth.json"
                )
        if "opencode" in self.adapters_in_use:
            path = self._resolve_opencode_auth()
            if path is not None:
                await self._upload_owned_file(
                    environment, path, f"{REMOTE_OPENCODE_DATA}/opencode/auth.json"
                )
        if "gemini" in self.adapters_in_use:
            path = self._resolve_gemini_auth()
            if path is not None:
                await self._upload_owned_file(
                    environment, path, f"{REMOTE_HOME}/.gemini/oauth_creds.json"
                )
        if "kimi" in self.adapters_in_use:
            home = self._resolve_kimi_home()
            if home is not None:
                for relative in (
                    Path("credentials/kimi-code.json"),
                    Path("oauth/kimi-code"),
                    Path("device_id"),
                ):
                    source = home / relative
                    if source.is_file():
                        await self._upload_owned_file(
                            environment, source, f"{REMOTE_KIMI_HOME}/{relative}"
                        )

    # --- execution -------------------------------------------------------

    FORWARDED_ENVS: dict[str, tuple[str, ...]] = {
        "claude": ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"),
        "codex": ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL"),
        "kimi": (
            "KIMI_MODEL_API_KEY",
            "KIMI_MODEL_NAME",
            "KIMI_MODEL_BASE_URL",
            "KIMI_MODEL_MAX_CONTEXT_SIZE",
        ),
        "opencode": (
            "ANTHROPIC_API_KEY",
            "DEEPSEEK_API_KEY",
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENROUTER_API_KEY",
            "OPENCODE_API_KEY",
        ),
        "gemini": (
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "GOOGLE_APPLICATION_CREDENTIALS",
            "GOOGLE_CLOUD_PROJECT",
            "GOOGLE_CLOUD_LOCATION",
            "GOOGLE_GENAI_USE_VERTEXAI",
            "GOOGLE_GEMINI_BASE_URL",
            "GEMINI_API_BASE",
        ),
    }

    def _runtime_env(self) -> dict[str, str]:
        base: dict[str, str | None] = {
            "CI": "1",
            "NO_COLOR": "1",
            "GEMINI_CLI_TRUST_WORKSPACE": "true",
        }
        for adapter in sorted(self.adapters_in_use):
            for key in self.FORWARDED_ENVS[adapter]:
                base[key] = self._get_env(key)
        return self.build_process_env(base)

    def _runtime_config(self) -> dict[str, Any]:
        return {
            "executionPlan": self.execution_plan,
            "runManifestDigest": hashlib.sha256(
                self.run_manifest_path.read_bytes()
            ).hexdigest(),
            "repoDir": "/app",
            "instructionPath": f"{OUTPUT_DIR}/instruction.md",
            "outputDir": OUTPUT_DIR,
            "workDir": WORK_DIR,
        }

    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        del context
        self._require_credentials()
        if not self.run_manifest_path.is_file():
            raise ValueError(f"run manifest does not exist: {self.run_manifest_path}")
        env = self._runtime_env()
        try:
            await self._configure_credentials(environment, env)
            with tempfile.TemporaryDirectory(prefix="deep-swe-agent-") as temp_dir:
                staging = Path(temp_dir)
                instruction_path = staging / "instruction.md"
                config_path = staging / "config.json"
                instruction_path.write_text(instruction)
                config_path.write_text(json.dumps(self._runtime_config(), indent=2))
                await self.exec_as_agent(environment, command=f"mkdir -p {OUTPUT_DIR}")
                for source, target in (
                    (instruction_path, f"{OUTPUT_DIR}/instruction.md"),
                    (config_path, f"{OUTPUT_DIR}/config.json"),
                    (self.run_manifest_path, f"{OUTPUT_DIR}/run-manifest.json"),
                ):
                    await environment.upload_file(source, target)
            runtime = shlex.quote(self.runtime_path)
            command = (
                f'export PATH={runtime}/bin:"$PATH"; '
                f"exec {runtime}/bin/node {runtime}/dist/main.js "
                f"--config {OUTPUT_DIR}/config.json"
            )
            await self.exec_as_agent(environment, command=command, env=env)
        finally:
            await self._cleanup_credentials(environment)

    async def _cleanup_credentials(self, environment: BaseEnvironment) -> None:
        try:
            await self.exec_as_agent(
                environment,
                command=f"rm -rf {REMOTE_SECRETS} {REMOTE_HOME}",
            )
        except Exception:
            self.logger.warning(
                "Failed to clean up injected credentials", exc_info=True
            )

    # --- artifacts/context ----------------------------------------------

    def _read_summary(self) -> dict[str, Any] | None:
        path = self.logs_dir / "system" / "summary.json"
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            self.logger.exception("Failed to parse unified summary.json")
            return None
        return value if isinstance(value, dict) else None

    def populate_context_post_run(self, context: AgentContext) -> None:
        summary = self._read_summary()
        result = summary.get("result") if isinstance(summary, dict) else None
        usage = result.get("usage") if isinstance(result, dict) else None
        if isinstance(usage, dict):
            role_usage = [value for value in usage.values() if isinstance(value, dict)]
            context.n_input_tokens = sum(
                int(value.get("inputTokens") or 0) for value in role_usage
            )
            context.n_output_tokens = sum(
                int(value.get("outputTokens") or 0) for value in role_usage
            )
            context.n_agent_steps = sum(
                int(value.get("turns") or 0) for value in role_usage
            )
            costs = [
                float(value["costUsd"])
                for value in role_usage
                if value.get("costUsd") is not None
            ]
            context.cost_usd = sum(costs) if costs else None
        context.metadata = {
            "unified_agent_evaluation": {
                "topology": self.execution_plan.get("topology"),
                "workflow": self.execution_plan.get("workflow"),
                "engine": self.execution_plan.get("engine"),
                "outcome": result.get("outcome") if isinstance(result, dict) else None,
                "degraded_reason": (
                    result.get("degradedReason") if isinstance(result, dict) else None
                ),
                "deliverable": result.get("deliverable")
                if isinstance(result, dict)
                else None,
                "roles": summary.get("roles") if isinstance(summary, dict) else None,
                "usage": usage,
                "runtime": self.execution_plan.get("runtime"),
            }
        }
        system = self.logs_dir / "system"
        instruction_path = system / "instruction.md"
        events = load_events(system / "events.jsonl")
        try:
            trajectory = events_to_trajectory(
                events=events,
                instruction=(
                    instruction_path.read_text(errors="replace")
                    if instruction_path.is_file()
                    else ""
                ),
                summary=summary,
                agent_version=self.version() or "unknown",
            )
        except Exception:
            self.logger.exception("Failed to convert cligent events to ATIF")
            return
        if trajectory is None:
            return
        serialized = format_trajectory_json(trajectory.to_json_dict())
        (self.logs_dir / "trajectory.json").write_text(serialized)
        (system / "trajectory.json").write_text(serialized)
        if trajectory.final_metrics is not None:
            populate_context_from_final_metrics(context, trajectory.final_metrics)
            context.n_agent_steps = len(
                [step for step in trajectory.steps if step.source == "agent"]
            )

    # --- network ---------------------------------------------------------

    @staticmethod
    def _hostname(value: str | None) -> str | None:
        if not value:
            return None
        parsed = urlparse(value if "://" in value else f"https://{value}")
        return parsed.hostname

    def _models_for(self, adapter: str) -> list[str]:
        return [
            role["model"]
            for role in self.execution_plan["roles"].values()
            if isinstance(role, dict)
            and role.get("adapter") == adapter
            and isinstance(role.get("model"), str)
        ]

    def network_allowlist(self) -> NetworkAllowlist:
        domains: set[str] = set()
        if "claude" in self.adapters_in_use:
            domains.add("api.anthropic.com")
        if "codex" in self.adapters_in_use:
            domains.update({"api.openai.com", "auth.openai.com", "chatgpt.com"})
            if host := self._hostname(self._get_env("OPENAI_BASE_URL")):
                domains.add(host)
        if "kimi" in self.adapters_in_use:
            domains.update({"api.kimi.com", "api.moonshot.ai"})
            if host := self._hostname(self._get_env("KIMI_MODEL_BASE_URL")):
                domains.add(host)
        if "opencode" in self.adapters_in_use:
            provider_domains = {
                "anthropic": "api.anthropic.com",
                "deepseek": "api.deepseek.com",
                "google": "generativelanguage.googleapis.com",
                "openai": "api.openai.com",
                "opencode": "opencode.ai",
                "openrouter": "openrouter.ai",
                "xai": "api.x.ai",
            }
            for model in self._models_for("opencode"):
                provider = model.split("/", 1)[0]
                if domain := provider_domains.get(provider):
                    domains.add(domain)
            if host := self._hostname(self._get_env("OPENAI_BASE_URL")):
                domains.add(host)
        if "gemini" in self.adapters_in_use:
            domains.update(
                {
                    "generativelanguage.googleapis.com",
                    "oauth2.googleapis.com",
                    "accounts.google.com",
                }
            )
            for key in ("GOOGLE_GEMINI_BASE_URL", "GEMINI_API_BASE"):
                if host := self._hostname(self._get_env(key)):
                    domains.add(host)
        return NetworkAllowlist(domains=sorted(domains))
