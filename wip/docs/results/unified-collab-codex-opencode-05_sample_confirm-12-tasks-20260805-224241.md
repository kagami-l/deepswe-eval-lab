# unified-collab-codex-opencode-05_sample_confirm-12-tasks-20260805-224241 结果分析

分析日期：2026-08-06。

原始工件：

- [job result](../../../jobs/unified-collab-05_sample_confirm-12-tasks-20260805-224241/result.json)
- [job config](../../../jobs/unified-collab-05_sample_confirm-12-tasks-20260805-224241/config.json)
- [run manifest](../../../jobs/.agent-eval-manifests/unified-collab-05_sample_confirm-12-tasks-20260805-224241.json)

## Reviewer 异常结论

本 job 使用 Codex `gpt-5.6-luna` 作为 modifier，OpenCode `deepseek/deepseek-v4-flash` 作为 reviewer。24 个 trial 均产生了非空 `model.patch`，但 review-loop 只有 1 个 trial 记录为 `approved`，另外 23 个记录为 `degraded`：13 个 `reviewer_failed`，10 个 `invalid_review_output`。

详细检查表明这里有两类独立问题：

1. reviewer turn 真实触发了 600 秒硬超时；
2. `invalid_review_output` 全部是 OpenCode 事件归一化与本地 JSON 提取逻辑共同造成的误判，不是 reviewer 最终没有给出合法 review JSON。

## Reviewer attempt 统计

24 个 trial 共触发 51 次 reviewer attempt：

| 状态 | 次数 |
|---|---:|
| reviewer 进程成功结束 | 23 |
| 600 秒硬超时 | 28 |
| 成功结束但被判 JSON 无效 | 18 |
| 成功结束且成功解析 | 5 |

最终 workflow outcome：

| Outcome | Trial 数 |
|---|---:|
| `approved` | 1 |
| `degraded / reviewer_failed` | 13 |
| `degraded / invalid_review_output` | 10 |

16/24 个 trial 至少发生过一次 reviewer timeout。13 个 `reviewer_failed` 中，12 个是在相应 review round 的两次 attempt 都超时；剩余 1 个 TOMLKit trial `Us6UVR4` 是第一次成功返回但被误判为非法 JSON，第二次重试才超时。

## Timeout 原因

Job 配置为：

| 参数 | 值 |
|---|---:|
| `reviewerTimeoutSeconds` | 600 秒 |
| `eventSilenceTimeoutSeconds` | 900 秒 |
| `maxAgentAttempts` | 2 |

28 次 timeout 的实际时长为 599.802–602.662 秒，中位数 600.098 秒，明确对应 reviewer 的 600 秒硬超时，而不是随机退出。成功结束的 23 次 reviewer attempt 中位耗时已经达到 476.010 秒，最长 598.722 秒，因此 600 秒几乎没有用于整理最终结果的余量。

28 次 timeout 中有 23 次在结束前 10 秒内仍有 reviewer 事件。它们通常仍在读代码、设计探针、运行测试或反复核对边界条件，并非服务无响应。Anko、Tengo、Textual、Go-critic 等任务的中断轨迹都停在继续调查的自然语言推理中。

少数 attempt 确实在工具调用中长时间没有新事件：

- Kombu `iUc5G6h/review-1-a1`：最后一次读取操作后约 536 秒没有事件，超时清理时相关进程已是 zombie；
- Textual `kpaeoYF/review-1-a1`：测试命令约 168 秒没有返回，清理时终止 3 个子进程；
- Prometheus `3BEVDQv/review-1-a2`：测试命令约 116 秒没有返回，清理时终止 3 个子进程；
- Arcane `JVFvgR6/review-1-a1`：`go vet` 等待约 53 秒后撞上总时限。

`eventSilenceTimeoutSeconds=900` 大于 reviewer 的 600 秒硬超时，因此 event-silence watchdog 不可能先于硬超时触发，对上述工具停滞没有实际保护作用。

当前编排还把所有 `result.ok == false` 统一归类为 `reviewer_failed`，没有优先检查 `result.timedOut`。因此原始 metadata 中虽然清楚记录了 `status=interrupted`、`timedOut=true` 和约 600 秒 duration，最终 `degraded_reason` 仍是 `reviewer_failed`，掩盖了真实原因。

## `invalid_review_output` 的真实原因

OpenCode adapter 的第一条 `text` 事件是完整 reviewer prompt，随后才是 reviewer 的分析和最终回答；`done` 事件中的 `result` 又为空。Runner 因而回退到拼接所有 `text` 内容，交给 `parseReview` 的 `finalText` 实际形如：

```text
<完整 reviewer prompt>
<task 与 patch 中的代码/JSON 示例>
<reviewer 分析>
<最终合法 review JSON>
```

JSON 提取器优先选择第一个无语言/JSON fenced object，否则选择第一个 `{` 到最后一个 `}`。当 prompt、task 或 patch 中已有对象时，它就会解析错误的候选内容，而不是末尾的 review JSON。

原始失败形态包括：

- Cliffy：末尾有合法的 `{"verdict":"revise",...}`，但解析器先选中前面的代码对象，报 `Expected property name or '}' at position 2`；
- Prometheus：末尾是一行严格合法的 review JSON，仍因完整 prompt 位于前面而失败；
- FastAPI：prompt 中有 `{"deprecated_hits": int, "sunset_hits": int}` 这样的类型示例，解析器先选中它并报 `Unexpected token 'i'`；
- Mobly：解析器选中前面的 `{}`/代码片段，随后遇到更多字符，报 `Unexpected non-whitespace character after JSON`；
- TOMLKit：解析器选中 Python 风格的 `{"enabled": True}`，报 `Unexpected token 'T'`。

可直接核对 [Cliffy 原始返回](../../../jobs/unified-collab-05_sample_confirm-12-tasks-20260805-224241/cliffy-config-file-parsing__i4SCz7D/agent/system/rounds/01-review/review-raw-a2.txt)、[Prometheus 原始返回](../../../jobs/unified-collab-05_sample_confirm-12-tasks-20260805-224241/prometheus-typed-label-sorting__XUosyjD/agent/system/rounds/01-review/review-raw-a2.txt) 和 [FastAPI 原始返回](../../../jobs/unified-collab-05_sample_confirm-12-tasks-20260805-224241/fastapi-deprecation-response-hea__Bhffo46/agent/system/rounds/01-review/review-raw-a2.txt)。

对全部 18 次 parse-error attempt 从文本末尾反向查找并重新按 review schema 验证，18/18 都能恢复出合法 review JSON。因此这批 `invalid_review_output` 是 100% 的解析误判。

## 恢复出的 review 结果

10 个最终标记为 `invalid_review_output` 的 trial，按最后一次 attempt 的实际 JSON 恢复如下：

| Trial | 恢复 verdict | Findings | 本应发生的流程 |
|---|---|---:|---|
| Arcane `JVFvgR6` | `approve` | 4 个非阻塞 | `approved` |
| Clack `3iEPjPP` | `approve` | 0 | `approved` |
| Clack `v5VzvX5` | `approve` | 3 个非阻塞 | `approved` |
| Cliffy `i4SCz7D` | `revise` | 2 | 进入 modifier revision |
| FastAPI `Bhffo46` | `approve` | 2 个非阻塞 | `approved` |
| FastAPI `uNNDZiY` | `approve` | 5 个非阻塞 | `approved` |
| Mobly `LkpGtQ2` | `revise` | 1 个 major | 进入下一次 revision |
| Mobly `oC6R6Uj` | `approve` | 1 个 suggestion | `approved` |
| Prometheus `XUosyjD` | `approve` | 2 个 suggestion | `approved` |
| TOMLKit `twxSpwf` | `revise` | 3 | 进入 modifier revision |

其中 7 个本应直接批准，3 个本应进入 revision。另一个最终标记为 `reviewer_failed` 的 TOMLKit `Us6UVR4`，第一次 attempt 也能恢复出 `revise` 和 5 个 findings；它同样是先被误解析，重试才超时。

这意味着至少 4 个带 blocking findings 的有效 review 被丢弃，没有触发本应执行的 modifier revision：Cliffy `i4SCz7D`、Mobly `LkpGtQ2`、TOMLKit `twxSpwf` 和 TOMLKit `Us6UVR4`。

## 指标影响

1. `approved=1/24` 严重低估 reviewer 的实际批准情况。
2. 28 次 timeout 的 terminal usage 均为 0，job 中 reviewer token 和 cost 明显少算。
3. `reviewer_failed` 混合了硬超时、进程/工具失败以及“解析误判后重试再超时”，不能作为单一错误类别比较。
4. 10 个 `invalid_review_output` 不能用于评价 DeepSeek 的格式遵循率；从保留的最终回答看，18 次相关 attempt 都生成了可恢复的合法 JSON。

## 修复建议

1. OpenCode 事件归一化必须过滤 prompt echo 和累计 transcript，只把最终 assistant answer 交给 `parseReview`。
2. JSON 提取应从末尾寻找最后一个可解析且通过 review schema 的完整对象，不能使用第一个 fence 或第一个 `{`。
3. 增加包含 prompt pseudo-JSON、patch 代码对象、推理文本和末尾合法 JSON 的回归测试。
4. `result.timedOut=true` 时应记录 `degraded_reason=timeout`，并保留更细的 `turn_timeout` 原因。
5. 修复解析问题后再调整 timeout；当前可把 reviewer turn 提高到约 900 秒，同时把 event-silence watchdog 调低至 240–300 秒，并对测试命令设置独立上限。
6. timeout 时应保留部分 usage；当前将所有 interrupted attempt 记为 0 会系统性低估协作成本。

## 与 Codex reviewer job 的对比

对照 job 为 [unified-collab-opencode-codex-05_sample_confirm-12-tasks-20260804-200817](unified-collab-opencode-codex-05_sample_confirm-12-tasks-20260804-200817.md)：OpenCode `deepseek/deepseek-v4-flash` 做 modifier，Codex `gpt-5.6-luna` 做 reviewer。两个 job 使用相同的 12 个 confirm task、每题两次 trial、`maxAgentAttempts=2`、`maxReviews=3`、600 秒 reviewer turn timeout、900 秒 revision timeout和 5100/5400 秒 workflow soft/hard budget。

两次运行不是纯 reviewer A/B：modifier 与 reviewer 同时互换，生成的 patch 也不同；runtime image 从 `e87ec83987608685` 更新到 `12129eb84c44eb9d`。因此只能比较两个完整协作系统在这两次运行中的行为，不能把所有差异单独归因给模型。

### Reviewer 执行统计

| 指标 | Codex reviewer | OpenCode reviewer |
|---|---:|---:|
| 进入 reviewer 的 trial | 21 | 24 |
| Review round 目录 | 45 | 28 |
| Reviewer attempts | 57 | 51 |
| 成功结束 attempts | 39（68.4%） | 23（45.1%） |
| Timeout attempts | 18（31.6%） | 28（54.9%） |
| 至少一次 timeout 的 trial | 12 | 16 |
| 有成功 attempt 的 review round | 39/45（86.7%） | 16/28（57.1%） |
| 成功且被 parser 接受的 round | 39 | 5 |
| Parse errors | 0 | 18 attempts / 11 rounds |
| 编排记录的 accepted reviews | 39 | 5 |
| 执行的 modifier revisions | 29 | 4 |

Codex reviewer 并非没有 timeout。它有 18 次 interrupted attempt，涉及 12 个 trial；其中 7 个 review round 在第二次 attempt 成功恢复，另有 6 个 review round 最终没有成功结果。5 个 trial 最终因此记录为 `degraded/reviewer_failed`，另有一个 Textual review round 受 workflow 剩余预算限制后记录为 `degraded/timeout`。

OpenCode reviewer 有 12 个 review round 的两次 attempt 都没有成功结束。另有 3 个 first-attempt timeout 后 second-attempt 成功的 round，但成功结果又被 JSON parser 误判。也就是说，它既有更高的 turn timeout 比率，又没有从 retry 中获得应有的恢复收益。

### 速度并不是主要差异

| 成功 attempt duration | Codex reviewer | OpenCode reviewer |
|---|---:|---:|
| 最短 | 340.218 秒 | 317.075 秒 |
| 中位数 | 472.506 秒 | 476.010 秒 |
| 平均 | 479.190 秒 | 471.989 秒 |
| 最长 | 597.987 秒 | 598.722 秒 |

两者成功 attempt 的耗时分布几乎相同，都非常接近 600 秒上限。Codex reviewer 看起来更顺利，不是因为其成功 review 明显更快，而是因为：

1. 它更经常能在 600 秒内完成，而不是被硬超时切断；
2. 一旦完成，返回文本能被现有 parser 稳定提取；
3. timeout 后第二次 attempt 的恢复率更高；
4. 成功解析 review 后 workflow 能继续 revision/review，而不是第一轮就退化交付 checkpoint。

### 输入大小不能解释 OpenCode 的更高 timeout

Codex reviewer 实际面对的 patch 和 prompt 更大：

| 输入大小 | Codex reviewer | OpenCode reviewer |
|---|---:|---:|
| Patch 中位数 | 47,046 bytes | 24,986 bytes |
| Patch 平均 | 53,760 bytes | 26,171 bytes |
| Prompt 中位数 | 53,144 bytes | 28,915 bytes |
| Prompt 平均 | 59,134 bytes | 30,728 bytes |

虽然 Codex reviewer 的 patch/prompt 大约是 OpenCode reviewer 的两倍，它仍有更高的 attempt 完成率。因此本次差异不能用“Codex modifier 产生的 patch 更大、更难审”解释；证据更支持 reviewer 的行为模式和 adapter 事件/结果归一化差异。

### Codex adapter 为什么不会污染 JSON

Codex reviewer 的成功原始输出只有 382–4,153 bytes，中位数 2,004 bytes、平均 2,154 bytes。典型事件顺序是：

```text
init
text: "I’m inspecting the implementation..."
text: "{ \"verdict\": ... }"
done: success
```

它不会把 reviewer prompt 作为 `text` 事件回传。39 份成功 raw 中有 32 份在 JSON 前包含简短进度说明，只有 7 份真正以 `{` 开头；所以 Codex 也没有严格做到“ONLY JSON”。但进度说明中没有其他对象，当前 parser 取第一个 `{` 到最后一个 `}` 时恰好得到最终 review JSON，39/39 都成功解析。

例如 [Anko 的 Codex review raw](../../../jobs/unified-collab-05_sample_confirm-12-tasks-20260804-200817/anko-default-function-arguments__SvgJuDM/agent/system/rounds/01-review/review-raw-a1.txt) 只有一句进度说明和一个 247 字符左右的最终 JSON，没有 prompt echo。

OpenCode reviewer 的成功 raw 为 26,198–68,308 bytes，中位数 35,342 bytes、平均 38,016 bytes。23/23 份都以完整的 `You are an independent code reviewer...` prompt 开头。由于 prompt 和 patch 本身包含大量 `{}`、pseudo-JSON 和代码块，当前 parser 无法可靠定位末尾结果。

因此，Codex 的“格式很顺”主要是 adapter 输出契约与当前 parser 恰好兼容；OpenCode 的失败则主要是 adapter 把 prompt/transcript 混入 `finalText` 后，parser 仍假设输入接近单一 final answer。这不是单纯的模型格式遵循能力差异。

### Reviewer 行为差异

OpenCode/DeepSeek 的轨迹公开了连续的 `text_delta`、thinking 和大量工具事件。多数 timeout attempt 在最后几秒仍在继续探索或追加验证，没有给最终结构化输出预留时间。Codex 的事件流更稀疏，timeout attempt 的最后可见事件通常距中断数分钟；由于 Codex adapter 不暴露等价的工具事件，无法判断这些时间是在内部推理、执行工具还是等待进程，不能把事件静默直接解释为 Codex 卡死。

从最终结果看，Codex 对 review-loop 更友好的行为是：以较短的 progress 文本开场，完成检查后一次性给出小而完整的 JSON。OpenCode/DeepSeek 则把完整上下文和长过程暴露到 `text` 流中，并更频繁地持续检查到硬 deadline。

### Runtime 差异是否是原因

两个 job 使用不同的 content-addressed runtime image，但依赖声明和 reviewer prompt/parser 源码在两次对应 Git commit 之间没有变化；主要 runtime 变化是增加 event-silence 诊断和 turn 进程树清理。Reviewer timeout 仍是 600 秒，JSON 提取算法也相同。

旧 job 的 `eventSilenceTimeoutSeconds=600`，新 job 为 900；但 reviewer 自身硬 timeout 同样是 600 秒，因此两者 reviewer turn 都主要由硬 timeout 截断。这一差异不能解释 0 对 18 的 parse-error 差距。

所以 runtime 版本是实验混杂因素，需要在后续正式 A/B 中冻结；但现有原始事件已经直接证明：本次 JSON 差异来自 Codex/OpenCode adapter 输出形态与 parser 的相容性，而不是新版 runtime 的进程清理功能。

### 对比结论

Codex reviewer job 的 review-loop 确实比 OpenCode reviewer job 顺利，但应拆成两部分理解：

1. **模型/agent 完成率优势**：Codex attempt 成功率 68.4%，OpenCode 为 45.1%；在更大的 patch/prompt 下 Codex 仍更常在 600 秒内完成。
2. **集成兼容性优势**：Codex 的成功输出 39/39 可解析；OpenCode 的 18 次 parse error 实际都带有合法末尾 JSON，只是被 prompt echo 和错误候选提取误杀。这部分差距属于 adapter/parser bug，不应计入模型质量。

修复 OpenCode final-answer 提取后，它当前 28 个 review round 中至少有 16 个 round 已存在成功且可恢复的 review，而不是记录的 5 个；但仍有 12 个 round 两次 attempt 都没有在预算内成功，timeout/收尾问题仍需独立处理。
