# opencode-deepseek-v4-flash-05_sample_confirm-20260803-104234 结果分析

分析日期：2026-08-05。

原始工件：

- [job result](../../../jobs/opencode-deepseek-v4-flash-05_sample_confirm-20260803-104234/result.json)
- [job config](../../../jobs/opencode-deepseek-v4-flash-05_sample_confirm-20260803-104234/config.json)
- [全部 trial](../../../jobs/opencode-deepseek-v4-flash-05_sample_confirm-20260803-104234/)

## 结论

本次 job 完成了 `05_sample_confirm.txt` 中 12 个任务的两次独立 trial，共 24 个 trial。所有 trial 都正常结束并得到有效 verifier reward，没有 provider、verifier、network、timeout 或其他 Pier exception，也没有 retry。

- Trial-level Pass@1：`10 / 24 = 41.67%`。
- 12 个任务中有 7 个至少一次通过，手工计算 task-level pass@2：`7 / 12 = 58.33%`。
- 3 个任务两次均通过：`fastapi-deprecation-response-headers`、`mobly-grouped-test-barriers`、`textual-richlog-follow-state`。
- 4 个任务一过一败：`arcane-drift-detection-baselines`、`clack-async-autocomplete-options`、`prometheus-typed-label-sorting`、`tomlkit-toml-table-converters`。
- 5 个任务两次均失败：`anko-default-function-arguments`、`cliffy-config-file-parsing`、`go-critic-doc-link-checker`、`kombu-single-active-consumer-priority`、`tengo-callable-instance-isolation`。

Pier aggregate reward `0.4166666667` 与 `10/24` 一致。因为 24 个 trial 均有有效评分，本 job 不需要调整分母，也不建议以 infrastructure retry 名义补跑。

## 运行配置

| 项目 | 值 |
|---|---|
| 开始时间 | 2026-08-03 10:42:38 CST |
| 结束时间 | 2026-08-03 19:56:35 CST |
| 总 wall-clock | 约 9 小时 14 分钟 |
| Pier | `0.3.0` |
| 任务数 | 12 |
| 每任务 trials | 2 |
| 总 trials | 24 |
| 并发 | 2 |
| Agent | OpenCode `1.18.10`，terminal-event watchdog adapter |
| 模型 | `deepseek/deepseek-v4-flash`，OpenCode `--thinking` |
| Runtime | shared `deep-swe/opencode-runtime:1.18.10`，挂载到 `/opt/opencode-runtime` |
| Agent timeout | 每个 task 5400 秒 |
| Verifier timeout | 每个 task 1800 秒 |
| Agent network | `no-network` |
| Verifier environment | `separate`、`no-network` |
| Retry | `max_retries=0` |

Watchdog 为每个 trial 都记录了完整的 `running → main_session_identified → terminal_grace → terminating → signal_sent → process_exited` 序列。这里的 `SIGTERM` 是在 OpenCode 已输出主 session 的 terminal `step_finish(reason="stop")` 后，等待 10 秒仍未退出时进行的预期清理；24 个 trial 均被 Pier 视为正常 Agent 完成，不是超时或异常中止。

## 汇总指标

| 指标 | 值 |
|---|---:|
| Reward | 10 / 24（41.67%） |
| Task-level pass@2 | 7 / 12（58.33%） |
| Macro F2P | 82.69% |
| Macro P2P | 99.33% |
| Macro partial | 97.39% |
| 总 Agent steps | 3,409 |
| 平均 / 中位 Agent steps | 142.0 / 124.5 |
| Agent 执行时间合计 | 约 11 小时 59 分钟 |
| 平均 / 中位 Agent 时间 | 29 分 58 秒 / 27 分 23 秒 |
| 平均 / 中位 trial 时间 | 31 分 54 秒 / 29 分 18 秒 |
| Verifier 时间合计 | 约 40 分 32 秒 |
| 记录的总 input / cache / output tokens | 476,563,809 / 474,133,632 / 817,385 |
| 记录的总 cost | `$2.3791677896` |
| 最大 peak context | 299,359 tokens |

F2P、P2P 和 partial 是 Pier 对 24 个 trial 的等权均值，不是把所有测试 node 汇总后的 micro average。二元 reward 要求该 trial 的全部 F2P 和 P2P 都通过，因此高 partial 不能替代正式通过率。

Token 和 cost 来自 OpenCode/Pier 转换后的 usage 记录。输入 token 中绝大部分同时记为 cache token；这组数值可用于本 job 内诊断，但不同 Agent/编排的 usage 转换语义可能不同，不宜直接用于跨系统成本比较。

## Task 级结果

下表只依据 verifier reward。`F2P` 和 `P2P` 显示通过 node 数；partial 保留两位小数。

| Task | Trial 1 | Trial 2 | pass@2 |
|---|---|---|---:|
| `arcane-drift-detection-baselines` | `steiage`: 0，F2P 67/82，P2P 2/2，82.14% | `6WpWT3Z`: 1，82/82，2/2 | 1 |
| `tengo-callable-instance-isolation` | `73H6EQM`: 0，22/23，122/122，99.31% | `A74LTcb`: 0，22/23，122/122，99.31% | 0 |
| `mobly-grouped-test-barriers` | `DtTvoWp`: 1，79/79，808/808 | `Ljy9VxM`: 1，79/79，808/808 | 1 |
| `fastapi-deprecation-response-headers` | `RVkUJs7`: 1，137/137，3134/3134 | `M9mqLPf`: 1，137/137，3134/3134 | 1 |
| `anko-default-function-arguments` | `GMEYori`: 0，1/2，119/119，99.17% | `LUzJsjR`: 0，1/2，119/119，99.17% | 0 |
| `prometheus-typed-label-sorting` | `J4LT3Ld`: 0，16/17，27/28，95.56% | `KRtV2Hg`: 1，17/17，28/28 | 1 |
| `kombu-single-active-consumer-priority` | `3Hza86j`: 0，84/85，1421/1421，99.93% | `F5HrjzR`: 0，76/85，1421/1421，99.40% | 0 |
| `textual-richlog-follow-state` | `uw2NMiK`: 1，20/20，6/6 | `KAVKpYV`: 1，20/20，6/6 | 1 |
| `tomlkit-toml-table-converters` | `MzTDxAD`: 0，59/60，964/964，99.90% | `3YXn5zF`: 1，60/60，964/964 | 1 |
| `cliffy-config-file-parsing` | `BN5NSUf`: 0，0/37，451/451，92.42% | `sfbbdoR`: 0，0/37，451/451，92.42%，空 patch | 0 |
| `go-critic-doc-link-checker` | `9zp5S9C`: 0，2/3，15/16，89.47% | `vFmb8Ms`: 0，2/3，15/16，89.47% | 0 |
| `clack-async-autocomplete-options` | `gGmrVSU`: 1，82/82，643/643 | `7yaPUX2`: 0，80/82，643/643，99.72% | 1 |

## 失败分布与稳定性

14 个失败 trial 中：

- 11 个完整保留了 P2P，说明大多数失败是功能覆盖不完整，而不是大面积回归。
- 7 个只差 1～2 个 F2P 且 P2P 全过，包括两个 Anko、一个 Clack、一个 Kombu、两个 Tengo 和一个 Tomlkit trial。这些都是二元 reward 下的真实失败，但属于非常接近通过的失败。
- 3 个出现 P2P 回归：两个 Go Critic trial，以及 Prometheus 的 `J4LT3Ld`。
- Anko、Tengo、Go Critic 的两次 trial 得到完全相同的 F2P/P2P 计数和失败节点，显示出稳定、可复现的能力盲点，而不是单纯采样噪声。
- Arcane、Clack、Prometheus、Tomlkit 一过一败，说明这四题对采样路径较敏感；只跑一次会显著受随机性影响。

## 五个两次均失败的任务

### 1. anko-default-function-arguments

两个 trial 都通过 119/119 P2P，只失败同一个 F2P：`TestDefaultArgumentsVisible`。这表明主要语法、参数校验和回归行为已实现，但默认参数在函数内部的可见性/绑定语义存在同一个稳定缺口。

### 2. tengo-callable-instance-isolation

两个 trial 都通过 122/122 P2P 和 22/23 F2P，只失败 `TestCompiledFunctionCall_CloneKeepsNestedCallableGraphsIsolated`，实际值为 10、期望值为 11。两次独立实现都没有完整隔离 clone 后的嵌套 callable graph，属于高度稳定的深层状态复制问题。

### 3. go-critic-doc-link-checker

两个 trial 都失败同一个 F2P `TestCheckers/brokenDocLink`，并同时使 P2P `TestCheckers` 失败，计数均为 F2P 2/3、P2P 15/16。与前两题不同，这里不仅遗漏新功能边界，还引入了已有 checker 聚合测试回归。

### 4. kombu-single-active-consumer-priority

两个 trial 都保留 1421/1421 P2P，但完成度差异较大：

- `3Hza86j` 只差 `test_sac_status_none_for_non_sac`：普通队列应返回 `None`，实现却返回了状态字典。
- `F5HrjzR` 失败 9 个 F2P，集中在 cancel notification 和 consumer SAC 查询方法。

第一条采样已经非常接近通过，但两次都没有覆盖完整接口契约，所以 task-level pass@2 仍为 0。

### 5. cliffy-config-file-parsing

两个 trial 的失败机制不同，值得单独记录：

- `sfbbdoR` 在实现和本地测试过程中正常修改了工作区，但 terminal event 出现在完整测试/提交之前。任务明确要求 commit，而 DeepSWE 的 `model.patch` 只提取 base commit 到最终 `HEAD` 的差异，因此最终 patch 为空，verifier 实际评测的是未修改的 base state。该 trial 没有 Pier exception，但属于 Agent 未完成交付，应保留为 reward 0。
- `BN5NSUf` 成功提交了 12 个文件、1160 行新增的 patch，并报告自写测试和全量测试通过；隐藏测试随后在 type-check 阶段发现 `command/mod.ts` 没有导出 `ConfigParseError` 和 `ConfigValidationError`。37 个 F2P 因测试文件无法编译而全部缺失，P2P 451/451 仍通过。Agent 验证了自己的新增测试，却没有验证与任务要求一致的公共入口导出。

这不是 verifier 或 patch 提取故障：一个 trial 没有把修改提交进 `HEAD`，另一个 trial 提交的 patch 本身缺少公共导出。

## 一过一败任务的失败侧

- Arcane `steiage`：15 个 handler F2P 失败，集中在路由注册和 compliance handler API；同题另一 trial 全过，表现方差较大。
- Clack `7yaPUX2`：只失败“异步加载失败时显示错误信息”和“重试耗尽后显示 fallbackOptions”两个 F2P，P2P 全过。
- Prometheus `J4LT3Ld`：失败一个 malformed fallback F2P，同时回归一个 typed-value 相等时 natural tie-break 的 P2P；另一 trial 全过。
- Tomlkit `MzTDxAD`：只失败嵌套路径下 dotted-key 转换的一个 F2P，P2P 全过；另一 trial 全过。

## 与同确认集协作 job 的对照

同一 12 题、每题 2 次的 [unified-collab job](unified-collab-05_sample_confirm-12-tasks-20260804-200817.md) 得到 11/24 raw reward、9/12 task-level pass@2，其中一个 Prometheus trial 无 verifier，排除后为 11/23。

| 口径 | 本 job：单 OpenCode + DeepSeek V4 Flash | unified-collab |
|---|---:|---:|
| Raw trial reward | 10/24（41.67%） | 11/24（45.83%） |
| 有效 verifier trial | 24/24 | 23/24 |
| 有效 trial pass rate | 10/24（41.67%） | 11/23（47.83%） |
| Task-level pass@2 | 7/12（58.33%） | 9/12（75.00%） |

按任务看，本 job 相比协作 job 多通过一次 FastAPI、两次 Textual；少通过一次 Tengo、一次 Kombu 和两次 Cliffy。其余任务的通过次数相同。净结果是少 1 个通过 trial、少 2 个至少一次通过的 task。

该对照只能说明这两次具体运行的结果差异。协作 job 使用额外 reviewer、不同编排和不同 runtime，且存在一个基础设施异常；当前只有每题两次采样，不足以把差值稳定归因于协作机制或模型能力。两边 token/cost 的事件转换语义也不同，不应直接用记录的 usage 数字比较成本效率。

## 建议

1. 将本 job 作为无异常的单 Agent 基线，正式记录 `Pass@1=41.67%`、`task-level pass@2=58.33%` 和 coverage `24/24`，不做错误排除。
2. 优先复查 Cliffy 的公共导出与提交前状态；adapter 可以在 terminal event 后检测“`HEAD` 未变化但工作区仍 dirty”并写出醒目诊断，但不应替 Agent 自动提交，否则会改变被评系统的行为边界。
3. 将 Anko 的默认参数可见性、Tengo 的嵌套 callable clone 隔离、Go Critic 的 checker 回归作为稳定能力缺口；它们比一过一败任务更适合做定向回归用例。
4. 若用于正式比较，建议按预注册方案增加到每题 4 次，并保持任务、timeout、OpenCode/runtime 版本、网络与错误排除规则一致。当前 4 个一过一败任务已经说明两次采样仍有明显随机波动。
5. 不建议原地 resume 或选择性补跑失败 trial：本 job 没有基础设施异常，补跑只会改变预先固定的两次采样并抬高结果。
