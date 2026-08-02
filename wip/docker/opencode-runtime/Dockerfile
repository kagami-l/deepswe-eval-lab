# syntax=docker/dockerfile:1

ARG NODE_IMAGE=node:22-bookworm-slim
FROM ${NODE_IMAGE} AS builder

ARG OPENCODE_VERSION=1.18.10
ENV npm_config_prefix=/opt/opencode-runtime

RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    npm install --global "opencode-ai@${OPENCODE_VERSION}"; \
    /opt/opencode-runtime/bin/opencode --version; \
    mkdir -p /opt/opencode-runtime/watchdog; \
    cp "$(command -v node)" /opt/opencode-runtime/bin/node

COPY wip/agents/opencode_watchdog_runner.mjs /opt/opencode-runtime/watchdog/opencode-watchdog.mjs

FROM scratch
ARG OPENCODE_VERSION=1.18.10
LABEL org.opencontainers.image.title="DeepSWE shared OpenCode runtime" \
      io.merico.deep-swe.opencode.version="${OPENCODE_VERSION}"
COPY --from=builder /opt/opencode-runtime/ /
