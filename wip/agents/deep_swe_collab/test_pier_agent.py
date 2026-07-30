from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pier.models.agent.context import AgentContext

from wip.agents.deep_swe_collab.pier_agent import (
    OUTPUT_DIR,
    RUNTIME_DIR,
    DeepSweCollabAgent,
)

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
