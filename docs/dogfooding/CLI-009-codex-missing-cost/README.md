# CLI-009 Codex 未提供费用报告的证据

本目录保存 cligent `0.26.0` + Codex SDK/CLI `0.151.0` 的三次成功 turn：
single 首轮、collab 首轮、collab 恢复会话后的修订轮。模型均为 `gpt-5.6-luna`，
reasoning effort 为 `xhigh`；三次统一 `done.payload.usage` 均没有 `cost`。

- [representative-events.jsonl](./representative-events.jsonl)：原始统一事件中的 init/done 行，未改写 payload；按 single modify、collab modify、collab revise 排列。
- [case-summary.json](./case-summary.json)：版本、来源文件及行号、每轮 usage、metadata 和 summary 对照。

首次修改轮都有 token，因此费用缺失并不只发生在 token 缺失的修订轮。
本目录中的“原始事件”指 cligent 输出，未保存转换前的原生 Codex SDK stream；不能据此认定
SDK 已报告费用而 cligent 丢弃了它。完整问题、请求上游确认的事项和验收标准见
[问题总表 CLI-009](../cligent-dogfooding-issues.md#cli-009codex-成功-turn-未提供费用报告无法汇总完整-job-cost)。
