from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from wip.agents.deep_swe_agent.atif import events_to_trajectory
from wip.agents.deep_swe_agent.pier_agent import DeepSweAgent, ExecutionPlanError


def plan(*, modifier: str = "codex", reviewer: str | None = None) -> dict:
    def role(name: str) -> dict:
        return {
            "name": name,
            "adapter": name,
            "model": f"{name}-model",
            "effort": "high",
            "permissions": ("auto" if name in {"kimi", "opencode"} else "bypass"),
        }

    topology = "collab" if reviewer else "single"
    return {
        "schemaVersion": 1,
        "topology": topology,
        "workflow": "review-loop" if reviewer else "single",
        "engine": "direct",
        "roles": {
            "modifier": role(modifier),
            "reviewer": role(reviewer) if reviewer else None,
        },
        "budget": {"soft_deadline_seconds": 5100.0},
        "runtime": {"manifestDigest": "a" * 64, "image": "runtime:test"},
        "workflowConfig": {},
    }


def agent(
    logs: Path,
    value: dict,
    *,
    extra_env: dict[str, str] | None = None,
    as_dict: bool = False,
) -> DeepSweAgent:
    return DeepSweAgent(
        logs_dir=logs,
        model_name="test",
        execution_plan_json=value if as_dict else json.dumps(value),
        run_manifest_path=str(logs / "run.json"),
        extra_env=extra_env,
    )


class _Environment:
    default_user = "agent"

    def __init__(self) -> None:
        self.uploads: list[tuple[Path, str]] = []

    def agent_process_env(self, env):
        return env

    async def exec(self, **kwargs):
        return SimpleNamespace(return_code=0, stdout="", stderr="")

    async def upload_file(self, source: Path, target: str) -> None:
        self.uploads.append((source, target))


class PierAgentTests(unittest.IsolatedAsyncioTestCase):
    def test_plan_rejects_single_with_reviewer(self) -> None:
        value = plan()
        value["roles"]["reviewer"] = value["roles"]["modifier"]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ExecutionPlanError, "must not define"):
                agent(Path(directory), value)

    def test_collab_reports_both_adapters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            instance = agent(
                Path(directory),
                plan(modifier="kimi", reviewer="codex"),
                as_dict=True,
            )
            self.assertEqual(instance.adapters_in_use, {"kimi", "codex"})

    def test_opencode_allowlist_uses_only_selected_provider(self) -> None:
        value = plan(modifier="opencode")
        value["roles"]["modifier"]["model"] = "deepseek/deepseek-v4-pro"
        with tempfile.TemporaryDirectory() as directory:
            domains = agent(Path(directory), value).network_allowlist().domains
        self.assertEqual(domains, ["api.deepseek.com"])

    async def test_kimi_injection_copies_credentials_but_not_behavior_config(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "kimi"
            (home / "credentials").mkdir(parents=True)
            (home / "oauth").mkdir()
            (home / "credentials" / "kimi-code.json").write_text("{}")
            (home / "oauth" / "kimi-code").write_text("token")
            (home / "device_id").write_text("device")
            (home / "config.toml").write_text("personal = true")
            instance = agent(
                root,
                plan(modifier="kimi"),
                extra_env={"KIMI_AUTH_HOME_PATH": str(home)},
            )
            environment = _Environment()
            await instance._configure_credentials(environment, {})
            sources = {source.name for source, _ in environment.uploads}
            self.assertEqual(sources, {"kimi-code.json", "kimi-code", "device_id"})
            self.assertNotIn("config.toml", sources)

    async def test_opencode_uses_immutable_runtime_assets_without_user_config(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            instance = agent(Path(directory), plan(modifier="opencode"))
            environment = _Environment()
            env: dict[str, str] = {}
            await instance._configure_credentials(environment, env)
            self.assertEqual(env["OPENCODE_PURE"], "1")
            self.assertEqual(env["OPENCODE_DISABLE_PROJECT_CONFIG"], "1")
            self.assertEqual(env["OPENCODE_DISABLE_MODELS_FETCH"], "1")
            self.assertEqual(
                env["OPENCODE_MODELS_PATH"],
                "/opt/deep-swe-agent-runtime/opencode/models.json",
            )
            self.assertEqual(
                env["OPENCODE_CONFIG_DIR"],
                "/tmp/deep-swe-agent-secrets/opencode-config/opencode",
            )

    def test_atif_combines_roles_in_one_valid_trajectory(self) -> None:
        events = [
            {
                "label": "modify-a1",
                "type": "init",
                "agent": "codex",
                "timestamp": 1_700_000_000_000,
                "sessionId": "modifier-session",
                "payload": {"model": "gpt-test"},
            },
            {
                "label": "modify-a1",
                "type": "tool_use",
                "sessionId": "modifier-session",
                "payload": {
                    "toolUseId": "1",
                    "toolName": "shell",
                    "input": {"cmd": "git diff"},
                },
            },
            {
                "label": "modify-a1",
                "type": "tool_result",
                "sessionId": "modifier-session",
                "payload": {
                    "toolUseId": "1",
                    "toolName": "shell",
                    "status": "success",
                    "output": "ok",
                },
            },
            {
                "label": "modify-a1",
                "type": "done",
                "sessionId": "modifier-session",
                "payload": {
                    "status": "success",
                    "result": "fixed",
                    "usage": {"inputTokens": 10, "outputTokens": 5, "toolUses": 1},
                },
            },
            {
                "label": "review-1-a1",
                "type": "done",
                "agent": "claude-code",
                "sessionId": "reviewer-session",
                "payload": {
                    "status": "success",
                    "result": "approved",
                    "usage": {"inputTokens": 7, "outputTokens": 2, "toolUses": 0},
                },
            },
        ]
        trajectory = events_to_trajectory(
            events=events,
            instruction="fix it",
            summary=None,
            agent_version="test",
        )
        self.assertIsNotNone(trajectory)
        assert trajectory is not None
        self.assertEqual(len(trajectory.steps), 3)
        self.assertEqual(trajectory.steps[1].extra["role"], "modifier")
        self.assertEqual(trajectory.steps[2].extra["role"], "reviewer")
        self.assertEqual(trajectory.final_metrics.total_prompt_tokens, 17)


if __name__ == "__main__":
    unittest.main()
