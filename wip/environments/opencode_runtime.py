"""Docker environment adapter for a shared OpenCode runtime image."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from pier.environments.docker.docker import DockerEnvironment
from pier.models.trial.config import ServiceVolumeConfig


DEFAULT_RUNTIME_IMAGE = "deep-swe/opencode-runtime:1.18.10"
DEFAULT_RUNTIME_TARGET = "/opt/opencode-runtime"
_SAFE_IMAGE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._/:@+-]*$")
_SAFE_PATH = re.compile(r"^/[0-9A-Za-z._+/-]+$")


class SharedOpenCodeRuntimeDockerEnvironment(DockerEnvironment):
    """Run task images directly and mount one immutable OpenCode runtime."""

    def __init__(
        self,
        *args: Any,
        runtime_image: str = DEFAULT_RUNTIME_IMAGE,
        runtime_target: str = DEFAULT_RUNTIME_TARGET,
        mounts_json: list[ServiceVolumeConfig] | None = None,
        **kwargs: Any,
    ) -> None:
        if not _SAFE_IMAGE.fullmatch(runtime_image):
            raise ValueError(f"Invalid shared runtime image: {runtime_image!r}")
        target = runtime_target.rstrip("/")
        if (
            target in {"", "/"}
            or not _SAFE_PATH.fullmatch(target)
            or "//" in target
            or "/../" in f"{target}/"
            or "/./" in f"{target}/"
        ):
            raise ValueError(f"Invalid shared runtime target: {runtime_target!r}")
        self._runtime_image = runtime_image
        self._runtime_target = target
        super().__init__(*args, mounts_json=mounts_json, **kwargs)
        pier_mounts = list(self._mounts_json or [])
        if any(mount.get("target") == target for mount in pier_mounts):
            raise ValueError(f"Mount target {target!r} is reserved for OpenCode runtime")
        self._mounts_json = [
            *pier_mounts,
            {
                "type": "image",
                "source": runtime_image,
                "target": target,
                "read_only": True,
            },
        ]

    async def _runtime_image_is_local(self) -> bool:
        process = await asyncio.create_subprocess_exec(
            "docker",
            "image",
            "inspect",
            self._runtime_image,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return await process.wait() == 0

    async def start(self, force_build: bool) -> None:
        if not await self._runtime_image_is_local():
            raise RuntimeError(
                f"Shared OpenCode runtime image {self._runtime_image!r} is not available locally"
            )
        await super().start(force_build=force_build)

    async def stop(self, delete: bool) -> None:
        await self.prepare_logs_for_host()
        if self._keep_containers:
            await self._run_docker_compose_command(["stop"])
        elif delete:
            await self._run_docker_compose_command(
                ["down", "--volumes", "--remove-orphans"]
            )
        else:
            await self._run_docker_compose_command(["down"])
        self._cleanup_resources_compose_file()
