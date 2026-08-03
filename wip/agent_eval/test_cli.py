from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from wip.agent_eval import cli
from wip.agent_eval.runtime_image import RuntimeStatus


ROOT = Path(__file__).resolve().parents[2]
TASK = "abs-module-cache-flags"


class CliTests(unittest.TestCase):
    def test_redacts_forwarded_secrets_from_rendered_command(self) -> None:
        values = [
            "pier",
            "run",
            "--ae",
            "OPENAI_API_KEY=secret",
            "--agent-env=TOKEN=also-secret",
        ]
        rendered = cli._redact_args(values)
        self.assertNotIn("secret", " ".join(rendered))
        self.assertIn("OPENAI_API_KEY=<redacted>", rendered)
        self.assertIn("--agent-env=TOKEN=<redacted>", rendered)

    def test_single_dry_run_builds_unified_pier_command(self) -> None:
        status = RuntimeStatus(
            image="deep-swe/agent-runtime:test",
            manifest_digest="digest",
            exists=True,
            matches=True,
            image_id="sha256:test",
            platform="linux/amd64",
        )
        output = io.StringIO()
        with mock.patch.object(cli.RuntimeImageManager, "inspect", return_value=status):
            with redirect_stdout(output):
                code = cli.main(
                    [
                        "eval",
                        "--task",
                        TASK,
                        "--agent",
                        "codex",
                        "--job-name",
                        "test-job",
                        "--dry-run",
                    ]
                )
        self.assertEqual(code, 0)
        rendered = output.getvalue()
        self.assertIn("DeepSweAgent", rendered)
        self.assertIn("SharedAgentRuntimeDockerEnvironment", rendered)
        self.assertIn('"topology": "single"', rendered)

    def test_runtime_dry_run_does_not_build(self) -> None:
        status = RuntimeStatus(
            image="deep-swe/agent-runtime:test",
            manifest_digest="digest",
            exists=False,
            matches=False,
            image_id=None,
            platform=None,
        )
        with mock.patch.object(cli.RuntimeImageManager, "inspect", return_value=status):
            with mock.patch.object(cli.RuntimeImageManager, "prepare") as prepare:
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(cli.main(["runtime", "prepare", "--dry-run"]), 0)
        prepare.assert_not_called()

    def test_single_rejects_explicit_max_reviews(self) -> None:
        with redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(SystemExit, "2"):
                cli.main(
                    [
                        "eval",
                        "--task",
                        TASK,
                        "--agent",
                        "codex",
                        "--max-reviews",
                        "1",
                        "--dry-run",
                    ]
                )


if __name__ == "__main__":
    unittest.main()
