"""Pier OpenCode adapter with terminal-event lifecycle cleanup."""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any

from pier.agents.installed.base import NonZeroAgentExitCodeError, with_prompt_template
from pier.agents.installed.opencode import OpenCode
from pier.environments.base import BaseEnvironment
from pier.models.agent.context import AgentContext


_REMOTE_RUNNER = "/installed-agent/opencode-watchdog.mjs"
_WATCHDOG_LOG = "/logs/agent/opencode-watchdog.jsonl"
_SAFE_RUNTIME_PATH = re.compile(r"^/[0-9A-Za-z._+/-]+$")


def _non_negative_float(name: str, value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a non-negative number") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be a non-negative number")
    return parsed


def _replace_ask(value: Any) -> Any:
    if value == "ask":
        return "deny"
    if isinstance(value, dict):
        return {key: _replace_ask(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_replace_ask(child) for child in value]
    return value


def _no_ask_permissions(value: Any, *, default_action: str = "allow") -> dict[str, Any]:
    if isinstance(value, str):
        permissions: dict[str, Any] = {
            "*": "deny" if value == "ask" else value
        }
    elif isinstance(value, dict):
        permissions = {
            key: _replace_ask(action) for key, action in value.items()
        }
    else:
        permissions = {}

    permissions.setdefault("*", default_action)
    # Headless benchmark runs cannot answer these prompts. External read-only
    # dependencies (for example Go's module cache) are useful task context and
    # the task container is already the isolation boundary.
    permissions.update(
        {
            "external_directory": "allow",
            "doom_loop": "deny",
            "question": "deny",
        }
    )
    read = permissions.get("read")
    if isinstance(read, str):
        read_permissions: dict[str, Any] = {
            "*": "deny" if read == "ask" else read
        }
    elif isinstance(read, dict):
        read_permissions = {
            key: _replace_ask(action) for key, action in read.items()
        }
    else:
        read_permissions = {"*": "allow"}
    read_permissions.update(
        {
            "*.env": "deny",
            "*.env.*": "deny",
            "*.env.example": "allow",
        }
    )
    permissions["read"] = read_permissions
    return permissions


class OpenCodeWatchdogAgent(OpenCode):
    """Stock OpenCode behavior with direct-file logging and a terminal watchdog."""

    def __init__(
        self,
        *args: Any,
        terminal_grace_seconds: Any = 10,
        terminate_grace_seconds: Any = 5,
        poll_interval_ms: Any = 100,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.terminal_grace_seconds = _non_negative_float(
            "terminal_grace_seconds", terminal_grace_seconds
        )
        self.terminate_grace_seconds = _non_negative_float(
            "terminate_grace_seconds", terminate_grace_seconds
        )
        self.poll_interval_ms = _non_negative_float("poll_interval_ms", poll_interval_ms)

    async def setup(self, environment: BaseEnvironment) -> None:
        await super().setup(environment)
        runner = Path(__file__).with_name("opencode_watchdog_runner.mjs")
        await environment.upload_file(runner, _REMOTE_RUNNER)

    def _runner_path(self) -> str:
        return _REMOTE_RUNNER

    def _node_executable(self) -> str:
        return "node"

    def _opencode_executable(self) -> str:
        return "opencode"

    def _shell_prefix(self) -> str:
        return ". ~/.nvm/nvm.sh; "

    def _runtime_env(self) -> dict[str, str]:
        if not self.model_name or "/" not in self.model_name:
            raise ValueError("Model name must be in the format provider/model_name")
        provider, _ = self.model_name.split("/", 1)
        env = self.build_process_env()
        provider_keys = {
            "amazon-bedrock": ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"),
            "anthropic": ("ANTHROPIC_API_KEY",),
            "azure": ("AZURE_RESOURCE_NAME", "AZURE_API_KEY"),
            "deepseek": ("DEEPSEEK_API_KEY",),
            "github-copilot": ("GITHUB_TOKEN",),
            "google": (
                "GEMINI_API_KEY",
                "GOOGLE_GENERATIVE_AI_API_KEY",
                "GOOGLE_APPLICATION_CREDENTIALS",
                "GOOGLE_CLOUD_PROJECT",
                "GOOGLE_CLOUD_LOCATION",
                "GOOGLE_GENAI_USE_VERTEXAI",
                "GOOGLE_API_KEY",
            ),
            "groq": ("GROQ_API_KEY",),
            "huggingface": ("HF_TOKEN",),
            "llama": ("LLAMA_API_KEY",),
            "mistral": ("MISTRAL_API_KEY",),
            "openai": ("OPENAI_API_KEY", "OPENAI_BASE_URL"),
            "opencode": ("OPENCODE_API_KEY",),
            "openrouter": ("OPENROUTER_API_KEY",),
            "xai": ("XAI_API_KEY",),
        }
        for key in provider_keys.get(provider, ()):
            if value := self._get_env(key):
                env[key] = value
        env["OPENCODE_FAKE_VCS"] = "git"
        return env

    def _build_runtime_config(self, *, include_mcp: bool) -> dict[str, Any]:
        """Enforce a deterministic no-prompt policy for parent and subagents."""

        config = super()._build_runtime_config(include_mcp=include_mcp)
        config["permission"] = _no_ask_permissions(config.get("permission"))
        agents = config.get("agent")
        if not isinstance(agents, dict):
            agents = {}
            config["agent"] = agents
        for name in ("build", "plan", "general", "explore"):
            agent = agents.get(name)
            if not isinstance(agent, dict):
                agent = {}
                agents[name] = agent
            agent["permission"] = _no_ask_permissions(agent.get("permission"))
        return config

    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        del context
        env = self._runtime_env()

        if skills_command := self._build_register_skills_command():
            await self.exec_as_agent(environment, command=skills_command, env=env)
        if mcp_command := self._build_register_config_command():
            await self.exec_as_agent(environment, command=mcp_command, env=env)

        cli_flags = self.build_cli_flags()
        opencode_args = [
            self._opencode_executable(),
            f"--model={self.model_name}",
            "run",
            "--format=json",
        ]
        if cli_flags:
            # build_cli_flags is produced from validated Pier CLI kwargs.
            opencode_args.extend(shlex.split(cli_flags))
        opencode_args.extend(
            ["--thinking", "--dangerously-skip-permissions", "--", instruction]
        )

        command = [
            self._node_executable(),
            self._runner_path(),
            "--output",
            "/logs/agent/opencode.txt",
            "--state-log",
            _WATCHDOG_LOG,
            "--terminal-grace-ms",
            str(round(self.terminal_grace_seconds * 1000)),
            "--terminate-grace-ms",
            str(round(self.terminate_grace_seconds * 1000)),
            "--poll-interval-ms",
            str(round(self.poll_interval_ms)),
            "--",
            *opencode_args,
        ]
        shell_command = self._shell_prefix() + " ".join(
            shlex.quote(part) for part in command
        )
        await self.exec_as_agent(environment, command=shell_command, env=env)

        if messages := self._error_messages():
            raise NonZeroAgentExitCodeError(
                "OpenCode emitted error event(s): " + "; ".join(messages[:3])
            )


class SharedRuntimeOpenCodeWatchdogAgent(OpenCodeWatchdogAgent):
    """OpenCode watchdog backed by a read-only shared runtime image mount."""

    def __init__(
        self,
        *args: Any,
        runtime_path: str = "/opt/opencode-runtime",
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
        super().__init__(*args, **kwargs)

    def install_spec(self) -> None:  # type: ignore[override]
        """Use the task image directly; the environment mounts the runtime."""

        return None

    def get_version_command(self) -> str | None:
        return None

    async def setup(self, environment: BaseEnvironment) -> None:
        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
                f"test -x {shlex.quote(self._node_executable())}; "
                f"test -x {shlex.quote(self._opencode_executable())}; "
                f"test -r {shlex.quote(self._runner_path())}; "
                f"{shlex.quote(self._opencode_executable())} --version"
            ),
        )

    def _runner_path(self) -> str:
        return f"{self.runtime_path}/watchdog/opencode-watchdog.mjs"

    def _node_executable(self) -> str:
        return f"{self.runtime_path}/bin/node"

    def _opencode_executable(self) -> str:
        return f"{self.runtime_path}/bin/opencode"

    def _shell_prefix(self) -> str:
        return ""
