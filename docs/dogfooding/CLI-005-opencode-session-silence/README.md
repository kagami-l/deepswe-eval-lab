# CLI-005 OpenCode session silence evidence

本目录保存两个独立 OpenCode headless session 的精简、脱敏后证据。两个 session 都在工具
事件后停止产生 SSE/terminal event；取证时没有仍在运行的工具子进程，只有调用方 Node 和
`opencode serve` 继续存活。

- [`case-summary.json`](./case-summary.json)：时间线、事件计数、终止方式和进程状态投影。
- `anko` 由 5100 秒调用方 deadline abort，adapter 随后报告 `done(interrupted)`。
- `adaptix` 在持续静默约 48 分钟后由人工 SIGTERM，未产生 adapter terminal event。

原始事件日志包含大量 `text_delta` 和 CLI-001 导致的重复 `tool_use`，不在本目录复制。精简
统计保留唯一 tool call 数、最后事件和 terminal event 情况，足以复核 lifecycle hang。

本证据不能单独判断 OpenCode session、provider、SDK/SSE 或 cligent session 过滤中的哪一层
丢失了 terminal progress；这正是建议增加 raw SSE 与 session-status 快照的原因。
