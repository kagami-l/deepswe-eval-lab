"""Docker environment adapter for a shared mini-swe-agent runtime image."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from pier.environments.docker.docker import DockerEnvironment
from pier.models.trial.config import ServiceVolumeConfig


DEFAULT_RUNTIME_IMAGE = "deep-swe/mini-swe-runtime:2.4.6"
DEFAULT_RUNTIME_TARGET = "/opt/mini-swe-runtime"

_SAFE_IMAGE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._/:@+-]*$")
_SAFE_PATH = re.compile(r"^/[0-9A-Za-z._+/-]+$")


def _validate_runtime_image(value: str) -> str:
    if not _SAFE_IMAGE.fullmatch(value):
        raise ValueError(f"Invalid shared runtime image reference: {value!r}")
    return value


def _validate_runtime_target(value: str) -> str:
    normalized = value.rstrip("/")
    if (
        normalized in {"", "/"}
        or not _SAFE_PATH.fullmatch(normalized)
        or "//" in normalized
        or "/../" in f"{normalized}/"
        or "/./" in f"{normalized}/"
    ):
        raise ValueError(f"Invalid shared runtime target: {value!r}")
    return normalized


class SharedRuntimeDockerEnvironment(DockerEnvironment):
    """Use task images directly and mount one immutable agent runtime.

    Pier normally replaces its log mounts when ``mounts_json`` is supplied.
    This adapter always retains those mounts, then adds caller mounts and the
    runtime image mount.  The runtime image must already exist locally so an
    evaluation cannot unexpectedly stall while pulling it from a registry.
    """

    def __init__(
        self,
        *args: Any,
        runtime_image: str = DEFAULT_RUNTIME_IMAGE,
        runtime_target: str = DEFAULT_RUNTIME_TARGET,
        mounts_json: list[ServiceVolumeConfig] | None = None,
        **kwargs: Any,
    ) -> None:
        self._runtime_image = _validate_runtime_image(runtime_image)
        self._runtime_target = _validate_runtime_target(runtime_target)

        # Let DockerEnvironment create Pier's three standard log mounts first.
        super().__init__(*args, mounts_json=None, **kwargs)
        default_mounts = list(self._mounts_json or [])
        caller_mounts = list(mounts_json or [])

        conflicting = [
            mount
            for mount in [*default_mounts, *caller_mounts]
            if mount.get("target") == self._runtime_target
        ]
        if conflicting:
            raise ValueError(
                f"Mount target {self._runtime_target!r} is reserved for the "
                "shared mini-swe runtime"
            )

        runtime_mount: ServiceVolumeConfig = {
            "type": "image",
            "source": self._runtime_image,
            "target": self._runtime_target,
            "read_only": True,
        }
        self._mounts_json = [*default_mounts, *caller_mounts, runtime_mount]

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
                f"Shared mini-swe runtime image {self._runtime_image!r} is not "
                "available locally. Run wip/scripts/run_mini_swe_eval.sh once "
                "with runtime auto-build enabled, or select --runtime-mode per-task."
            )
        await super().start(force_build=force_build)

    async def stop(self, delete: bool) -> None:
        """Remove trial containers while retaining shared and task images.

        Pier's stock Docker cleanup uses ``docker compose down --rmi all``.
        That is useful for generated agent images, but shared mode deliberately
        runs the task's named prebuilt image directly; removing it would defeat
        reuse across attempts and jobs.
        """

        await self.prepare_logs_for_host()
        if self._keep_containers and delete:
            self.logger.warning(
                "Both `keep_containers` and `--delete` option are set. "
                "keep_containers takes precedence."
            )
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
