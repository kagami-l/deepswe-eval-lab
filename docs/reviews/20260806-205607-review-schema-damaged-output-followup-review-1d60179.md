# Review Schema 损坏输出处理复审

- 评审时间：2026-08-06 20:56:07（Asia/Shanghai）
- 评审提交：`1d60179`（`Fail closed on damaged and ambiguous reviewer output`）
- 前次 Review：`docs/reviews/20260806-201408-review-schema-fail-closed-followup-review-717dd9d.md`
- 评审范围：前次 Review 的 2 个 P1、1 个 P2 处理情况，以及最新候选扫描逻辑的剩余边界

## 结论

本次提交的修复方向合理，也覆盖了前次 Review 中给出的四个具体复现场景：

- 有闭合花括号但 JSON 语法损坏的最新 verdict 不再复活旧 approval；
- 多个 verdict-less 候选不再静默选择尾部日志；
- 合法外层日志中的嵌套 verdict 不再覆盖正式 review；
- 有闭合花括号但语法损坏的最新 resolutions 不再回退旧报告。

但提交把 `{"verdict":"revise","findings":[}` 称为“truncated”，这个输入仍然有最终闭合
花括号，扫描器可以产出一个 balanced candidate。真正的 EOF 截断——整个对象缺少最终 `}`——
不会产生 candidate，因而仍会回退到更早的 approval。该路径位于最终交付裁决之前，触发后
可能错误批准，前次 P1 不能标记为完全处理。

此外，raw key 检测会把无效外层 region 中的嵌套 key 当成外层声明，`resolutions` 也保留了
同类 EOF 回退问题。本次复审结论为：主要修复有效，但仍有 **1 个 P1、2 个 P2**；可以继续
smoke 和小规模运行，建议在大批量无人值守运行前修复错误批准路径。

## Findings

### [P1] 真正 EOF 截断的最新 verdict 仍会回退旧 approval

位置：

- `wip/agents/deep_swe_agent/runtime/src/review-schema.ts:71`
- `wip/agents/deep_swe_agent/runtime/src/review-schema.ts:166`
- `wip/agents/deep_swe_agent/runtime/src/direct-engine.ts:536`

`jsonObjectCandidates()` 只在遇到 `}` 时产出候选。输入结束时，`opens` 中尚未闭合的 region
直接丢失；`parseReview()` 因而完全看不到最新 verdict，仍会采用较早的合法 approval：

```text
{"verdict":"approve","findings":[]}
Correction: {"verdict":"revise","findings":[]
```

实测当前返回 `verdict=approve`、`hasBlockingFindings=false`。Direct engine 随后在
`!review.hasBlockingFindings` 分支设置 `outcome=approved`，不会触发 `invalid_review_output`
重试。

新增测试使用的是：

```text
Correction: {"verdict":"revise","findings":[}
```

它是 balanced 但 JSON 非法的对象，只证明 `declaresKey()` 能处理“有 `}` 的损坏 region”，
没有覆盖注释所说的“losing the closing brace”。建议扫描结束时保留未闭合的最内层 raw region；
如果它在顶层声明 `verdict`，必须抛出 `ReviewParseError`。同时增加 schema 和 direct-engine
两层真正缺少最终 `}` 的回归测试。

### [P2] 无效外层 region 会把有效内层 review 误判为损坏 verdict

位置：

- `wip/agents/deep_swe_agent/runtime/src/review-schema.ts:116`
- `wip/agents/deep_swe_agent/runtime/src/review-schema.ts:129`
- `wip/agents/deep_swe_agent/runtime/src/review-schema.ts:176`

保留“被无法解析的外层 region 包含”的内层候选是合理的，它让散乱花括号中的真实答案仍然
可达。但候选按 closing position 倒序处理时，外层 region 位于内层之后；`declaresKey(raw,
'verdict')` 又会匹配外层 raw 中属于内层对象的 key：

```text
{broken
{"verdict":"approve","findings":[]}}
```

内层是合法、独立可解析的 review，当前却先检查无效外层并抛出 `ReviewParseError`。这不会
直接造成错误批准，但会产生一次不必要的格式重试；重试仍失败时会进入 degraded delivery。

建议让 `declaresKey()` 只识别候选顶层 key，或在已找到合法内层 review 时忽略仅通过嵌套内容
命中 key 的无效外层 region，并增加“balanced invalid outer + valid inner answer”测试。

### [P2] 真正 EOF 截断的最新 resolutions 仍会回退旧报告

位置：

- `wip/agents/deep_swe_agent/runtime/src/review-schema.ts:71`
- `wip/agents/deep_swe_agent/runtime/src/review-schema.ts:235`

`parseResolutions()` 与 verdict 共用候选扫描器，所以同样看不到没有最终 `}` 的最新报告：

```text
Earlier {"resolutions":[{"id":"R1-F1","status":"accepted"}]}
Final {"resolutions":[
```

实测当前仍返回较早的 `R1-F1=accepted`。提交中的测试 `Final {"resolutions":[}` 只覆盖
balanced damaged region，没有覆盖 EOF 截断。

该报告只进入下一轮 reviewer context，不直接决定最终 outcome，因此严重度低于 verdict 路径。
建议与 P1 共用 EOF candidate 修复：最近的未闭合 region 若在顶层声明 `resolutions`，立即返回
`null`，不能继续向前搜索。

## 已确认修复的内容

### Balanced damaged verdict

候选现在保留 raw、位置和解析结果。最新 balanced region 声明 `verdict` 但无法解析时，
`parseReview()` 会 fail closed，不再回退旧 approval。

### Verdict-less 多候选歧义

单个 verdict-less review 仍兼容；存在多个顶层对象且没有显式 verdict 时会抛错。该策略能
阻止尾部 `{"findings":[]}` 日志覆盖 earlier blocking review，且历史 81 份 reviewer raw
都带显式 verdict，因此兼容风险低。

### 合法外层对象中的嵌套 verdict

被可解析外层对象包含的 region 已从 eligible candidates 排除，尾部
`{"payload":{"verdict":"approve",...}}` 的内部 verdict 不会覆盖 earlier blocking review。

### Balanced damaged resolutions

最新 balanced region 声明 `resolutions` 但无法解析时，函数返回 `null`，不再复活旧报告。

## 验证结果

| 检查项 | 结果 |
| --- | --- |
| runtime `npm test`（含 TypeScript build） | 72/72 通过 |
| 前次 Review 的四个具体复现场景 | 均已修复 |
| 真正 EOF 截断 verdict | 仍返回旧 `approve` |
| 无效 balanced outer 包含合法 inner review | 抛 `ReviewParseError` |
| 真正 EOF 截断 resolutions | 仍返回旧 `accepted` |
| 提交记录的历史兼容回放 | 81/81 raw 可解析；62/62 可比结果一致 |

## 风险与处理建议

三个问题都位于 review 解析链路，但需要“同一成功 turn 中出现旧结果和特殊损坏的新结果”等
组合才能触发，现有历史输出也没有命中，因此属于核心位置上的低概率边界，不是当前常见故障。

- P1 的优先级来自触发后可能错误批准，而不是高发生频率；不阻塞 smoke，但建议批量运行前修复。
- 两个 P2 主要造成额外重试、degraded 或下一轮上下文失真，可与 P1 一并处理，不单独阻塞。

建议实施顺序：

1. 扫描结束时保留真正 EOF 未闭合的最内层候选。
2. 将 `verdict` / `resolutions` 的 raw key 检测限定在候选顶层。
3. 增加三个精确回归测试，其中 verdict 同时覆盖 direct-engine 重试路径。
4. 重跑 runtime 测试与历史 reviewer raw 回放，确认 fail-closed 收紧不影响兼容性。

## 处理情况（2026-08-06）

修复随本文档同一提交落地。3 条 finding 全部处理，前两轮 Review 的场景一并回归确认。

- **P1（EOF 截断的最新 verdict）已处理**：扫描结束时保留最内层未闭合区域，作为最后一个
  候选（它一直延伸到输出末尾）。指出的措辞问题属实——上次测试用的
  `{"findings":[}` 是 balanced 区域，注释却写成 “losing the closing brace”，两者不是同一
  回事。现已拆成两个测试分别覆盖"有闭合括号但语法损坏"和"真正缺少闭合括号"。
- **P2（无效外层误判内层 review）已处理**，但修法与建议不同，原因见下。
- **P2（EOF 截断的最新 resolutions）已处理**：与 verdict 共用同一候选扫描器，EOF 候选补上
  后自动覆盖；已补精确回归测试。

### 一个必须记录的中间失败

先按建议实现了"raw key 检测限定在候选顶层"（按花括号和方括号计算深度），单元测试全绿，
但历史回放从 23/23 掉到 **21/23**：Clack `v5VzvX5` 的两次 attempt 开始误报。

追查后发现根因不在 key 检测，而在 EOF 候选本身：那个未闭合区域并不是"被截断的答案"，
而是 **patch 代码里一个不配对的花括号开出的区域**，它一路延伸到输出末尾，把真正的 review
整个包在里面。引用代码中的方括号还会让深度计算漂移，使内层的 `"verdict"` 恰好落在深度 1。

因此改为按**结构**而非文本深度判定：**损坏区域若包含一个解析成功且带 `verdict` 的候选，
即判定为噪声，不作为"被截断的声明"**。这条规则同时解决了 P2 的无效外层误判——
`{broken\n{...}}` 正是"外层损坏、内层完整"的同一形态——因此不再需要依赖深度启发式来区分。
深度检测仍保留但改为只计花括号（JSON 对象的 key 必然直接位于 `{` 内，方括号与之无关）。

这个中间失败说明：对**引用代码构成的损坏区域**做结构推断本身不可靠，只有"里面是否存在
一个完整可解析的答案"这类基于解析结果的判据才稳。

### 复验结果

| 场景 | 修复前 | 修复后 |
| --- | --- | --- |
| 旧 approval + EOF 截断的新 verdict | 返回旧 `approve` | 抛 `ReviewParseError` |
| 无效 balanced 外层包含合法内层 review | 抛 `ReviewParseError` | 正确返回内层 `approve` |
| 旧 resolutions + EOF 截断的新报告 | 返回旧 `accepted` | 返回 `null` |
| 引用代码不配对花括号延伸至末尾 | （新增守护）| 正确返回内层 verdict |

前两轮 Review 的场景全部保持：balanced 损坏 verdict 抛错、非法 verdict 值抛错、尾部嵌套
approval 日志不覆盖、多候选无 verdict fail closed、未闭合括号在答案之前可解析、单个
verdict-less review 可接受。

### 回归验证

| 检查项 | 结果 |
| --- | --- |
| runtime `npm test`（含 TypeScript build） | 76/76 通过 |
| opencode reviewer 原始 finalText（含 prompt echo） | 23/23 解析成功 |
| opencode reviewer 剥离 prompt echo 后 | 23/23 解析成功 |
| codex reviewer 全部历史 raw | 58/58 解析成功 |
| 与已记录 `review.json` 的 verdict / findings 逐条比对 | 62/62 一致 |
