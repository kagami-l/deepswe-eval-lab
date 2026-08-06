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

## 处理情况（2026-08-06）

修复随本文档同一提交落地（`Fail closed on the reviewer's latest verdict`）。三条
finding 全部处理，四个复现场景已逐一复验。

- **P1 已处理**，但两个场景的定性不同，修复方式也不同：
  - 尾部无关对象覆盖 blocking review 是 `b24f724` 引入的安全回归。旧提取器对该输入
    会切出非法 JSON 直接报错，`b24f724` 把"报错重试"变成了"静默错误批准"，方向反了。
  - 回退到被推翻的旧 verdict 原本被当作有意设计写进了测试，现确认该判断有误：reviewer
    明确写出新 verdict 却格式无效时，正确响应是 `invalid_review_output` 加重试，而不是
    复活它刚推翻的结论。原测试已改为断言抛错。
  - 实现上以**最后一个带 `verdict` 字段的对象**为权威：它必须通过校验，否则抛出
    `ReviewParseError`，不再向前回退。没有任何候选带 `verdict` 时才退回"最后一个通过
    校验的对象"，以保留 schema 对无 verdict review 的容忍（findings 决定裁决）。
  - 未采用建议中"候选包含 `verdict` **或** `findings` 判别字段即须校验成功"的写法：
    那样 `{"findings":[]}` 会命中判别条件并直接抛错，把一个本可正确解析的 review 变成
    失败。用 `verdict` 单独作判别更准，也同时解决了这两个场景。
- **P2（同行引号内花括号）已处理**：改为在所有深度跟踪引号状态，与既有的"裸换行终止
  字符串"不变量配合——换行重置已把落单引号的影响限制在单行内，因此不再需要在深度 0
  放弃引号跟踪。未采用"每个 `{` 独立扫描"的方案，避免引入最坏 O(n²) 的重扫描。
- **P2（空 resolutions 回退）已处理**：按建议实现，找到最近的 `resolutions` 数组后立即
  停止，有合法项则返回，空数组或全部 item 无效时返回 `null`，不再向更早报告回退。
- **建议 5 已处理**：新增两个 direct-engine 集成测试，分别断言被推翻的 verdict 走重试
  而非 `approved`，以及尾部日志对象不会跳过 revision（并校验 revision prompt 中带有
  对应 finding id）。

### 复验结果

| 场景 | 修复前 | 修复后 |
| --- | --- | --- |
| 旧 approval + 无效新 verdict | 静默返回旧 `approve` | 抛 `ReviewParseError`（消息含 `maybe`） |
| blocking review + 尾部 `{"findings":[]}` | `verdict=null`，无 blocking | `verdict=revise`，保留 blocking |
| 同行引号内 `{` + 有效答案 | `no JSON object found` | 正确返回 `approve` |
| 旧 resolutions + 最新空数组 | 返回旧 `accepted` | 返回 `null` |

### 回归验证

本次修复收紧了裁决逻辑，因此重点确认没有把原本可解析的输出变成失败：

| 检查项 | 结果 |
| --- | --- |
| runtime `npm test`（含 TypeScript build） | 67/67 通过 |
| opencode reviewer 原始 finalText（含 prompt echo） | 23/23 解析成功 |
| opencode reviewer 剥离 prompt echo 后 | 23/23 解析成功 |
| codex reviewer 全部历史 raw | 58/58 解析成功 |
| 与已记录 `review.json` 的 verdict / findings 逐条比对 | 62/62 一致 |

### 后续复审补充（2026-08-06）

复审 `717dd9d` 时发现本次「fail closed」只覆盖了已成功 `JSON.parse` 的候选，语法损坏的
最新 verdict / resolutions 仍会回退旧结果，verdict-less 与嵌套对象也各留有一条错误批准
路径。这三条已在后续提交中处理，详见
[`20260806-201408-review-schema-fail-closed-followup-review-717dd9d.md`](./20260806-201408-review-schema-fail-closed-followup-review-717dd9d.md)。
