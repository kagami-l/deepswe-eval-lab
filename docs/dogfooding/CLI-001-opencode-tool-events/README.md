# CLI-001 OpenCode 工具事件证据

本目录保存 CLI-001 的最小可复核证据集。样本来自一次 cligent `0.16.0` +
OpenCode CLI/SDK `1.18.10` 的真实运行。

## 结论摘要

- OpenCode 调用工具的功能正常，cligent 输出流中也出现了 `tool_use`。
- 253 条 `tool_use` 只有 56 个唯一 ID，存在 197 条重复事件。
- 253 条 `tool_use` 的 `payload.input` 全部是空对象。
- cligent 输出流中没有任何 `tool_result`。
- 同一个 ID 最多出现 25 次；对应样本见
  [`duplicate-tool-use-excerpt.jsonl`](./duplicate-tool-use-excerpt.jsonl)。
- 下游 trajectory 因此包含 253 个 tool calls，但没有 observation。

详细统计见 [`event-stats.json`](./event-stats.json)，下游结构性影响见
[`trajectory-summary.json`](./trajectory-summary.json)。

## 文件说明

- `event-stats.json`：从完整 `events.jsonl` 计算出的事件类型、空参数和重复 ID 统计。
- `duplicate-tool-use-excerpt.jsonl`：同一个 bash 工具调用的首尾 8 条真实事件；完整日志中
  该 ID 共出现 25 次，时间跨度约 20 秒。
- `trajectory-summary.json`：从完整 trajectory 提取的 tool call/observation 计数。

样本只保留结构性事件，没有复制 prompt、模型文本、工具输出、代码内容或凭据。完整原始
日志未放入本文档目录，因为其中包含大量与问题无关的模型文本增量。

## 原始文件校验

生成证据时使用的原始文件 SHA-256：

```text
events.jsonl    6c5ae5864ac6e2008cf3c38791717d288fb320ff0e165b575226f703f25878f1
trajectory.json 5960e7bc643f03107c0802910eea8e2b27fcf7fe40dce57c9bd768d79f4b5c81
summary.json    1b02f35e0599bde628c1a9af1165fdbc9bd8ef4b7e55266d23b749c29377ae71
```

## 证据边界

本次运行没有保存 cligent 转换前的原始 OpenCode SSE。因此，这组文件可以直接证明：

1. cligent 的规范化输出存在空参数、重复 `tool_use` 和缺失 `tool_result`；
2. 这些异常会进一步造成工具计数和下游 trajectory 失真。

它不能单独展示对应的原始 `part.state.input/output/error`。修复时应补充 OpenCode SSE
fixture，并对 raw event 与 normalized event 做成对测试。

