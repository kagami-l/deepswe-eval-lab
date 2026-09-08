# CLI-010 Codex 恢复会话后缺少 token 的证据

本目录保存同一个 collab job 中 Codex modifier 的首次修改和修订事件。
环境为 cligent `0.26.0`、Codex SDK/CLI `0.151.0`、`gpt-5.6-luna` / `xhigh`。
两轮 session ID 相同且均成功结束：首轮有 token，修订轮 usage 只有 `toolUses: 6`。

- [representative-events.jsonl](./representative-events.jsonl)：依次为首次修改 init/done、恢复会话修订 init/done，直接复制原始统一事件行。
- [case-summary.json](./case-summary.json)：版本、原始文件及行号、两轮 usage、metadata 和 summary 对照。

已核对每轮原始 terminal usage 与 deep-swe summary 的 `usageReports` 完全一致；
deep-swe 在 normalization 之前保存事件，因此缺失已经发生在 cligent 输出边界。
没有保存原生 SDK usage 快照，不能区分 SDK 未提供 usage 和 cligent 增量计算省略 usage。
完整定位边界、排查建议和验收标准见
[问题总表 CLI-010](../cligent-dogfooding-issues.md#cli-010codex-首轮有-token恢复同一会话后的修订轮缺少-token)。
