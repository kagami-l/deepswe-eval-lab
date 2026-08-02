from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, Mock, patch

from pier.environments.docker.docker import DockerEnvironment

from wip.environments.opencode_runtime import SharedOpenCodeRuntimeDockerEnvironment


class SharedOpenCodeRuntimeTests(unittest.TestCase):
    @staticmethod
    def _fake_base_init(environment, *args, **kwargs) -> None:
        supplied = kwargs.get("mounts_json")
        environment._mounts_json = (
            [{"type": "bind", "source": "/host/logs", "target": "/logs/agent"}]
            if supplied is None
            else list(supplied)
        )

    def test_adds_read_only_image_mount(self) -> None:
        with patch.object(DockerEnvironment, "__init__", self._fake_base_init):
            environment = SharedOpenCodeRuntimeDockerEnvironment()
        mount = environment._mounts_json[-1]
        self.assertEqual(mount["type"], "image")
        self.assertEqual(mount["target"], "/opt/opencode-runtime")
        self.assertIs(mount["read_only"], True)

    def test_preserves_explicit_verifier_mounts(self) -> None:
        verifier = {"type": "bind", "source": "/host/v", "target": "/logs/verifier"}
        with patch.object(DockerEnvironment, "__init__", self._fake_base_init):
            environment = SharedOpenCodeRuntimeDockerEnvironment(mounts_json=[verifier])
        self.assertEqual(environment._mounts_json[0], verifier)
        self.assertNotIn("/logs/agent", {m["target"] for m in environment._mounts_json})

    def test_rejects_unsafe_values_and_collision(self) -> None:
        with self.assertRaises(ValueError):
            SharedOpenCodeRuntimeDockerEnvironment(runtime_image="bad image")
        with self.assertRaises(ValueError):
            SharedOpenCodeRuntimeDockerEnvironment(runtime_target="/")
        with patch.object(DockerEnvironment, "__init__", self._fake_base_init):
            with self.assertRaisesRegex(ValueError, "reserved"):
                SharedOpenCodeRuntimeDockerEnvironment(
                    mounts_json=[{"type": "volume", "target": "/opt/opencode-runtime"}]
                )


class SharedOpenCodeRuntimeCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_delete_does_not_remove_images(self) -> None:
        environment = object.__new__(SharedOpenCodeRuntimeDockerEnvironment)
        environment._keep_containers = False
        environment.logger = Mock()
        environment.prepare_logs_for_host = AsyncMock()
        environment._run_docker_compose_command = AsyncMock()
        environment._cleanup_resources_compose_file = Mock()
        await environment.stop(delete=True)
        command = environment._run_docker_compose_command.await_args.args[0]
        self.assertNotIn("--rmi", command)


if __name__ == "__main__":
    unittest.main()
