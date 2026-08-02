from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, Mock, patch

from pier.environments.docker.docker import DockerEnvironment

from wip.environments.mini_swe_runtime import SharedRuntimeDockerEnvironment


class SharedRuntimeDockerEnvironmentTests(unittest.TestCase):
    @staticmethod
    def _fake_base_init(
        environment: DockerEnvironment, *args: object, **kwargs: object
    ) -> None:
        environment._mounts_json = [  # type: ignore[attr-defined]
            {"type": "bind", "source": "/host/logs", "target": "/logs/agent"}
        ]

    def test_keeps_default_and_caller_mounts_then_adds_runtime(self) -> None:
        caller_mount = {
            "type": "bind",
            "source": "/host/input",
            "target": "/input",
        }
        with patch.object(DockerEnvironment, "__init__", self._fake_base_init):
            environment = SharedRuntimeDockerEnvironment(
                runtime_image="deep-swe/mini-swe-runtime:2.4.6",
                mounts_json=[caller_mount],
            )

        mounts = environment._mounts_json  # type: ignore[attr-defined]
        self.assertEqual(mounts[0]["target"], "/logs/agent")
        self.assertEqual(mounts[1], caller_mount)
        self.assertEqual(mounts[2]["type"], "image")
        self.assertEqual(mounts[2]["target"], "/opt/mini-swe-runtime")
        self.assertIs(mounts[2]["read_only"], True)

    def test_rejects_runtime_target_collision(self) -> None:
        with patch.object(DockerEnvironment, "__init__", self._fake_base_init):
            with self.assertRaisesRegex(ValueError, "reserved"):
                SharedRuntimeDockerEnvironment(
                    mounts_json=[
                        {
                            "type": "volume",
                            "source": "other",
                            "target": "/opt/mini-swe-runtime",
                        }
                    ]
                )

    def test_rejects_unsafe_image_and_target(self) -> None:
        with self.assertRaises(ValueError):
            SharedRuntimeDockerEnvironment(runtime_image="bad image")
        with self.assertRaises(ValueError):
            SharedRuntimeDockerEnvironment(runtime_target="/")


class SharedRuntimeCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_delete_keeps_task_and_runtime_images(self) -> None:
        environment = object.__new__(SharedRuntimeDockerEnvironment)
        environment._keep_containers = False
        environment.logger = Mock()
        environment.prepare_logs_for_host = AsyncMock()  # type: ignore[method-assign]
        environment._run_docker_compose_command = AsyncMock()  # type: ignore[method-assign]
        environment._cleanup_resources_compose_file = Mock()  # type: ignore[method-assign]

        await environment.stop(delete=True)

        environment._run_docker_compose_command.assert_awaited_once_with(  # type: ignore[attr-defined]
            ["down", "--volumes", "--remove-orphans"]
        )
        command = environment._run_docker_compose_command.await_args.args[0]  # type: ignore[attr-defined]
        self.assertNotIn("--rmi", command)


if __name__ == "__main__":
    unittest.main()
