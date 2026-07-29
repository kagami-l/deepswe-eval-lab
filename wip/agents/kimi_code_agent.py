"""Pier adapter for MoonshotAI's TypeScript-based Kimi Code CLI.

This adapter intentionally targets ``MoonshotAI/kimi-code`` (the npm package
``@moonshot-ai/kimi-code``), not the legacy Python ``kimi-cli`` package.  The
CLI is installed into Pier's derived agent image through ``install_spec()``, so
Docker can reuse the installation across attempts for the same task.
"""

from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from pier.agents.installed.base import (
    BaseInstalledAgent,
    NonZeroAgentExitCodeError,
    with_prompt_template,
)
from pier.environments.base import BaseEnvironment
from pier.models.agent.context import AgentContext
from pier.models.agent.install import AgentInstallSpec, InstallStep
from pier.models.agent.network import NetworkAllowlist
from pier.models.trajectories import (
    Agent,
    FinalMetrics,
    Metrics,
    Observation,
    ObservationResult,
    Step,
    ToolCall,
    Trajectory,
)
from pier.utils.trajectory_metrics import (
    extra_with_context_metrics,
    peak_context_tokens_from_steps,
    populate_context_from_final_metrics,
)
from pier.utils.trajectory_utils import format_trajectory_json


_SAFE_NPM_VERSION = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._+-]*$")


@dataclass
class _ParsedStep:
    message_parts: list[str] = field(default_factory=list)
    reasoning_parts: list[str] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    observations: list[ObservationResult] = field(default_factory=list)
    metrics: Metrics | None = None
    timestamp: str | None = None


class KimiCodeAgent(BaseInstalledAgent):
    """Run the official Kimi Code CLI as a cached Pier installed agent."""

    DEFAULT_VERSION = "0.30.0"
    OUTPUT_FILENAME = "kimi-code.jsonl"
    STDERR_FILENAME = "kimi-code.stderr.log"

    SUPPORTS_ATIF = True

    def __init__(
        self,
        *args: Any,
        version: str | None = DEFAULT_VERSION,
        **kwargs: Any,
    ) -> None:
        resolved_version = version or self.DEFAULT_VERSION
        if not _SAFE_NPM_VERSION.fullmatch(resolved_version):
            raise ValueError(f"Invalid Kimi Code npm version: {resolved_version!r}")
        super().__init__(*args, version=resolved_version, **kwargs)

    @staticmethod
    def name() -> str:
        return "kimi-code"

    def get_version_command(self) -> str | None:
        return (
            'export NVM_DIR="$HOME/.nvm"; '
            '[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"; '
            "kimi --version"
        )

    def install_spec(self) -> AgentInstallSpec:
        version = self._version or self.DEFAULT_VERSION
        package = shlex.quote(f"@moonshot-ai/kimi-code@{version}")
        root_install = r"""
set -euo pipefail
if command -v curl >/dev/null 2>&1 && command -v git >/dev/null 2>&1 \
    && [ -f /etc/ssl/certs/ca-certificates.crt ]; then
  exit 0
fi
if command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends ca-certificates curl git
  rm -rf /var/lib/apt/lists/*
elif command -v apk >/dev/null 2>&1; then
  apk add --no-cache bash ca-certificates curl git nodejs npm
elif command -v yum >/dev/null 2>&1; then
  yum install -y ca-certificates curl git
else
  echo "Unsupported package manager for Kimi Code installation" >&2
  exit 1
fi
""".strip()
        agent_install = f"""
set -euo pipefail
use_system_node=0
if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
  if node -e 'const [a,b]=process.versions.node.split(".").map(Number); process.exit(a > 22 || (a === 22 && b >= 19) ? 0 : 1)'; then
    npm_prefix="$(npm config get prefix)"
    if [ -w "$npm_prefix" ]; then
      use_system_node=1
    fi
  fi
fi
if [ "$use_system_node" -eq 0 ]; then
  export NVM_DIR="$HOME/.nvm"
  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
  . "$NVM_DIR/nvm.sh"
  nvm install 22.19.0
  nvm alias default 22.19.0
fi
node --version
npm --version
npm install --global {package}
kimi --version
npm cache clean --force
""".strip()
        return AgentInstallSpec(
            agent_name=self.name(),
            version=version,
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
                "package": "@moonshot-ai/kimi-code",
                "interface": "prompt-stream-json",
            },
        )

    @staticmethod
    def _hostname(value: str | None) -> str | None:
        if not value:
            return None
        parsed = urlparse(value if "://" in value else f"https://{value}")
        return parsed.hostname

    def network_allowlist(self) -> NetworkAllowlist:
        domains: set[str] = set()
        model_base_url = self._get_env("KIMI_MODEL_BASE_URL") or self._get_env(
            "KIMI_CODE_BASE_URL"
        )
        if hostname := self._hostname(model_base_url):
            domains.add(hostname)
        else:
            # Default for the built-in `kimi` provider. Explicit Kimi Code
            # credentials normally use https://api.kimi.com/coding/v1.
            domains.add("api.moonshot.ai")

        for key in ("KIMI_WEB_SEARCH_BASE_URL", "KIMI_WEB_FETCH_BASE_URL"):
            if hostname := self._hostname(self._get_env(key)):
                domains.add(hostname)
        return NetworkAllowlist(domains=sorted(domains))

    def _runtime_env(self) -> dict[str, str]:
        env = self.build_process_env(
            {
                "CI": "1",
                "NO_COLOR": "1",
                "KIMI_CODE_HOME": "/logs/agent/kimi-code-home",
                "KIMI_DISABLE_TELEMETRY": "1",
                "KIMI_CODE_NO_AUTO_UPDATE": "1",
                "KIMI_DISABLE_CRON": "1",
            }
        )
        if env.get("KIMI_MODEL_NAME") and not env.get("KIMI_MODEL_API_KEY"):
            raise ValueError(
                "KIMI_MODEL_API_KEY is required when KIMI_MODEL_NAME is configured"
            )
        return env

    def _mcp_payload(self) -> dict[str, Any] | None:
        if not self.mcp_servers:
            return None
        servers: dict[str, dict[str, Any]] = {}
        for server in self.mcp_servers:
            if server.transport == "stdio":
                servers[server.name] = {
                    "command": server.command,
                    "args": server.args,
                }
            else:
                servers[server.name] = {"url": server.url}
        return {"mcpServers": servers}

    async def _configure_runtime(
        self, environment: BaseEnvironment, env: dict[str, str]
    ) -> None:
        commands = ["mkdir -p /logs/agent/kimi-code-home"]
        if self.skills_dir:
            commands.append(
                "mkdir -p /logs/agent/kimi-code-home/skills && "
                f"cp -R {shlex.quote(self.skills_dir)}/. "
                "/logs/agent/kimi-code-home/skills/"
            )
        if payload := self._mcp_payload():
            encoded = shlex.quote(json.dumps(payload, separators=(",", ":")))
            commands.append(
                f"printf '%s' {encoded} > /logs/agent/kimi-code-home/mcp.json"
            )
        await self.exec_as_agent(environment, command=" && ".join(commands), env=env)

    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        del context  # Populated after logs are copied back to the host.
        env = self._runtime_env()
        await self._configure_runtime(environment, env)

        escaped_instruction = shlex.quote(instruction)
        command = (
            'export NVM_DIR="$HOME/.nvm"; '
            '[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"; '
            f"kimi --prompt {escaped_instruction} --output-format stream-json "
            f"2> >(stdbuf -oL tee /logs/agent/{self.STDERR_FILENAME} >&2) "
            f"| stdbuf -oL tee /logs/agent/{self.OUTPUT_FILENAME}"
        )
        await self.exec_as_agent(environment, command=command, env=env)

        if errors := self._error_messages():
            raise NonZeroAgentExitCodeError(
                "Kimi Code emitted error event(s): " + "; ".join(errors[:3])
            )

    def _parse_events(self) -> list[dict[str, Any]]:
        path = self.logs_dir / self.OUTPUT_FILENAME
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
        return events

    def _error_messages(self) -> list[str]:
        messages: list[str] = []
        for event in self._parse_events():
            role = str(event.get("role", "")).lower()
            event_type = str(event.get("type", "")).lower()
            if role != "error" and event_type != "error":
                continue
            value = event.get("message", event.get("content", event.get("error")))
            if isinstance(value, dict):
                value = value.get("message", value)
            messages.append(str(value))
        return messages

    @staticmethod
    def _json_arguments(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                return {"raw": value} if value else {}
            return decoded if isinstance(decoded, dict) else {"value": decoded}
        return {"value": value} if value is not None else {}

    @classmethod
    def _content_parts(
        cls, content: Any
    ) -> tuple[list[str], list[str], list[ToolCall]]:
        text: list[str] = []
        reasoning: list[str] = []
        calls: list[ToolCall] = []
        if isinstance(content, str):
            return ([content] if content else []), reasoning, calls
        if isinstance(content, dict):
            content = [content]
        if not isinstance(content, list):
            return text, reasoning, calls

        for index, part in enumerate(content):
            if isinstance(part, str):
                text.append(part)
                continue
            if not isinstance(part, dict):
                continue
            part_type = str(part.get("type", "")).lower()
            value = part.get("text", part.get("content", ""))
            if part_type in {"think", "thinking", "reasoning"}:
                if value:
                    reasoning.append(str(value))
            elif part_type in {"tool_use", "tool_call"}:
                call_id = str(
                    part.get("id") or part.get("tool_call_id") or f"tool-{index}"
                )
                name = str(part.get("name") or part.get("tool_name") or "unknown")
                arguments = cls._json_arguments(
                    part.get("input", part.get("arguments"))
                )
                calls.append(
                    ToolCall(
                        tool_call_id=call_id,
                        function_name=name,
                        arguments=arguments,
                    )
                )
            elif value:
                text.append(str(value))
        return text, reasoning, calls

    @classmethod
    def _event_tool_calls(cls, event: dict[str, Any]) -> list[ToolCall]:
        parsed: list[ToolCall] = []
        values = event.get("tool_calls")
        if not isinstance(values, list):
            return parsed
        for index, value in enumerate(values):
            if not isinstance(value, dict):
                continue
            function = value.get("function")
            function = function if isinstance(function, dict) else value
            call_id = str(
                value.get("id") or value.get("tool_call_id") or f"tool-{index}"
            )
            name = str(function.get("name") or value.get("name") or "unknown")
            parsed.append(
                ToolCall(
                    tool_call_id=call_id,
                    function_name=name,
                    arguments=cls._json_arguments(
                        function.get("arguments", value.get("arguments"))
                    ),
                )
            )
        return parsed

    @staticmethod
    def _usage(event: dict[str, Any]) -> Metrics | None:
        usage = event.get("usage", event.get("token_usage"))
        if not isinstance(usage, dict):
            return None

        def integer(*keys: str) -> int:
            for key in keys:
                value = usage.get(key)
                if isinstance(value, (int, float)):
                    return int(value)
            return 0

        prompt = integer("input_tokens", "prompt_tokens", "input")
        completion = integer("output_tokens", "completion_tokens", "output")
        cached = integer(
            "cache_read_input_tokens", "cached_tokens", "cache_read", "cache"
        )
        cache_write = integer("cache_creation_input_tokens", "cache_write")
        cost_value = usage.get("cost_usd", usage.get("cost"))
        cost = float(cost_value) if isinstance(cost_value, (int, float)) else None
        if not any((prompt, completion, cached, cache_write, cost)):
            return None
        return Metrics(
            prompt_tokens=prompt or None,
            completion_tokens=completion or None,
            cached_tokens=cached or None,
            cost_usd=cost,
            extra={"cache_write_tokens": cache_write} if cache_write else None,
        )

    @staticmethod
    def _session_id(event: dict[str, Any]) -> str | None:
        for key in ("session_id", "sessionId", "sessionID"):
            value = event.get(key)
            if isinstance(value, str) and value:
                return value
        data = event.get("data")
        if isinstance(data, dict):
            return KimiCodeAgent._session_id(data)
        return None

    @staticmethod
    def _merge_metrics(left: Metrics | None, right: Metrics | None) -> Metrics | None:
        if left is None:
            return right
        if right is None:
            return left
        left_extra = left.extra or {}
        right_extra = right.extra or {}
        cache_write = int(left_extra.get("cache_write_tokens", 0)) + int(
            right_extra.get("cache_write_tokens", 0)
        )
        return Metrics(
            prompt_tokens=(left.prompt_tokens or 0) + (right.prompt_tokens or 0),
            completion_tokens=(left.completion_tokens or 0)
            + (right.completion_tokens or 0),
            cached_tokens=(left.cached_tokens or 0) + (right.cached_tokens or 0),
            cost_usd=(left.cost_usd or 0.0) + (right.cost_usd or 0.0),
            extra={"cache_write_tokens": cache_write} if cache_write else None,
        )

    def _convert_events_to_trajectory(
        self, events: list[dict[str, Any]]
    ) -> Trajectory | None:
        parsed_steps: list[_ParsedStep] = []
        session_id: str | None = None

        for event in events:
            session_id = session_id or self._session_id(event)
            role = str(event.get("role", "")).lower()
            event_type = str(event.get("type", "")).lower()

            if role == "assistant":
                text, reasoning, calls = self._content_parts(event.get("content"))
                calls.extend(self._event_tool_calls(event))
                parsed_steps.append(
                    _ParsedStep(
                        message_parts=text,
                        reasoning_parts=reasoning,
                        tool_calls=calls,
                        metrics=self._usage(event),
                        timestamp=event.get("timestamp")
                        if isinstance(event.get("timestamp"), str)
                        else None,
                    )
                )
                continue

            if role == "tool":
                if not parsed_steps:
                    continue
                call_id = event.get("tool_call_id", event.get("toolCallId"))
                content = event.get("content", event.get("result"))
                parsed_steps[-1].observations.append(
                    ObservationResult(
                        source_call_id=str(call_id) if call_id else None,
                        content=(
                            content
                            if isinstance(content, str)
                            else json.dumps(content, ensure_ascii=False)
                            if content is not None
                            else None
                        ),
                    )
                )
                continue

            if event_type == "usage" or role == "meta":
                metrics = self._usage(event)
                if parsed_steps and metrics:
                    parsed_steps[-1].metrics = self._merge_metrics(
                        parsed_steps[-1].metrics, metrics
                    )

        steps: list[Step] = []
        for parsed in parsed_steps:
            known_call_ids = {call.tool_call_id for call in parsed.tool_calls}
            observations = [
                result
                for result in parsed.observations
                if result.source_call_id is None
                or result.source_call_id in known_call_ids
            ]
            steps.append(
                Step(
                    step_id=len(steps) + 1,
                    timestamp=parsed.timestamp,
                    source="agent",
                    model_name=self.model_name,
                    message="\n".join(parsed.message_parts),
                    reasoning_content=(
                        "\n\n".join(parsed.reasoning_parts)
                        if parsed.reasoning_parts
                        else None
                    ),
                    tool_calls=parsed.tool_calls or None,
                    observation=(
                        Observation(results=observations) if observations else None
                    ),
                    metrics=parsed.metrics,
                    llm_call_count=1,
                )
            )

        if not steps:
            return None

        prompt_tokens = sum(
            step.metrics.prompt_tokens or 0 for step in steps if step.metrics
        )
        completion_tokens = sum(
            step.metrics.completion_tokens or 0 for step in steps if step.metrics
        )
        cached_tokens = sum(
            step.metrics.cached_tokens or 0 for step in steps if step.metrics
        )
        total_cost = sum(step.metrics.cost_usd or 0.0 for step in steps if step.metrics)
        final_metrics = FinalMetrics(
            total_prompt_tokens=prompt_tokens or None,
            total_completion_tokens=completion_tokens or None,
            total_cached_tokens=cached_tokens or None,
            total_cost_usd=total_cost or None,
            total_steps=len(steps),
            extra=extra_with_context_metrics(
                None,
                peak_context_tokens=peak_context_tokens_from_steps(steps),
                summarization_count=None,
            ),
        )
        return Trajectory(
            schema_version="ATIF-v1.7",
            session_id=session_id or "unknown",
            agent=Agent(
                name=self.name(),
                version=self.version() or "unknown",
                model_name=self.model_name,
            ),
            steps=steps,
            final_metrics=final_metrics,
        )

    def populate_context_post_run(self, context: AgentContext) -> None:
        events = self._parse_events()
        if not events:
            return
        try:
            trajectory = self._convert_events_to_trajectory(events)
        except Exception:
            self.logger.exception("Failed to convert Kimi Code events to trajectory")
            return
        if trajectory is None:
            return

        try:
            (self.logs_dir / "trajectory.json").write_text(
                format_trajectory_json(trajectory.to_json_dict())
            )
        except OSError as exc:
            self.logger.debug(f"Failed to write Kimi Code trajectory: {exc}")
            return

        if trajectory.final_metrics:
            populate_context_from_final_metrics(context, trajectory.final_metrics)
            context.n_agent_steps = len(trajectory.steps)
