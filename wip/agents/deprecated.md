# 已移除的旧基线组件

统一 Agent 评测新基线是 `wip/agents/deep_swe_agent/` 加 `wip/scripts/run_agent_eval.py`
（见 [`docs/unified-agent-evaluation-design.md`](../../docs/unified-agent-evaluation-design.md)）。
下列旧基线组件已从仓库删除，没有调用方，也不再维护；代码可从删除前的 git 历史找回。

| 组件 | 删除日期 | 替代命令（在 `wip/` 下执行） |
|---|---|---|
| `wip/scripts/run_codex_eval.sh`（Pier 内置 Codex agent 的批量入口） | 2026-09-08 | `uv run python scripts/run_agent_eval.py eval --agent codex ...` |
| `wip/scripts/run_kimi_sample_dev.sh` | 2026-09-08 | `uv run python scripts/run_agent_eval.py eval --agent kimi ...` |
| `wip/scripts/run_opencode_eval.sh` | 2026-09-08 | `uv run python scripts/run_agent_eval.py eval --agent opencode ...` |
| `wip/agents/kimi_code_agent.py`、`test_kimi_code_agent.py` 及其 README（Kimi Code Pier adapter） | 2026-09-09 | `--agent kimi` |
| `wip/agents/opencode_watchdog_agent.py`、`opencode_watchdog_runner.mjs`、`test_opencode_watchdog.py` | 2026-09-09 | `--agent opencode` |
| `wip/environments/opencode_runtime.py`、`test_opencode_runtime.py` | 2026-09-09 | 统一 runtime 由 `wip/environments/agent_runtime.py` 提供 |
| `wip/docker/opencode-runtime/`（OpenCode shared runtime 镜像） | 2026-09-09 | `uv run python scripts/run_agent_eval.py runtime prepare` |
| `wip/agents/deep_swe_collab/`（旧的「修改 → 审查 → 修订」协作 Pier Agent 及其 Node runtime） | 2026-09-09 | `--agent collab --modifier ... --reviewer ...` |

补充说明：

- OpenCode watchdog 的问题分析见
  [`../docs/opencode-terminal-event-watchdog.md`](../docs/opencode-terminal-event-watchdog.md)；
  `deep_swe_collab` 的原设计见
  [`docs/archive/collab-agent-design.md`](../../docs/archive/collab-agent-design.md)。
  `deep_swe_collab` 的 direct engine、prompt、review schema 和 workspace 隔离已迁入 `deep_swe_agent/`。
- 早期由这些组件产生的 job 与结果文档（`wip/docs/results/` 中 2026-08-04 之前的 kimi-code、
  opencode-deepseek 条目）仍然有效，只是无法用当前代码重跑。
- 本机可能残留它们构建的 Docker 镜像（`deep-swe/opencode-runtime:*`、`deep-swe-kimi-code-agent:*`），
  不再需要时可用 `docker rmi` 清理。

不在移除范围内：`mini_swe_agent.py`、`../environments/mini_swe_runtime.py`、
`../docker/mini-swe-runtime/` 和 `../scripts/run_mini_swe_eval.sh`。统一 runtime 没有
mini-swe-agent profile，而官方 DeepSWE trials 使用的 harness 正是 mini-swe-agent，
这条入口保留用于复现官方基线（见 [`../docs/mini-swe-shared-runtime.md`](../docs/mini-swe-shared-runtime.md)）。
