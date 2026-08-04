ARG NODE_IMAGE=node:22-bookworm-slim
FROM ${NODE_IMAGE} AS builder

ARG RUNTIME_MANIFEST_DIGEST=unknown
ARG GEMINI_VERSION=0.50.0
ARG KIMI_VERSION=0.30.0
ARG OPENCODE_VERSION=1.18.10
ARG RIPGREP_VERSION=15.1.0
ARG RIPGREP_AMD64_SHA256=1c9297be4a084eea7ecaedf93eb03d058d6faae29bbc57ecdaf5063921491599
ARG RIPGREP_ARM64_SHA256=2b661c6ef508e902f388e9098d9c4c5aca72c87b55922d94abdba830b4dc885e
ARG OPENCODE_MODELS_SHA256=b3a52ba98bb4b58714734f8bb98c9bc7ffeff3558f915bcc3211cfe5f276728d
ARG TARGETARCH

ENV RUNTIME_DIR=/opt/deep-swe-agent-runtime \
    npm_config_prefix=/opt/deep-swe-agent-runtime \
    npm_config_fetch_retries=1 \
    npm_config_fetch_retry_maxtimeout=15000 \
    npm_config_fetch_timeout=30000 \
    PATH=/opt/deep-swe-agent-runtime/bin:$PATH

WORKDIR ${RUNTIME_DIR}

RUN apt-get update && \
    apt-get install --yes --no-install-recommends ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    case "${TARGETARCH}" in \
      amd64) \
        ripgrep_target=x86_64-unknown-linux-musl; \
        ripgrep_sha256="${RIPGREP_AMD64_SHA256}" \
        ;; \
      arm64) \
        ripgrep_target=aarch64-unknown-linux-gnu; \
        ripgrep_sha256="${RIPGREP_ARM64_SHA256}" \
        ;; \
      *) echo "Unsupported TARGETARCH: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    archive=/tmp/ripgrep.tar.gz; \
    curl --fail --location --retry 3 \
      "https://github.com/BurntSushi/ripgrep/releases/download/${RIPGREP_VERSION}/ripgrep-${RIPGREP_VERSION}-${ripgrep_target}.tar.gz" \
      --output "${archive}"; \
    printf '%s  %s\n' "${ripgrep_sha256}" "${archive}" | sha256sum --check --strict; \
    mkdir -p /tmp/ripgrep "${RUNTIME_DIR}/bin"; \
    tar --extract --gzip --file "${archive}" --directory /tmp/ripgrep \
      --strip-components=1 "ripgrep-${RIPGREP_VERSION}-${ripgrep_target}/rg"; \
    install -m 0555 /tmp/ripgrep/rg "${RUNTIME_DIR}/bin/rg"; \
    "${RUNTIME_DIR}/bin/rg" --version; \
    rm -rf "${archive}" /tmp/ripgrep

COPY wip/docker/agent-runtime/assets/opencode-models.json.gz /tmp/opencode-models.json.gz

RUN set -eux; \
    mkdir -p "${RUNTIME_DIR}/opencode"; \
    gzip --decompress --stdout /tmp/opencode-models.json.gz > \
      "${RUNTIME_DIR}/opencode/models.json"; \
    printf '%s  %s\n' "${OPENCODE_MODELS_SHA256}" \
      "${RUNTIME_DIR}/opencode/models.json" | sha256sum --check --strict; \
    chmod 0444 "${RUNTIME_DIR}/opencode/models.json"; \
    rm /tmp/opencode-models.json.gz

COPY wip/agents/deep_swe_agent/runtime/package.json ./package.json
COPY wip/agents/deep_swe_agent/runtime/package-lock.json ./package-lock.json
COPY wip/agents/deep_swe_agent/runtime/scripts ./scripts

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
