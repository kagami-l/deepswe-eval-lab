"""Load and validate version-controlled agent profiles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import AgentProfile


SUPPORTED_ADAPTERS = {"claude", "codex", "gemini", "kimi", "opencode"}
SUPPORTED_STATUSES = {"verified", "unverified"}
SUPPORTED_PERMISSION_MODES = {"auto", "bypass"}
SUPPORTED_EFFORTS = {
    "claude": {"minimal", "low", "medium", "high", "xhigh", "max", "ultracode"},
    "codex": {"minimal", "low", "medium", "high", "xhigh", "max", "ultra"},
    "gemini": {"minimal", "low", "medium", "high", "xhigh", "max"},
    "kimi": {"off", "on"},
    "opencode": {"minimal", "low", "medium", "high", "xhigh", "max"},
}


class ProfileError(ValueError):
    pass


class ProfileRegistry:
    def __init__(self, profiles: dict[str, AgentProfile], *, schema_version: int):
        self._profiles = profiles
        self.schema_version = schema_version

    @classmethod
    def load(cls, path: Path) -> "ProfileRegistry":
        try:
            raw = json.loads(path.read_text())
        except FileNotFoundError as exc:
            raise ProfileError(f"Profile file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise ProfileError(f"Invalid profile JSON in {path}: {exc}") from exc
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            raise ProfileError("agent profiles must use schema_version 1")
        entries = raw.get("profiles")
        if not isinstance(entries, dict) or not entries:
            raise ProfileError(
                "agent profiles must contain a non-empty profiles object"
            )
        profiles = {
            name: _parse_profile(name, value) for name, value in sorted(entries.items())
        }
        return cls(profiles, schema_version=1)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._profiles)

    def resolve(
        self,
        name: str,
        *,
        allow_unverified: bool = False,
        model: str | None = None,
        effort: str | None = None,
    ) -> AgentProfile:
        try:
            profile = self._profiles[name]
        except KeyError as exc:
            raise ProfileError(
                f"Unknown agent profile {name!r}; expected one of: "
                + ", ".join(self.names)
            ) from exc
        if profile.status == "unverified" and not allow_unverified:
            raise ProfileError(
                f"Agent profile {name!r} is unverified; pass --allow-unverified "
                "only for an explicit smoke test"
            )
        if model is not None and not model.strip():
            raise ProfileError(
                f"Agent profile {name!r} model override must be non-empty"
            )
        if effort is not None and not effort.strip():
            raise ProfileError(
                f"Agent profile {name!r} effort override must be non-empty"
            )
        resolved = profile.with_overrides(model=model, effort=effort)
        _validate_effort(resolved.adapter, resolved.effort, name)
        return resolved


def _required_string(raw: dict[str, Any], key: str, profile: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProfileError(f"profiles.{profile}.{key} must be a non-empty string")
    return value.strip()


def _parse_profile(name: str, value: Any) -> AgentProfile:
    if not isinstance(name, str) or not name or not isinstance(value, dict):
        raise ProfileError(f"Invalid profile entry: {name!r}")
    status = _required_string(value, "status", name)
    adapter = _required_string(value, "adapter", name)
    permissions = _required_string(value, "permissions", name)
    if status not in SUPPORTED_STATUSES:
        raise ProfileError(f"profiles.{name}.status must be verified or unverified")
    if adapter not in SUPPORTED_ADAPTERS:
        raise ProfileError(f"profiles.{name}.adapter is unsupported: {adapter}")
    if permissions not in SUPPORTED_PERMISSION_MODES:
        raise ProfileError(f"profiles.{name}.permissions must be auto or bypass")
    effort = value.get("effort")
    if effort is not None and (not isinstance(effort, str) or not effort.strip()):
        raise ProfileError(f"profiles.{name}.effort must be null or a string")
    benchmark_mode = value.get("benchmark_mode", True)
    if not isinstance(benchmark_mode, bool):
        raise ProfileError(f"profiles.{name}.benchmark_mode must be boolean")
    profile = AgentProfile(
        name=name,
        status=status,  # type: ignore[arg-type]
        adapter=adapter,  # type: ignore[arg-type]
        model=_required_string(value, "model", name),
        effort=effort.strip() if isinstance(effort, str) else None,
        auth=_required_string(value, "auth", name),
        permissions=permissions,  # type: ignore[arg-type]
        benchmark_mode=benchmark_mode,
    )
    _validate_effort(profile.adapter, profile.effort, name)
    if profile.adapter == "kimi" and profile.permissions != "auto":
        raise ProfileError("Kimi ACP profile permissions must be auto")
    return profile


def _validate_effort(adapter: str, effort: str | None, profile: str) -> None:
    if effort is None:
        return
    allowed = SUPPORTED_EFFORTS[adapter]
    if effort not in allowed:
        raise ProfileError(
            f"profiles.{profile}.effort {effort!r} is unsupported for {adapter}; "
            f"expected one of: {', '.join(sorted(allowed))}"
        )
