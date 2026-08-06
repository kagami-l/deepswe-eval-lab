# opencode-deepseek-v4-flash-05_sample_dev-20260803-205511 结果分析

分析日期：2026-08-05。

原始工件：

- [job result](../../../jobs/opencode-deepseek-v4-flash-05_sample_dev-20260803-205511/result.json)
- [job config](../../../jobs/opencode-deepseek-v4-flash-05_sample_dev-20260803-205511/config.json)
- [run lock](../../../jobs/opencode-deepseek-v4-flash-05_sample_dev-20260803-205511/lock.json)
- [job log](../../../jobs/opencode-deepseek-v4-flash-05_sample_dev-20260803-205511/job.log)
- [全部当前 trial](../../../jobs/opencode-deepseek-v4-flash-05_sample_dev-20260803-205511/)

## 结论

当前 job 目录是一次按 `AgentTimeoutError` 原地 resume 后的最终状态，不是最初 22 个 trial 的原始快照。Pier 当前汇总包含 11 个任务、每题 2 个现存 trial，共 22 个 trial：8 个 reward 1、14 个 reward 0，其中 3 个带 Agent exception。

- Pier 原始 aggregate reward：`8 / 22 = 36.36%`。
- 证据化计分口径：排除两个预算用尽前被外部终止的 trial，保留持续工作到 5400 秒上限的 Scriggo Agent timeout，得到 `8 / 20 = 40.00%`。
- 若机械排除当前全部 3 个 exception，则为 `8 / 19 = 42.11%`；不推荐该口径，因为 Scriggo 是有效的任务预算超时，按 DeepSWE 规则应作为失败保留。
- 当前结果树中 11 个任务有 7 个至少一次通过，经验 task-level pass@2 为 `7 / 11 = 63.64%`。
- 只有 `mnamer-daemon-watch-lifecycle` 两次均通过；6 个任务一过一败；4 个任务当前两次均未通过。

这个 `7/11` 不能视为干净、预注册的 pass@2 基线：原 job 曾有 6 个 Agent timeout，resume 删除并替换了这 6 个原 trial，使相应任务获得了额外尝试机会。尤其原 Adaptix trial 是持续工作到时限的真实任务超时，却与 5 个会话停滞 trial 一起被重跑，替代 trial 最终通过。

此外，冻结的 canonical sample-dev 集合有 12 个任务；本 job config 和 lock 只包含 11 个，缺少 `skrub-duration-encoding`。因此本 job 对 canonical sample-dev 的 task coverage 是 `11/12 = 91.67%`，不能直接当作完整 12 题 sample-dev 结果。

## Resume 历史与当前快照边界

[低优先级问题记录](../deepswe-evaluation-low-priority-known-issues.md)保存了第一次运行的现场：最初共有 6 个 `AgentTimeoutError`。

| 原 trial | 当时判断 | 当前替代 trial | 当前结果 |
|---|---|---|---|
| `adaptix-name-mapping-aliases__nT5DFzS` | 到时限前仍活跃，真实任务超时 | `QjSmnms` | 正常完成，reward 1 |
| `obsidian-linter-scoped-ignore-ma__VF6tjh6` | 长时间无事件，会话停滞 | `299DWKw` | 再次异常、外部 SIGTERM，reward 0 |
| `bandit-incremental-cache-control__knK8Bp9` | 长时间无事件，会话停滞 | `f9y5v2u` | 正常完成，reward 0 |
| `pebble-durability-wait-apis__Rynywqb` | 长时间无事件，会话停滞 | `ik7nNh4` | 外部 SIGKILL，reward 0 |
| `scriggo-method-declarations__BnLVBMr` | 长时间无事件，会话停滞 | `2uxyENZ` | 持续工作到 5400 秒，reward 0 |
| `mnamer-daemon-watch-lifecycle__DfeZKNv` | 长时间无事件，会话停滞 | `r6coy9A` | 正常完成，reward 1 |

Pier resume 会删除原 trial 目录再从头运行。当前目录只保留替代后的 22 个 trial；最初 6 个 timeout 的 patch、trajectory 和 usage 已不在 job 目录。因此：

- 当前 `result.json` 能描述最终目录状态，但不能恢复一个未经选择性重跑的原始 pass@2。
- 当前 trial 的 token/cost 合计不包含已删除的 6 个原 timeout，低于该 job 历史上实际消耗。
- job 的 14 小时 15 分钟 wall-clock 包含首次运行和 resume，不能与当前 22 个目录的累计时长一一对应。

## 运行配置与覆盖

| 项目 | 值 |
|---|---|
| 首次开始时间 | 2026-08-03 20:55:23 CST |
| 最终结束时间 | 2026-08-04 11:10:00 CST |
| 含 resume 的 wall-clock | 约 14 小时 15 分钟 |
| Pier | `0.3.0` |
| Job config 任务数 | 11 |
| Canonical sample-dev 任务数 | 12 |
| 缺失任务 | `skrub-duration-encoding` |
| 每任务现存 trials | 2 |
| 现存 trials | 22 |
| 并发 | 2 |
| Agent | OpenCode `1.18.10`，terminal-event watchdog adapter |
| 模型 | `deepseek/deepseek-v4-flash`，OpenCode `--thinking` |
| Runtime | shared `deep-swe/opencode-runtime:1.18.10` |
| Agent timeout | 5400 秒 |
| Verifier timeout | 1800 秒 |
| Retry | 首次 `max_retries=0`；之后人工按异常类型 resume |

Canonical 12 题列表以 [selection manifest](../../data/selection/manifest.json) 和 `05_sample_dev.csv` 为准。job 的 `config.json`、`lock.json` 和现存目录一致，均明确只有 11 题，所以这不是 Pier 汇总漏记，而是本次 invocation 的输入列表本身没有 Skrub。

## 当前结果树的汇总指标

| 指标 | 当前 22 个 trial |
|---|---:|
| Reward | 8 / 22（36.36%） |
| Pier errors | 3 / 22 |
| Evidence-scored | 8 / 20（40.00%） |
| 当前树 task-level pass@2 | 7 / 11（63.64%） |
| Pier macro F2P | 74.64% |
| Pier macro P2P | 99.98% |
| Pier macro partial | 95.93% |
| 排除两个外部中断后的 macro F2P | 82.11% |
| 排除两个外部中断后的 macro P2P | 99.98% |
| 排除两个外部中断后的 macro partial | 98.53% |
| 当前目录记录的 Agent steps | 4,115 |
| 当前目录记录的 input / cache / output tokens | 765,570,971 / 762,723,456 / 993,275 |
| 当前目录记录的 cost | `$3.3051594968` |
| 当前目录最大 peak context | 474,674 tokens |

上表 usage 和效率指标只覆盖 resume 后保留下来的当前 trial，不能当作整个历史 job 的实际总成本。OpenCode/Pier usage 转换还会把绝大部分 input 同时记为 cache；跨 Agent/编排的成本对照不应直接使用这些原始合计。

## Task 级结果

表中“异常”仍显示 verifier 对最终 committed patch 的评分。三个异常 trial 的 patch 都为空，因此 verifier 实际评测的是 base state。

| Task | Trial 1 | Trial 2 | 当前树 pass@2 |
|---|---|---|---:|
| `tengo-destructuring-bindings` | `WjBN35X`: 0，F2P 79/91，P2P 132/132，94.62% | `gZHJbTk`: 1，91/91，132/132 | 1 |
| `valibot-recursive-schema-composition` | `MoLEpHt`: 1，10/10，209/209 | `X5xzRTM`: 0，2/10，209/209，96.35% | 1 |
| `sqlite-utils-safe-import-checkpoints` | `RbaHE6q`: 0，46/60，1038/1038，98.72% | `kFmVVVS`: 0，48/60，1038/1038，98.91% | 0 |
| `pebble-durability-wait-apis` | `p27fU8k`: 0，57/59，44/44，98.06% | `ik7nNh4`: 外部中断，0，0/59，44/44，空 patch | 0 |
| `bandit-incremental-cache-control` | `FEsEKCv`: 0，80/88，275/275，97.80% | `f9y5v2u`: 0，85/88，275/275，99.17% | 0 |
| `scriggo-method-declarations` | `JpK9WRx`: 1，48/48，1049/1049 | `2uxyENZ`: Agent timeout，0，0/48，1049/1049，空 patch | 1 |
| `adaptix-name-mapping-aliases` | `gym4Zsd`: 0，40/44，2738/2738，99.86% | `QjSmnms`: 1，44/44，2738/2738 | 1 |
| `anko-typed-variable-bindings` | `Lx5Pgsh`: 0，1/9，94/94，92.23% | `pQP2prA`: 1，9/9，94/94 | 1 |
| `mnamer-daemon-watch-lifecycle` | `8qa5vwq`: 1，51/51，319/319 | `r6coy9A`: 1，51/51，319/319 | 1 |
| `obsidian-linter-scoped-ignore-markers` | `TxV57PS`: 0，31/33，1129/1133，99.49% | `299DWKw`: 外部中断，0，0/33，1133/1133，空 patch | 0 |
| `dasel-html-document-format` | `BQp8wH5`: 1，146/146，1012/1012 | `Q6ASgHF`: 0，144/146，1012/1012，99.83% | 1 |

## 当前三个异常 trial

### 1. obsidian-linter-scoped-ignore-ma__299DWKw

该 trial 没有 terminal `step_finish(reason="stop")`。最后一条事件是 2026-08-04 00:51:34 UTC 的已完成 edit 后 `step_finish(reason="tool-calls")`，之后约 20 分钟没有任何 OpenCode 事件，01:11:34 被外部 SIGTERM 结束。它只使用约 33 分钟 Agent 时间，远未到 5400 秒预算。

Agent 当时已有未提交修改，但最终 `model.patch` 为空；verifier 因此得到 F2P 0/33、P2P 1133/1133、reward 0。这个零分主要反映会话停滞和外部回收，不是一个语义完成后的正常解题失败，建议从有效 trial 分母排除。

### 2. pebble-durability-wait-apis__ik7nNh4

该 trial 同样没有 terminal event，但与 Obsidian 不同：最后一条 reasoning 事件在 01:58:19 UTC，01:59:22 即以 SIGKILL 退出，终止前仅静默约 1 分钟。它仍在规划更广的 Go 测试，不能据此认定为 provider stream stall。

Agent 运行约 40 分钟后被预算外提前终止，未提交的修改没有进入 patch，verifier 得到 F2P 0/59、P2P 44/44、reward 0。无论外部终止的操作原因是什么，这都不是完整的 5400 秒任务尝试，建议作为 external/operator interruption 排除，而不要解释成模型正常失败或已确认的会话停滞。

### 3. scriggo-method-declarations__2uxyENZ

该 trial 用满 5400 秒并触发 `AgentTimeoutError`。超时前仍在持续工作：最后事件是新的 `step_start`，时间戳甚至比 Pier 的 timeout cutoff 晚约 8 秒，可能包含缓冲/回收竞态，但足以排除长时间无事件停滞。

它在时限内没有完成提交，所以 patch 为空，verifier 得到 F2P 0/48、P2P 1049/1049。按 [DeepSWE 计分规则核查](../deepswe-pass-rate-and-leaderboard-scoring.md)，Agent timeout 属于预算内能力结果，应计为 reward 0，而不是因为 `exception_info` 非空就排除。同任务另一个 trial `JpK9WRx` 已完整通过。

## 正常失败的模式

除三个异常 trial 外，当前有 11 个正常完成但 reward 0 的 trial：

- 其中 10 个完整保留 P2P；唯一出现回归的是 Obsidian `TxV57PS`，失败 4 个 P2P 和 2 个 F2P。
- Adaptix `gym4Zsd` 只缺 4 个 alias collision/own-primary-key F2P；另一 trial 全过。
- Dasel `Q6ASgHF` 只缺 2 个复杂 implicit-closing F2P；另一 trial 全过。
- Pebble `p27fU8k` 只缺 `DurabilityNotifyBlocksUntilDurable` 和 `DurableStateAdvancesAndLatchesError` 两个 F2P，但第二次尝试被外部中断，不能据此认定稳定失败。
- Bandit 两个 trial 都失败 `cache-summary` 的 file count、无 target summary 和 `warm-cache` 不报告 issue 三个共同 F2P；这是可复现的功能缺口，第二个 trial 其余 85/88 F2P 已通过。
- SQLite-utils 两个 trial 共同失败 12 个 F2P，集中在 validation success/failure、strict mode、foreign-key validation、failure schema 和 error report；这是本批最明确的两次稳定功能缺口。
- Tengo、Valibot、Anko 的失败侧分别缺 12/91、8/10、8/9 F2P，而另一侧全过，显示较强采样方差。

结果整体几乎没有 P2P 回归，但 F2P 完成度在相同任务的两次采样之间波动很大。二元 reward 的失败不能用高 partial 改写为通过；这些分项只用于说明“接近通过”或定位缺口。

## 推荐报告口径

本 job 最适合作为运行与异常诊断样本，不适合作为最终系统基线。若必须引用，应同时报告：

| 口径 | 数值 | 含义 |
|---|---:|---|
| Pier raw | 8/22（36.36%） | 当前目录全部 reward 的机械均值，含两个外部中断零分 |
| Evidence-scored | 8/20（40.00%） | 排除两个提前外部终止，保留真实 Agent timeout |
| 当前树 task any-pass | 7/11（63.64%） | 仅描述现存目录；不是干净 pass@2 |
| Canonical task coverage | 11/12（91.67%） | 缺少 Skrub |

不建议只报告 `8/19=42.11%`，因为“所有 exception 都排除”会错误移除 Scriggo 的真实预算超时；也不建议把 `7/11` 与未 resume 的其他 job 当作同等 pass@2 横向比较。

## 建议

1. 保留本 job 作为 resume、会话停滞和外部终止的诊断记录，不再原地 resume；再次 resume 会继续删除异常现场并给部分任务额外采样机会。
2. 若要建立正式 sample-dev 基线，使用 canonical 12 题重新创建独立 job，明确包含 `skrub-duration-encoding`，固定每题重复数和异常排除规则，不复用本 job 的选择性重跑结果。
3. 将 inter-step stall 与真实总 timeout 分成不同错误类型；Obsidian 符合 stall 特征，Scriggo 不符合，Pebble 则是仍活跃时的外部终止。
4. 对 Bandit 的三个共同失败和 SQLite-utils 的 12 个共同失败建立定向回归；它们比一过一败任务更能代表稳定能力缺口。
5. 在正式成本比较中重新运行并保留所有 trial 工件；当前 `$3.3052` 只覆盖最终保留目录，不能代表该 job 含首次 timeout 和 resume 的实际总成本。
