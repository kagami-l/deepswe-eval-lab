# CLI-002 Codex 命令事件证据

本目录保存 CLI-002 的最小可复核证据集。样本来自 cligent `0.16.0` + Codex SDK/CLI
`0.144.5` 的一次真实运行。

## 结论摘要

- Agent 成功完成任务，产生 23 KiB patch，最终 verifier reward 为 1。
- cligent 事件流只包含文本、文件变更和终止事件。
- `tool_use`、`tool_result` 均为 0，`done.usage.toolUses` 也为 0。
- Codex SDK 将 shell 执行建模为 `command_execution`，将 MCP 调用建模为
  `mcp_tool_call`；cligent `0.16.0` 的 `item.completed` 解析没有覆盖这两种类型。

详细统计见 [`event-stats.json`](./event-stats.json)，代表性 cligent 事件见
[`representative-events.jsonl`](./representative-events.jsonl)，下游结构摘要见
[`trajectory-summary.json`](./trajectory-summary.json)。

## 证据边界

本次运行没有保存 cligent 转换前的 Codex SDK raw event stream。因此，运行产物直接证明
的是“成功执行后 cligent 输出没有工具事件”；SDK 类型和 adapter 分支检查进一步确认了
`command_execution`/`mcp_tool_call` 的映射缺口。修复时应使用 SDK ThreadItem fixture
补充确定性的 adapter 单元测试。

## 原始文件校验

```text
events.jsonl    24689dc30680101f8a2e583ec7303d2fb8fb0e5ec6f0334bf7cfe94d92497bd2
trajectory.json 6e4e80b7dbdd492bb7fad0f60b9c2624e5eb3dbcc765361dfc9ce37040b5b349
summary.json    40d543ba859f20fcc27cf11be8512e66feedf33bc6ae9ab3f03e0165f9af52ba
patch.diff      b3aa6c85176b7bb038521da5edd72e7e9fc9598b4ebf758fcb4d2caa574ea0ba
```

