# Review Schema Fail-Closed 修复复审

- 评审时间：2026-08-06 20:14:08（Asia/Shanghai）
- 评审提交：`717dd9d`（`Fail closed on the reviewer's latest verdict`）
- 前次 Review：`docs/reviews/20260806-193311-review-schema-candidate-selection-review-b24f724.md`
- 评审范围：前次 Review 的 1 个 P1、2 个 P2 处理情况，以及 direct review loop 的交付裁决

## 结论

最新提交修复了前次 Review 的主要测试场景，并增加了 review-schema 单元测试和
direct-engine 集成测试。以下路径已经正确：

- schema 合法但 verdict 值非法时，不再回退到旧 verdict；
- 带 verdict 的 blocking review，不再被尾部无 verdict 日志对象覆盖；
- 同一行引号内的 `{` 不再遮蔽有效答案；
- 最新合法空 `resolutions` 不再复活更早报告。

但“fail closed”目前只作用于已经成功 `JSON.parse` 的候选。语法损坏的最新 verdict /
resolutions 会在候选预处理阶段被丢弃，仍可能恢复旧结果；verdict-less 和嵌套对象也保留了
错误批准路径。因此前次 Review 还不能标记为全部处理完成。本次复审发现 2 个 P1、1 个
P2。

## Findings

### [P1] 语法损坏的最新 verdict 仍会复活旧 approval

位置：

- `wip/agents/deep_swe_agent/runtime/src/review-schema.ts:89`
- `wip/agents/deep_swe_agent/runtime/src/review-schema.ts:138`

`jsonObjects()` 对每个候选先执行 `JSON.parse`，解析失败就直接跳过。后续“最后一个带
`verdict` 的对象必须校验”因此只看得到语法合法的对象。

复现输入：

```text
{"verdict":"approve","findings":[]}
Correction: {"verdict":"revise","findings":[}
```

第二个对象明显是更新后的 reviewer 意图，但因为 JSON 语法损坏而从 `objects` 消失，当前
实现返回较早的 `approve`。Direct engine 随后会把它当成无 blocking finding 的合法 review
并交付，而不是进入 `invalid_review_output` 重试。

建议保留 raw candidate、解析状态和候选位置。若离输出末尾最近的 review-shaped candidate
在顶层表达了 `verdict`，即使 `JSON.parse` 失败也必须抛出 `ReviewParseError`，不能继续向前
寻找旧 verdict。需要增加 schema 与 direct-engine 两层测试。

### [P1] Verdict-less 和嵌套日志对象仍可覆盖 blocking review

位置：`wip/agents/deep_swe_agent/runtime/src/review-schema.ts:146`

当前仍兼容 verdict-less review，并在没有任何已解析对象携带 `verdict` 时返回最后一个通过
schema 的对象。这保留了以下错误批准路径：

```text
{"findings":[{"severity":"major","issue":"x"}]}
Log: {"findings":[]}
```

尾部日志对象被解释成 verdict-less approval，覆盖前面的 blocking finding。

此外，扫描器会把嵌套对象也作为独立候选。下面的尾部日志会取内部 `approve`，再次覆盖
前面的 blocking review：

```text
{"verdict":"revise","findings":[{"severity":"major","issue":"x"}]}
Log: {"payload":{"verdict":"approve","findings":[]}}
```

建议按 prompt 契约要求完整 review 必须带显式 `verdict`。若必须兼容 verdict-less 输出，
至少只能在存在唯一、明确的顶层 review candidate 时接受；多候选场景应 fail closed。同时
应过滤包含在另一个完整候选内的嵌套对象，除非其外层是不完整、无法闭合的噪声区域。

### [P2] 语法损坏的最新 resolutions 仍会回退到陈旧报告

位置：`wip/agents/deep_swe_agent/runtime/src/review-schema.ts:202`

合法空数组和 item 全部无效的场景已经修复，但语法损坏的最近报告仍会被 `jsonObjects()`
跳过：

```text
Earlier {"resolutions":[{"id":"R1-F1","status":"accepted"}]}
Final {"resolutions":[}
```

当前返回更早的 `R1-F1=accepted`。这会把已过期的处理状态传给下一轮 reviewer。

建议与 review verdict 使用同一套 raw candidate 策略：找到最近的顶层 `resolutions` 报告后
立即停止；解析失败、空数组或没有合法 item 时返回 `null`，不能向更早报告回退。

## 已确认修复的内容

### Schema 合法但 verdict 非法

以下输入现在抛出 `ReviewParseError`，错误信息包含 `maybe`：

```text
{"verdict":"approve","findings":[]}
Scratch that:
{"verdict":"maybe","findings":[]}
```

对应 direct-engine 集成测试确认会发起第二次 review，而不是产生 `approved` outcome。

### 尾部无 verdict 日志对象

当正式 blocking review 明确带有 `verdict=revise` 时，尾部 `{"findings":[]}` 不再覆盖它；
引擎会先执行 revision，再接受后续 approval。

### 同行引号内花括号

扫描器现在在所有深度跟踪引号状态，以下输入能够正确解析：

```text
The token "{" is special; answer: {"verdict":"approve","findings":[]}
```

### 合法空 resolutions

最近对象为 `{"resolutions":[]}` 时返回 `null`，不再回退旧 `accepted/rebutted` 状态。

## 验证结果

| 检查项 | 结果 |
| --- | --- |
| runtime `npm test`（含 TypeScript build） | 67/67 通过 |
| 提交 diff 格式检查 | 通过 |
| 旧 approval + schema 非法新 verdict | 已修复，抛 `ReviewParseError` |
| 旧 approval + JSON 语法损坏的新 verdict | 仍返回旧 `approve` |
| verdict-less blocking + 尾部空 findings | 仍被覆盖为无 blocking |
| blocking review + 尾部嵌套 approval 日志 | 仍被覆盖为 `approve` |
| 旧 resolutions + 最新合法空数组 | 已修复，返回 `null` |
| 旧 resolutions + 最新语法损坏报告 | 仍返回旧 `accepted` |

## 建议实施顺序

1. 保留 raw candidate 和解析错误，让最近的 verdict-shaped 候选真正 fail closed。
2. 收紧 verdict-less review 兼容策略，并阻止嵌套日志对象参与顶层 verdict 选择。
3. 对最近的 raw resolutions candidate 使用相同的停止规则。
4. 增加三个 schema 回归测试和至少一个 direct-engine 错误批准集成测试。
5. 修复后重新运行历史 reviewer raw output 对比，并更新前次 Review 文档的处理状态。
