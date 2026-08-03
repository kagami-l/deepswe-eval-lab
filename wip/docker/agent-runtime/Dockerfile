ARG NODE_IMAGE=node:22-bookworm-slim
FROM ${NODE_IMAGE} AS builder

ARG RUNTIME_MANIFEST_DIGEST=unknown
ARG GEMINI_VERSION=0.50.0
ARG KIMI_VERSION=0.30.0
ARG OPENCODE_VERSION=1.18.10

ENV RUNTIME_DIR=/opt/deep-swe-agent-runtime \
    npm_config_prefix=/opt/deep-swe-agent-runtime \
    npm_config_fetch_retries=1 \
    npm_config_fetch_retry_maxtimeout=15000 \
    npm_config_fetch_timeout=30000 \
    PATH=/opt/deep-swe-agent-runtime/bin:$PATH

WORKDIR ${RUNTIME_DIR}

COPY wip/agents/deep_swe_agent/runtime/package.json ./package.json
COPY wip/agents/deep_swe_agent/runtime/package-lock.json ./package-lock.json

RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    npm ci --no-audit --no-fund --loglevel=verbose

RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    npm install --global --no-audit --no-fund \
      --loglevel=verbose \
      "@google/gemini-cli@${GEMINI_VERSION}" \
      "@moonshot-ai/kimi-code@${KIMI_VERSION}" \
      "opencode-ai@${OPENCODE_VERSION}" && \
    cp "$(command -v node)" "${RUNTIME_DIR}/bin/node" && \
    chmod 0555 "${RUNTIME_DIR}/bin/node" && \
    "${RUNTIME_DIR}/bin/kimi" --help 2>&1 | grep -q acp && \
    "${RUNTIME_DIR}/bin/opencode" --version && \
    "${RUNTIME_DIR}/bin/gemini" --version && \
    cd "${RUNTIME_DIR}" && \
    "${RUNTIME_DIR}/bin/node" --input-type=module \
      -e "await import('@sublang/cligent'); console.log('cligent-ok')"

COPY wip/agents/deep_swe_agent/runtime/tsconfig.json ./tsconfig.json
COPY wip/agents/deep_swe_agent/runtime/src ./src

RUN npm run build && npm prune --omit=dev --no-audit --no-fund

COPY wip/config/runtime-manifest.json ${RUNTIME_DIR}/runtime-manifest.json

RUN printf '%s\n' "${RUNTIME_MANIFEST_DIGEST}" > \
      ${RUNTIME_DIR}/runtime-manifest.digest

FROM scratch
ARG RUNTIME_MANIFEST_DIGEST=unknown
LABEL org.opencontainers.image.title="DeepSWE unified Agent runtime" \
      io.merico.deep-swe.agent-runtime.schema="1" \
      io.merico.deep-swe.agent-runtime.manifest-digest="${RUNTIME_MANIFEST_DIGEST}"
COPY --from=builder /opt/deep-swe-agent-runtime/ /
