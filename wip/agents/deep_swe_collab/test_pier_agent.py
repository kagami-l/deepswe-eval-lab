from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pier.models.agent.context import AgentContext

from wip.agents.deep_swe_collab.pier_agent import (
    OUTPUT_DIR,
    REMOTE_CODEX_HOME,
    REMOTE_KIMI_HOME,
    REMOTE_SECRETS_DIR,
    RUNTIME_DIR,
    DeepSweCollabAgent,
)


class _FakeExecResult:
    return_code = 0
    stdout = ""
    stderr = ""


class FakeEnvironment:
    """Records exec/upload calls made by the auth-injection helpers."""

    default_user = "agent"

    def __init__(self) -> None:
        self.commands: list[dict[str, object]] = []
        self.uploads: list[tuple[str, str, str]] = []

    def agent_process_env(self, env: dict[str, str] | None) -> dict[str, str]:
        return dict(env or {})

    async def exec(
        self,
        command: str,
        user: str | int | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> _FakeExecResult:
        del cwd, timeout_sec
        self.commands.append({"command": command, "user": user, "env": dict(env or {})})
        return _FakeExecResult()

    async def upload_file(self, source_path: Path | str, target_path: str) -> None:
        self.uploads.append(("file", str(source_path), target_path))

    async def upload_dir(self, source_dir: Path | str, target_dir: str) -> None:
        self.uploads.append(("dir", str(source_dir), target_dir))

    def all_commands(self) -> str:
        return "\n".join(str(entry["command"]) for entry in self.commands)


RUNTIME_PACKAGE_JSON = Path(__file__).parent / "runtime" / "package.json"


def make_agent(logs_dir: Path, **kwargs: object) -> DeepSweCollabAgent:
    extra_env = kwargs.pop(
        "extra_env",
        {"OPENAI_API_KEY": "test-openai", "ANTHROPIC_API_KEY": "test-anthropic"},
    )
    return DeepSweCollabAgent(
        logs_dir=logs_dir,
        model_name="collab/codex+claude",
        extra_env=extra_env,
        **kwargs,
    )


class InstallSpecTests(unittest.TestCase):
    def test_install_spec_is_pinned_and_cacheable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = make_agent(Path(directory))
            spec = agent.install_spec()
            self.assertEqual(spec.agent_name, "deep-swe-collab")
            self.assertEqual(spec.version, "0.16.0")
            self.assertIn('"@sublang/cligent": "0.16.0"', spec.steps[1].run)
            self.assertIn(RUNTIME_DIR, spec.steps[1].run)
            self.assertNotIn("test-openai", json.dumps(spec.model_dump()))
            self.assertEqual(spec.fingerprint(), agent.install_spec().fingerprint())

    def test_kimi_cli_installed_only_when_a_role_uses_kimi(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            default = make_agent(Path(directory)).install_spec()
            self.assertNotIn("@moonshot-ai/kimi-code", default.steps[1].run)

            kimi = make_agent(
                Path(directory),
                reviewer_adapter="kimi",
                extra_env={"OPENAI_API_KEY": "k", "KIMI_MODEL_API_KEY": "k"},
            ).install_spec()
            self.assertIn("@moonshot-ai/kimi-code@0.30.0", kimi.steps[1].run)
            # Guards against the legacy Python kimi-cli shadowing the binary.
            self.assertIn("grep -q acp", kimi.steps[1].run)

    def test_runtime_dependencies_match_host_package_json(self) -> None:
        package = json.loads(RUNTIME_PACKAGE_JSON.read_text())
        with tempfile.TemporaryDirectory() as directory:
            agent = make_agent(Path(directory))
            self.assertEqual(agent.runtime_dependencies(), package["dependencies"])


class ValidationTests(unittest.TestCase):
    def test_unsupported_adapter_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for name in ("gemini", "opencode", "gpt"):
                with self.assertRaises(ValueError):
                    make_agent(Path(directory), modifier_adapter=name)

    def test_unsafe_versions_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                make_agent(Path(directory), cligent_version="0.16.0; rm -rf /")
            with self.assertRaises(ValueError):
                make_agent(Path(directory), kimi_code_version="$(curl evil)")

    def test_string_kwargs_from_ak_are_coerced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = make_agent(
                Path(directory),
                max_reviews="2",
                strict="true",
                total_timeout_seconds="4800",
            )
            self.assertEqual(agent.max_reviews, 2)
            self.assertTrue(agent.strict)
            self.assertEqual(agent.total_timeout_seconds, 4800.0)
            with self.assertRaises(ValueError):
                make_agent(Path(directory), max_reviews="many")

    def test_missing_credentials_fail_fast(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = make_agent(Path(directory), extra_env={"OPENAI_API_KEY": "k"})
            with self.assertRaises(ValueError) as caught:
                agent._require_credentials()
            self.assertIn("claude", str(caught.exception))

            ok = make_agent(Path(directory))
            ok._require_credentials()  # Should not raise.


class CodexAuthTests(unittest.TestCase):
    def test_explicit_auth_json_path_resolves_and_satisfies_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            auth = Path(directory) / "auth.json"
            auth.write_text("{}")
            agent = make_agent(
                Path(directory),
                extra_env={
                    "ANTHROPIC_API_KEY": "k",
                    "CODEX_AUTH_JSON_PATH": str(auth),
                },
            )
            self.assertEqual(agent._resolve_codex_auth_json_path(), auth)
            agent._require_credentials()  # Should not raise.

    def test_missing_auth_json_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = make_agent(
                Path(directory),
                extra_env={
                    "ANTHROPIC_API_KEY": "k",
                    "CODEX_AUTH_JSON_PATH": str(Path(directory) / "nope.json"),
                },
            )
            with self.assertRaises(ValueError):
                agent._resolve_codex_auth_json_path()

    def test_force_auth_json_reads_home_codex_login(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            (home / ".codex").mkdir(parents=True)
            (home / ".codex" / "auth.json").write_text("{}")
            agent = make_agent(
                Path(directory),
                extra_env={"ANTHROPIC_API_KEY": "k", "CODEX_FORCE_AUTH_JSON": "1"},
            )
            with mock.patch(
                "wip.agents.deep_swe_collab.pier_agent.Path.home",
                return_value=home,
            ):
                self.assertEqual(
                    agent._resolve_codex_auth_json_path(),
                    home / ".codex" / "auth.json",
                )

    def test_force_disabled_without_key_fails_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = make_agent(
                Path(directory),
                extra_env={"ANTHROPIC_API_KEY": "k", "CODEX_FORCE_AUTH_JSON": "0"},
            )
            with self.assertRaises(ValueError) as caught:
                agent._require_credentials()
            self.assertIn("codex", str(caught.exception))


class KimiAuthTests(unittest.TestCase):
    @staticmethod
    def make_kimi_home(root: Path) -> Path:
        home = root / "kimi-home"
        (home / "credentials").mkdir(parents=True)
        (home / "credentials" / "kimi-code.json").write_text("{}")
        (home / "config.toml").write_text("theme = 'dark'\n")
        return home

    def test_auth_home_path_resolves_and_satisfies_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = self.make_kimi_home(Path(directory))
            agent = make_agent(
                Path(directory),
                modifier_adapter="kimi",
                extra_env={
                    "ANTHROPIC_API_KEY": "k",
                    "KIMI_AUTH_HOME_PATH": str(home),
                },
            )
            self.assertEqual(agent._resolve_kimi_auth_home(), home)
            agent._require_credentials()  # Should not raise.

    def test_home_without_login_credential_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "empty-home"
            home.mkdir()
            agent = make_agent(
                Path(directory),
                modifier_adapter="kimi",
                extra_env={
                    "ANTHROPIC_API_KEY": "k",
                    "KIMI_AUTH_HOME_PATH": str(home),
                },
            )
            with self.assertRaises(ValueError) as caught:
                agent._resolve_kimi_auth_home()
            self.assertIn("kimi login", str(caught.exception))

    def test_kimi_without_auth_or_key_fails_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = make_agent(
                Path(directory),
                modifier_adapter="kimi",
                extra_env={"ANTHROPIC_API_KEY": "k"},
            )
            with self.assertRaises(ValueError) as caught:
                agent._require_credentials()
            self.assertIn("kimi", str(caught.exception))


class AuthInjectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_codex_auth_json_is_uploaded_and_linked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            auth = Path(directory) / "auth.json"
            auth.write_text("{}")
            agent = make_agent(
                Path(directory),
                extra_env={
                    "ANTHROPIC_API_KEY": "k",
                    "CODEX_AUTH_JSON_PATH": str(auth),
                },
            )
            environment = FakeEnvironment()
            env: dict[str, str] = {}
            await agent._configure_codex_auth(environment, env)

            self.assertEqual(env["CODEX_HOME"], REMOTE_CODEX_HOME)
            self.assertIn(
                ("file", str(auth), f"{REMOTE_SECRETS_DIR}/codex-auth.json"),
                environment.uploads,
            )
            commands = environment.all_commands()
            self.assertIn("ln -sf", commands)
            self.assertIn('"$CODEX_HOME/auth.json"', commands)
            chowns = [c for c in environment.commands if c["user"] == "root"]
            self.assertTrue(any("chown" in str(c["command"]) for c in chowns))

    async def test_codex_api_key_mode_materializes_without_leaking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = make_agent(
                Path(directory),
                extra_env={
                    "ANTHROPIC_API_KEY": "k",
                    "OPENAI_API_KEY": "sk-super-secret",
                },
            )
            environment = FakeEnvironment()
            env: dict[str, str] = {}
            await agent._configure_codex_auth(environment, env)

            self.assertEqual(environment.uploads, [])
            commands = environment.all_commands()
            self.assertIn("${OPENAI_API_KEY}", commands)
            self.assertNotIn("sk-super-secret", commands)
            self.assertIn('"$CODEX_HOME/auth.json"', commands)

    async def test_kimi_home_is_uploaded_with_owner_only_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = KimiAuthTests.make_kimi_home(Path(directory))
            agent = make_agent(
                Path(directory),
                reviewer_adapter="kimi",
                extra_env={
                    "OPENAI_API_KEY": "k",
                    "KIMI_AUTH_HOME_PATH": str(home),
                },
            )
            environment = FakeEnvironment()
            env: dict[str, str] = {}
            await agent._configure_kimi_auth(environment, env)

            self.assertEqual(env["KIMI_CODE_HOME"], REMOTE_KIMI_HOME)
            self.assertIn(
                ("dir", str(home / "credentials"), f"{REMOTE_KIMI_HOME}/credentials"),
                environment.uploads,
            )
            self.assertIn(
                ("file", str(home / "config.toml"), f"{REMOTE_KIMI_HOME}/config.toml"),
                environment.uploads,
            )
            commands = environment.all_commands()
            self.assertIn("chmod -R go-rwx", commands)

    async def test_kimi_provider_config_mode_skips_upload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = make_agent(
                Path(directory),
                reviewer_adapter="kimi",
                extra_env={"OPENAI_API_KEY": "k", "KIMI_MODEL_API_KEY": "mk"},
            )
            environment = FakeEnvironment()
            env: dict[str, str] = {}
            await agent._configure_kimi_auth(environment, env)

            self.assertEqual(environment.uploads, [])
            self.assertEqual(env["KIMI_CODE_HOME"], REMOTE_KIMI_HOME)
            self.assertEqual(env["KIMI_DISABLE_TELEMETRY"], "1")


class RuntimeConfigTests(unittest.TestCase):
    def test_config_matches_runtime_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = make_agent(
                Path(directory),
                modifier_model="gpt-5.3-codex",
                reviewer_model="claude-opus-5",
                max_reviews="3",
            )
            config = agent.build_runtime_config()
            self.assertEqual(config["repoDir"], "/app")
            self.assertEqual(config["outputDir"], OUTPUT_DIR)
            self.assertEqual(config["modifier"]["adapter"], "codex")
            self.assertEqual(config["modifier"]["model"], "gpt-5.3-codex")
            self.assertEqual(config["reviewer"]["adapter"], "claude")
            self.assertEqual(config["maxReviews"], 3)
            self.assertFalse(config["strict"])
            self.assertEqual(config["instructionPath"], f"{OUTPUT_DIR}/instruction.md")


class ContextTests(unittest.TestCase):
    def make_summary(self) -> dict[str, object]:
        return {
            "engine": "direct",
            "modifier": {"role": "modifier", "adapter": "codex"},
            "reviewer": {"role": "reviewer", "adapter": "claude"},
            "result": {
                "outcome": "approved",
                "degradedReason": None,
                "deliverable": True,
                "reviewCount": 1,
                "revisionCount": 0,
                "noChangeRevision": False,
                "findingsTotal": 2,
                "blockingFindingsTotal": 0,
                "checkpoints": [
                    {"label": "collab: initial implementation", "commit": "abc"}
                ],
                "protocolViolations": [],
                "usage": {
                    "modifier": {
                        "inputTokens": 1000,
                        "outputTokens": 400,
                        "toolUses": 12,
                        "costUsd": 0.5,
                        "turns": 1,
                        "wallMs": 60000,
                    },
                    "reviewer": {
                        "inputTokens": 600,
                        "outputTokens": 100,
                        "toolUses": 4,
                        "costUsd": None,
                        "turns": 1,
                        "wallMs": 30000,
                    },
                },
            },
        }

    def test_populate_context_from_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            logs_dir = Path(directory)
            agent = make_agent(logs_dir)
            collab_dir = logs_dir / "collab"
            collab_dir.mkdir()
            (collab_dir / "summary.json").write_text(json.dumps(self.make_summary()))

            context = AgentContext()
            agent.populate_context_post_run(context)
            self.assertEqual(context.n_input_tokens, 1600)
            self.assertEqual(context.n_output_tokens, 500)
            self.assertEqual(context.n_agent_steps, 2)
            self.assertEqual(context.cost_usd, 0.5)
            assert context.metadata is not None
            collab_meta = context.metadata["collab"]
            self.assertEqual(collab_meta["outcome"], "approved")
            self.assertEqual(collab_meta["review_count"], 1)

    def test_missing_summary_leaves_context_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = make_agent(Path(directory))
            context = AgentContext()
            agent.populate_context_post_run(context)
            self.assertTrue(context.is_empty())


class NetworkTests(unittest.TestCase):
    def test_allowlist_covers_roles_in_use(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = make_agent(Path(directory))
            domains = agent.network_allowlist().domains
            self.assertIn("api.anthropic.com", domains)
            self.assertIn("api.openai.com", domains)
            self.assertIn("registry.npmjs.org", domains)
            self.assertNotIn("api.kimi.com", domains)

    def test_allowlist_uses_kimi_base_url_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = make_agent(
                Path(directory),
                modifier_adapter="kimi",
                extra_env={
                    "ANTHROPIC_API_KEY": "k",
                    "KIMI_MODEL_API_KEY": "k",
                    "KIMI_MODEL_BASE_URL": "https://gateway.example.test/v1",
                },
            )
            domains = agent.network_allowlist().domains
            self.assertIn("gateway.example.test", domains)
            self.assertIn("api.moonshot.ai", domains)


if __name__ == "__main__":
    unittest.main()
