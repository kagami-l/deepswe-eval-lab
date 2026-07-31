# DeepSWE Collab Auth 注入实现 Review

- 评审时间：2026-07-30 18:07:18（Asia/Shanghai）
- 评审提交：`b70987e`（`Add host auth injection for codex and kimi adapters`）
- 评审范围：该提交新增的 Codex、Claude、Kimi 认证配置和宿主凭据注入链路

## 结论

Codex 的 `CODEX_FORCE_AUTH_JSON=1` 主路径已经可以进入 smoke test；Claude 通过 `--ae CLAUDE_CODE_OAUTH_TOKEN=...` 的路径也合理。

开始批量评测前应先修复宿主环境变量传播问题。Kimi 暂不建议批量运行，需先解决 ACP provider-key 误判和 OAuth clone/refresh 生命周期问题。

## Findings

### [P1] 宿主 `export` 的 API key/OAuth token 只通过校验，没有注入容器

位置：

- `wip/agents/deep_swe_collab/pier_agent.py:474`
- `wip/agents/deep_swe_collab/README.md:41`

`_runtime_env()` 仅包含 `extra_env` 和 Pier resolved env，不包含任意 `os.environ`；但 `_require_credentials()` 使用的 `_has_env()` 会检查宿主环境。

实际验证结果：

```text
require_credentials=passed
OPENAI_API_KEY_in_runtime_env=False
ANTHROPIC_API_KEY_in_runtime_env=False
```

因此以下情况会通过 fail-fast 校验，但在实际调用时认证失败：

- 仅 `export OPENAI_API_KEY=...`
- 仅 `export CODEX_API_KEY=...`
- 仅 `export ANTHROPIC_API_KEY=...`
- 仅 `export CLAUDE_CODE_OAUTH_TOKEN=...`
- 仅 export Kimi provider 变量

Codex 的 `OPENAI_API_KEY` 分支还会生成一个空 key 的 `auth.json`。

这和 README 中“宿主 export 和 `--ae` 均可”的承诺不一致。

建议 `_runtime_env()` 从 `_get_env()` 显式复制一份受控 allowlist，而不是复制全部宿主环境。另一种选择是修改文档和错误信息，规定 token/API key 必须通过 `--ae`；`CODEX_FORCE_AUTH_JSON` 等仅供宿主侧控制的变量仍可直接 export。

### [P1] `KIMI_MODEL_API_KEY` 被当成充分凭据，但当前 cligent 的 Kimi ACP 明确要求 OAuth

位置：`wip/agents/deep_swe_collab/pier_agent.py:434`

当前校验接受仅有 `KIMI_MODEL_API_KEY` 的配置，新增测试也把这个分支视为成功。

但当前固定的 cligent 0.16.0 明确说明：Kimi Code ACP 要求 `kimi login` 生成的 OAuth credential。项目 README 自己也承认 provider-only 配置在 ACP 下可能不足。

这使 fail-fast 校验失效：配置阶段成功，首个真实 Kimi turn 才失败。

建议在当前版本中要求 `_resolve_kimi_auth_home()` 非空，移除 `KIMI_MODEL_API_KEY` 作为独立认证方式。未来确认某个 Kimi Code/cligent 版本真的支持 ACP provider-key auth 后再恢复。

### [P1] 每个 trial 都从同一个 Kimi home 克隆 OAuth 凭据，不适合并发或长时间批量评测

位置：`wip/agents/deep_swe_collab/pier_agent.py:399`

每个 Pier trial 都从同一个宿主 Kimi home 复制一份凭据。

cligent 自己明确警告：克隆运行可能旋转 OAuth refresh credential，使原 source credential 失效。

在 113 个任务或 `--n-concurrent N` 下可能出现：

1. 多个 trial 拿到相同 refresh token；
2. 某个容器刷新并旋转 token；
3. 宿主源文件没有得到更新；
4. 后续或并发 trial 使用旧 token 认证失败。

这不是单元测试能够覆盖的问题。正式 Kimi 批量评测前需要验证真实 token 的刷新行为，并设计专门的评测凭据策略，例如为每个 worker 准备独立登录态；不应让多个并发容器共享同一个可旋转 refresh credential。

### [P2] 注入的凭据在 Agent 结束后没有清理

位置：`wip/agents/deep_swe_collab/pier_agent.py:477`

`run()` 注入凭据并运行 Node orchestrator，但没有通过 `finally` 清理：

- `/tmp/collab-secrets`
- `/tmp/codex-home`
- `/tmp/kimi-code-home`

这些路径不会被自动同步为 artifacts，但在后续 verifier 阶段、保留的调试容器以及异常退出后的容器中仍然存在。Pier 内置 Codex agent 会进行 best-effort cleanup。

建议围绕 orchestrator 调用增加 `try/finally`，清理失败只记录 warning，不能覆盖原始 Agent 异常。

## 正面结论

Codex 的核心文件注入链路实现正确：

- 能解析 `CODEX_AUTH_JSON_PATH` 和 `CODEX_FORCE_AUTH_JSON`；
- 上传后修正 owner 和 `0600` 权限；
- 通过 `CODEX_HOME/auth.json` 让 cligent 子进程继承登录态；
- key 没有直接拼入 shell command；
- 路径位于 `/tmp` 而非 `/logs`。

Kimi home 的目录创建、owner 修正和权限收紧也基本正确。

## 验证结果

| 检查项 | 结果 |
| --- | --- |
| Python 单元测试 | 23/23 通过 |
| Ruff | 通过 |
| `git show --check b70987e` | 通过 |
| 真实凭据 live auth smoke test | 未执行 |

## 建议实施顺序

1. 修复宿主环境变量与 runtime env 的不一致，或明确要求 API key/token 必须通过 `--ae`。
2. 清理 Kimi provider-only 的错误成功路径。
3. 为 Kimi 批量评测设计 refresh token 生命周期和并发策略。
4. 在 `finally` 中清理容器内临时凭据。
5. 分别执行 Codex、Claude、Kimi 的真实凭据 smoke test。

## 处理记录（2026-07-30）

Findings 1、2、4 已修复；Finding 3 以文档警告落地，实际策略推迟到 Kimi
批量评测前用真实凭据验证后确定。

| Finding | 状态 | 处理方式 |
| --- | --- | --- |
| [P1] 宿主 export 的凭据未注入容器 | ✅ 已修复（采用建议的 allowlist 方案） | `_runtime_env()` 按 adapter 从 `_get_env()` 显式转发受控 allowlist（claude: `ANTHROPIC_API_KEY`/`CLAUDE_CODE_OAUTH_TOKEN`；codex: `OPENAI_API_KEY`/`CODEX_API_KEY`/`OPENAI_BASE_URL`；kimi: `KIMI_MODEL_*`）作为 base 层，`--ae` 值经 `build_process_env` 合并顺序天然覆盖；宿主控制变量（`CODEX_FORCE_AUTH_JSON` 等）与无关宿主变量不转发。Codex API-key 分支补 `env.setdefault("OPENAI_API_KEY", ...)`（与 pier 内置 agent 一致），杜绝空 key auth.json。README「export 或 --ae 均可」的承诺现在成立 |
| [P1] `KIMI_MODEL_API_KEY` 被当成充分凭据 | ✅ 已修复 | `_require_credentials()` 对 kimi 角色要求 `_resolve_kimi_auth_home()` 非空，错误信息明确指出 ACP 需要 `kimi login` OAuth 凭据；`KIMI_MODEL_*` 降级为辅助配置（仍转发进容器但不构成凭据）。README 同步，并注明待上游确认支持 provider-key ACP 后再恢复 |
| [P1] Kimi OAuth clone/refresh 生命周期 | ⏸ 文档警告，策略推迟 | 按建议属于批量评测前置项而非代码可修：README 认证章节新增显著警告（并发/批量前必须用真实凭据验证 token 刷新行为，为每个 worker 准备独立登录态，不共享可旋转 refresh credential；单任务 smoke 不受影响） |
| [P2] 注入凭据未清理 | ✅ 已修复 | `run()` 将 auth 注入与 orchestrator 调用包进 `try/finally`，finally 中 best-effort `rm -rf /tmp/collab-secrets /tmp/codex-home /tmp/kimi-code-home`（仅 codex/kimi 参与时执行）；清理失败只记 warning，不覆盖原始异常。补充说明：verifier 运行于独立环境（`environment_mode=separate`），泄漏面主要是保留的调试容器 |

处理后验证：Python unittest 30/30（新增 7 个：宿主 export 转发、`--ae` 优先、
无关变量不转发、kimi provider-only 拒绝、成功/失败路径的清理、claude-only
跳过清理）；ruff 通过。真实凭据 live smoke test 仍待执行（建议实施顺序第 5 项）。
