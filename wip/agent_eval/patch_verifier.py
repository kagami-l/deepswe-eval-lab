"""Verification seam for post-hoc patch scoring.

``PatchVerifier`` is the narrow interface the scorer depends on. The
production adapter, ``PierPatchVerifier``, reuses Pier's own separate-verifier
path (environment factory + artifact upload + ``Verifier.verify``) so a
rescored patch is graded by exactly the machinery the official eval used.
All knowledge of Pier's private surface is confined to this module and
guarded by explicit contract checks against the pinned ``datacurve-pier``.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


ADAPTER_SCHEMA_VERSION = 1
REQUIRED_PIER_VERSION = "0.3.0"
_MAX_SESSION_ID_LEN = 63


class PierContractError(RuntimeError):
    """The installed Pier does not match the pinned private-surface contract."""


@dataclass(frozen=True)
class VerificationRequest:
    """One frozen patch to grade with the task's official verifier."""

    task_dir: Path
    patch_path: Path
    output_dir: Path  # host dir receiving artifacts/, verifier/, reward.json
    session_key: str  # unique, path/DNS-safe suffix for the container session
    environment_config: dict[str, Any]  # recorded trial config "environment"
    verifier_config: dict[str, Any]  # recorded trial config "verifier"
    timeout_multiplier: float = 1.0
    verifier_timeout_multiplier: float | None = None
    extra_artifacts: tuple[str, ...] = ()


@dataclass
class VerificationRecord:
    """Outcome of a single verification attempt."""

    status: str  # "success" | "timeout" | "error"
    rewards: dict[str, Any] | None = None
    error_type: str | None = None
    error_message: str | None = None
    retryable: bool = False
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class PatchVerifier(Protocol):
    async def verify_patch(self, request: VerificationRequest) -> VerificationRecord: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_signature(callable_obj: Any, required: set[str], label: str) -> None:
    try:
        parameters = set(inspect.signature(callable_obj).parameters)
    except (TypeError, ValueError) as exc:
        raise PierContractError(f"cannot inspect {label}: {exc}") from exc
    missing = required - parameters
    if missing:
        raise PierContractError(f"{label} lost expected parameters: {sorted(missing)}")


def check_pier_contract(*, pier_bin: str | None = "pier") -> dict[str, str]:
    """Fail closed unless the installed Pier matches the pinned contract.

    Returns identity metadata (versions) for manifests.
    """
    try:
        import importlib.metadata as importlib_metadata

        package_version = importlib_metadata.version("datacurve-pier")
    except Exception as exc:  # noqa: BLE001 - any lookup failure is fatal
        raise PierContractError(f"datacurve-pier is not installed: {exc}") from exc
    if package_version != REQUIRED_PIER_VERSION:
        raise PierContractError(
            f"datacurve-pier=={REQUIRED_PIER_VERSION} required, "
            f"found {package_version}"
        )

    cli_version: str | None = None
    if pier_bin and shutil.which(pier_bin):
        result = subprocess.run(
            [pier_bin, "--version"], capture_output=True, text=True, check=False
        )
        output = (result.stdout or "").strip()
        if result.returncode == 0 and output:
            cli_version = output.splitlines()[-1].strip()
            normalized = cli_version.split()[-1].lstrip("v")
            if normalized != package_version:
                raise PierContractError(
                    f"pier CLI reports {cli_version!r} but the Python package "
                    f"is {package_version}; refusing to mix versions"
                )

    from pier.environments.base import BaseEnvironment
    from pier.environments.factory import EnvironmentFactory
    from pier.models.task.verifier_mode import resolve_effective_verifier_env_config
    from pier.models.trial.paths import TrialPaths
    from pier.trial.artifact_handler import ArtifactHandler
    from pier.verifier.verifier import Verifier

    _check_signature(
        Verifier.__init__,
        {
            "task",
            "trial_paths",
            "environment",
            "override_env",
            "skip_tests_upload",
            "verifier_env",
            "step_name",
        },
        "pier Verifier.__init__",
    )
    _check_signature(
        EnvironmentFactory.create_environment_from_config,
        {
            "config",
            "environment_dir",
            "environment_name",
            "session_id",
            "trial_paths",
            "task_env_config",
            "default_user",
        },
        "pier EnvironmentFactory.create_environment_from_config",
    )
    _check_signature(
        resolve_effective_verifier_env_config,
        {"task_cfg", "step_cfg"},
        "pier resolve_effective_verifier_env_config",
    )
    _check_signature(
        ArtifactHandler.upload_artifacts,
        {
            "target_env",
            "artifacts_dir",
            "source_artifacts_dir",
            "target_artifacts_dir",
            "artifacts",
        },
        "pier ArtifactHandler.upload_artifacts",
    )
    for method in ("start", "stop", "empty_dirs", "upload_file"):
        if not hasattr(BaseEnvironment, method):
            raise PierContractError(f"pier BaseEnvironment lacks {method}()")
    for attribute in ("artifacts_dir", "verifier_dir", "reward_json_path"):
        if not isinstance(getattr(TrialPaths, attribute, None), property):
            raise PierContractError(f"pier TrialPaths lacks {attribute}")

    return {
        "pierVersion": package_version,
        "pierCliVersion": cli_version or "",
        "adapterSchemaVersion": str(ADAPTER_SCHEMA_VERSION),
    }


def _session_id(raw: str) -> str:
    safe = "".join(
        char if char.isalnum() or char in "-._" else "_" for char in raw
    )
    if len(safe) <= _MAX_SESSION_ID_LEN:
        return safe
    digest = hashlib.sha1(safe.encode()).hexdigest()[:8]
    suffix = f"__{digest}"
    prefix = safe[: _MAX_SESSION_ID_LEN - len(suffix)].rstrip("-._")
    return f"{prefix}{suffix}"


class PierPatchVerifier:
    """Grade frozen patches through Pier's separate-verifier machinery."""

    def __init__(self, *, pier_bin: str | None = "pier"):
        self.identity = check_pier_contract(pier_bin=pier_bin)

    async def verify_patch(self, request: VerificationRequest) -> VerificationRecord:
        from pier.verifier.verifier import (
            AddTestsDirError,
            DownloadVerifierDirError,
            RewardFileEmptyError,
            RewardFileNotFoundError,
            VerifierOutputParseError,
        )

        started = _now()
        loop = asyncio.get_running_loop()
        start_clock = loop.time()

        def record(status: str, **kwargs: Any) -> VerificationRecord:
            return VerificationRecord(
                status=status,
                started_at=started,
                finished_at=_now(),
                duration_seconds=round(loop.time() - start_clock, 3),
                **kwargs,
            )

        try:
            rewards = await self._verify(request)
        except asyncio.TimeoutError:
            return record(
                "timeout",
                error_type="VerifierTimeoutError",
                error_message="verifier execution exceeded the task timeout",
                retryable=True,
            )
        except (
            AddTestsDirError,
            DownloadVerifierDirError,
            RewardFileNotFoundError,
            RewardFileEmptyError,
            VerifierOutputParseError,
        ) as exc:
            return record(
                "error",
                error_type=type(exc).__name__,
                error_message=str(exc),
                retryable=True,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - infra failures classified retryable
            return record(
                "error",
                error_type=type(exc).__name__,
                error_message=str(exc),
                retryable=True,
            )
        return record("success", rewards=rewards)

    async def _verify(self, request: VerificationRequest) -> dict[str, Any]:
        from pier.environments.factory import EnvironmentFactory
        from pier.models.task.task import Task
        from pier.models.task.verifier_mode import (
            resolve_effective_verifier_env_config,
        )
        from pier.models.trial.config import EnvironmentConfig
        from pier.models.trial.paths import EnvironmentPaths, TrialPaths
        from pier.trial.artifact_handler import ArtifactHandler
        from pier.verifier.verifier import Verifier

        task = Task(task_dir=request.task_dir)
        separate_env_config = resolve_effective_verifier_env_config(task.config, None)
        if separate_env_config is None:
            raise PierContractError(
                f"task {task.name} does not use a separate verifier environment; "
                "post-hoc scoring only supports environment_mode='separate'"
            )

        output_dir = request.output_dir.resolve()
        trial_paths = TrialPaths(trial_dir=output_dir)
        trial_paths.mkdir()
        shutil.copyfile(
            request.patch_path, trial_paths.artifacts_dir / "model.patch"
        )

        logger = logging.getLogger(f"{__name__}.{request.session_key}")
        logger.setLevel(logging.DEBUG)
        log_handler = logging.FileHandler(output_dir / "verify.log")
        logger.addHandler(log_handler)

        verifier_cfg = request.verifier_config or {}
        override_timeout = verifier_cfg.get("override_timeout_sec")
        max_timeout = verifier_cfg.get("max_timeout_sec")
        multiplier = (
            request.verifier_timeout_multiplier
            if request.verifier_timeout_multiplier is not None
            else request.timeout_multiplier
        )
        timeout_seconds = min(
            override_timeout or task.config.verifier.timeout_sec,
            max_timeout or float("inf"),
        ) * multiplier

        env_paths = EnvironmentPaths.for_os(separate_env_config.os)
        mounts = [
            {
                "type": "bind",
                "source": trial_paths.verifier_dir.resolve().as_posix(),
                "target": str(env_paths.verifier_dir),
            }
        ]
        environment = EnvironmentFactory.create_environment_from_config(
            config=EnvironmentConfig.model_validate(request.environment_config),
            environment_dir=task.paths.tests_dir,
            environment_name=task.name,
            session_id=_session_id(request.session_key),
            trial_paths=trial_paths,
            task_env_config=separate_env_config,
            logger=logger,
            mounts_json=mounts,
            agent_install_spec=None,
            network_allowlist=None,
            default_user=task.config.verifier.user,
        )
        try:
            await environment.start(force_build=False)
            await environment.empty_dirs([environment.env_paths.verifier_dir], chmod=True)
            handler = ArtifactHandler(
                artifacts=[*task.config.artifacts, *request.extra_artifacts],
                logger=logger,
            )
            await handler.upload_artifacts(
                environment,
                artifacts_dir=trial_paths.artifacts_dir,
                source_artifacts_dir=environment.env_paths.artifacts_dir,
                target_artifacts_dir=environment.env_paths.artifacts_dir,
                artifacts=None,
            )
            verifier = Verifier(
                task=task,
                trial_paths=trial_paths,
                environment=environment,
                override_env=dict(verifier_cfg.get("env") or {}) or None,
                logger=logger,
                skip_tests_upload=True,
                verifier_env=None,
                step_name=None,
            )
            result = await asyncio.wait_for(verifier.verify(), timeout=timeout_seconds)
        finally:
            try:
                await asyncio.shield(environment.stop(delete=True))
            except Exception as exc:  # noqa: BLE001 - cleanup is best-effort
                logger.debug(f"failed to stop verifier environment: {exc}")
            logger.removeHandler(log_handler)
            log_handler.close()

        rewards = result.rewards
        if not isinstance(rewards, dict) or "reward" not in rewards:
            from pier.verifier.verifier import VerifierOutputParseError

            raise VerifierOutputParseError(
                f"verifier returned no canonical reward: {rewards!r}"
            )
        return dict(rewards)
