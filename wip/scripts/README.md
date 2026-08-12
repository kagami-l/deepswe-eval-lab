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

`token_usage.py` 对一个 job 目录输出按模型（角色）区分的 token 消耗：job 级合计、
trial 级明细、分布统计（mean/median/p90/min/max）、通过与失败 trial 的均值对比,
以及 Pier job 级混合口径参照。数据源是各 trial `summary.json` 的 `result.usage`
（唯一分角色可信来源）；兼容 single/collab 拓扑,容忍缺 usage 的 trial（列入 skipped）。

```bash
# 在 wip/ 目录下执行
uv run python scripts/token_usage.py ../jobs/<job-name>          # 人读格式
uv run python scripts/token_usage.py ../jobs/<job-name> --json   # 机器格式
```

口径注意：input tokens 跨 adapter 语义不同,只宜同模型纵向对比；登录订阅制 adapter
的 cost 为 null；中断 attempt 计 0。所有记录层（summary usage、events.jsonl、pier
`n_cache_tokens`）都**不区分 cached / uncached**,cligent 落盘前已拍平。按量级推断
（2026-08 记录）：codex 与 claude 的 inputTokens **含** cache 读取（逐次调用全上下文
累计口径）,opencode/deepseek **不含** cache 命中（miss-only,数字小约两个数量级）;
两类口径互不可比,也都不能直接乘单价折算成本。output tokens 无缓存概念,跨 adapter
可比。

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
