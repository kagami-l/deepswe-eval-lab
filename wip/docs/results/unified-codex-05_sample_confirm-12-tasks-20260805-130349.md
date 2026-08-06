# unified-codex-05_sample_confirm-12-tasks-20260805-130349 结果分析

分析日期：2026-08-05。

原始工件：

- [job result](../../../jobs/unified-codex-05_sample_confirm-12-tasks-20260805-130349/result.json)
- [job config](../../../jobs/unified-codex-05_sample_confirm-12-tasks-20260805-130349/config.json)
- [run manifest](../../../jobs/.agent-eval-manifests/unified-codex-05_sample_confirm-12-tasks-20260805-130349.json)
- [全部 trial](../../../jobs/unified-codex-05_sample_confirm-12-tasks-20260805-130349/)

## 结论

本次 job 完成了 `05_sample_confirm.txt` 中 12 个任务的两次独立 trial，共 24 个 trial。所有 trial 都正常结束并得到有效 verifier reward；没有 Pier exception、retry、watchdog timeout、provider/verifier/network 异常或空 patch。24 个 unified workflow 均记录为 `outcome=completed`、`deliverable=true`。

- Trial-level Pass@1：`14 / 24 = 58.33%`。
- 12 个任务中有 9 个至少一次通过，手工计算 task-level pass@2：`9 / 12 = 75.00%`。
- 5 个任务两次均通过：`anko-default-function-arguments`、`arcane-drift-detection-baselines`、`prometheus-typed-label-sorting`、`tengo-callable-instance-isolation`、`textual-richlog-follow-state`。
- 4 个任务一过一败：`fastapi-deprecation-response-headers`、`go-critic-doc-link-checker`、`kombu-single-active-consumer-priority`、`mobly-grouped-test-barriers`。
- 3 个任务两次均失败：`clack-async-autocomplete-options`、`cliffy-config-file-parsing`、`tomlkit-toml-table-converters`。

Pier aggregate reward `0.5833333333` 与 `14/24` 一致。因为 24 个 trial 均有有效评分，本 job 不需要调整分母，也没有合理的 infrastructure retry 对象。

## 运行配置

| 项目 | 值 |
|---|---|
| 开始时间 | 2026-08-05 13:03:57 CST |
| 结束时间 | 2026-08-05 17:12:26 CST |
| 总 wall-clock | 约 4 小时 8 分钟 29 秒 |
| Pier | `0.3.0` |
| 任务数 | 12 |
| 每任务 trials | 2 |
| 总 trials | 24 |
| 并发 | 2 |
| Workflow | `single / single / direct` |
| Agent adapter | Codex，benchmark mode，permissions bypass |
| 模型 | `gpt-5.6-luna`，effort `xhigh` |
| Reviewer | 无 |
| Runtime | `deep-swe/agent-runtime:12129eb84c44eb9d` |
| Runtime digest | `12129eb84c44eb9d0f90ae8ae9c999c439b132e37c5ed92c0be5c946bd58b708` |
| Runtime image ID | `sha256:854a1eedc3d79fdff96bc1bd848b9d4a0015af381cd886f1ac2e3da1771f1e89` |
| Runtime platform | `linux/amd64`，manifest 匹配 |
| Task hard timeout | 5400 秒 |
| Workflow soft deadline | 5100 秒，cleanup reserve 300 秒 |
| Event-silence watchdog | 900 秒 |
| 每个 turn 内 Agent 尝试 | 最多 2 次 |
| Review 上限 | 0 |
| Agent network | provider-only：`api.openai.com`、`auth.openai.com`、`chatgpt.com` |
| Git commit | `97d0241ce9ec4aab0359928ef085da6fb0088c32`，dirty worktree |

Run manifest 中的 dirty 状态只列出 `wip/data/selection/05_sample_dev.txt` 及其 `.bk` 文件的修改，不涉及本次使用的 `05_sample_confirm.txt`。

## 汇总指标

| 指标 | 值 |
|---|---:|
| Reward | 14 / 24（58.33%） |
| Task-level pass@2 | 9 / 12（75.00%） |
| Macro F2P | 97.09% |
| Macro P2P | 99.74% |
| Macro partial | 99.44% |
| Agent 执行时间合计 | 约 7 小时 17 分钟 |
| 平均 / 中位 Agent 时间 | 18 分 13 秒 / 17 分 52 秒 |
| 平均 / 中位 trial 时间 | 20 分 3 秒 / 19 分 45 秒 |
| Verifier 时间合计 | 约 38 分 42 秒 |
| 记录的总 input / cache / output tokens | 186,728,957 / 0 / 1,048,752 |
| 平均 / 中位 input tokens | 7,780,373 / 6,601,148 |
| 平均 / 中位 output tokens | 43,698 / 42,684 |
| 记录的 cost | 无（`null`） |

F2P、P2P 和 partial 是 Pier 对 24 个 trial 的等权均值，不是汇总所有 test node 后的 micro average。二元 reward 要求该 trial 的全部 F2P 和 P2P 都通过，因此 99.44% 的 macro partial 不能替代 58.33% 的正式通过率。

Unified Codex wrapper 将每个 trial 记录为一个 modifier turn，因此 `n_agent_steps=1`、`toolUses=0` 不表示 Agent 只执行了一步或没有使用工具，也不能与 OpenCode 原生 step/tool-use 数直接比较。Input token 未记录 cache token，cost 也为空；这组 usage 只适合本 job 内诊断，不适合直接做跨 adapter 的成本效率比较。

## Task 级结果

下表只依据 verifier reward。`F2P` 和 `P2P` 显示通过 node 数；partial 保留两位小数。

| Task | Trial 1 | Trial 2 | pass@2 |
|---|---|---|---:|
| `arcane-drift-detection-baselines` | `iPpoVX2`: 1，F2P 82/82，P2P 2/2 | `HZ2b6JS`: 1，82/82，2/2 | 1 |
| `tengo-callable-instance-isolation` | `RCU9iWw`: 1，23/23，122/122 | `waEj64x`: 1，23/23，122/122 | 1 |
| `mobly-grouped-test-barriers` | `UbQsedo`: 1，79/79，808/808 | `2VKDjLU`: 0，77/79，808/808，99.77% | 1 |
| `fastapi-deprecation-response-headers` | `8VoBe6L`: 0，136/137，3134/3134，99.97% | `u3nxvaW`: 1，137/137，3134/3134 | 1 |
| `anko-default-function-arguments` | `4MWH277`: 1，2/2，119/119 | `DDXp3u4`: 1，2/2，119/119 | 1 |
| `prometheus-typed-label-sorting` | `35fzB48`: 1，17/17，28/28 | `2y8xBKp`: 1，17/17，28/28 | 1 |
| `kombu-single-active-consumer-priority` | `6vdVD2v`: 0，84/85，1421/1421，99.93% | `ERiyiA4`: 1，85/85，1421/1421 | 1 |
| `textual-richlog-follow-state` | `Lx4QUyp`: 1，20/20，6/6 | `5TTiKkU`: 1，20/20，6/6 | 1 |
| `tomlkit-toml-table-converters` | `hMsyfk5`: 0，53/60，964/964，99.32% | `KiScK2c`: 0，59/60，964/964，99.90% | 0 |
| `cliffy-config-file-parsing` | `SAJecxJ`: 0，36/37，451/451，99.80% | `rcE7ufQ`: 0，36/37，451/451，99.80% | 0 |
| `go-critic-doc-link-checker` | `kqdi3C2`: 1，3/3，16/16 | `xcwxY9V`: 0，2/3，15/16，89.47% | 1 |
| `clack-async-autocomplete-options` | `RtaWn2D`: 0，72/82，643/643，98.62% | `KLikGtb`: 0，81/82，643/643，99.86% | 0 |

## 失败分布与稳定性

10 个失败 trial 中：

- 9 个完整保留 P2P，说明绝大多数失败是新功能边界覆盖不完整，而不是已有行为的大面积回归。
- 7 个只差 1～2 个 F2P 且 P2P 全过：两个 Cliffy，以及各一个 Clack、FastAPI、Kombu、Mobly、Tomlkit trial。它们在二元 reward 下仍是真实失败，但都是明确近失。
- `go-critic-doc-link-checker__xcwxY9V` 是唯一出现 P2P 失败的 trial：F2P 2/3、P2P 15/16。
- Cliffy 两次独立实现失败完全相同的隐藏测试，显示稳定的嵌套配置处理盲点。
- Tomlkit 和 Clack 都是两次失败，但两次完成度差异显著；它们既有稳定能力缺口，也明显受采样路径影响。
- 4 个任务一过一败，说明每题两次采样仍不足以消除较大的结果方差。

24 个 trial 都生成了非空 patch。合计是 135 次文件触达、14,236 行新增、489 行删除；这是把两次独立实现逐一相加的诊断数，不是仓库的唯一净变更量。多个方案为单题新增 400～1,200 行代码/测试，近失并非因为没有交付，而是大实现中遗漏了少数契约边界。

## 三个两次均失败的任务

### 1. cliffy-config-file-parsing

两个 trial 都通过 451/451 P2P 和 36/37 F2P，并失败同一个 `command - config - handles nested config objects`。隐藏测试期望嵌套 JSON 配置中的 `localhost` 能映射到对应选项，实际得到 `undefined`。

两个 patch 都实现了配置加载、flatten、错误类型、导出和 precedence，规模分别为 7 个文件 `+649/-2` 与 10 个文件 `+667/-5`，但嵌套对象 flatten 后的 dotted key 没有正确进入 option lookup。与之前 OpenCode job 的公共导出/空 patch 失败不同，本次是两次一致、可复现的功能语义缺口。

### 2. tomlkit-toml-table-converters

两个 trial 都保留 964/964 P2P，但失败机制不同：

- `hMsyfk5` 失败 7 个 F2P，全部集中在 `to_super_table`。实现无法识别解析后由 dotted-key assignment 表示的结构，反复抛出 `ConversionError: No matching dotted keys found`，影响基本转换、返回同一 doc、值保留、注释迁移和 round-trip。
- `KiScK2c` 只失败 `TestMultiLevelKeyPath.test_dotted_at_nested_path`。转换后重新解析的结果缺少 `data["parent"]["child"]`，说明 `to_dotted_keys("parent.child", doc)` 没有保持嵌套 key path 的归属。

这不是同一个失败节点，但共同表明对 TOMLKit 内部 `Container`/`DottedKey` 表示与嵌套路径写回的理解不完整。

### 3. clack-async-autocomplete-options

两个 trial 都保留 643/643 P2P：

- `RtaWn2D` 失败 10 个 F2P。其中 9 个断言是 transient `loadError` 被重置成空字符串 `''`，而契约要求 `undefined`；这波及 AbortError 静默处理、成功后清理、retry/fallback、close cleanup 等多个表面用例。另一个失败是启动新 fetch 时没有让前一个 `AbortController.signal.aborted` 变为 `true`。
- `KLikGtb` 已修正 `loadError` 语义，只剩同一个“new fetch aborts previous controller”失败，达到 81/82 F2P。

第二次已非常接近通过，优先补齐 controller 生命周期即可形成有价值的定向回归用例。

## 一过一败任务的失败侧

- FastAPI `8VoBe6L`：只失败 nested `include_router` 的 nearest-wins precedence。期望内层 `Sunset: Sun, 15 Jun 2031 12:00:00 GMT`，实际被外层 `Tue, 01 Jan 2030 00:00:00 GMT` 覆盖。
- Kombu `6vdVD2v`：只失败 `test_promote_fires_on_cancel_for_demoted`。实现将 promotion 限制在被取消 consumer 原本为 active 的情况，遗漏 demoted consumer 取消时要求的 promotion/lifecycle notification。
- Mobly `2VKDjLU`：只失败 `synchronized_step/context` 的两个 `timeout=0` 用例。单 participant barrier 会立即 release，绕过了“timeout==0 必须抛 `signals.TestError`”的显式契约。
- Go Critic `xcwxY9V`：没有产生隐藏测试期待的 `[strings.NewReader]` 与 `[strings.Replacer.Replace]`“package strings is not imported”诊断，说明 import 校验没有严格限定到声明所在文件；同一 `TestCheckers` 聚合测试也被判为 P2P 失败。另一 trial 全过，说明该题对实现路径敏感。

## 与同确认集两个 job 的对照

另两个 job 使用同一 12 题、每题 2 次：

- [单 OpenCode + DeepSeek V4 Flash](opencode-deepseek-v4-flash-05_sample_confirm-20260803-104234.md)：24/24 有效，10/24 通过，7/12 task-level pass@2。
- [OpenCode + DeepSeek modifier、Codex reviewer 的协作 job](unified-collab-opencode-codex-05_sample_confirm-12-tasks-20260804-200817.md)：11/24 raw reward，其中 1 个 Prometheus trial 无 verifier；有效口径 11/23，9/12 task-level pass@2。

| 口径 | 单 OpenCode | unified-collab | 本 job：unified Codex |
|---|---:|---:|---:|
| Raw trial reward | 10/24（41.67%） | 11/24（45.83%） | 14/24（58.33%） |
| 有效 verifier trial | 24/24 | 23/24 | 24/24 |
| 有效 trial pass rate | 10/24（41.67%） | 11/23（47.83%） | 14/24（58.33%） |
| Task-level pass@2 | 7/12（58.33%） | 9/12（75.00%） | 9/12（75.00%） |

| Task | 单 OpenCode 通过次数 | unified-collab 通过次数 | 本 job 通过次数 |
|---|---:|---:|---:|
| `arcane-drift-detection-baselines` | 1 | 1 | 2 |
| `tengo-callable-instance-isolation` | 0 | 1 | 2 |
| `mobly-grouped-test-barriers` | 2 | 2 | 1 |
| `fastapi-deprecation-response-headers` | 2 | 1 | 1 |
| `anko-default-function-arguments` | 0 | 0 | 2 |
| `prometheus-typed-label-sorting` | 1 | 1（另 1 次无 verifier） | 2 |
| `kombu-single-active-consumer-priority` | 0 | 1 | 1 |
| `textual-richlog-follow-state` | 2 | 0 | 2 |
| `tomlkit-toml-table-converters` | 1 | 1 | 0 |
| `cliffy-config-file-parsing` | 0 | 2 | 0 |
| `go-critic-doc-link-checker` | 0 | 0 | 1 |
| `clack-async-autocomplete-options` | 1 | 1 | 0 |

相较单 OpenCode job，本 job 多 4 个通过 trial，raw pass rate 高 16.67 个百分点，task-level pass@2 多覆盖 2 题。新增覆盖 Tengo、Anko、Kombu、Go Critic，同时失去 Tomlkit、Clack；按通过次数还在 Arcane、Prometheus 上增加，在 Mobly、FastAPI 上减少。

相较协作 job，本 job 多 3 个 raw 通过 trial；按有效分母高 10.50 个百分点，但 task-level pass@2 同为 9/12。任务集合并不相同：本 job 新覆盖 Anko、Textual、Go Critic，协作 job 则覆盖 Tomlkit、Cliffy、Clack，正好交换 3 题。

这些对照只能描述三次具体运行。Agent/model、single/review-loop 编排、runtime、watchdog 参数和运行日期均不同，而且每题只有两次采样；不能把差值稳定归因于 Codex 模型、reviewer 或 unified runtime。各 adapter 的 token/tool-use/cost 转换语义也不同，不应直接比较成本效率。

## 建议

1. 将本 job 作为无异常的 unified Codex 单 Agent 基线，正式记录 `Pass@1=58.33%`、`task-level pass@2=75.00%` 和 coverage `24/24`，不做错误排除。
2. 优先把 Cliffy 的嵌套对象 option lookup、Tomlkit 的 parsed dotted-key 表示/嵌套路径写回、Clack 的前序 controller abort 做成定向回归用例；它们直接对应本 job 的三项 task-level 缺口。
3. 单独检查 Go Critic 的 file-local import resolution，避免新 checker 的测试 fixture 同时使既有 `TestCheckers` 聚合 P2P 失败。
4. 保留 FastAPI nearest-wins、Kombu demoted cancel、Mobly zero-timeout 作为近失边界；同题另一 trial 已通过，适合用于分析采样路径差异。
5. 若用于正式系统比较，建议预注册每题至少 4 次采样，并固定 task 集、timeout、runtime、网络和异常排除规则。不要原地 resume 或选择性补跑本 job 的失败 trial；它没有基础设施异常，补跑只会改变预先固定的样本。
