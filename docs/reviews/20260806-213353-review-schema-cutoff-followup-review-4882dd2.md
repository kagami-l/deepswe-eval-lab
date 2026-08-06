# Review Schema EOF 候选修复复审

- 评审时间：2026-08-06 21:33:53（Asia/Shanghai）
- 评审提交：`4882dd2`（`Keep a cut-off answer visible to the review parser`）
- 前次 Review：`docs/reviews/20260806-205607-review-schema-damaged-output-followup-review-1d60179.md`
- 评审范围：前次 Review 的 1 个 P1、2 个 P2 处理情况，以及 EOF 候选和噪声豁免的新边界

## 结论

最新提交正确区分了 balanced damaged region 和真正 EOF 截断，补上了顶层 verdict、顶层
resolutions 的 EOF 候选，并修复了普通无效外层 region 包含完整答案的误报。历史 patch
噪声场景也增加了守护测试，修复方向总体合理。

但 EOF 扫描只保留最内层未闭合 region。若截断发生在 finding / resolution item 内，真正
拥有 `verdict` / `resolutions` 的外层对象仍会消失，继续恢复旧结果。此外，
`wrapsIntactVerdict()` 的豁免范围过大：损坏候选即使拥有自己的顶层 verdict，只要内部存在
另一个完整 verdict，也会被当作噪声跳过，可能直接采用嵌套 approval。

本次复审发现 **2 个 P1、1 个 P2**。当前提交不能将前次 finding 全部标记完成。

## Findings

### [P1] 嵌套 finding 内 EOF 截断仍会恢复旧 approval

位置：

- `wip/agents/deep_swe_agent/runtime/src/review-schema.ts:94`
- `wip/agents/deep_swe_agent/runtime/src/review-schema.ts:232`
- `wip/agents/deep_swe_agent/runtime/src/direct-engine.ts:536`

扫描结束时只执行：

```ts
makeCandidate(text, opens[opens.length - 1], text.length)
```

因此只保留最内层未闭合对象。下面的最新 review 在 finding 中截断时，最内层候选只有
`severity` / `issue`，不包含 verdict；拥有 `verdict=revise` 的外层 review 被丢弃：

```text
{"verdict":"approve","findings":[]}
Correction: {"verdict":"revise","findings":[{"severity":"major","issue":"x"
```

实测当前返回旧 `approve`、`hasBlockingFindings=false`，direct engine 会进入 approved 分支。

建议在 EOF 时保留完整的未闭合 ancestor 链，并让 key 检测识别每个候选自己的顶层字段。
需要增加 schema 与 direct-engine 两层嵌套截断测试。

### [P1] 完整的嵌套 verdict 会错误豁免拥有顶层 verdict 的损坏 review

位置：

- `wip/agents/deep_swe_agent/runtime/src/review-schema.ts:149`
- `wip/agents/deep_swe_agent/runtime/src/review-schema.ts:247`

`wrapsIntactVerdict()` 只要发现候选内部存在任意可解析且带 verdict 的对象，就把整个损坏候选
视为噪声，没有确认损坏候选命中的 verdict 是否真正来自该子对象：

```text
{"verdict":"revise","findings":[oops {"verdict":"approve","findings":[]}]}
```

外层明确拥有顶层 `verdict=revise`，但语法损坏；当前实现跳过外层并返回嵌套 `approve`。
实测结果为 `approve`、无 blocking finding。

建议把豁免绑定到 key 的具体位置：若命中的 key 位于完整子候选范围内，可以视为包裹噪声；
若损坏候选在子候选之外拥有自己的顶层 verdict，必须 fail closed。

### [P2] 嵌套 resolution item 内 EOF 截断仍会恢复旧报告

位置：

- `wip/agents/deep_swe_agent/runtime/src/review-schema.ts:94`
- `wip/agents/deep_swe_agent/runtime/src/review-schema.ts:305`

同一个最内层候选问题也影响 modifier resolutions：

```text
Earlier {"resolutions":[{"id":"R1-F1","status":"accepted"}]}
Final {"resolutions":[{"id":"R1-F1","status":"rebutted"
```

当前返回旧 `R1-F1=accepted`，而不是 `null`。应在保留 EOF ancestor 链后，让最近的外层
`resolutions` 声明阻止继续向前回退。

## 已确认合理的处理

- 顶层 EOF 截断 verdict 会抛出 `ReviewParseError`，direct engine 会重试而非批准。
- 顶层 EOF 截断 resolutions 会返回 `null`。
- balanced damaged region 与 EOF cut-off 已拆分测试，测试名称和实际输入一致。
- 普通 invalid outer + valid inner review 已恢复为选择内层合法答案。
- 历史 patch 不配对花括号延伸到输出末尾的场景已有守护测试。
- 提交记录的历史回放保持 23/23 OpenCode、58/58 Codex raw 可解析，62/62 可比结果一致。

## 验证结果

| 检查项 | 结果 |
| --- | --- |
| runtime `npm test`（含 TypeScript build） | 76/76 通过 |
| 顶层 EOF verdict / resolutions | 已修复 |
| finding 内 EOF verdict | 仍返回旧 `approve` |
| 损坏顶层 revise + 嵌套完整 approve | 错误返回嵌套 `approve` |
| resolution item 内 EOF | 仍返回旧 `accepted` |

## 建议实施顺序

1. EOF 时按 innermost → outermost 顺序加入全部未闭合候选，使倒序裁决先看外层声明。
2. 用候选位置范围排除属于嵌套候选的 key，不再使用宽泛的 `wrapsIntactVerdict()` 豁免。
3. 为三个复现场景增加 schema 测试，并给嵌套 verdict EOF 增加 direct-engine 集成测试。
4. 重跑完整 runtime 测试和历史 raw 回放。

## 处理情况（2026-08-06）

上述 2 个 P1、1 个 P2 已在工作区处理：

- EOF 扫描现在按 innermost → outermost 顺序保留全部未闭合 ancestor。倒序裁决会先看到
  拥有 `verdict` / `resolutions` 的外层声明，不再因最内层 finding/item 缺少 key 而回退。
- 删除宽泛的 `wrapsIntactVerdict()` 豁免。`declaresOwnKey()` 仍要求对象深度为 1，同时用
  candidate 的绝对位置范围排除嵌套候选中的 key；历史 patch 噪声中的 verdict 因属于完整
  内层 candidate 而被忽略，损坏 review 自己的顶层 verdict 则继续 fail closed。
- 新增 3 个 schema 回归测试，分别覆盖 finding 内 EOF、损坏 owning verdict 包含完整嵌套
  approval、resolution item 内 EOF；另增加 1 个 direct-engine 集成测试确认嵌套 EOF 会重试。

### 修复后验证

| 检查项 | 结果 |
| --- | --- |
| runtime `npm test`（含 TypeScript build） | 80/80 通过 |
| OpenCode reviewer 原始 finalText（含 prompt echo） | 23/23 解析成功 |
| OpenCode reviewer 精确剥离 prompt echo 后 | 23/23 解析成功 |
| Codex reviewer 全部历史 raw | 58/58 解析成功 |
| 与已记录 `review.json` 的 verdict / findings 比对 | 62/62 一致 |
| 提交 diff 格式检查 | 通过 |
