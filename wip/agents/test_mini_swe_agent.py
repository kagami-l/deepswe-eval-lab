from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from wip.agents.mini_swe_agent import (
    OptimizedMiniSweAgent,
    SharedRuntimeMiniSweAgent,
)


class OptimizedMiniSweAgentTests(unittest.TestCase):
    def make_agent(self, logs_dir: Path, **kwargs: object) -> OptimizedMiniSweAgent:
        return OptimizedMiniSweAgent(
            logs_dir=logs_dir,
            model_name="deepseek/deepseek-v4-pro",
            version="2.4.6",
            **kwargs,
        )

    def test_install_spec_reuses_tools_and_pins_agent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            spec = self.make_agent(Path(directory)).install_spec()

        self.assertEqual(spec.agent_name, "mini-swe-agent")
        self.assertEqual(spec.version, "2.4.6")
        self.assertIn("command -v curl", spec.steps[0].run)
        self.assertIn("Reusing preinstalled curl", spec.steps[0].run)
        self.assertIn("command -v uv", spec.steps[1].run)
        self.assertIn("Reusing preinstalled $(uv --version)", spec.steps[1].run)
        self.assertIn("mini-swe-agent==2.4.6", spec.steps[1].run)
        self.assertIn("--default-index", spec.steps[1].run)
        self.assertNotIn("raw.githubusercontent.com", spec.steps[1].run)

    def test_index_is_in_install_environment_and_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            logs_dir = Path(directory)
            first = self.make_agent(
                logs_dir,
                pypi_index_url="https://mirror-one.example/simple/",
            ).install_spec()
            second = self.make_agent(
                logs_dir,
                pypi_index_url="https://mirror-two.example/simple",
            ).install_spec()

        self.assertEqual(
            first.steps[1].env["UV_DEFAULT_INDEX"],
            "https://mirror-one.example/simple",
        )
        self.assertNotEqual(first.fingerprint(), second.fingerprint())

    def test_extra_python_packages_use_same_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            spec = self.make_agent(
                Path(directory),
                extra_python_packages=["google-auth==2.0", "example[extra]"],
            ).install_spec()

        self.assertIn('uv pip install --python "$python_bin"', spec.steps[1].run)
        self.assertIn("google-auth==2.0", spec.steps[1].run)
        self.assertIn("'example[extra]'", spec.steps[1].run)

    def test_invalid_urls_and_versions_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            logs_dir = Path(directory)
            with self.assertRaises(ValueError):
                self.make_agent(logs_dir, pypi_index_url="file:///tmp/index")
            with self.assertRaises(ValueError):
                self.make_agent(
                    logs_dir,
                    pypi_index_url="https://user:secret@example.test/simple",
                )
            with self.assertRaises(ValueError):
                self.make_agent(logs_dir, uv_fallback_version="0.9.18; bad")


class SharedRuntimeMiniSweAgentTests(unittest.IsolatedAsyncioTestCase):
    def make_agent(self, logs_dir: Path, **kwargs: object) -> SharedRuntimeMiniSweAgent:
        return SharedRuntimeMiniSweAgent(
            logs_dir=logs_dir,
            model_name="deepseek/deepseek-v4-pro",
            version="2.4.6",
            **kwargs,
        )

    def test_shared_runtime_disables_pier_agent_image_build(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = self.make_agent(Path(directory))

        self.assertIsNone(agent.install_spec())
        self.assertIsNone(agent.get_version_command())

    async def test_setup_only_writes_path_shim_and_verifies_runtime(self) -> None:
        class FakeEnvironment:
            def __init__(self) -> None:
                self.calls: list[dict[str, object]] = []

            def agent_process_env(self, env: dict[str, str]) -> dict[str, str]:
                return env

            async def exec(self, **kwargs: object) -> SimpleNamespace:
                self.calls.append(kwargs)
                return SimpleNamespace(return_code=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as directory:
            agent = self.make_agent(Path(directory))
            environment = FakeEnvironment()
            await agent.setup(environment)  # type: ignore[arg-type]

        self.assertEqual(len(environment.calls), 1)
        command = str(environment.calls[0]["command"])
        self.assertIn("/opt/mini-swe-runtime/bin/mini-swe-agent", command)
        self.assertIn('$HOME/.local/bin/env', command)
        self.assertNotIn("uv tool install", command)

    async def test_extra_packages_require_a_custom_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = self.make_agent(
                Path(directory), extra_python_packages=["google-auth"]
            )
            with self.assertRaisesRegex(ValueError, "extra_python_packages"):
                await agent.setup(SimpleNamespace())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
