from __future__ import annotations

import unittest
from unittest.mock import patch

from pier.environments.docker.docker import DockerEnvironment
from wip.environments.agent_runtime import SharedAgentRuntimeDockerEnvironment


class SharedAgentRuntimeDockerEnvironmentTests(unittest.TestCase):
    @staticmethod
    def _fake_base_init(environment, *args, **kwargs) -> None:
        supplied = kwargs.get("mounts_json")
        environment._mounts_json = [] if supplied is None else list(supplied)

    def test_adds_read_only_image_mount(self) -> None:
        with patch.object(DockerEnvironment, "__init__", self._fake_base_init):
            environment = SharedAgentRuntimeDockerEnvironment(
                runtime_image="deep-swe/agent-runtime:abc",
                mounts_json=[{"type": "volume", "source": "a", "target": "/app"}],
            )
        self.assertEqual(
            environment._mounts_json[-1],
            {
                "type": "image",
                "source": "deep-swe/agent-runtime:abc",
                "target": "/opt/deep-swe-agent-runtime",
                "read_only": True,
            },
        )

    def test_rejects_target_collision(self) -> None:
        with patch.object(DockerEnvironment, "__init__", self._fake_base_init):
            with self.assertRaisesRegex(ValueError, "reserved"):
                SharedAgentRuntimeDockerEnvironment(
                    runtime_image="deep-swe/agent-runtime:abc",
                    mounts_json=[
                        {
                            "type": "volume",
                            "source": "bad",
                            "target": "/opt/deep-swe-agent-runtime",
                        }
                    ],
                )

    def test_rejects_unsafe_values(self) -> None:
        with self.assertRaises(ValueError):
            SharedAgentRuntimeDockerEnvironment(runtime_image="bad image")
        with self.assertRaises(ValueError):
            SharedAgentRuntimeDockerEnvironment(
                runtime_image="deep-swe/runtime:x", runtime_target="/"
            )


if __name__ == "__main__":
    unittest.main()
