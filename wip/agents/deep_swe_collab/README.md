# DeepSWE Collab Agent（deep-swe-collab）

按 [docs/collab-agent-design.md](../../../docs/collab-agent-design.md) 实现的
「修改 → 审查 → 修订」协作 Agent，作为一个 Pier 自定义复合 Agent 运行：

- `pier_agent.py`：宿主侧适配层（`BaseInstalledAgent`）。负责把 Node runtime
  装进任务容器（`install_spec()` 走 npm registry，可烘进派生镜像）、注入
  adapter 凭据、上传编译产物、启动容器内 orchestrator，并从 `summary.json`
  回填 `AgentContext`。
- `runtime/`：容器内 TypeScript orchestrator。用 cligent 驱动 Modifier
  （`/app`，session 复用）和 Reviewer（独立完整拷贝，fresh session），本地
  确定性解析 Reviewer 严格 JSON，机械 checkpoint commit 交给
  `pre_artifacts.sh` 提取 patch。

协作循环中只有 Modifier 和 Reviewer 两个 LLM Agent；状态流转、JSON 仲裁、
checkpoint 全部是本地确定性代码，不产生额外模型调用。

## 前置条件

- 宿主机：Node ≥ 18.3（构建 runtime）、Docker、`pier`（uv tool）。
- 任务镜像自带 Node 24，容器内无需装 Node。
- 至少配置好 Modifier 和 Reviewer 两个 adapter 的凭据（见下文）。

## 构建

```bash
cd wip/agents/deep_swe_collab/runtime
npm ci
npm run build        # 产出 dist/，setup 时上传到容器 /opt/collab-runtime/dist
```

未构建就运行会在 setup 阶段直接报错提示。

## 认证配置

`run()` 启动前做 fail-fast 校验：每个用到的 adapter 必须满足下表任一方式，
否则直接报错列出缺失项。所有注入的凭据文件都放在容器 `/tmp` 下
（`/tmp/codex-home`、`/tmp/kimi-code-home`、`/tmp/collab-secrets`），
不会进入 `/logs`（`/logs` 会作为 artifacts 同步回宿主机）。

环境变量既可以在宿主 shell `export`（每个 adapter 的凭据变量按 allowlist
自动转发进容器，无关宿主变量不会带入），也可以用 `pier run --ae KEY='${KEY}'`
显式传入（`--ae` 支持 `${VAR}` 引用宿主变量，job config 序列化时自动脱敏，
且优先级高于宿主 export）。注入的凭据在 agent 结束后（含异常退出）会
best-effort 清理。

### Codex

三种方式，机制与 pier 内置 Codex agent 完全一致（统一落到
`$CODEX_HOME/auth.json`，cligent spawn 的 `codex` 二进制继承 `CODEX_HOME`）：

| 方式 | 配置 | 说明 |
|---|---|---|
| 宿主 codex 登录（推荐） | `CODEX_FORCE_AUTH_JSON=1` | 上传宿主机 `~/.codex/auth.json`（先 `codex login`），chown 给 agent 用户后软链进 `$CODEX_HOME` |
| 指定 auth.json | `CODEX_AUTH_JSON_PATH=/path/to/auth.json` | 同上，但用指定文件 |
| API Key | `--ae OPENAI_API_KEY='${OPENAI_API_KEY}'` | 容器内从环境变量生成 auth.json（umask 077，key 不出现在命令行日志） |

`CODEX_API_KEY` 也被接受（纯环境变量透传，不物化 auth.json）。
优先级：`CODEX_AUTH_JSON_PATH` > `CODEX_FORCE_AUTH_JSON` > API Key。

### Claude

Claude 没有对称的凭据文件注入路径：macOS 宿主的 claude 登录凭据存放在
Keychain，不是可拷贝文件。标准做法二选一：

| 方式 | 配置 | 说明 |
|---|---|---|
| API Key | `--ae ANTHROPIC_API_KEY='${ANTHROPIC_API_KEY}'` | 直接走 Anthropic API |
| 宿主 claude 登录（标准做法） | 宿主执行 `claude setup-token` 生成长期 OAuth token，然后 `--ae CLAUDE_CODE_OAUTH_TOKEN='${CLAUDE_CODE_OAUTH_TOKEN}'` | 使用 Claude 订阅额度；token 是普通环境变量，容器内 claude-agent-sdk 直接识别 |

### Kimi

cligent 通过新版 Kimi Code CLI 的 `kimi acp`（ACP over stdio）驱动。
**ACP 模式要求 `kimi login` 产生的 OAuth 凭据**（`credentials/kimi-code.json`），
因此 Kimi 角色必须走凭据注入，仅有 `KIMI_MODEL_API_KEY` 无法通过启动校验：

| 方式 | 配置 | 说明 |
|---|---|---|
| 宿主 kimi 登录（推荐） | `KIMI_FORCE_AUTH_HOME=1` | 上传宿主机 `~/.kimi-code` 的 `config.toml` + `credentials/` 到容器 `$KIMI_CODE_HOME`，chmod 700（做法与 cligent 自身 CI 一致；不上传 `bin/`，容器内 CLI 由 `install_spec()` 按 `kimi_code_version` 固定安装） |
| 指定 Kimi home | `KIMI_AUTH_HOME_PATH=/path/to/kimi-home` | 同上，但用指定目录 |

`KIMI_MODEL_*`（API key / model / base URL）作为**辅助配置**仍会转发进容器，
但不构成独立凭据；待某个 Kimi Code/cligent 版本确认支持 provider-key ACP
认证后再放开。

> ⚠️ **并发/批量警告**：每个 trial 都会从同一宿主 Kimi home 克隆 OAuth
> 凭据，而克隆运行可能旋转 refresh credential 使源凭据失效（cligent 文档
> 明确警告过此行为）。Kimi 参与的批量或 `--n-concurrent > 1` 评测前，必须
> 先用真实凭据验证 token 刷新行为，并为每个 worker 准备独立登录态；不要让
> 多个并发容器共享同一份可旋转 refresh credential。单任务 smoke 不受影响。

注意：宿主机若同时装过旧版 Python `kimi-cli`（同名二进制 `kimi`），不影响
容器——容器内安装步骤自带 `kimi --help | grep -q acp` 探针，装错会直接失败。

## 运行

单任务（cross-review：codex 改、claude 审）：

```bash
cd /Users/kgm/Projects/merico/deep-swe

CODEX_FORCE_AUTH_JSON=1 pier run \
  -p tasks/fastapi-implicit-head-options \
  --agent-import-path wip.agents.deep_swe_collab.pier_agent:DeepSweCollabAgent \
  --ak modifier_adapter=codex \
  --ak reviewer_adapter=claude \
  --ae CLAUDE_CODE_OAUTH_TOKEN='${CLAUDE_CODE_OAUTH_TOKEN}'
```

Self-review（同一 adapter 自审）：

```bash
CODEX_FORCE_AUTH_JSON=1 pier run \
  -p tasks/fastapi-implicit-head-options \
  --agent-import-path wip.agents.deep_swe_collab.pier_agent:DeepSweCollabAgent \
  --ak modifier_adapter=codex --ak reviewer_adapter=codex
```

Kimi 作 Reviewer：

```bash
CODEX_FORCE_AUTH_JSON=1 KIMI_FORCE_AUTH_HOME=1 pier run \
  -p tasks/fastapi-implicit-head-options \
  --agent-import-path wip.agents.deep_swe_collab.pier_agent:DeepSweCollabAgent \
  --ak modifier_adapter=codex --ak reviewer_adapter=kimi
```

常用 pier 选项：`--n-concurrent N`（并发 trial 数）、`--n-attempts K`、
`--agent-setup-timeout-multiplier`（首次在线安装依赖较慢时放大 360s setup
超时）、`--agent-timeout-multiplier`。批量正式实验建议用 Pier job config
固化配置（参考 `wip/scripts/run_kimi_sample_dev.sh` 的做法）。

## `--ak` 参数

| kwarg | 默认 | 说明 |
|---|---|---|
| `modifier_adapter` / `reviewer_adapter` | `codex` / `claude` | 仅支持 `claude` / `codex` / `kimi`（首阶段排除 gemini/opencode，见设计文档 6.4） |
| `modifier_model` / `reviewer_model` | 空 | 透传给 cligent；**正式评测请显式指定**（不指定时使用 provider 当时的默认模型）。无论是否指定，summary 中 `modifier.actualModel` / `reviewer.actualModel` 都会记录 provider 实际解析的模型（取自 cligent init 事件） |
| `modifier_effort` / `reviewer_effort` | 空 | 透传给 cligent；正式评测建议显式指定 |
| `max_reviews` | 3 | 与 SWE-bench Pro collab 默认一致；预算不足时后段轮次自动跳过。`0` 表示跳过审查、同一条管线跑 modifier-only（可作 Single 基线的 matched-pipeline 对照组） |
| `max_agent_attempts` | 2 | 每轮（modifier/review）重试上限 |
| `modifier_timeout_seconds` | 2400 | 初始实现单轮超时 |
| `reviewer_timeout_seconds` | 600 | 每次 review 超时 |
| `revision_timeout_seconds` | 900 | 每次修订超时 |
| `total_timeout_seconds` | 5100 | 协作总 deadline（任务 5400s 内留余量） |
| `strict` | false | degraded 不交付、trial 失败（设计文档 §13） |
| `keep_workspaces` | false | 保留 review 拷贝目录便于调试 |
| `cligent_version` | 0.18.0 | npm 锁定版本 |
| `kimi_code_version` | 0.31.1 | 仅当某角色为 kimi 时安装 `@moonshot-ai/kimi-code` |

## 产物（`/logs/agent/collab/`）

```
summary.json               # engine/adapter/outcome/usage 汇总（AgentContext 数据源）
orchestrator-trace.jsonl   # 状态迁移 trace
cligent-events.jsonl       # 全部 cligent 事件（含 role/label）
rounds/00-modify/          # prompt.md / events.jsonl / metadata.json
rounds/01-review/          # + patch.diff / review-raw-a*.txt / review.json
rounds/01-revise/ ...
final/patch.diff           # base→HEAD 最终 diff（与 pre_artifacts.sh 一致口径）
final/git-status.txt
```

### Outcome 语义（设计文档 §13）

| outcome | 交付 | 说明 |
|---|---|---|
| `approved` | ✅ exit 0 | Reviewer 无 blocking finding |
| `max_reviews_reached` | ✅ exit 0 | 用完 review 轮次后交付最终修订（含 no-change revision 短路） |
| `degraded` | ✅ exit 0 | 已有可信 checkpoint 后 reviewer/修订/超时/基础设施故障（`reviewer_failed` / `invalid_review_output` / `revision_failed` / `timeout` / `infrastructure`），交付该 checkpoint；`degraded_reason` 单独统计，`strict` 模式下改为失败 |
| `modifier_failed` / `timeout` / `empty_patch` / `checkpoint_failed` | ❌ exit 2 | 无可信 patch，trial 失败并允许 Pier retry |

## 测试

```bash
# Python（用 pier 的 venv 解释器，unittest 约定同 wip/agents/README.md）
PYTHONDONTWRITEBYTECODE=1 \
  /Users/kgm/.local/share/uv/tools/datacurve-pier/bin/python \
  -m unittest -v wip.agents.deep_swe_collab.test_pier_agent

# TypeScript（fake runner 驱动完整状态机）
cd wip/agents/deep_swe_collab/runtime && npm test

# Lint
PYENV_VERSION=dc ruff check wip/agents/deep_swe_collab
```

单测不调用真实模型、不消耗 API 额度。两条防漂移保障：
`test_runtime_dependencies_match_host_package_json` 强制 `install_spec()`
内嵌依赖与 `runtime/package.json` 一致；auth 注入测试断言 API key 只以
`${OPENAI_API_KEY}` 形式出现在容器命令中、绝不落入日志。

## 故障排查

- **setup 超时（360s）**：首次在线 `npm install` 较慢时加
  `--agent-setup-timeout-multiplier 3`；批量运行让 pier 用 `install_spec()`
  构建派生镜像后即无此问题。
- **Codex 沙箱报错**：容器内 Codex 必须绕过自带 OS 沙箱运行（runtime 已
  固定 `mode: 'bypass'`，容器即隔离边界，与 pier 内置 Codex 行为一致）；
  若见 `bwrap`/`landlock` 相关报错说明配置被改动。
- **Reviewer 跑不了公开测试**：review 在 `/tmp` 下的完整拷贝中进行，个别
  项目若把绝对路径 `/app` 写死进构建产物会失败——smoke 阶段按语言逐一确认，
  确不可行的任务降级为只读审查（见设计文档 6.2）。
- **kimi 安装失败在 acp 探针**：说明装到的 `kimi` 不是新版
  `@moonshot-ai/kimi-code`（例如镜像里残留旧版 Python kimi-cli），检查
  `kimi_code_version` 与 npm registry 可达性。
