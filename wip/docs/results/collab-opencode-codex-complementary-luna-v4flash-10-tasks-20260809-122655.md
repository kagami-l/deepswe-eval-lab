# collab-opencode-codex-complementary-luna-v4flash 结果分析（含配对重打分）

分析日期：2026-08-10。

本文是 [luna/v4-flash 互补子集](../deepswe-luna-v4flash-complementary-subset.md) 上的第二个
collab 方向：OpenCode/DeepSeek-v4-flash（max）modifier + Codex/luna（xhigh）reviewer。与
[c→o 方向](collab-codex-opencode-complementary-luna-v4flash-10-tasks-20260809-003646.md)
互为对照；两方向合并结论见
[互补实验总结](complementary-luna-v4flash-collab-summary.md)。

原始工件：

- [job result](../../../jobs/collab-opencode-codex-complementary-luna-v4flash-10-tasks-20260809-122655/result.json)
- [job config](../../../jobs/collab-opencode-codex-complementary-luna-v4flash-10-tasks-20260809-122655/config.json)
- [run manifest](../../../jobs/.agent-eval-manifests/collab-opencode-codex-complementary-luna-v4flash-10-tasks-20260809-122655.json)
- [patch-scores 汇总](../../../jobs/collab-opencode-codex-complementary-luna-v4flash-10-tasks-20260809-122655/patch-scores/summary.json)
- [配对表 pairs.csv](../../../jobs/collab-opencode-codex-complementary-luna-v4flash-10-tasks-20260809-122655/patch-scores/pairs.csv)
- [阶段表 stages.csv](../../../jobs/collab-opencode-codex-complementary-luna-v4flash-10-tasks-20260809-122655/patch-scores/stages.csv)

## 结论

1. 正式 reward `17/40 = 42.5%`，task-level pass@4 `7/10`（meriyah、superjson、sqlfmt 全败）。
   40/40 完成 verifier，2 个 trial 为 modifier 首轮实现超时（无 patch、ineligible）。
2. **核心发现（证伪强先验）：codex reviewer 在 luna 强格子的 capture = 0/14。** rest 集
   +48 F2P 展示的推动力没有在互补格子兑现。stage 轨迹给出了原因：flash 在 luna 强题上的
   失败是**路线级**的（多数 initial 接近 0 F2P），而 findings 通道只能传递"补齐式"信息,
   无法在 3 轮 review 内传授一条实现路线。
3. 配对净结果 +1：initial `16/38 = 42.1%` → final `17/38 = 44.7%`，1 修好、**0 修坏**,
   CI `[0, +0.079]`。唯一翻转（anko `uKc9Di6`，F2P 5/9 → 9/9）仍是"补齐式"，且发生在
   flash 自己的强侧任务上。**强 reviewer 零破坏**（16 个 initial 通过全部保住），与
   flash reviewer 15.4% 的 harm rate 形成鲜明对照。
4. **预算是本方向的第一约束，multiplier 1.5 仍不够**：16 个 degraded（全部 timeout）+
   2 个 modifier 首轮超时，中位 trial 105 分钟、最长 135 分钟贴住 8100 秒上限。codex
   reviewer 的高强度审查（83 轮 review、59 次 revision，是 flash reviewer 的 3 倍）进一步
   压缩了预算。1200 秒 watchdog 零触发（codex reviewer 事件频繁），本方向的瓶颈不在
   watchdog 而在总预算。
5. 评分管线完全干净：97 个 unique patch 全部评分成功，conformance `38/38 matched`,
   exit 0，无本 job 的 flaky 事件。
6. **flash 侧内部确认喜忧参半**：eicrud、python-statemachine 强复现,anko 部分复现;
   **onedump（官方 4/4 → 内部 1/4）、prometheus-transactional（官方 4/4 → 内部 1/4）
   大幅弱化**；numba 反向反转（官方 1/4 → 内部 4/4，变成双强题）。

## 运行配置

| 项目 | 值 |
|---|---|
| 开始 / 结束时间 | 2026-08-09 12:27:01 / 08-10 06:09:56 CST（约 17 小时 43 分） |
| 任务数 / trials | 10 / 40（每题 4 次），并发 4 |
| Modifier | OpenCode `deepseek/deepseek-v4-flash`，effort `max`，permissions `auto` |
| Reviewer | Codex `gpt-5.6-luna`，effort `xhigh`，permissions `bypass` |
| Budget | `--agent-timeout-multiplier 1.5` → hard 8100 / soft 7800 秒 |
| Event-silence watchdog | **1200 秒**（依 c→o 的 8 次 900 秒触顶经验上调） |
| Runtime | `deep-swe/agent-runtime:bd704fc758b47046` |
| `maxReviews` / `maxAgentAttempts` | 3 / 2 |
| Pier | `0.3.0` |

## 汇总指标

| 指标 | 值 |
|---|---:|
| Reward | 17 / 40（42.5%） |
| Task-level pass@4 | 7 / 10 |
| Outcome 分布 | 11 approved / 11 max_reviews_reached / 16 degraded（全 timeout）/ 2 modifier 超时 |
| 平均 / 中位 / 最长 trial | 98 分 / 105 分 / 135 分 |
| Review 轮次 / revision | 83 / 59 |
| Reviewer attempts | 86（3 失败，**0 event_silence**） |
| Pier 记录 input / output tokens | 216,152,795 / 3,396,340 |
| Pier 记录 cost | `$5.2556`（仅 OpenCode modifier；flash-max 成本显著高于 high 档历史 job） |

## Task 级配对结果

`initial→final` 为通过数（eligible trial 口径）；rev 为该任务 revision 总数。

| Task | 方向 | initial | final | rev | Outcomes |
|---|---|---:|---:|---:|---|
| `meriyah-explicit-resource-declarations` | luna 强 | 0/3 | 0/3 | 2 | 3 degraded（另 1 errored） |
| `superjson-error-stack-serialization` | luna 强 | 0/4 | 0/4 | 10 | 3 max_reviews + 1 approved |
| `numba-stencil-boundary-modes` | luna 强 | 4/4 | 4/4 | 1 | 4 degraded |
| `valibot-recursive-schema-composition` | luna 强 | 1/4 | 1/4 | 3 | 1 approved + 3 degraded |
| `sqlfmt-create-table-ddl-formatting` | luna 强 | 0/4 | 0/4 | 6 | 4 degraded |
| `eicrud-keyset-pagination-cursor` | flash 强 | 4/4 | 4/4 | 12 | 4 max_reviews |
| `onedump-dump-encryption-pipeline` | flash 强 | 1/4 | 1/4 | 6 | 3 approved + 1 max_reviews |
| `python-statemachine-state-data-scoping` | flash 强 | 3/3 | 3/3 | 4 | 2 degraded + 1 approved（另 1 errored） |
| `prometheus-transactional-reload-status` | flash 强 | 1/4 | 1/4 | 4 | 4 approved |
| `anko-typed-variable-bindings` | flash 强 | 2/4 | **3/4 ▲** | 11 | 3 max_reviews + 1 approved |
| **luna 强合计** | | **5/19** | **5/19** | | |
| **flash 强合计** | | **11/19** | **12/19** | | |

### 配对汇总

| 口径 | 对数 | initial | final | 修好 | 修坏 | McNemar | 95% CI |
|---|---:|---:|---:|---:|---:|---:|---|
| Intention-to-treat | 38 | 42.1% | 44.7% | 1 | 0 | 1.0 | [0, +0.079] |
| Completed-protocol | 22 | 45.5% | 50.0% | 1 | 0 | — | — |

## 各 trial 的 review / revision 轮次与最终状态

`Review` 为"启动轮次 / 有效 review 数"（有效 = 产出可解析 review.json）；`Att(失败)` 为
reviewer attempts 及其中失败数；`Verdict` 为最后一个有效 verdict。

| Trial | Review | Att(失败) | Revision | Verdict | Outcome | Reward |
|---|---:|---:|---:|---|---|---:|
| anko `9FrCT8D` | 3 / 3 | 3(0) | 3 | revise | max_reviews | 1 |
| anko `SaSbReh` | 3 / 3 | 3(0) | 3 | revise | max_reviews | 1 |
| anko `uKc9Di6` | 3 / 3 | 3(0) | 3 | revise | max_reviews | 1 |
| anko `vnEsQiD` | 3 / 3 | 3(0) | 2 | approve | approved | 0 |
| eicrud `8UU5xpD` | 3 / 3 | 3(0) | 3 | revise | max_reviews | 1 |
| eicrud `AWC7J2x` | 3 / 3 | 3(0) | 3 | revise | max_reviews | 1 |
| eicrud `CBbSfAB` | 3 / 3 | 3(0) | 3 | revise | max_reviews | 1 |
| eicrud `qsfMSpr` | 3 / 3 | 3(0) | 3 | revise | max_reviews | 1 |
| meriyah `7sfkjw8` | 0 / 0 | 0(0) | 0 | — | modifier 超时 | 0 |
| meriyah `amNrPRg` | 2 / 1 | 2(1) | 1 | revise | degraded/timeout | 0 |
| meriyah `o8gmksP` | 1 / 1 | 1(0) | 0 | revise | degraded/timeout | 0 |
| meriyah `wVE3uNB` | 2 / 1 | 2(1) | 1 | revise | degraded/timeout | 0 |
| numba `AMC8TZv` | 1 / 1 | 1(0) | 0 | revise | degraded/timeout | 1 |
| numba `HsegjVk` | 1 / 1 | 1(0) | 0 | revise | degraded/timeout | 1 |
| numba `LwMsGru` | 1 / 1 | 1(0) | 0 | revise | degraded/timeout | 1 |
| numba `MYCeHn7` | 2 / 2 | 2(0) | 1 | revise | degraded/timeout | 1 |
| onedump `3jPo4ES` | 1 / 1 | 1(0) | 0 | approve | approved | 0 |
| onedump `4rKWyiB` | 3 / 3 | 3(0) | 3 | revise | max_reviews | 1 |
| onedump `WDaxabR` | 3 / 3 | 3(0) | 2 | approve | approved | 0 |
| onedump `nPBk8gU` | 2 / 2 | 2(0) | 1 | approve | approved | 0 |
| prometheus-t `CMY9Pfu` | 3 / 3 | 3(0) | 2 | approve | approved | 1 |
| prometheus-t `EZDNc7n` | 1 / 1 | 1(0) | 0 | approve | approved | 0 |
| prometheus-t `Xm6eCrZ` | 2 / 2 | 2(0) | 1 | approve | approved | 0 |
| prometheus-t `kqY6ZS7` | 2 / 2 | 2(0) | 1 | approve | approved | 0 |
| psm `4mFbwzo` | 1 / 1 | 1(0) | 0 | revise | degraded/timeout | 1 |
| psm `X6WP3Uh` | 3 / 3 | 3(0) | 2 | approve | approved | 1 |
| psm `a92ucSD` | 0 / 0 | 0(0) | 0 | — | modifier 超时 | 0 |
| psm `u6vvBrA` | 3 / 3 | 3(0) | 2 | revise | degraded/timeout | 1 |
| sqlfmt `2Qrqwff` | 3 / 3 | 3(0) | 2 | revise | degraded/timeout | 0 |
| sqlfmt `9H9gr84` | 3 / 3 | 3(0) | 2 | revise | degraded/timeout | 0 |
| sqlfmt `C99mZ2q` | 2 / 2 | 2(0) | 1 | revise | degraded/timeout | 0 |
| sqlfmt `UE3moA4` | 2 / 1 | 2(1) | 1 | revise | degraded/timeout | 0 |
| superjson `H7TtpUF` | 3 / 3 | 3(0) | 3 | revise | max_reviews | 0 |
| superjson `NAzKsWG` | 2 / 2 | 2(0) | 1 | approve | approved | 0 |
| superjson `XT8bdX3` | 3 / 3 | 3(0) | 3 | revise | max_reviews | 0 |
| superjson `diMRCMi` | 3 / 3 | 3(0) | 3 | revise | max_reviews | 0 |
| valibot `57QnYbG` | 2 / 2 | 2(0) | 1 | approve | approved | 1 |
| valibot `9943h7x` | 2 / 2 | 2(0) | 1 | revise | degraded/timeout | 0 |
| valibot `veWRUwK` | 2 / 2 | 2(0) | 1 | revise | degraded/timeout | 0 |
| valibot `wAadiQP` | 1 / 1 | 1(0) | 0 | revise | degraded/timeout | 0 |

汇总关系：

- 86 个 review 轮次被启动，83 个形成有效 review；3 个失败轮（meriyah ×2、sqlfmt ×1）的
  attempt 各失败一次且未能在剩余预算内重试成功。0 个 event_silence（1200 秒 watchdog
  全程未触发,失败均为总预算耗尽）。
- 83 个有效 verdict：**11 approve / 72 revise（87% revise 率）**；产生 findings 197 个,
  其中 blocking（critical/major）176 个（**89%**）。对照 confirm 集的 flash reviewer
  （45 个 verdict 中 20 approve、104 findings 中 35 blocking），codex reviewer 的审查
  严格度完全是另一个量级。
- 流程形态：2 个 modifier 首轮超时；2 个首轮 approve；5 个 1 次 revision 后 approve;
  4 个 2 次 revision 后 approve；11 个打满 max_reviews（3 review + final-revision）;
  16 个在 review/revision 途中耗尽预算 degraded（rev 0 / 1 / 2 各 6 / 7 / 3 个）。
- 严格度的代价与收益不对称：11 个 max_reviews trial 中 8 个 reward=1（reviewer 到最后
  仍在 revise 已通过 verifier 的 patch——审查目标与 verifier 口径错位）；而它推动的
  59 次 revision 只产生 1 次 reward 翻转。approve 的 11 个 trial 中 reward=1 仅 3 个,
  `approved-but-verifier-failed` 为 8/11,方向与 flash reviewer 相同。

## 预注册指标读数

**Capture rate（luna 强 5 题 = codex reviewer 强格子）**：initial 失败 14 个，翻转 **0 个**。
codex reviewer 并非没有努力——superjson 10 次 revision、sqlfmt 6 次——revision 在推进
（部分 trial F2P 有增长）但没有一个跨过 verifier 阈值。与 c→o 方向 eicrud 三连翻的对比
说明：capture 的决定因素不是 reviewer 的能力或投入,而是**缺口的类型**（初始 patch 是否
已有可补齐的骨架）。

**Harm rate（flash 强 5 题 + 其他 initial 通过 = 16 个）**：改坏 **0 个**。codex reviewer
的 findings 精度足以避免把好 patch 改坏,弱侧 reviewer（flash）则做不到（c→o 为 2/13）。

## score-patches

| 项目 | 值 |
|---|---|
| Stage 实例 | 135（38 initial + 59 revision + 38 final） |
| Unique patch | 97，0 cached，全部成功 |
| Final conformance | matched 38 / mismatched 0 |
| Coverage / exit | 38/38 对完整 + 2 ineligible；exit 0 |

## 内部确认：flash-max 官方 → 内部迁移对照

initial 即 flash-max 在本 harness 的单体代理成绩：

| Task | 方向 | 官方 flash max | 内部 initial | 判定 |
|---|---|---:|---:|---|
| `meriyah` | luna 强 | 0/4 | 0/3 | 复现（弱侧确认） |
| `superjson` | luna 强 | 0/4 | 0/4 | 复现（与 luna 侧 0/4 合并 → **双弱**） |
| `numba` | luna 强 | 1/4 | **4/4** | **反向反转 → 双强** |
| `valibot` | luna 强 | 1/4 | 1/4 | 复现 |
| `sqlfmt` | luna 强 | 0/4 | 0/4 | 复现 |
| `eicrud` | flash 强 | 4/4 | 4/4 | 复现（强侧确认） |
| `onedump` | flash 强 | 4/4 | **1/4** | **大幅弱化** |
| `python-statemachine` | flash 强 | 4/4 | 3/3 | 复现 |
| `prometheus-transactional` | flash 强 | 4/4 | **1/4** | **大幅弱化** |
| `anko` | flash 强 | 3/4 | 2/4 | 复现（弱） |

## 建议

1. 本 job 正式计为 `17/40`；flash-max 单体基线记为 initial 的 `16/38`。
2. 机制结论与子集修订并入[互补实验总结](complementary-luna-v4flash-collab-summary.md),
   此处不重复。
3. 若未来在该方向继续实验,预算应再放宽（multiplier ≥2）或把 `maxReviews` 降到 2:
   16 个 degraded timeout 中大部分是 codex reviewer 的多轮审查耗尽预算所致，而这些审查
   在 capture 上颗粒无收——当前配置把算力花在了机制无法兑现的地方。
