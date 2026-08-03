# CLI-003 Kimi 未知 token usage 证据

本目录保存 CLI-003 的最小可复核证据集。样本来自 cligent `0.16.0` + Kimi Code CLI
`0.30.0` 的一次真实成功运行。

## 结论摘要

- Kimi 成功运行约 20 分 35 秒，输出 4310 个文本字符并产生 56 对工具事件。
- 最终 patch 为 22,963 bytes，workflow outcome 为 `completed`。
- `done.payload.usage` 和下游 trajectory 却都将 prompt/completion token 记录为 0。
- Kimi adapter 在 ACP prompt response 没有 `usage` 时返回固定的零值 usage，因此“上游
  未提供”与“实际消耗为零”无法区分。

统计见 [`event-stats.json`](./event-stats.json)，代表性 init/done 摘要见
[`usage-events.jsonl`](./usage-events.jsonl)，下游影响见
[`trajectory-summary.json`](./trajectory-summary.json)。

## 证据边界

本次运行没有保存 Kimi ACP 转换前的 raw JSON-RPC response，因此运行产物直接证明的是
“成功且有大量输出的运行被报告为零 token”。adapter 源码进一步证明，当
`session/prompt` response 缺少 usage 时，cligent 主动构造零值 token usage。修复时应以
ACP response fixture 分别覆盖“usage 缺失”和“真实零值”。

## 原始文件校验

```text
events.jsonl    b8dbee59d15f881cf633fa84a2b0b926c1e241da701ff1285636c06b26e9e6bb
trajectory.json d270fdbfbe61442601dc1882d3224c245bdec37af2d8ecb19e10a2a7b979c4c8
summary.json    e02d23492a53127382529e66d3169ba006cd6fefb11747e8099c6bbf2476995e
model.patch     f50f099fe83e2544c624641693da8ed837e307429efb745bcee340b342023917
```
