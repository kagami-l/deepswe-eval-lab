# 已弃用的旧基线 adapter

统一 Agent 评测新基线是 `wip/agents/deep_swe_agent/` 加 `wip/scripts/run_agent_eval.py`
（见 [`docs/unified-agent-evaluation-design.md`](../../docs/unified-agent-evaluation-design.md)）。
下列旧基线组件的启动脚本已于 2026-09-08 从 `wip/scripts/` 移除；代码本身暂时保留，
仅作实现与问题排查记录，不再维护，也没有批量运行入口。

| 组件 | 原入口（已删除） | 替代命令（在 `wip/` 下执行） |
|---|---|---|
| `kimi_code_agent.py`、`test_kimi_code_agent.py`、`README.md`（Kimi adapter 文档） | `run_kimi_sample_dev.sh` | `uv run python scripts/run_agent_eval.py eval --agent kimi ...` |
| `opencode_watchdog_agent.py`、`opencode_watchdog_runner.mjs`、`test_opencode_watchdog.py` | `run_opencode_eval.sh` | `uv run python scripts/run_agent_eval.py eval --agent opencode ...` |
| `../environments/opencode_runtime.py`、`../environments/test_opencode_runtime.py` | `run_opencode_eval.sh` | 同上（统一 runtime 由 `../environments/agent_runtime.py` 提供） |
| `../docker/opencode-runtime/` | `run_opencode_eval.sh` | `uv run python scripts/run_agent_eval.py runtime prepare` |

Pier 内置 Codex agent 的旧入口 `run_codex_eval.sh` 同时移除，替代命令是
`eval --agent codex`；它没有仓库内的 adapter 代码。

OpenCode watchdog 的问题分析与实现记录见
[`../docs/opencode-terminal-event-watchdog.md`](../docs/opencode-terminal-event-watchdog.md)。

不在弃用范围内：`mini_swe_agent.py`、`../environments/mini_swe_runtime.py`、
`../docker/mini-swe-runtime/` 和 `../scripts/run_mini_swe_eval.sh`。统一 runtime 没有
mini-swe-agent profile，而官方 DeepSWE trials 使用的 harness 正是 mini-swe-agent，
这条入口保留用于复现官方基线（见 [`../docs/mini-swe-shared-runtime.md`](../docs/mini-swe-shared-runtime.md)）。
