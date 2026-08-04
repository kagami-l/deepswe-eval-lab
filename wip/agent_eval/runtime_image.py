"""Content-addressed shared runtime image inspection and preparation."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_RUNTIME_REPOSITORY = "deep-swe/agent-runtime"


class RuntimeImageError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeSpec:
    manifest: dict[str, Any]
    manifest_digest: str
    image: str
    platform: str
    dockerfile: Path
    context_dir: Path


@dataclass(frozen=True)
class RuntimeStatus:
    image: str
    manifest_digest: str
    exists: bool
    matches: bool
    image_id: str | None
    platform: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "image": self.image,
            "manifestDigest": self.manifest_digest,
            "exists": self.exists,
            "matches": self.matches,
            "imageId": self.image_id,
            "platform": self.platform,
        }


def resolve_runtime_spec(
    repo_root: Path,
    *,
    explicit_image: str | None = None,
    platform: str | None = None,
) -> RuntimeSpec:
    manifest_path = repo_root / "wip/config/runtime-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except FileNotFoundError as exc:
        raise RuntimeImageError(f"Runtime manifest not found: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeImageError(f"Invalid runtime manifest: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise RuntimeImageError("runtime manifest must use schema_version 1")
    digest = runtime_input_digest(repo_root, manifest)
    resolved_platform = platform or str(manifest.get("default_platform", ""))
    if resolved_platform not in {"linux/amd64", "linux/arm64"}:
        raise RuntimeImageError(
            f"Runtime platform must be linux/amd64 or linux/arm64: {resolved_platform!r}"
        )
    image = explicit_image or f"{DEFAULT_RUNTIME_REPOSITORY}:{digest[:16]}"
    return RuntimeSpec(
        manifest=manifest,
        manifest_digest=digest,
        image=image,
        platform=resolved_platform,
        dockerfile=repo_root / "wip/docker/agent-runtime/Dockerfile",
        context_dir=repo_root,
    )


def runtime_input_digest(repo_root: Path, manifest: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode())
    candidates = [
        repo_root / "wip/docker/agent-runtime/Dockerfile",
        repo_root / "wip/agents/deep_swe_agent/runtime/package.json",
        repo_root / "wip/agents/deep_swe_agent/runtime/package-lock.json",
        repo_root / "wip/agents/deep_swe_agent/runtime/tsconfig.json",
        repo_root / "wip/docker/agent-runtime/assets/opencode-models.json.gz",
    ]
    source_dir = repo_root / "wip/agents/deep_swe_agent/runtime/src"
    if source_dir.is_dir():
        candidates.extend(sorted(source_dir.glob("**/*")))
    scripts_dir = repo_root / "wip/agents/deep_swe_agent/runtime/scripts"
    if scripts_dir.is_dir():
        candidates.extend(sorted(scripts_dir.glob("**/*")))
    for path in candidates:
        if not path.is_file():
            continue
        digest.update(str(path.relative_to(repo_root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def runtime_build_args(manifest: dict[str, Any]) -> dict[str, str]:
    """Resolve all versioned Docker build inputs from the runtime manifest."""

    try:
        globals_ = manifest["global_packages"]
        assets = manifest["assets"]
        ripgrep = assets["ripgrep"]
        ripgrep_sha = ripgrep["sha256"]
        values = {
            "GEMINI_VERSION": globals_["@google/gemini-cli"],
            "KIMI_VERSION": globals_["@moonshot-ai/kimi-code"],
            "OPENCODE_VERSION": globals_["opencode-ai"],
            "RIPGREP_VERSION": ripgrep["version"],
            "RIPGREP_AMD64_SHA256": ripgrep_sha["amd64"],
            "RIPGREP_ARM64_SHA256": ripgrep_sha["arm64"],
            "OPENCODE_MODELS_SHA256": assets["opencode_models"]["sha256"],
        }
    except (KeyError, TypeError) as exc:
        raise RuntimeImageError(
            f"runtime manifest is missing a required build input: {exc}"
        ) from exc
    if not all(isinstance(value, str) and value for value in values.values()):
        raise RuntimeImageError("runtime manifest build inputs must be non-empty strings")
    return values


class RuntimeImageManager:
    def __init__(self, spec: RuntimeSpec):
        self.spec = spec

    def inspect(self) -> RuntimeStatus:
        process = subprocess.run(
            ["docker", "image", "inspect", self.spec.image],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
        )
        if process.returncode != 0:
            return RuntimeStatus(
                image=self.spec.image,
                manifest_digest=self.spec.manifest_digest,
                exists=False,
                matches=False,
                image_id=None,
                platform=None,
            )
        try:
            raw = json.loads(process.stdout)[0]
            labels = raw.get("Config", {}).get("Labels") or {}
            platform = f"{raw.get('Os')}/{raw.get('Architecture')}"
            image_id = raw.get("Id")
        except (IndexError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeImageError(
                f"Could not parse docker inspect output for {self.spec.image}"
            ) from exc
        matches = (
            labels.get("io.merico.deep-swe.agent-runtime.manifest-digest")
            == self.spec.manifest_digest
            and platform == self.spec.platform
        )
        return RuntimeStatus(
            image=self.spec.image,
            manifest_digest=self.spec.manifest_digest,
            exists=True,
            matches=matches,
            image_id=image_id if isinstance(image_id, str) else None,
            platform=platform,
        )

    def prepare(self, *, rebuild: bool = False) -> RuntimeStatus:
        status = self.inspect()
        if status.exists and status.matches and not rebuild:
            return status
        if status.exists and not status.matches and not rebuild:
            raise RuntimeImageError(
                f"Runtime image {self.spec.image!r} exists but its manifest/platform "
                "does not match; pass --rebuild or choose another image"
            )
        if not self.spec.dockerfile.is_file():
            raise RuntimeImageError(
                f"Runtime Dockerfile not found: {self.spec.dockerfile}"
            )
        build_args = [
            "docker",
            "build",
            "--platform",
            self.spec.platform,
            "--file",
            str(self.spec.dockerfile),
            "--build-arg",
            f"RUNTIME_MANIFEST_DIGEST={self.spec.manifest_digest}",
        ]
        for name, value in runtime_build_args(self.spec.manifest).items():
            build_args.extend(("--build-arg", f"{name}={value}"))
        build_args.extend(("--tag", self.spec.image, str(self.spec.context_dir)))
        process = subprocess.run(build_args, check=False)
        if process.returncode != 0:
            raise RuntimeImageError(
                f"Runtime image build failed with exit status {process.returncode}"
            )
        final = self.inspect()
        if not final.matches:
            raise RuntimeImageError(
                f"Built runtime image {self.spec.image!r} failed manifest validation"
            )
        return final
