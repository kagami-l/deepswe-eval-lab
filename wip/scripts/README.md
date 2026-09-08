# WIP 脚本

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
下文的 `run_codex_eval.sh`、`run_opencode_eval.sh`、`run_kimi_sample_dev.sh` 和
mini-swe 入口保留为旧基线/历史参考，不迁移到统一 runtime。

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

## 用共享 mini-swe-agent runtime 运行评测

`wip/scripts/run_mini_swe_eval.sh` 默认使用只读共享 runtime 镜像。第一次运行
构建一次固定版本的 runtime，之后不同任务、attempt 和 job 都直接复用，不再
重复构建 Python 依赖层。设计、兼容回退模式和 Docker 要求见
`wip/docs/mini-swe-shared-runtime.md`。

## 用 Codex 运行筛选样本

`wip/scripts/run_codex_eval.sh` 会读取任务 ID 列表，将其转换为 Pier 的任务过滤参数，并在 Docker 中运行 Codex 和独立 verifier。默认运行 `05_sample_dev.txt`，每题 1 次、并发 2：

```bash
wip/scripts/run_codex_eval.sh
```

先校验输入并查看最终命令：

```bash
wip/scripts/run_codex_eval.sh --dry-run
```

指定其他任务列表或运行配置：

```bash
wip/scripts/run_codex_eval.sh \
  --task-list wip/data/selection/05_sample_confirm.txt \
  --codex-version 0.146.0 \
  --model openai/gpt-5.6-sol \
  --job-name codex-confirm-k4
```

脚本默认使用宿主机 `codex login` 生成的 `~/.codex/auth.json`。同一任务和同一 Codex 安装配置会复用 Docker 构建缓存；不要为常规评测追加 `--force-build`。
