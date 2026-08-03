from __future__ import annotations

import json
import tempfile
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace

from wip.agents.deep_swe_agent.atif import events_to_trajectory
from wip.agents.deep_swe_agent.pier_agent import DeepSweAgent, ExecutionPlanError


def plan(*, modifier: str = "codex", reviewer: str | None = None) -> dict:
    def role(name: str) -> dict:
        value = {
            "name": name,
            "adapter": name,
            "model": f"{name}-model",
            "effort": "high",
            "permissions": ("auto" if name in {"kimi", "opencode"} else "bypass"),
        }
        if name == "kimi":
            value.update(
                {
                    "model": "kimi-code/k3",
                    "model_config": {
                        "provider": "managed:kimi-code",
                        "provider_type": "kimi",
                        "base_url": "https://api.kimi.com/coding/v1",
                        "upstream_model": "k3",
                        "max_context_size": 1048576,
                        "capabilities": [
                            "thinking",
                            "always_thinking",
                            "image_in",
                            "video_in",
                            "tool_use",
                        ],
                        "support_efforts": ["low", "high", "max"],
                        "default_effort": "high",
                    },
                }
            )
        return value

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
        self.uploaded_contents: dict[str, str] = {}

    def agent_process_env(self, env):
        return env

    async def exec(self, **kwargs):
        return SimpleNamespace(return_code=0, stdout="", stderr="")

    async def upload_file(self, source: Path, target: str) -> None:
        self.uploads.append((source, target))
        self.uploaded_contents[target] = source.read_text()


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

    async def test_kimi_injection_copies_credentials_and_generates_model_config(
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
            self.assertEqual(
                sources, {"kimi-code.json", "kimi-code", "device_id", "config.toml"}
            )
            self.assertNotIn(
                home / "config.toml", [source for source, _ in environment.uploads]
            )
            generated = environment.uploaded_contents[
                "/tmp/deep-swe-agent-secrets/kimi/config.toml"
            ]
            self.assertEqual(
                generated,
                'default_model = "kimi-code/k3"\n\n'
                '[providers."managed:kimi-code"]\n'
                'type = "kimi"\n'
                'api_key = ""\n'
                'base_url = "https://api.kimi.com/coding/v1"\n\n'
                '[providers."managed:kimi-code".oauth]\n'
                'storage = "file"\n'
                'key = "oauth/kimi-code"\n\n'
                '[models."kimi-code/k3"]\n'
                'provider = "managed:kimi-code"\n'
                'model = "k3"\n'
                "max_context_size = 1048576\n"
                'capabilities = [ "thinking", "always_thinking", "image_in", '
                '"video_in", "tool_use" ]\n'
                'support_efforts = [ "low", "high", "max" ]\n'
                'default_effort = "high"\n',
            )
            self.assertNotIn("personal", generated)
            parsed = tomllib.loads(generated)
            self.assertEqual(parsed["default_model"], "kimi-code/k3")
            self.assertEqual(
                parsed["providers"]["managed:kimi-code"]["oauth"],
                {"storage": "file", "key": "oauth/kimi-code"},
            )
            self.assertEqual(
                parsed["models"]["kimi-code/k3"]["max_context_size"], 1048576
            )

    def test_kimi_login_material_accepts_non_empty_credential_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "credentials").mkdir()
            credentials = home / "credentials" / "kimi-code.json"

            credentials.write_text(json.dumps({"access_token": "access"}))
            self.assertTrue(DeepSweAgent._has_kimi_login_material(home))

            credentials.write_text(json.dumps({"refresh_token": "refresh"}))
            self.assertTrue(DeepSweAgent._has_kimi_login_material(home))

    def test_kimi_login_material_accepts_non_empty_oauth_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "oauth").mkdir()
            (home / "oauth" / "kimi-code").write_text("oauth-token")
            self.assertTrue(DeepSweAgent._has_kimi_login_material(home))

    def test_kimi_login_material_rejects_empty_or_malformed_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "credentials").mkdir()
            (home / "oauth").mkdir()
            credentials = home / "credentials" / "kimi-code.json"
            oauth = home / "oauth" / "kimi-code"

            credentials.write_text(
                json.dumps({"access_token": "", "refresh_token": "   "})
            )
            oauth.write_text("\n")
            self.assertFalse(DeepSweAgent._has_kimi_login_material(home))

            credentials.write_text("not-json")
            self.assertFalse(DeepSweAgent._has_kimi_login_material(home))

    def test_explicit_kimi_home_rejects_empty_login_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "kimi"
            (home / "credentials").mkdir(parents=True)
            (home / "credentials" / "kimi-code.json").write_text(
                json.dumps({"access_token": "", "refresh_token": ""})
            )
            instance = agent(
                root,
                plan(modifier="kimi"),
                extra_env={"KIMI_AUTH_HOME_PATH": str(home)},
            )
            with self.assertRaisesRegex(ValueError, "non-empty Kimi login"):
                instance._require_credentials()

    def test_kimi_plan_requires_model_registration(self) -> None:
        value = plan(modifier="kimi")
        del value["roles"]["modifier"]["model_config"]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ExecutionPlanError, "model_config"):
                agent(Path(directory), value)

    async def test_kimi_config_registers_models_for_both_roles(self) -> None:
        value = plan(modifier="kimi", reviewer="kimi")
        value["roles"]["reviewer"]["model"] = "kimi-code/k3-256k"
        value["roles"]["reviewer"]["model_config"] = {
            "provider": "managed:kimi-code",
            "provider_type": "kimi",
            "base_url": "https://api.kimi.com/coding/v1",
            "upstream_model": "k3",
            "max_context_size": 262144,
            "capabilities": [
                "thinking",
                "always_thinking",
                "image_in",
                "video_in",
                "tool_use",
            ],
            "support_efforts": ["low", "high", "max"],
            "default_effort": "high",
        }
        with tempfile.TemporaryDirectory() as directory:
            instance = agent(Path(directory), value)
            environment = _Environment()
            await instance._configure_kimi_model(environment)
        generated = environment.uploaded_contents[
            "/tmp/deep-swe-agent-secrets/kimi/config.toml"
        ]
        self.assertIn('[models."kimi-code/k3"]', generated)
        self.assertIn('[models."kimi-code/k3-256k"]', generated)

    def test_kimi_plan_rejects_conflicting_model_registrations(self) -> None:
        value = plan(modifier="kimi", reviewer="kimi")
        value["roles"]["reviewer"]["model_config"]["max_context_size"] = 262144
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ExecutionPlanError, "conflicting"):
                agent(Path(directory), value)

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
