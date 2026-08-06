# Review Schema 候选选择改进 Review

- 评审时间：2026-08-06 19:33:11（Asia/Shanghai）
- 评审提交：`b24f724`（`Take the last schema-valid object as the review JSON`）
- 评审基线：当前 `eval-lab` 最新代码
- 评审范围：`review-schema.ts`、`review-schema.test.ts`，以及其在 direct review loop 中的裁决影响

## 结论

改动方向合理：从“首个代码围栏/首个左花括号”改为倒序扫描候选对象，能够处理 prompt
模板、patch 代码、嵌套对象和未闭合花括号干扰，覆盖了 dogfooding 中出现的主要误解析形态。

但当前“最后一个 schema-valid 对象”策略存在 fail-open 风险：最新 reviewer 意图无效时，
可能静默采用更早的旧 verdict，甚至把 blocking review 覆盖成 approval。建议修复下述 P1
后再依赖该逻辑做交付裁决；两个 P2 可一并处理。

## Findings

### [P1] 最新 review-shaped 对象无效时会回退到旧 review，可能错误批准交付

位置：

- `wip/agents/deep_swe_agent/runtime/src/review-schema.ts:135`
- `wip/agents/deep_swe_agent/runtime/src/review-schema.test.ts:196`
- `wip/agents/deep_swe_agent/runtime/src/direct-engine.ts:536`

`parseReview()` 倒序遍历候选对象，但 schema 校验失败后会继续向前搜索。提交中的测试明确
固定了以下行为：

```text
{"verdict":"approve","findings":[]}
Scratch that, my verdict is:
{"verdict":"maybe","findings":[]}
```

最终返回较早的 `approve`。这不是安全的容错：末尾对象明显表达了 reviewer 的最新意图，
但格式无效时本应触发 `invalid_review_output` 和重试，而不是恢复已被推翻的旧 verdict。

还有一个更直接的错误批准路径：

```text
{"verdict":"revise","findings":[{"severity":"major","issue":"x"}]}
Log: {"findings":[]}
```

由于 `buildReview()` 允许缺少 `verdict`，末尾无关对象也通过 schema，并以零 blocking
finding 覆盖真正的 review。Direct engine 随后在 `review.hasBlockingFindings === false` 时
直接将 outcome 设为 `approved`。

建议倒序扫描时只跳过明显无关的代码对象；一旦候选包含 `verdict` / `findings` 等 review
判别字段，就必须成功校验或抛出 `ReviewParseError`，不能继续回退。多候选选择时还应要求
显式 `verdict`，避免仅含 `findings` 的普通对象被当成完整 review。对应测试应改为断言格式
错误并触发重试。

### [P2] 同一行引号中的左花括号会遮蔽后续有效答案

位置：`wip/agents/deep_swe_agent/runtime/src/review-schema.ts:67`

扫描器只在已经见到左花括号后跟踪字符串状态。下面的有效输出无法解析：

```text
The token "{" is special; answer: {"verdict":"approve","findings":[]}
```

引号内的 `{` 被当成对象起点，其后的闭引号又被当成字符串起点，后续答案花括号一直被
屏蔽。当前“遇到 raw newline 结束字符串”的恢复逻辑只覆盖答案另起一行的情况。

建议让每个 `{` 候选独立扫描，或正确维护对象外的引号状态，并增加同一行“引号内花括号
与有效答案”的回归测试。

### [P2] 空的最新 resolutions 会回退到更早的陈旧报告

位置：`wip/agents/deep_swe_agent/runtime/src/review-schema.ts:188`

`parseResolutions()` 只有在解析出至少一个合法 item 时才返回。若 modifier 最新报告为：

```json
{"resolutions":[]}
```

函数会继续向前搜索，并可能返回 prompt 或前文中更早的 `accepted/rebutted` 状态。实测：

```text
Earlier {"resolutions":[{"id":"R1-F1","status":"accepted"}]}
Final {"resolutions":[]}
```

当前返回陈旧的 `R1-F1=accepted`。

建议找到最近的 `resolutions` 数组后立即停止：有合法项则返回；空数组或全部 item 无效时
返回 `null` 或空数组，但不能采用更早报告。

## 正面结论

- 倒序候选选择解决了首个 fence、prompt 模板和 patch 伪 JSON 抢占答案的问题。
- 外层 review 对象会晚于嵌套 finding 对象闭合，因此正常嵌套 JSON 的选择顺序正确。
- 字符串内花括号、转义字符、前置未闭合花括号和 fenced answer 均有新增测试覆盖。
- 错误信息优先保留离输出末尾最近的候选，诊断方向合理。
- 同一候选提取逻辑复用于 modifier resolutions，减少了两套解析逻辑分叉。

## 验证结果

| 检查项 | 结果 |
| --- | --- |
| runtime `npm test`（含 TypeScript build） | 61/61 通过 |
| 提交 diff 格式检查 | 通过 |
| 旧 approval + 无效新 verdict | 复现静默返回旧 approval |
| blocking review + 尾部 `{"findings":[]}` | 复现被覆盖为无 blocking findings |
| 同行引号内 `{` + 有效答案 | 复现 `no JSON object found` |
| 旧 resolutions + 最新空数组 | 复现返回旧 `accepted` |

## 建议实施顺序

1. 改为对最近的 review-shaped 候选 fail closed，修复错误批准路径。
2. 收紧多候选场景的 review 判别条件，并更新“invalid trailing object”测试。
3. 修复同行引号内花括号的扫描恢复。
4. 让最近的空/无效 resolutions 阻止向更早报告回退。
5. 运行完整 runtime 测试，并补一个 direct-engine 集成测试，确认无效最新 verdict 会进入
   retry，而不是产生 `approved` outcome。
