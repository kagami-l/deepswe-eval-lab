# syntax=docker/dockerfile:1

# Build a self-contained Linux runtime once.  The final scratch image is not a
# runnable task image: Docker mounts its root filesystem read-only at
# /opt/mini-swe-runtime inside each task container.
ARG PYTHON_IMAGE=python:3.12-slim-bookworm
FROM ${PYTHON_IMAGE} AS builder

ARG MINI_SWE_AGENT_VERSION=2.4.6
ARG UV_VERSION=0.9.18
ARG PYPI_INDEX_URL=https://pypi.org/simple

ENV UV_TOOL_DIR=/opt/mini-swe-runtime/tools \
    UV_TOOL_BIN_DIR=/opt/mini-swe-runtime/bin \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_LINK_MODE=copy \
    UV_DEFAULT_INDEX=${PYPI_INDEX_URL} \
    LITELLM_LOCAL_MODEL_COST_MAP=true

RUN set -eux; \
    python -m pip install \
      --disable-pip-version-check \
      --no-cache-dir \
      --index-url "$PYPI_INDEX_URL" \
      "uv==${UV_VERSION}"; \
    mkdir -p /opt/mini-swe-runtime/python; \
    cp -a /usr/local/. /opt/mini-swe-runtime/python/; \
    python_bin=/opt/mini-swe-runtime/python/bin/python; \
    "$python_bin" --version

# Keep uv's download cache outside the final layer. Interrupted builds can
# resume package downloads without bloating the exported runtime image.
RUN --mount=type=cache,target=/tmp/uv-cache,sharing=locked \
    set -eux; \
    python_bin=/opt/mini-swe-runtime/python/bin/python; \
    uv tool install \
      --python "$python_bin" \
      --default-index "$PYPI_INDEX_URL" \
      "mini-swe-agent==${MINI_SWE_AGENT_VERSION}"; \
    /opt/mini-swe-runtime/bin/mini-swe-agent --help >/dev/null

FROM scratch
ARG MINI_SWE_AGENT_VERSION=2.4.6
LABEL org.opencontainers.image.title="DeepSWE shared mini-swe-agent runtime" \
      io.merico.deep-swe.mini-swe-agent.version="${MINI_SWE_AGENT_VERSION}"
COPY --from=builder /opt/mini-swe-runtime/ /
