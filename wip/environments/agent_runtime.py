"""Docker environment that mounts the unified Agent runtime read-only."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from pier.environments.docker.docker import DockerEnvironment
from pier.models.trial.config import ServiceVolumeConfig


DEFAULT_RUNTIME_TARGET = "/opt/deep-swe-agent-runtime"
_SAFE_IMAGE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._/:@+-]*$")
_SAFE_PATH = re.compile(r"^/[0-9A-Za-z._+/-]+$")


def _validate_image(value: str) -> str:
    if not _SAFE_IMAGE.fullmatch(value):
        raise ValueError(f"Invalid shared Agent runtime image: {value!r}")
    return value


def _validate_target(value: str) -> str:
    normalized = value.rstrip("/")
    if (
        normalized in {"", "/"}
        or not _SAFE_PATH.fullmatch(normalized)
        or "//" in normalized
        or "/../" in f"{normalized}/"
        or "/./" in f"{normalized}/"
    ):
        raise ValueError(f"Invalid shared Agent runtime target: {value!r}")
    return normalized


class SharedAgentRuntimeDockerEnvironment(DockerEnvironment):
    """Run the task image directly with one immutable Agent runtime mount."""

    def __init__(
        self,
        *args: Any,
        runtime_image: str,
        runtime_target: str = DEFAULT_RUNTIME_TARGET,
        mounts_json: list[ServiceVolumeConfig] | None = None,
        **kwargs: Any,
    ) -> None:
        self._runtime_image = _validate_image(runtime_image)
        self._runtime_target = _validate_target(runtime_target)
        super().__init__(*args, mounts_json=mounts_json, **kwargs)
        pier_mounts = list(self._mounts_json or [])
        if any(mount.get("target") == self._runtime_target for mount in pier_mounts):
            raise ValueError(
                f"Mount target {self._runtime_target!r} is reserved for the "
                "shared Agent runtime"
            )
        runtime_mount: ServiceVolumeConfig = {
            "type": "image",
            "source": self._runtime_image,
            "target": self._runtime_target,
            "read_only": True,
        }
        self._mounts_json = [*pier_mounts, runtime_mount]

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
                f"Shared Agent runtime image {self._runtime_image!r} is not local; "
                "run `cd wip && uv run python "
                "scripts/run_agent_eval.py runtime prepare` first"
            )
        await super().start(force_build=force_build)

    async def stop(self, delete: bool) -> None:
        """Clean trial containers without deleting task or shared images."""
        await self.prepare_logs_for_host()
        if self._keep_containers:
            try:
                await self._run_docker_compose_command(["stop"])
            except Exception as exc:
                self.logger.warning(f"Docker compose stop failed: {exc}")
        elif delete:
            try:
                await self._run_docker_compose_command(
                    ["down", "--volumes", "--remove-orphans"]
                )
            except Exception as exc:
                self.logger.warning(f"Docker compose down failed: {exc}")
        else:
            try:
                await self._run_docker_compose_command(["down"])
            except Exception as exc:
                self.logger.warning(f"Docker compose down failed: {exc}")
        self._cleanup_resources_compose_file()
