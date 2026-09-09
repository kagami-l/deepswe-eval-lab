# wip/agents

本目录存放本地 DeepSWE 评测使用的 Pier 自定义 Agent。

| 路径 | 用途 | 文档 |
|---|---|---|
| `deep_swe_agent/` | 统一 Agent 评测新基线的 Pier adapter 与容器内 runtime（single 与 collab 共用），入口是 `wip/scripts/run_agent_eval.py` | [`docs/unified-agent-evaluation-design.md`](../../docs/unified-agent-evaluation-design.md) |
| `usage.py` | `deep_swe_agent` 共用的 cligent 用量与费用汇总工具 | 同上 |
| `mini_swe_agent.py`、`test_mini_swe_agent.py` | 旧基线：mini-swe-agent 的 Pier adapter，入口是 `wip/scripts/run_mini_swe_eval.sh`；保留用于复现官方 trials 的 harness | [`../docs/mini-swe-shared-runtime.md`](../docs/mini-swe-shared-runtime.md) |
| `deprecated.md` | 已删除的旧基线组件清单、删除日期与替代命令 | — |

测试（在 `wip/` 下执行）：

```bash
uv run python -m unittest discover -s agents/deep_swe_agent -t .. -p 'test_*.py'
uv run python -m unittest discover -s agents -t .. -p 'test_*.py'
```
