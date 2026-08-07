# collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833 结果分析

分析日期：2026-08-07。

原始工件：

- [job result](../../../jobs/collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833/result.json)
- [job config](../../../jobs/collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833/config.json)
- [run manifest](../../../jobs/.agent-eval-manifests/collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833.json)
- [全部 trial](../../../jobs/collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833/)

## 结论

本次 job 是一次完整、可计分的 Codex modifier + OpenCode/DeepSeek reviewer 协作运行。12 个任务各运行 2 次，共 24 个 trial；24/24 均完成 verifier，0 exception、0 retry、0 verifier RuntimeError，正式 reward 为：

- Trial-level Pass@1：`14 / 24 = 58.33%`。
- Task-level pass@2：`8 / 12 = 66.67%`。
- 6 个任务两次均通过：Anko、Arcane、Mobly、Tengo、Textual、TOMLKit。
- 2 个任务一过一败：Kombu、Prometheus。
- 4 个任务两次均失败：Clack、Cliffy、FastAPI、Go Critic。

与前一次同角色 job `unified-collab-05_sample_confirm-12-tasks-20260805-224241` 相比，运行时问题已经实质修复：OpenCode reviewer 的成功 attempt 从 `23/51` 提升到 `45/47`，timeout 从 28 次降到 2 次，JSON parse error 从 18 次降到 0；workflow outcome 从 23/24 degraded 恢复为 20 approved、3 max_reviews_reached、1 degraded。上一 job 的 24 个 verifier RuntimeError 也没有复现。

但评分侧没有显示协作带来净提升。与同一确认集的 standalone Codex job 相比，两者都是 `14/24`；本 job 的 task-level pass@2 反而从 `9/12` 降到 `8/12`，wall-clock 从约 4 小时 8 分增加到约 9 小时 52 分。单次、每题两样本不足以做稳定因果判断，但当前结果至少不支持“加入这个 reviewer 已提高总体通过率”。

剩余的核心问题也不再是 review JSON 或编排失败，而是 review 判断与 verifier 的差距：20 个 `approved` trial 中有 9 个 verifier reward 为 0。多数是 reviewer 在可见测试和自建探针上认为功能完整，但 verifier-side F2P 仍命中一个未覆盖的精确边界。

## 运行配置

| 项目 | 值 |
|---|---|
| 开始时间 | 2026-08-06 22:48:42 CST |
| 结束时间 | 2026-08-07 08:41:02 CST |
| 总 wall-clock | 约 9 小时 52 分 20 秒 |
| Pier | `0.3.0` |
| 任务数 / trials | 12 / 24（每题 2 次） |
| 并发 | 2 |
| Topology / workflow / engine | `collab / review-loop / direct` |
| Modifier | Codex `gpt-5.6-luna`，effort `xhigh`，permissions `bypass` |
| Reviewer | OpenCode `deepseek/deepseek-v4-flash`，effort `high`，permissions `auto` |
| Runtime | `deep-swe/agent-runtime:2c85b8fb96e280ea` |
| Runtime digest | `2c85b8fb96e280eab977b9c730be7a77ce9634c93a01793dc30fe188978419b6` |
| Task hard / soft deadline | 5400 / 5100 秒，cleanup reserve 300 秒 |
| Event-silence watchdog | 900 秒 |
| `maxAgentAttempts` / `maxReviews` | 2 / 3 |
| `minTurnSeconds` | 120 秒 |
| Reviewer / revision stage timeout | 未配置；turn 共享剩余 workflow 总预算 |
| Git commit | `5194794c061e59cdb12985d5080c980ef12b7d3c`，dirty=false |

本次最重要的配置差异是取消了旧 job 的固定 `reviewerTimeoutSeconds=600` 和 `revisionTimeoutSeconds=900`。Reviewer 和 revision turn 默认共享 5100 秒 workflow soft deadline 下的剩余预算；900 秒只用于“无事件”检测，不再把所有正常工作的 reviewer 在第 600 秒直接截断。

## 汇总指标

| 指标 | 值 |
|---|---:|
| Reward | 14 / 24（58.33%） |
| Task-level pass@2 | 8 / 12（66.67%） |
| Macro F2P | 96.54% |
| Macro P2P | 99.48% |
| Macro partial | 99.00% |
| Trial 执行时间合计 | 约 19 小时 19 分 |
| Agent 阶段时间合计 | 约 18 小时 36 分 |
| Verifier 时间合计 | 约 38 分 5 秒 |
| 平均 / 中位 trial 时间 | 48 分 17 秒 / 50 分 34 秒 |
| Pier 记录 input / output tokens | 428,032,294 / 2,782,643 |
| Pier 记录 cost | `$1.131239` |

Pier 的 cost 只来自 OpenCode reviewer；Codex modifier cost 为 `null`，所以 `$1.131239` 不是完整 job 成本。中断的两个 reviewer attempt 也各记录 0 token、0 tool use、null cost，仍会低估实际 reviewer 消耗。不同 adapter 的 input token 聚合语义也不完全相同，不宜据此直接比较模型成本效率。

## Task 级结果

`F2P`、`P2P` 为通过 node 数。Outcome 是协作编排结果，不是 verifier 判分。

| Task | Trial 1 | Trial 2 | pass@2 |
|---|---|---|---:|
| `anko-default-function-arguments` | `4QdKMdb`: 1，2/2，119/119，approved | `AYN5MhD`: 1，2/2，119/119，approved | 1 |
| `arcane-drift-detection-baselines` | `j5ZxGvX`: 1，82/82，2/2，approved | `tduG2uV`: 1，82/82，2/2，approved | 1 |
| `clack-async-autocomplete-options` | `ddnwt5p`: 0，81/82，643/643，approved | `t7AW9LD`: 0，81/82，643/643，approved | 0 |
| `cliffy-config-file-parsing` | `QG2fVMb`: 0，36/37，451/451，approved | `cQ7tP9d`: 0，36/37，451/451，approved | 0 |
| `fastapi-deprecation-response-headers` | `jbGvFZv`: 0，136/137，3134/3134，approved | `xCcgJ2J`: 0，136/137，3134/3134，approved | 0 |
| `go-critic-doc-link-checker` | `qG7JRk5`: 0，2/3，15/16，approved | `RGFqwkq`: 0，2/3，15/16，max reviews | 0 |
| `kombu-single-active-consumer-priority` | `UYS9QJ3`: 1，85/85，1421/1421，approved | `ZXz6KYJ`: 0，84/85，1421/1421，approved | 1 |
| `mobly-grouped-test-barriers` | `3JC3N3W`: 1，79/79，808/808，approved | `dHgC4b9`: 1，79/79，808/808，approved | 1 |
| `prometheus-typed-label-sorting` | `afHT2KR`: 1，17/17，28/28，degraded/timeout | `WtSqCjs`: 0，16/17，28/28，approved | 1 |
| `tengo-callable-instance-isolation` | `kPyvB8r`: 1，23/23，122/122，approved | `ahKpCiN`: 1，23/23，122/122，approved | 1 |
| `textual-richlog-follow-state` | `5SepKJv`: 1，20/20，6/6，approved | `ABqw2iA`: 1，20/20，6/6，approved | 1 |
| `tomlkit-toml-table-converters` | `SQgJiwu`: 1，60/60，964/964，max reviews | `Yoaiwcp`: 1，60/60，964/964，max reviews | 1 |

10 个失败 trial 全部是近失：其中 8 个只失败 1 个 F2P 且 P2P 全过；另外两个 Go Critic trial 都是 F2P 2/3、P2P 15/16。两次独立 patch 的哈希均不同，因此 Clack、Cliffy、FastAPI、Go Critic 的重复失败不是同一 patch 被重复计数，而是不同实现收敛到相同语义缺口。

## 各 trial 的 review / revision 轮次与最终状态

下表中的 `Review` 写成“启动轮次 / 有效 review 数”。通常两者相同；Prometheus `afHT2KR` 启动了 1 个 review round，但两个 attempts 都 timeout，未形成有效 review，因此为 `1 / 0`。`Revision` 采用 `summary.json` 的正式 `revisionCount`；三个 `max_reviews_reached` trial 的第 3 次 revision 是 `06-final-revision`，它会应用最后一次 review 后结束，不再进入第 4 次 review。

| Task / trial | Review（启动/有效） | Attempts（timeout） | Revision | 最后有效 verdict | Workflow 最终状态 | Reward |
|---|---:|---:|---:|---|---|---:|
| Anko `4QdKMdb` | 1 / 1 | 1（0） | 0 | approve | approved | 1 |
| Anko `AYN5MhD` | 2 / 2 | 2（0） | 1 | approve | approved | 1 |
| Arcane `j5ZxGvX` | 1 / 1 | 1（0） | 0 | approve | approved | 1 |
| Arcane `tduG2uV` | 2 / 2 | 2（0） | 1 | approve | approved | 1 |
| Clack `ddnwt5p` | 1 / 1 | 1（0） | 0 | approve | approved | 0 |
| Clack `t7AW9LD` | 3 / 3 | 3（0） | 2 | approve | approved | 0 |
| Cliffy `QG2fVMb` | 2 / 2 | 2（0） | 1 | approve | approved | 0 |
| Cliffy `cQ7tP9d` | 3 / 3 | 3（0） | 2 | approve | approved | 0 |
| FastAPI `jbGvFZv` | 1 / 1 | 1（0） | 0 | approve | approved | 0 |
| FastAPI `xCcgJ2J` | 1 / 1 | 1（0） | 0 | approve | approved | 0 |
| Go Critic `qG7JRk5` | 1 / 1 | 1（0） | 0 | approve | approved | 0 |
| Go Critic `RGFqwkq` | 3 / 3 | 3（0） | 3 | revise | max_reviews_reached | 0 |
| Kombu `UYS9QJ3` | 2 / 2 | 2（0） | 1 | approve | approved | 1 |
| Kombu `ZXz6KYJ` | 2 / 2 | 2（0） | 1 | approve | approved | 0 |
| Mobly `3JC3N3W` | 3 / 3 | 3（0） | 2 | approve | approved | 1 |
| Mobly `dHgC4b9` | 1 / 1 | 1（0） | 0 | approve | approved | 1 |
| Prometheus `afHT2KR` | 1 / 0 | 2（2） | 0 | — | degraded / timeout | 1 |
| Prometheus `WtSqCjs` | 3 / 3 | 3（0） | 2 | approve | approved | 0 |
| Tengo `kPyvB8r` | 2 / 2 | 2（0） | 1 | approve | approved | 1 |
| Tengo `ahKpCiN` | 2 / 2 | 2（0） | 1 | approve | approved | 1 |
| Textual `5SepKJv` | 1 / 1 | 1（0） | 0 | approve | approved | 1 |
| Textual `ABqw2iA` | 2 / 2 | 2（0） | 1 | approve | approved | 1 |
| TOMLKit `SQgJiwu` | 3 / 3 | 3（0） | 3 | revise | max_reviews_reached | 1 |
| TOMLKit `Yoaiwcp` | 3 / 3 | 3（0） | 3 | revise | max_reviews_reached | 1 |

汇总关系如下：

- 46 个 review round 被启动；其中 45 个形成有效、可解析 review，另 1 个 round 的两个 attempts 均 timeout。
- 47 个 reviewer attempts：45 success、2 timeout；没有因 retry 产生重复成功 attempt。
- 45 个有效 verdict：20 approve、25 revise。
- 25 次 revision：22 次普通 `revise` turn，加上 3 个 max-reviews trial 的 `final-revision`。
- 20 个 trial 最终 approved，3 个 max_reviews_reached，1 个 degraded/timeout。

按流程形态可分为：8 个 trial 首轮 approve、8 个经过 1 次 revision 后 approve、4 个经过 2 次 revision 后 approve、3 个在 3 次 review 后执行 final revision 并以 max_reviews_reached 结束，以及 1 个首轮 review 两次 timeout 后 degraded。最终状态与 reward 并不等价：9 个 approved trial reward=0，2 个 max_reviews_reached 和 1 个 degraded trial 反而 reward=1。

## 失败用例分析

### Clack：前一个 AbortController 没有真正进入 aborted 状态

两个 trial 都只失败：

`AutocompletePrompt - AbortController > previous AbortController is aborted when new fetch starts`

期望旧 controller 的 `signal.aborted === true`，实际仍是 `false`。第二个 trial 经历了两轮 revision，最终 reviewer 明确声称 abort/stale-result 生命周期正确，却仍遗漏了这个精确状态断言。这是本 job 最直接的 reviewer false approval。

### Cliffy：嵌套配置对象没有正确映射到 option

两个 trial 都只失败 `command - config - handles nested config objects`：期望解析得到 `"localhost"`，实际为 `undefined`。Reviewer 在 revision 后称 config 测试、precedence、kebab-case/camelCase、quoted value 等均已通过，但没有覆盖 verifier 对 nested object lookup 的路径。

### FastAPI：多层 include_router 的 nearest-wins precedence 错误

两个 trial 都只失败 `test_nested_include_router_overrides_at_every_level`。期望响应头为内层配置：

`Sun, 15 Jun 2031 12:00:00 GMT`

实际被外层值覆盖为：

`Tue, 01 Jan 2030 00:00:00 GMT`

两个最终 review 都是首轮 approve，summary 还分别称“all traced chains”和“inheritance at every level”正确；这说明 reviewer 的自建继承链没有复现 verifier 的 exact nesting/override 组合。

### Go Critic：file-local import 判断与目标语义相反

两个 trial 都没有为 `[strings.NewReader]`、`[strings.Replacer.Replace]` 产生预期诊断：

`package "strings" is not imported`

F2P 的 `TestCheckers/brokenDocLink` 因此失败，并连带使聚合 `TestCheckers` 计为 1 个 P2P 失败。`qG7JRk5` 被 reviewer approve；`RGFqwkq` 经 3 次 review 后仍是 revise/max_reviews_reached。后者 reviewer 关注的是 current-package 和未显式 import 的 stdlib doc-link false positive，和 verifier 要求严格 file-local import 校验的方向存在张力，说明 task 预期与 reviewer 采用的 go/doc 语义基准没有完全对齐。

### Kombu：非 SAC 队列的状态接口返回值不符合契约

`ZXz6KYJ` 只失败 `test_sac_status_none_for_non_sac`：普通队列应返回 `None`，实际返回包含 `active=None`、`consumer_count=None`、`standby=[]` 的状态字典。Reviewer 经一轮 revision 后称全部指定特性已端到端验证，未检查“非 SAC 队列必须返回 None”这一负向契约。

### Prometheus：等值 duration 的自然排序 tie-break 错误

`WtSqCjs` 只失败 `TestSortByLabelMultiTypeDurationOrdering`。`1h30m` 和 `90m` 数值相等时，期望自然字符串 tie-break 把 `1h30m` 放在 `90m` 前，实际顺序相反。Reviewer 经两轮 revision 后 approve，并明确称 typed-equal natural tie-break 正确，但自建回归 pair 没覆盖这个等值表示。

## Reviewer loop 健康度

### 正常工作的部分

| 指标 | 值 |
|---|---:|
| 完成的 review | 45 |
| Reviewer attempts | 47 |
| 成功 attempts | 45（95.74%） |
| Interrupted / timeout | 2（4.26%） |
| JSON parse errors | 0 |
| Review verdict | 20 approve / 25 revise |
| 执行 revisions | 25 |
| 产生 findings | 104，其中 blocking 35 |
| 有 revision 的 trials | 15 / 24 |
| Protocol violations | 0 |

15 个 trial 至少执行一次 revision，全部 revision turn 成功且都有变更；说明 review-loop 已经实际运转，而不是像上一 job 那样大多在首轮 reviewer timeout/parse error 后直接降级。修订过的 trial 通过 9/15，未修订 trial 通过 5/9；样本过小且没有相同初始 patch 的反事实，不能把这个差异解释为 revision 的因果收益。

Reviewer 成功 attempt 的耗时为：最短 238.977 秒，中位 627.659 秒，平均 652.491 秒，最长 1095.825 秒。45 个成功 attempt 中有 27 个超过 600 秒、4 个超过 900 秒。这直接证明旧的 600 秒固定 reviewer timeout 与 OpenCode/DeepSeek 的实际工作时长不匹配；若本次仍使用旧上限，至少这些完成结果都会在输出 JSON 前被截断。

### 唯一 degraded trial 的 timeout 原因

Prometheus `afHT2KR` 的首轮 review 两次 attempt 都中断，详见 [review metadata](../../../jobs/collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833/prometheus-typed-label-sorting__afHT2KR/agent/system/rounds/01-review/metadata.json) 和 [events](../../../jobs/collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833/prometheus-typed-label-sorting__afHT2KR/agent/system/rounds/01-review/events.jsonl)：

1. Attempt 1 运行 1495.717 秒后触发 `event_silence`。最后一个事件是 reviewer 启动 `go test ./promql/ ...`，命令自身 timeout 设为 900 秒；此后 899.949 秒没有新 OpenCode event，恰好命中 900 秒 silence watchdog。
2. Attempt 2 运行 1801.045 秒后触发 `total_deadline`。Reviewer 先有一个 300 秒测试命令超时，随后尝试 `go test -c` 并把命令 timeout 设为 600 秒；在继续编译/验证时耗尽 workflow 剩余总预算，未能形成 review JSON。

因此这不是 provider 无响应或 JSON 格式问题，而是 reviewer 在大型 Prometheus Go 编译和测试路径上反复投入长命令，没有在剩余总预算前收尾。最终 outcome 正确记录为 `degraded_reason=timeout`。该 trial 的 modifier patch 实际通过全部 verifier，所以 timeout 没有污染正式 reward，但浪费了约 55 分钟 reviewer wall time，且两次 interrupted usage 都被记为 0。

## Reviewer 与 verifier 的差距

Workflow outcome 不能作为 verifier reward 的代理：

- 20 个 approved 中只有 11 个 verifier 通过，9 个未通过；若把 approve 粗略当作“会通过 verifier”的预测，其本次精确率只有 `11/20 = 55%`。
- 2 个 TOMLKit trial 最终仍有 major finding、outcome 为 max_reviews_reached，却都通过 verifier。Reviewer 找到的是 verifier 未覆盖的嵌套 inline table / dotted-key round-trip 问题。
- Prometheus `afHT2KR` 没有有效 review、outcome degraded，却完整通过 verifier。

这不等于 reviewer 的 findings 没价值。它确实识别并推动修复了 35 个 blocking finding，而且 TOMLKit 的最终 major findings 看起来是具体、可复现的额外缺陷。问题在于 reviewer 的目标是通用代码审查，可见测试集与 verifier-side F2P 又不完全重合；因此“approve”只能表示未发现 major/critical，不能解释为隐藏测试必过。

对 9 个 approved-but-failed trial，最终 review summary 多次使用“fully correct”“all requirements verified”“all tests pass”等强断言。后续应要求 reviewer 明确区分：

- 已由现有测试验证；
- 由自建 probe 验证；
- 只经静态推断、尚未覆盖 exact boundary。

这会比单纯提高 review 次数更有助于暴露盲区。

## 与相关 job 对照

### 与上一轮同角色协作 job 对照

对照报告：[unified-collab-codex-opencode-05_sample_confirm-12-tasks-20260805-224241](unified-collab-codex-opencode-05_sample_confirm-12-tasks-20260805-224241.md)。上一 job verifier 环境整体失效，不能比较 reward，但可以比较 reviewer runtime：

| 指标 | 上一 job | 本 job |
|---|---:|---:|
| Reviewer attempts | 51 | 47 |
| 成功结束 | 23（45.1%） | 45（95.7%） |
| Timeout | 28（54.9%） | 2（4.3%） |
| Parse errors | 18 | 0 |
| Accepted reviews | 5 | 45 |
| Modifier revisions | 4 | 25 |
| Approved trials | 1 | 20 |
| Degraded trials | 23 | 1 |
| 有效 verifier | 0/24 | 24/24 |

改进来自几项可从本次工件验证的 runtime 变化：

1. [agent-runner.ts](../../agents/deep_swe_agent/runtime/src/agent-runner.ts) 将 OpenCode 首个 prompt echo 重标为 `runtime:prompt_echo`，不再把整段 prompt 混入 finalText。
2. [review-schema.ts](../../agents/deep_swe_agent/runtime/src/review-schema.ts) 从尾部检查候选对象并选择权威 verdict，同时对损坏/歧义输出 fail closed；本次 45 个成功输出全部解析。
3. Collab turn 默认共享 workflow 总预算，替代不适合当前 reviewer 速度的 600 秒固定 stage timeout。
4. Timeout 分类得到保留；本次 Prometheus 明确记录 `event_silence`、`total_deadline` 和最终 `degraded_reason=timeout`，不再笼统落为 `reviewer_failed`。

### 与 standalone Codex 基线对照

对照报告：[unified-codex-05_sample_confirm-12-tasks-20260805-130349](unified-codex-05_sample_confirm-12-tasks-20260805-130349.md)。两个 job 使用同一 12 题、Codex `gpt-5.6-luna` xhigh modifier、每题两次，但不是相同初始 patch 的配对实验：

| 口径 | Standalone Codex | 本 job |
|---|---:|---:|
| Reward | 14/24（58.33%） | 14/24（58.33%） |
| Task-level pass@2 | 9/12（75.00%） | 8/12（66.67%） |
| 两次均通过任务 | 5 | 6 |
| 至少一次通过任务 | 9 | 8 |
| Wall-clock | 约 4:08:29 | 约 9:52:20 |

任务覆盖发生了交换：本 job 相比 standalone 多通过 1 次 Mobly、2 次 TOMLKit；少通过 1 次 FastAPI、1 次 Go Critic、1 次 Prometheus，净 reward 为 0。TOMLKit 从 standalone 的 0/2 提升到 2/2，是最积极的协作信号；但同一批数据里 FastAPI 从 1/2 降到 0/2、Go Critic 从 1/2 降到 0/2、Prometheus 从 2/2 降到 1/2。

由于抽样不同、review revision 改变了 patch、runtime commit 也不同，不能断言 reviewer“导致”这些升降。更可靠的实验应保存同一个 modifier 初始 checkpoint，分别走 no-review 和 review-loop，再对最终 patch 做 verifier-only 配对评分。

## 建议

1. 将本 job 正式计为 `14/24`，coverage `24/24`；不需要 verifier-only 补分或排除任何 trial。
2. 将本 job 作为 OpenCode reviewer runtime 修复后的新基线：结构化输出问题可视为已修复，固定 600 秒 reviewer timeout 不应恢复。
3. 为 reviewer 的 shell 工具增加更短的单命令预算和剩余时间提示。大型仓库优先定向 compile/test；在剩余预算进入收尾阈值时停止探索并强制输出 review JSON。
4. 优先把六类失败用例加入 reviewer 可运行的定向 smoke tests：AbortController replacement、nested config object、nested include_router nearest-wins、file-local imports、non-SAC status、equal-duration tie-break。
5. 将 `approved-but-verifier-failed` 作为独立指标。本次为 `9/20`；它比 JSON parse rate 更能衡量 runtime 修复后 reviewer 的实际校验能力。
6. 对 TOMLKit 最终 review 的 major findings 单独建回归用例。它们未影响本轮 verifier reward，但可能是现有 verifier 的覆盖缺口，不应因 2/2 通过而忽略。
7. 若要判断 reviewer 是否提升分数，做初始 patch 配对实验，而不是继续比较独立随机 job：同一 checkpoint 分叉为直接 verifier 与 review-loop 两支，并记录每轮 revision 后的 verifier delta。
