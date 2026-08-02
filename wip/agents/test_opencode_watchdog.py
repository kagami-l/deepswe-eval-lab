from __future__ import annotations

import asyncio
import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace

from pier.models.agent.context import AgentContext
from wip.agents.opencode_watchdog_agent import (
    OpenCodeWatchdogAgent,
    SharedRuntimeOpenCodeWatchdogAgent,
)


RUNNER = Path(__file__).with_name("opencode_watchdog_runner.mjs")


class OpenCodeWatchdogRunnerTests(unittest.TestCase):
    def run_fake(self, source: str, *, terminal_ms: int = 100, terminate_ms: int = 100):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "fake.mjs"
            output = root / "events.jsonl"
            state = root / "watchdog.jsonl"
            fake.write_text(textwrap.dedent(source))
            completed = subprocess.run(
                [
                    "node",
                    str(RUNNER),
                    "--output",
                    str(output),
                    "--state-log",
                    str(state),
                    "--terminal-grace-ms",
                    str(terminal_ms),
                    "--terminate-grace-ms",
                    str(terminate_ms),
                    "--poll-interval-ms",
                    "10",
                    "--",
                    "node",
                    str(fake),
                ],
                text=True,
                capture_output=True,
                timeout=5,
            )
            states = [json.loads(line) for line in state.read_text().splitlines()]
            return completed, states, output.read_text()

    def test_normal_terminal_exit_is_not_signalled(self) -> None:
        completed, states, _ = self.run_fake(
            """
            console.log(JSON.stringify({type:'step_start', sessionID:'main', part:{}}));
            console.log(JSON.stringify({type:'step_finish', sessionID:'main', part:{reason:'stop'}}));
            """,
            terminal_ms=500,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertNotIn("signal_sent", [item["state"] for item in states])

    def test_terminal_hang_is_terminated_and_reported_success(self) -> None:
        completed, states, _ = self.run_fake(
            """
            console.log(JSON.stringify({type:'step_start', sessionID:'main', part:{}}));
            console.log(JSON.stringify({type:'step_finish', sessionID:'main', part:{reason:'stop'}}));
            setInterval(() => {}, 1000);
            """
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("signal_sent", [item["state"] for item in states])

    def test_child_session_stop_does_not_end_main_session(self) -> None:
        completed, states, output = self.run_fake(
            """
            console.log(JSON.stringify({type:'step_start', sessionID:'main', part:{}}));
            console.log(JSON.stringify({type:'step_finish', sessionID:'child', part:{reason:'stop'}}));
            setTimeout(() => {
              console.log(JSON.stringify({type:'text', sessionID:'main', part:{text:'continued'}}));
              process.exit(7);
            }, 200);
            """,
            terminal_ms=50,
        )
        self.assertEqual(completed.returncode, 7)
        self.assertIn("continued", output)
        self.assertNotIn("terminal_grace", [item["state"] for item in states])

    def test_split_terminal_line_is_parsed(self) -> None:
        completed, states, _ = self.run_fake(
            """
            process.stdout.write('{"type":"step_start","sessionID":"main","part":{}}\\n');
            process.stdout.write('{"type":"step_finish","sessionID":"main",');
            setTimeout(() => {
              process.stdout.write('"part":{"reason":"stop"}}\\n');
              setInterval(() => {}, 1000);
            }, 30);
            """
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("terminal_grace", [item["state"] for item in states])

    def test_descendant_is_cleaned_after_main_process_exits(self) -> None:
        completed, states, _ = self.run_fake(
            """
            import { spawn } from 'node:child_process';
            console.log(JSON.stringify({type:'step_start', sessionID:'main', part:{}}));
            console.log(JSON.stringify({type:'step_finish', sessionID:'main', part:{reason:'stop'}}));
            const child = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], {
              stdio: 'inherit'
            });
            child.unref();
            """,
            terminal_ms=500,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("descendant_cleanup", [item["state"] for item in states])
        self.assertIn("signal_sent", [item["state"] for item in states])


class OpenCodeWatchdogAgentTests(unittest.TestCase):
    def test_invalid_watchdog_settings_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                OpenCodeWatchdogAgent(
                    logs_dir=Path(directory),
                    model_name="deepseek/deepseek-v4-pro",
                    terminal_grace_seconds=-1,
                )

    def test_run_uses_runner_without_tee(self) -> None:
        class FakeEnvironment:
            def __init__(self) -> None:
                self.commands = []

            @staticmethod
            def agent_process_env(env):
                return env

            async def exec(self, **kwargs):
                self.commands.append(kwargs["command"])
                return SimpleNamespace(return_code=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as directory:
            agent = OpenCodeWatchdogAgent(
                logs_dir=Path(directory),
                model_name="deepseek/deepseek-v4-pro",
                extra_env={"DEEPSEEK_API_KEY": "test-key"},
            )
            environment = FakeEnvironment()
            asyncio.run(agent.run("do the task", environment, AgentContext()))  # type: ignore[arg-type]
            command = environment.commands[-1]
            self.assertIn("opencode-watchdog.mjs", command)
            self.assertIn("opencode.txt", command)
            self.assertNotIn(" tee ", command)

    def test_shared_runtime_skips_install_and_uses_mounted_binaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = SharedRuntimeOpenCodeWatchdogAgent(
                logs_dir=Path(directory),
                model_name="deepseek/deepseek-v4-pro",
                version="1.18.10",
            )
            self.assertIsNone(agent.install_spec())
            self.assertEqual(
                agent._opencode_executable(),
                "/opt/opencode-runtime/bin/opencode",
            )
            self.assertEqual(agent._shell_prefix(), "")

    def test_runtime_config_forces_no_ask_for_all_builtin_agents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent = OpenCodeWatchdogAgent(
                logs_dir=Path(directory),
                model_name="deepseek/deepseek-v4-pro",
                opencode_config={
                    "permission": {"bash": "ask"},
                    "agent": {"explore": {"permission": {"read": "ask"}}},
                },
            )
            config = agent._build_runtime_config(include_mcp=True)
            policies = [config["permission"]] + [
                config["agent"][name]["permission"]
                for name in ("build", "plan", "general", "explore")
            ]
            for policy in policies:
                self.assertEqual(policy["*"], "allow")
                self.assertEqual(policy["external_directory"], "allow")
                self.assertEqual(policy["question"], "deny")
                self.assertEqual(policy["doom_loop"], "deny")
                self.assertEqual(policy["read"]["*.env"], "deny")
                self.assertNotIn("ask", json.dumps(policy))


if __name__ == "__main__":
    unittest.main()
