# WIP 脚本

除特别说明外，命令都在 `wip/` 目录下执行（先 `uv sync`，见 [`../README.md`](../README.md)）。

## 目录索引

| 文件 | 用途 | 详细文档 |
|---|---|---|
| `run_agent_eval.py` | 统一 Agent 评测入口：`runtime prepare`、`eval`、`score-patches` | 下节；[`docs/unified-agent-evaluation-design.md`](../../docs/unified-agent-evaluation-design.md) |
| `token_usage.py` | 汇总一个 job 的 token 与费用报告 | 本文“Token 消耗报告” |
| `official_trials_to_pier_jobs.py` | 把官方 DeepSWE v1.1 `trials.json` 转成 `pier view --jobs` 可读的 jobs 目录 | [`../data/README.md`](../data/README.md) |
| `select_discriminative_tasks.py` | 从官方 v1.1 数据生成分层任务筛选结果和 `data/selection/` 样本 | [`../data/README.md`](../data/README.md) |
| `run_mini_swe_eval.sh` | 旧基线：用 Pier 运行 mini-swe-agent（官方 trials 的 harness） | 本文末节；[`../docs/mini-swe-shared-runtime.md`](../docs/mini-swe-shared-runtime.md) |
| `test_*.py` | 上述 Python 脚本的单元测试 | 本文“测试” |
| `.env` | gitignored 凭据，`run_agent_eval.py` 启动时自动加载（已导出的变量优先） | [`docs/claude-code-oauth-token.md`](../../docs/claude-code-oauth-token.md) |

每个脚本都支持 `--help`；`run_agent_eval.py` 的每个子命令也各自支持 `--help`。

旧基线入口 `run_codex_eval.sh`、`run_kimi_sample_dev.sh`、`run_opencode_eval.sh` 已于
2026-09-08 移除，等价命令是 `run_agent_eval.py eval --agent codex|kimi|opencode`。它们专属的
adapter 代码暂时保留，弃用说明见 [`../agents/deprecated.md`](../agents/deprecated.md)。

## 统一 Agent 评测新基线

single 和固定 review-loop collab 的新实验统一使用：

```bash
cd wip
uv sync
uv run python scripts/run_agent_eval.py runtime prepare
uv run python scripts/run_agent_eval.py eval --task <task> --agent codex --dry-run
uv run python scripts/run_agent_eval.py eval \
  --task <task> --agent collab --modifier kimi --reviewer codex --dry-run
```

未传 `--job-name` 时，自动名称以 Agent 开头并包含 task-list 的文件名。例如
`--agent codex --task-list data/selection/05_sample_dev.txt` 会生成形如
`codex-05_sample_dev-12-tasks-20260804-120000` 的名称；`--agent collab`
会在 `collab-` 后插入 `{modifier}-{reviewer}`，例如
`collab-opencode-codex-05_sample_dev-12-tasks-20260804-120000`。显式
`--job-name` 仍会完整覆盖该默认值。

每个 Agent turn 默认在连续 900 秒没有任何事件时保存诊断快照并提前终止，避免静默 session
占用完整 task timeout。可按实验需要调整：

```bash
uv run python scripts/run_agent_eval.py eval \
  --task-list data/selection/05_sample_dev.txt \
  --agent collab --modifier opencode --reviewer codex \
  --event-silence-timeout-seconds 900
```

触发后，结构化快照和终止前 tracked patch 位于对应 trial 的
`agent/system/rounds/<round>/diagnostics/`。runtime 会在 adapter abort 的短暂 grace period
后定向清理该 turn 新建且仍存活的进程树，结果记录为
`runtime:turn_process_cleanup` 事件。

完整契约、认证路径、预算语义和验收记录见
[`docs/unified-agent-evaluation-design.md`](../../docs/unified-agent-evaluation-design.md)。

### 事后评分 collab 各阶段 patch

`score-patches` 对已完成的 collab job，用 Pier 的 direct verifier 重新给各阶段冻结的 patch
打分，不调用任何模型；非 collab 的 trial 会被标记为 ineligible：

```bash
uv run python scripts/run_agent_eval.py score-patches --job-path ../jobs/<job-name>
uv run python scripts/run_agent_eval.py score-patches --job-path ../jobs/<job-name> \
  --trial '<trial-glob>' --reuse-final-score
```

设计与输出格式见
[`../docs/collab-paired-checkpoint-verification-design.md`](../docs/collab-paired-checkpoint-verification-design.md)。

## Token 消耗报告

`token_usage.py` 仅接受当前 cligent 对应的 `usageSchema=2` summary，要求每个 turn
都有一个 `usageReports` 槽位（没有报告时为 null）。旧 flat 格式明确报错；不读取旧价格表，
不支持 `--pricing`。single/collab 共用同一入口。

脚本从每轮原始报告重新计算 job、角色、trial 和 turn 用量，忽略 summary 的旧扁平投影。
文本和 `reportSchemaVersion=2` JSON 区分 `observedInputTokens/observedOutputTokens`
小计与完整 `inputTokens/outputTokens`；只有所有轮次均为 complete 时后者才有值。
缓存读写已包含在 input total，reasoning 已包含在 output total，不能再相加。
文本展示这些细项及报告轮次；细项缺失保持未知，真实零保留为 0。

报告含明确的 complete/partial/missing 轮次、实际模型 records、每轮用量及统计样本数。
分布和按评分分组的均值使用已观测值，缺失值不按零计算；无评分的 trial 单独列为 unscored。
缺 result/usage 的 trial 列为 excluded，并使 job 完整总量保持未知。
`toolUses`、turns 和 wall time 独立汇总。

```bash
# 在 wip/ 目录下执行
uv run python scripts/token_usage.py ../jobs/<job-name>
uv run python scripts/token_usage.py ../jobs/<job-name> --json
```

费用仅来自每轮上游 `cost`，保留 provider-reported、agent-estimate 或 account-estimate
来源。`observedCostUsd` 是已报告小计，`costUsd` 仅在完整覆盖时有值；费用覆盖与 token
覆盖独立计算。模型 records 的费用已包含在本轮费用中，不再重复相加，也不构造 input/cache/output
费用分栏。完整角色费用不能冒充整个 job 费用。没有上游费用时保持未知，不按配置模型估价。
所有原始 records（包括 requests、pricedUnits）保留在 JSON 的 `usageReports` 中。

## 旧基线：用共享 mini-swe-agent runtime 运行评测

`run_mini_swe_eval.sh` 是旧基线入口，不迁移到统一 runtime；保留它是因为官方 DeepSWE
trials 使用的 harness 就是 mini-swe-agent，需要时可用它复现官方基线。脚本在仓库根目录执行，
默认使用只读共享 runtime 镜像：第一次运行构建一次固定版本的 runtime，之后不同任务、attempt
和 job 都直接复用，不再重复构建 Python 依赖层。设计、兼容回退模式和 Docker 要求见
[`../docs/mini-swe-shared-runtime.md`](../docs/mini-swe-shared-runtime.md)。

```bash
# 在仓库根目录执行
wip/scripts/run_mini_swe_eval.sh --dry-run
```

## 测试

```bash
uv run python -m unittest discover -s scripts -p 'test_*.py'
uv run ruff check scripts
```
