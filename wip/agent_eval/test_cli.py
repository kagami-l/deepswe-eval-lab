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
    def test_default_job_name_includes_task_list_filename_and_single_task(self) -> None:
        job_name = cli._default_job_name(
            "codex", [TASK], [Path("data/selection/one_task.txt")]
        )
        self.assertRegex(
            job_name,
            rf"^codex-one_task-{TASK}-\d{{8}}-\d{{6}}$",
        )

    def test_default_job_name_includes_task_list_filename_and_task_count(self) -> None:
        job_name = cli._default_job_name(
            "collab",
            ["task-a", "task-b"],
            [Path("data/selection/05 sample confirm.txt")],
            modifier="opencode",
            reviewer="codex",
        )
        self.assertRegex(
            job_name,
            r"^collab-opencode-codex-05-sample-confirm-2-tasks-\d{8}-\d{6}$",
        )

    def test_default_job_name_includes_multiple_task_list_labels(self) -> None:
        job_name = cli._default_job_name(
            "opencode",
            ["task-a", "task-b"],
            [Path("first.txt"), Path("second.tasks.txt")],
        )
        self.assertRegex(
            job_name,
            r"^opencode-first-and-second.tasks-2-tasks-\d{8}-\d{6}$",
        )

    def test_generated_job_name_is_bounded_and_keeps_timestamp(self) -> None:
        job_name = cli._default_job_name(
            "codex", [TASK], [Path(f"{'a' * 300}.txt")]
        )
        self.assertLessEqual(len(job_name), cli.MAX_JOB_NAME_LENGTH)
        self.assertRegex(job_name, r"-[0-9a-f]{8}-\d{8}-\d{6}$")

    def test_explicit_job_name_rejects_path_like_or_overlong_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "may not be"):
            cli._validate_explicit_job_name("..")
        with self.assertRaisesRegex(ValueError, "200 characters"):
            cli._validate_explicit_job_name("a" * 201)

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
        self.assertIn('"eventSilenceTimeoutSeconds": 600.0', rendered)

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

    def test_live_kimi_eval_checks_login_before_preparing_runtime(self) -> None:
        with mock.patch.object(
            cli,
            "require_kimi_auth_home",
            side_effect=ValueError("empty Kimi login"),
        ) as require_auth:
            with mock.patch.object(cli.RuntimeImageManager, "prepare") as prepare:
                with redirect_stderr(io.StringIO()):
                    with self.assertRaisesRegex(SystemExit, "2"):
                        cli.main(
                            [
                                "eval",
                                "--task",
                                TASK,
                                "--agent",
                                "kimi",
                            ]
                        )
        require_auth.assert_called_once()
        prepare.assert_not_called()


if __name__ == "__main__":
    unittest.main()
