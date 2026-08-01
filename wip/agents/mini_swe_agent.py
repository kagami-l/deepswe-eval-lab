"""Optimized Pier adapter for running mini-swe-agent in DeepSWE images.

Pier's stock adapter installs build tools and downloads uv unconditionally.
DeepSWE v1.1 images already contain those tools, so this adapter keeps the
stock runtime/trajectory behavior and only replaces the install specification:

* reuse curl, git, build tools, Python, and uv when they already exist;
* install missing OS tools only as a compatibility fallback;
* resolve Python packages through a configurable package index;
* avoid Pier's optional GitHub model-cost-map refresh during image builds.
"""

from __future__ import annotations

import re
import shlex
from typing import Any
from urllib.parse import urlparse

from pier.agents.installed.mini_swe_agent import MiniSweAgent
from pier.models.agent.install import AgentInstallSpec, InstallStep


DEFAULT_PYPI_INDEX_URL = "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple"
DEFAULT_DEBIAN_MIRROR_URL = "https://mirrors.ustc.edu.cn"
DEFAULT_UV_FALLBACK_VERSION = "0.9.18"

_SAFE_VERSION = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._+-]*$")


def _validated_http_url(name: str, value: str) -> str:
    normalized = value.rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{name} must be an absolute HTTP(S) URL: {value!r}")
    if parsed.username or parsed.password:
        raise ValueError(f"{name} must not contain credentials")
    return normalized


class OptimizedMiniSweAgent(MiniSweAgent):
    """MiniSweAgent with a cache-friendly install spec for DeepSWE images."""

    def __init__(
        self,
        *args: Any,
        pypi_index_url: str = DEFAULT_PYPI_INDEX_URL,
        debian_mirror_url: str = DEFAULT_DEBIAN_MIRROR_URL,
        uv_fallback_version: str = DEFAULT_UV_FALLBACK_VERSION,
        **kwargs: Any,
    ) -> None:
        self._pypi_index_url = _validated_http_url("pypi_index_url", pypi_index_url)
        self._debian_mirror_url = _validated_http_url(
            "debian_mirror_url", debian_mirror_url
        )
        if not _SAFE_VERSION.fullmatch(uv_fallback_version):
            raise ValueError(f"Invalid uv fallback version: {uv_fallback_version!r}")
        self._uv_fallback_version = uv_fallback_version
        super().__init__(*args, **kwargs)

    def _root_install_command(self) -> str:
        mirror = shlex.quote(self._debian_mirror_url)
        return rf"""
set -euo pipefail

need_curl=0
need_git=0
need_build=0
command -v curl >/dev/null 2>&1 || need_curl=1
command -v git >/dev/null 2>&1 || need_git=1
if ! command -v gcc >/dev/null 2>&1 || ! command -v make >/dev/null 2>&1; then
  need_build=1
fi

if [ "$need_curl" -eq 0 ] && [ "$need_git" -eq 0 ] && [ "$need_build" -eq 0 ]; then
  echo "Reusing preinstalled curl, git, gcc, and make"
  exit 0
fi

if command -v apt-get >/dev/null 2>&1; then
  debian_mirror={mirror}
  for sources_file in /etc/apt/sources.list /etc/apt/sources.list.d/*.sources; do
    [ -f "$sources_file" ] || continue
    sed -i \
      -e "s|https\?://deb.debian.org/debian-security|$debian_mirror/debian-security|g" \
      -e "s|https\?://deb.debian.org/debian|$debian_mirror/debian|g" \
      "$sources_file"
  done

  packages=()
  [ "$need_curl" -eq 0 ] || packages+=(curl)
  [ "$need_git" -eq 0 ] || packages+=(git)
  [ "$need_build" -eq 0 ] || packages+=(build-essential)
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends "${{packages[@]}}"
  rm -rf /var/lib/apt/lists/*
elif command -v apk >/dev/null 2>&1; then
  apk add --no-cache curl bash build-base git python3 py3-pip
elif command -v yum >/dev/null 2>&1; then
  yum install -y curl git gcc make
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y curl git gcc make
else
  echo "Missing required tools and no supported package manager was found" >&2
  exit 1
fi
""".strip()

    def _agent_install_command(self) -> str:
        version_spec = f"=={self._version}" if self._version else ""
        package = shlex.quote(f"mini-swe-agent{version_spec}")
        index = shlex.quote(self._pypi_index_url)
        uv_version = shlex.quote(self._uv_fallback_version)

        install_extra_packages = ""
        if self._install_python_packages:
            packages = " ".join(
                shlex.quote(package) for package in self._install_python_packages
            )
            install_extra_packages = (
                'uv pip install --python "$python_bin" '
                f"--default-index {index} {packages}\n"
            )

        return f"""
set -euo pipefail

if command -v uv >/dev/null 2>&1; then
  echo "Reusing preinstalled $(uv --version)"
else
  curl -LsSf https://astral.sh/uv/{uv_version}/install.sh | sh
fi

mkdir -p "$HOME/.local/bin"
printf '%s\\n' 'export PATH="$HOME/.local/bin:$PATH"' > "$HOME/.local/bin/env"
export PATH="$HOME/.local/bin:$PATH"

uv tool install {package} --default-index {index}

python_bin="$(head -n 1 "$(command -v mini-swe-agent)" | sed 's/^#!//')"
{install_extra_packages}
mini-swe-agent --help >/dev/null
""".strip()

    def install_spec(self) -> AgentInstallSpec:
        return AgentInstallSpec(
            agent_name=self.name(),
            version=self._version,
            steps=[
                InstallStep(
                    user="root",
                    env={"DEBIAN_FRONTEND": "noninteractive"},
                    run=self._root_install_command(),
                ),
                InstallStep(
                    user="agent",
                    env={
                        "LITELLM_LOCAL_MODEL_COST_MAP": "true",
                        "UV_DEFAULT_INDEX": self._pypi_index_url,
                    },
                    run=self._agent_install_command(),
                ),
            ],
            verification_command=self.get_version_command(),
            metadata={
                "base_adapter": "pier.mini-swe-agent",
                "pypi_index_url": self._pypi_index_url,
                "reuses_preinstalled_tools": True,
                "refreshes_litellm_cost_map": False,
            },
        )
