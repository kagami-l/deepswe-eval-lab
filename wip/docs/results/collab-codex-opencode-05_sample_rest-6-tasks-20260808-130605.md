# collab-codex-opencode-05_sample_rest-6-tasks-20260808-130605 结果分析（含配对重打分）

分析日期：2026-08-08。

本文合并记录该 job 的正常 eval 结果与其 `score-patches` 配对重打分结果（后者在 job 结束当晚执行，
方法见[设计文档](../collab-paired-checkpoint-verification-design.md)），并与
[官方公开数据切片](../deepswe-target-configs-sample-pass-rates.md) 对照。

原始工件：

- [job result](../../../jobs/collab-codex-opencode-05_sample_rest-6-tasks-20260808-130605/result.json)
- [job config](../../../jobs/collab-codex-opencode-05_sample_rest-6-tasks-20260808-130605/config.json)
- [run manifest](../../../jobs/.agent-eval-manifests/collab-codex-opencode-05_sample_rest-6-tasks-20260808-130605.json)
- [patch-scores 汇总](../../../jobs/collab-codex-opencode-05_sample_rest-6-tasks-20260808-130605/patch-scores/summary.json)
- [配对表 pairs.csv](../../../jobs/collab-codex-opencode-05_sample_rest-6-tasks-20260808-130605/patch-scores/pairs.csv)
- [阶段表 stages.csv](../../../jobs/collab-codex-opencode-05_sample_rest-6-tasks-20260808-130605/patch-scores/stages.csv)

## 结论

1. **运行完全干净**：6 题各 3 次共 18 个 trial，18/18 完成 verifier，0 exception、0 retry、
   0 degraded、0 reviewer 超时轮次。正式 reward `15/18 = 83.33%`，task-level pass@3 `6/6`。
   这是两方向 collab 配置至今最干净的一次运行。
2. **配对主结果：review-loop 的净 verifier 价值再次为零，且这次连不一致对都没有。**
   同一批 initial patch 直接提交是 `15/18`，review-loop 终稿也是 `15/18`；18 对全部
   unchanged（0 修好、0 修坏），5 次 revision 的 parent→child delta 全为 0，
   task-clustered bootstrap 95% CI `[0, 0]`。ITT 与 completed-protocol 完全一致。
3. **评分管线保真度再次成立**：direct final 重打分与 Pier eval reward `18/18 matched`，
   0 verifier 错误、0 retry，全程约 16 分钟。这是 `score-patches` 首次在新鲜 job（非历史
   fixture）上全量运行。
4. **codex `gpt-5.6-luna` xhigh 的"单体代理"成绩由 initial patch 免费获得**：`15/18`
   （83.3%），高于官方 mini-swe harness 下同模型同 effort 的 `18/24`（75%），任务难度
   排序与官方一致（opa 最难、yaegi 次之）。rest 集不再需要单独跑 codex 单体 job。
5. 3 个失败 trial 全部是 reviewer 首轮 approve 的 false approval，failed F2P 高度收敛
   （两个 opa trial 失败完全相同的 3 个测试）。与 confirm 集结论一致：这个 reviewer
   探测不到 verifier 的精确边界。

## 运行配置

| 项目 | 值 |
|---|---|
| 开始 / 结束时间 | 2026-08-08 13:06:12 / 18:58:19 CST |
| 总 wall-clock | 约 5 小时 52 分 |
| 任务数 / trials | 6（`05_sample_rest`）/ 18（每题 3 次） |
| 并发 | 2（与 opencode→codex 反向 job 并行运行，总 4 slot） |
| Topology / workflow | `collab / review-loop` |
| Modifier | Codex `gpt-5.6-luna`，effort `xhigh`，permissions `bypass` |
| Reviewer | OpenCode `deepseek/deepseek-v4-flash`，effort `high`，permissions `auto` |
| Runtime | `deep-swe/agent-runtime:bd704fc758b47046`（job 启动时按当前 manifest 重建） |
| Task hard / soft deadline | 5400 / 5100 秒 |
| Event-silence watchdog | 600 秒 |
| `maxReviews` / `maxAgentAttempts` / `minTurnSeconds` | 3 / 2 / 120 秒 |
| Pier / git commit | `0.3.0` / `7fd0cebdb70d8596d0c696547ddf32d61f3384f3`，dirty=false |

与 `20260806-224833`（confirm 集）相比，watchdog 从 900 秒回到默认 600 秒，本次没有触发任何
event-silence 中断，说明 600 秒对 codex modifier + v4-flash reviewer 的正常节奏已足够。

## 汇总指标

| 指标 | 值 |
|---|---:|
| Reward | 15 / 18（83.33%） |
| Task-level pass@3 | 6 / 6 |
| 平均 / 中位 trial 时间 | 37 分 42 秒 / 36 分 33 秒（最短 20:46，最长 57:10） |
| Review 轮次合计 | 23（13 个 trial 首轮 approve，5 个经 1 次 revision 后 approve） |
| Reviewer attempts | 25（23 成功，2 中断后在轮内重试成功） |
| Pier 记录 input / output tokens | 188,036,512 / 1,132,437 |
| Pier 记录 cost | `$0.5305`（仅 OpenCode reviewer；Codex modifier cost 为 null） |

## Task 级结果

每格为 `reward（F2P 通过/总数，review 轮次/revision 次数）`。

| Task | Trial 1 | Trial 2 | Trial 3 | pass@3 |
|---|---|---|---|---:|
| `bandit-interprocedural-taint-checks` | `bKaoWMH`: 1（66/66，1/0） | `Q666L75`: 1（66/66，1/0） | `ToAo5eb`: 1（66/66，2/1） | 1 |
| `dateutil-rfc5545-timezone-interop` | `Vq2wmPD`: 1（67/67，2/1） | `hcKHJnK`: 1（67/67，2/1） | `Hu8kvFi`: 1（67/67，2/1） | 1 |
| `fd-deterministic-multi-key-sorting` | `JF2goY5`: 1（43/43，1/0） | `iksFJ8C`: 1（43/43，2/1） | `3HNXqpN`: 1（43/43，1/0） | 1 |
| `httpx-multipart-response-parsing` | `755v8NV`: 1（122/122，1/0） | `XgQmjFB`: 1（122/122，1/0） | `xVCs5Sy`: 1（122/122，1/0） | 1 |
| `opa-rego-rule-profiling` | `hk7fiLv`: 1（25/25，1/0） | `oagDPp5`: 0（22/25，1/0） | `GbXWn8H`: 0（22/25，1/0） | 1 |
| `yaegi-go-embed-directives` | `ngu7mnm`: 1（38/38，1/0） | `4hmUN7A`: 0（37/38，1/0） | `vZLwcLs`: 1（38/38，1/0） | 1 |

P2P 全部满通过（18/18 trial）。值得注意的是 dateutil（核心池 hard 档）3/3 全过，
且三次都经历了恰好一轮 revision。

## Review loop 健康度

- 23 个 review 轮次全部形成有效 verdict：18 approve、5 revise；5 次 revision 全部成功执行。
- 25 个 reviewer attempts 中 2 个中断，均在轮内重试成功，没有轮次失败，没有 degraded trial。
- 无 protocol violation；outcome 全部为 `approved`（没有 max_reviews_reached）。
- **False approval**：3 个 reward=0 的 trial（opa×2、yaegi×1）全部是首轮 approve。
  `approved-but-verifier-failed` 为 `3/18 = 16.7%`（confirm 集为 9/20 = 45%）。比例下降主要
  因为本集对 codex 更容易，而非 reviewer 判别力提升——它依旧没有拦下任何一个真实失败。

## score-patches 配对结果

| 项目 | 值 |
|---|---|
| 命令 | `score-patches --job-path jobs/collab-codex-opencode-…-130605 --concurrency 2` |
| Stage 实例 | 41（18 initial + 5 revision + 18 final） |
| Unique patch（完整 fingerprint 去重） | 23（13 个 final 与 initial 相同，5 个与 revision-1 相同） |
| Verifier 运行 | 23 成功 / 0 失败 / 0 retry，总耗时约 16 分钟 |
| Final conformance | matched 18 / mismatched 0 / unavailable 0 |
| Exit code | 0，coverage 完整（18/18 对） |

### 配对汇总

| 口径 | 对数 | initial 通过 | final 通过 | 修好 (0→1) | 修坏 (1→0) | 不变 | 均值 delta | McNemar p | 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Intention-to-treat | 18 | 15 (83.33%) | 15 (83.33%) | 0 | 0 | 18 | 0.0 | —（无不一致对） | [0, 0] |
| Completed-protocol | 18 | 同上 | 同上 | 0 | 0 | 18 | 0.0 | — | [0, 0] |

2×2 四格：passedBoth 15、failedBoth 3、improved 0、harmed 0。

5 次 revision 全部发生在 initial 已通过的 trial 上（bandit `ToAo5eb`、dateutil 三次、fd
`iksFJ8C`），parent→child reward delta 全为 0。3 个失败 trial 反而全部首轮 approve、零
revision——reviewer 的修订动作与 verifier 失败完全不相交，这是比"delta 为 0"更直接的
无效证据：**review-loop 的注意力没有落在任何一个真实缺陷上**。

## 失败用例分析

### opa：rule profile 聚合语义缺口（两个 trial 失败完全相同）

`GbXWn8H` 与 `oagDPp5` 都恰好失败同 3 个 F2P（P2P 6/6 全过）：

- `TestRuleProfileDiffChanged`
- `TestRuleProfileHotRules`
- `TestRuleProfileMultipleDefinitions`

两个独立 patch（SHA 不同）收敛到相同语义缺口，与 confirm 集 Clack/Cliffy/FastAPI 的
"不同实现、相同精确边界缺失"模式一致。同 task 的 `hk7fiLv` 25/25 全过，说明缺口可补，
是 rule-level profile 的 diff/hot-rules/多定义聚合路径未覆盖。

### yaegi：批量 ReadDir 边界

`4hmUN7A` 只失败 `TestEmbedFSReadDirBatched`（37/38）。另两个 trial 全过。

## 与官方公开数据对照

官方数据为 mini-swe-agent harness、每格 4 次（[来源](../deepswe-target-configs-sample-pass-rates.md)）；
本 job 为 deep-swe unified runtime、每题 3 次。initial 列即 no-review 反事实，可视为本
harness 下 codex 单体的代理成绩。

| Task | 官方 luna xhigh | 本 job initial | 本 job final |
|---|---:|---:|---:|
| `fd-deterministic-multi-key-sorting` | 4/4 | 3/3 | 3/3 |
| `dateutil-rfc5545-timezone-interop` | 3/4 | 3/3 | 3/3 |
| `yaegi-go-embed-directives` | 3/4 | 2/3 | 2/3 |
| `httpx-multipart-response-parsing` | 3/4 | 3/3 | 3/3 |
| `opa-rego-rule-profiling` | 2/4 | 1/3 | 1/3 |
| `bandit-interprocedural-taint-checks` | 3/4 | 3/3 | 3/3 |
| **合计** | **18/24（75%）** | **15/18（83.3%）** | **15/18（83.3%）** |

- 难度排序与官方一致：opa 最难（官方 0.50 / 本次 0.33），yaegi 次之（0.75 / 0.67），
  其余四题两边都接近或达到全过。本 harness 下 codex 略高于官方 mini-swe 口径（+8pp），
  在两边各自 ±0.25 级别的单格噪声内，不构成 harness 优劣结论。
- Reviewer 模型族（v4-flash）在官方 rest 层均值只有 0.58，明显弱于 modifier（0.75）。
  "弱 reviewer 审强 modifier"与观察到的零边际价值、3 次 false approval 相互印证。

## 与 confirm 集配对结果的合并证据

同方向（codex modifier + v4-flash reviewer）现在有两个 job 的配对数据：

| Job | 对数 | initial | final | 修好 | 修坏 | 不一致率 |
|---|---:|---:|---:|---:|---:|---:|
| confirm 12×2（[20260806-224833 配对分析](collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833-paired-rescore.md)） | 24 | 14 (58.3%) | 14 (58.3%) | 1 | 1 | 2/24 |
| rest 6×3（本文） | 18 | 15 (83.3%) | 15 (83.3%) | 0 | 0 | 0/18 |
| **合计** | **42** | **29 (69.0%)** | **29 (69.0%)** | **1** | **1** | **2/42** |

42 对、两个任务集、不同难度水平下，净效应精确为 0，不一致率 4.8%。当前配置
（v4-flash high reviewer 审 codex xhigh modifier）对 verifier reward 无净收益的结论已经
相当稳固，继续同配置扩样的边际信息量很低。

## 建议

1. 本 job 正式计为 `15/18`，coverage 18/18；rest 集的 codex 单体基线记为 initial 的
   `15/18`，无需另跑单体 job。
2. 同配置（codex modifier + v4-flash reviewer）不必再扩样。若继续探索 collab 增益，
   优先改变 reviewer 侧配置（更强模型/更高 effort、定向 smoke tests、要求区分
   "已运行测试验证"与"静态推断"），再用同一配对框架检验。
3. 反向 job（opencode modifier + codex reviewer）是当前更有信息量的方向：modifier 更弱、
   revision 更频繁，理论上 review 有更大改进空间。其 score-patches 结果出来后与本文
   合并解读。
4. opa 的 3 个收敛失败测试（DiffChanged / HotRules / MultipleDefinitions）与 yaegi 的
   `TestEmbedFSReadDirBatched` 可加入 reviewer 定向探针清单（沿用 confirm 集建议 4 的思路）。
5. `score-patches` 在新鲜 job 上首次全量运行即 18/18 conformance、16 分钟完成，可正式
   作为 collab eval 的常规后处理步骤。
