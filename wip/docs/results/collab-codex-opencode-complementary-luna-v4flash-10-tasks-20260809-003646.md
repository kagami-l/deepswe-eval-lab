# collab-codex-opencode-complementary-luna-v4flash 结果分析（含配对重打分）

分析日期：2026-08-09。

本文是 [luna/v4-flash 互补子集](../deepswe-luna-v4flash-complementary-subset.md)（机制探测池）上的
第一个 collab 方向：codex/luna modifier + OpenCode/DeepSeek-v4-flash（max）reviewer。核心问题是
**review-loop 能否把 reviewer 一侧的已知能力迁移给做不出该题的 modifier**。反方向见
[o→c 结果](collab-opencode-codex-complementary-luna-v4flash-10-tasks-20260809-122655.md),
两方向合并结论见[互补实验总结](complementary-luna-v4flash-collab-summary.md)。

原始工件：

- [job result](../../../jobs/collab-codex-opencode-complementary-luna-v4flash-10-tasks-20260809-003646/result.json)
- [job config](../../../jobs/collab-codex-opencode-complementary-luna-v4flash-10-tasks-20260809-003646/config.json)
- [run manifest](../../../jobs/.agent-eval-manifests/collab-codex-opencode-complementary-luna-v4flash-10-tasks-20260809-003646.json)
- [patch-scores 汇总](../../../jobs/collab-codex-opencode-complementary-luna-v4flash-10-tasks-20260809-003646/patch-scores/summary.json)
- [配对表 pairs.csv](../../../jobs/collab-codex-opencode-complementary-luna-v4flash-10-tasks-20260809-003646/patch-scores/pairs.csv)
- [阶段表 stages.csv](../../../jobs/collab-codex-opencode-complementary-luna-v4flash-10-tasks-20260809-003646/patch-scores/stages.csv)

## 结论

1. 运行干净：40/40 trial 完成 verifier，0 exception、0 retry；正式 reward `15/40 = 37.5%`。
   `--agent-timeout-multiplier 1.5`（hard 8100 秒）下仅 4 个 degraded（全部 timeout），
   相比 rest 集 o→c 方向的 9/18 大幅改善。
2. **98 个配对以来首次观察到真实的能力迁移**：flash 强 5 题的 18 个 initial 失败中,
   3 个被 review-loop 翻正（capture rate 16.7%），全部集中在 `eicrud`——三个 trial 的
   initial 都是 F2P 8/14 的真实功能缺口，flash-max reviewer 的 findings 各经一轮 revision
   推到 14/14。已用 stage 级 F2P 轨迹排除 verifier 抖动解释。
3. **对称的损害同样真实**：luna 强 5 题的 13 个 initial 通过中 2 个被改坏（harm rate
   15.4%），meriyah 49/49→46/49、sqlfmt 32/32→30/32，均为满分 patch 在弱侧 reviewer
   要求的 revision-1 中回归。净效应 +1 对（ITT initial 35.9% → final 38.5%），McNemar
   p=1.0，CI `[-0.100, +0.216]`，不显著。
4. **一个 conformance mismatch（exit 1）**：`eicrud __GuJLHF6` 的 eval 正式分为 0
   （P2P 167/168），direct 对同一 patch 两次评为满分 168/168。eicrud 在子集文档中本就带
   "评分敏感 Δ−0.15" 标记，判定为 verifier 侧 flaky P2P 节点。该对已按设计隔离,
   其余 39/39 matched。正式 reward 维持 Pier eval 口径不变。
5. **内部确认再添两例官方→内部反转**：`superjson` 官方 luna 4/4 → 内部 0/4（luna 侧
   首例大反转）；`eicrud` 官方 luna 0/4，内部却有 1 次 initial 全过 + 三次 8/14。
   叠加 rest 集的 bandit 反例，官方单格 4 次数据的逐题结论在内部 harness 只能当假设。

## 运行配置

| 项目 | 值 |
|---|---|
| 开始 / 结束时间 | 2026-08-09 00:36:56 / 10:06:40 CST（约 9 小时 30 分） |
| 任务数 / trials | 10（`complementary-luna-v4flash`）/ 40（每题 4 次） |
| 并发 | 4 |
| Modifier | Codex `gpt-5.6-luna`，effort `xhigh`，permissions `bypass` |
| Reviewer | OpenCode `deepseek/deepseek-v4-flash`，effort `max`，permissions `auto` |
| Budget | `--agent-timeout-multiplier 1.5` → hard 8100 / soft 7800 秒 |
| Event-silence watchdog | 900 秒 |
| Runtime | `deep-swe/agent-runtime:bd704fc758b47046` |
| `maxReviews` / `maxAgentAttempts` | 3 / 2 |
| Pier / git commit | `0.3.0` / `31f6517bdff7`，dirty=false |

flash 侧 effort 为 `max`（与官方 `v4_flash_max` 对齐,区别于此前所有 job 的 `high`）,
是本子集实验的预设条件。

## 汇总指标

| 指标 | 值 |
|---|---:|
| Reward | 15 / 40（37.5%） |
| Outcome 分布 | 35 approved / 1 max_reviews_reached / 4 degraded（全部 timeout） |
| 平均 / 中位 / 最长 trial | 51 分 / 46 分 / 2 小时 13 分 |
| Revision 总数 | 20 |
| Reviewer attempts | 66，其中 10 失败（**8 个 event_silence**、2 个其他） |
| Pier 记录 input / output tokens | 758,428,027 / 3,340,862 |
| Pier 记录 cost | `$1.4912`（仅 OpenCode reviewer；Codex cost 为 null） |

4 个并发 codex xhigh session 未出现限流/认证类失败;并发 4 的资源占用全程健康。
flash-max reviewer 的 8 次 event_silence 说明 900 秒 watchdog 对 max 档已经贴边,
反方向 job（flash-max 当 modifier）建议上调至 1200 秒。

## Task 级配对结果

每格为 `initial→final（revision 数）`；`†` = degraded/timeout，`‡` = max_reviews_reached,
`▲` = 修好，`▼` = 修坏。

| Task | 方向 | T1 | T2 | T3 | T4 | initial | final |
|---|---|---|---|---|---|---:|---:|
| `meriyah-explicit-resource-declarations` | luna 强 | 1→1(0) | **1→0(1)†▼** | 0→0(2)† | 0→0(0) | 2/4 | 1/4 |
| `superjson-error-stack-serialization` | luna 强 | 0→0(0) ×4 | | | | 0/4 | 0/4 |
| `numba-stencil-boundary-modes` | luna 强 | 1→1(0) | 1→1(1) | 1→1(1) | 1→1(0) | 4/4 | 4/4 |
| `valibot-recursive-schema-composition` | luna 强 | 1→1(0) | 1→1(1) | 1→1(0) | 1→1(0) | 4/4 | 4/4 |
| `sqlfmt-create-table-ddl-formatting` | luna 强 | 1→1(0) | **1→0(1)▼** | 1→1(2) | 0→0(0)† | 3/4 | 2/4 |
| `eicrud-keyset-pagination-cursor` | flash 强 | 1→1(0)†* | **0→1(1)▲** | **0→1(1)▲** | **0→1(3)‡▲** | 1/4 | 4/4 |
| `onedump-dump-encryption-pipeline` | flash 强 | 0→0，1 个 trial 有 1 次 revision | | | | 0/4 | 0/4 |
| `python-statemachine-state-data-scoping` | flash 强 | 1→1(1) | 0→0(2) | 0→0(0) | 0→0(1) | 1/4 | 1/4 |
| `prometheus-transactional-reload-status` | flash 强 | 0→0，1 个 trial 有 1 次 revision | | | | 0/4 | 0/4 |
| `anko-typed-variable-bindings` | flash 强 | 0→0(0) ×4 | | | | 0/4 | 0/4 |
| **luna 强合计** | | | | | | **13/20** | **11/20** |
| **flash 强合计** | | | | | | **2/20** | **5/20** |

`*` eicrud `GuJLHF6`：direct 口径 initial=final=1（168/168），eval 正式分 0（167/168 flaky）,
conformance mismatched，已从主配对剔除（上表 initial/final 按 direct 口径显示）。

## score-patches 与 conformance mismatch

| 项目 | 值 |
|---|---|
| Stage 实例 | 100（40 initial + 20 revision + 40 final） |
| Unique patch | 60，0 cached，全部评分成功 |
| Final conformance | matched 39 / **mismatched 1**（eicrud `GuJLHF6`）/ unavailable 0 |
| Coverage / exit | 40/40 对完整；exit 1（因 mismatch） |

mismatch 详情：eval 正式 verifier 报 P2P 167/168（reward 0），direct 重评同一 patch
（initial 与 final 同指纹）为 168/168（reward 1）。

抖动归属已由复跑确认（2026-08-09，`--trial 'eicrud-…__GuJLHF6' --force` ×2 + 原始运行,
备份见该 trial 的 `patch-scores/results-run1-backup/`、`results-run2-backup/`）：

- direct 路径 **3 次独立评分全部 168/168、reward 1**，单次 verifier 152 秒,完全确定;
- 唯一的 167/168 出现在 eval 正式运行中，方向为 eval 偏低。

结合 eicrud 的 `v1-delta −0.15` 评分敏感标记，判定为 **eval 侧一次性 flaky P2P 节点**,
direct 评分路径无漂移。处置：官方 reward 不改（Pier eval 是 canonical）；该对保留在
sensitivity 表；复跑后的全量幂等重跑确认 60 个 unique patch 全部缓存命中（0 次新
verifier），汇总完整恢复。

### 配对汇总

| 口径 | 对数 | initial | final | 修好 | 修坏 | McNemar | 95% CI |
|---|---:|---:|---:|---:|---:|---:|---|
| Intention-to-treat | 39 | 35.9% | 38.5% | 3 | 2 | 1.0 | [−0.100, +0.216] |
| Completed-protocol | 36 | 36.1% | 41.7% | 3 | 1 | — | — |

## 预注册指标读数

**Capture rate（flash 强 5 题 = reviewer 强格子）**：initial 失败 18 个，翻正 3 个 =
**16.7%**，全部来自 eicrud。三次翻正的 stage 轨迹一致：initial F2P 8/14（真实功能缺口,
非抖动）→ 首轮 review findings → revision-1 后 14/14。这是 confirm/rest 两集 98 对中
从未出现过的模式：**reviewer 把自己会做、modifier 不会做的部分通过 findings 教给了
modifier**。但其余 4 题（anko、onedump、prometheus-transactional、python-statemachine）
零拯救——迁移只在 reviewer 优势最明确（官方 A 档 4/4 vs 0/4）且缺口是"补齐剩余功能"
而非"推翻实现路线"的题上发生。

**Harm rate（luna 强 5 题 = reviewer 弱格子）**：initial 通过 13 个，改坏 2 个 =
**15.4%**。两例同型：满分 patch 被弱侧 reviewer 要求 revision，luna 修改后回归
（meriyah −3 F2P；sqlfmt −2 F2P −2 P2P）。与 rest 集 o→c 的 dateutil 案例合并,
"reviewer 弱于 modifier 时 revision 是净风险"已有 3 例，无反例。

**净读数**：capture 与 harm 数量级相同（+3/−2），当前配置在互补集上不构成可用的
路由替代；它证明的是**机制可行性**（迁移通道存在），不是**配置有效性**。

## 内部确认：官方 → 内部迁移对照

initial 即 luna xhigh 在本 harness 的单体代理成绩：

| Task | 方向 | 官方 luna xhigh | 内部 initial | 复现判定 |
|---|---|---:|---:|---|
| `meriyah-explicit-resource-declarations` | luna 强 | 4/4 | 2/4 | 弱化复现 |
| `superjson-error-stack-serialization` | luna 强 | 4/4 | **0/4** | **反转** |
| `numba-stencil-boundary-modes` | luna 强 | 4/4 | 4/4 | 复现 |
| `valibot-recursive-schema-composition` | luna 强 | 4/4 | 4/4 | 复现 |
| `sqlfmt-create-table-ddl-formatting` | luna 强 | 3/4 | 3/4 | 复现 |
| `eicrud-keyset-pagination-cursor` | flash 强 | 0/4 | 1/4（另三次 8/14） | 部分反转 |
| `onedump-dump-encryption-pipeline` | flash 强 | 0/4 | 0/4 | 复现 |
| `python-statemachine-state-data-scoping` | flash 强 | 0/4 | 1/4 | 复现（弱） |
| `prometheus-transactional-reload-status` | flash 强 | 1/4 | 0/4 | 复现 |
| `anko-typed-variable-bindings` | flash 强 | 1/4 | 0/4 | 复现 |

luna 强侧合计官方 19/20 → 内部 13/20。superjson 是继 rest 集 bandit（flash 侧）之后
第二例完全反转，说明官方 mini-swe 口径的逐题结论跨 harness 迁移风险是双向的。
superjson 的互补前提（luna 会做）在内部不成立，该题在 c→o 中实际处于"双弱"状态;
待 o→c 的 flash initial 数据落地后，按子集文档的替补规则决定去留。

## 对 o→c 方向与后续设计的建议

1. **o→c 照计划执行**，两处调整：event-silence 上调至 1200 秒（flash-max 当 modifier,
   本次 8 次 silence 触顶的主体换到关键路径上）；沿用 multiplier 1.5。
2. o→c 的观察重点由本次结果细化：codex reviewer 在 luna 强 5 题上的 capture 是否高于
   flash reviewer 的 16.7%（rest 集 +48 F2P 的先验支持更高值）；以及 flash-max initial
   对 flash 强 5 题的内部确认（决定 eicrud 之外的 4 题是"迁移失败"还是"前提不成立"）。
3. eicrud 的三次成功翻正值得单独做案例研究（review findings 内容 → revision diff 的
   对应关系），为"什么样的缺口可以被 findings 迁移"提供第一手材料。
4. superjson（luna 侧反转）、eicrud（flaky P2P + 官方反转）记入子集修订清单。
5. 机制层面的初步画像：**findings 通道可以迁移"补齐式"能力,但对"路线式"差距无效,
   且弱 reviewer 对强 patch 有 ~15% 的破坏率**。若 o→c 复现该画像，下一步实验应转向
   非对称保护机制（如 reviewer 置信度门槛、initial 通过可见测试时限制 revision 范围）,
   而不是继续扫配置组合。
