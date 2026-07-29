from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pier.models.agent.context import AgentContext

from wip.agents.kimi_code_agent import KimiCodeAgent


class KimiCodeAgentTests(unittest.TestCase):
    def make_agent(self, logs_dir: Path, **kwargs: object) -> KimiCodeAgent:
        return KimiCodeAgent(
            logs_dir=logs_dir,
            model_name="kimi-code/k3",
            extra_env={
                "KIMI_MODEL_NAME": "k3",
                "KIMI_MODEL_API_KEY": "test-key",
                "KIMI_MODEL_BASE_URL": "https://api.kimi.com/coding/v1",
            },
            **kwargs,
        )

    def test_install_spec_is_pinned_and_cacheable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = self.make_agent(Path(directory))
            spec = agent.install_spec()
            self.assertEqual(spec.agent_name, "kimi-code")
            self.assertEqual(spec.version, "0.30.0")
            self.assertIn("@moonshot-ai/kimi-code@0.30.0", spec.steps[1].run)
            self.assertNotIn("test-key", json.dumps(spec.model_dump()))
            self.assertEqual(spec.fingerprint(), agent.install_spec().fingerprint())

    def test_invalid_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                self.make_agent(Path(directory), version="0.30.0; echo unsafe")

    def test_allowlist_uses_runtime_api_host(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = self.make_agent(Path(directory))
            self.assertEqual(agent.network_allowlist().domains, ["api.kimi.com"])

    def test_allowlist_keeps_default_api_with_optional_web_service(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = KimiCodeAgent(
                logs_dir=Path(directory),
                model_name="kimi-code/k3",
                extra_env={
                    "KIMI_WEB_SEARCH_BASE_URL": "https://search.example.test/v1"
                },
            )
            self.assertEqual(
                agent.network_allowlist().domains,
                ["api.moonshot.ai", "search.example.test"],
            )

    def test_stream_events_convert_to_atif_and_context(self) -> None:
        events = [
            {
                "role": "meta",
                "type": "session.resume_hint",
                "session_id": "session-123",
            },
            {
                "role": "assistant",
                "content": "I will inspect the files.",
                "tool_calls": [
                    {
                        "type": "function",
                        "id": "call-1",
                        "function": {
                            "name": "Bash",
                            "arguments": json.dumps({"command": "ls"}),
                        },
                    }
                ],
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "cache_read_input_tokens": 30,
                },
            },
            {
                "role": "tool",
                "tool_call_id": "call-1",
                "content": "README.md",
            },
            {
                "role": "assistant",
                "content": "Implemented and committed the change.",
                "usage": {"prompt_tokens": 200, "completion_tokens": 40},
            },
        ]

        with tempfile.TemporaryDirectory() as directory:
            logs_dir = Path(directory)
            agent = self.make_agent(logs_dir)
            (logs_dir / agent.OUTPUT_FILENAME).write_text(
                "\n".join(json.dumps(event) for event in events)
            )

            context = AgentContext()
            agent.populate_context_post_run(context)

            trajectory = json.loads((logs_dir / "trajectory.json").read_text())
            self.assertEqual(trajectory["session_id"], "session-123")
            self.assertEqual(len(trajectory["steps"]), 2)
            first = trajectory["steps"][0]
            self.assertEqual(first["tool_calls"][0]["function_name"], "Bash")
            self.assertEqual(
                first["observation"]["results"][0]["source_call_id"], "call-1"
            )
            self.assertEqual(context.n_input_tokens, 300)
            self.assertEqual(context.n_cache_tokens, 30)
            self.assertEqual(context.n_output_tokens, 60)
            self.assertEqual(context.n_agent_steps, 2)


if __name__ == "__main__":
    unittest.main()
