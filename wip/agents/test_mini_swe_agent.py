from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wip.agents.mini_swe_agent import OptimizedMiniSweAgent


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


if __name__ == "__main__":
    unittest.main()
