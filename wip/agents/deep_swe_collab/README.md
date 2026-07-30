# DeepSWE Collab Agent（deep-swe-collab）

按 `docs/collab-agent-design.md` 实现的「修改 → 审查 → 修订」协作 Agent：

- `pier_agent.py`：宿主侧 Pier 适配层（`BaseInstalledAgent`）。负责把 Node
  runtime 装进任务容器（`install_spec()` 走 npm registry，可烘进派生镜像）、
  上传编译产物、启动容器内 orchestrator，并从 `summary.json` 回填
  `AgentContext`。
- `runtime/`：容器内 TypeScript orchestrator。用 cligent 驱动 Modifier
  （`/app`，session 复用）和 Reviewer（独立完整拷贝，fresh session），本地
  确定性解析 Reviewer 严格 JSON，机械 checkpoint commit 交给
  `pre_artifacts.sh` 提取 patch。

## 构建

宿主机需要 Node ≥ 18.3（构建）；任务镜像自带 Node 24：

```bash
cd wip/agents/deep_swe_collab/runtime
npm ci
npm run build        # 产出 dist/，setup 时上传到容器 /opt/collab-runtime/dist
npm test             # 22 个单测（fake runner 驱动完整状态机）
```

## 运行

```bash
cd /Users/kgm/Projects/merico/deep-swe

pier run \
  -p tasks/fastapi-implicit-head-options \
  --agent-import-path wip.agents.deep_swe_collab.pier_agent:DeepSweCollabAgent \
  --ak modifier_adapter=codex \
  --ak reviewer_adapter=claude \
  --ae OPENAI_API_KEY='${OPENAI_API_KEY}' \
  --ae ANTHROPIC_API_KEY='${ANTHROPIC_API_KEY}'
```

凭据按 adapter 任选其一，缺失时 run 阶段直接报错：

| adapter | 环境变量（any of） |
|---|---|
| claude | `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN` |
| codex | `OPENAI_API_KEY` / `CODEX_API_KEY` |
| kimi | `KIMI_CODE_HOME`（含 `kimi login` 凭据）/ `KIMI_MODEL_API_KEY` |

## `--ak` 参数

| kwarg | 默认 | 说明 |
|---|---|---|
| `modifier_adapter` / `reviewer_adapter` | `codex` / `claude` | 仅支持 `claude` / `codex` / `kimi`（首阶段排除 gemini/opencode，见设计文档 6.4） |
| `modifier_model` / `reviewer_model` | 空 | 透传给 cligent |
| `modifier_effort` / `reviewer_effort` | 空 | 透传给 cligent |
| `max_reviews` | 3 | 与 SWE-bench Pro collab 默认一致 |
| `max_agent_attempts` | 2 | 每轮（modifier/review）重试上限 |
| `modifier_timeout_seconds` | 2400 | 初始实现单轮超时 |
| `reviewer_timeout_seconds` | 600 | 每次 review 超时 |
| `revision_timeout_seconds` | 900 | 每次修订超时 |
| `total_timeout_seconds` | 5100 | 协作总 deadline（任务 5400s 内留余量） |
| `strict` | false | degraded 不交付、trial 失败（设计文档 §13） |
| `keep_workspaces` | false | 保留 review 拷贝目录便于调试 |
| `cligent_version` | 0.16.0 | npm 锁定版本 |
| `kimi_code_version` | 0.30.0 | 仅当某角色为 kimi 时安装 `@moonshot-ai/kimi-code` |

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

Outcome 语义见设计文档 §13：`approved` / `max_reviews_reached` / `degraded`
正常交付（exit 0），其余 exit 2 使 trial 失败并允许 Pier retry。

## 测试

```bash
# Python（用 pier 的 venv 解释器，unittest 约定同 wip/agents/README.md）
PYTHONDONTWRITEBYTECODE=1 \
  /Users/kgm/.local/share/uv/tools/datacurve-pier/bin/python \
  -m unittest -v wip.agents.deep_swe_collab.test_pier_agent

# TypeScript
cd wip/agents/deep_swe_collab/runtime && npm test

# Lint
PYENV_VERSION=dc ruff check wip/agents/deep_swe_collab
```

单测不调用真实模型。`test_runtime_dependencies_match_host_package_json`
强制 `install_spec()` 内嵌的依赖与 `runtime/package.json` 保持一致，防止
派生镜像与宿主构建漂移。
