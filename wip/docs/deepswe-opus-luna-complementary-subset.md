# opus-high 与 luna-max 能力互补任务子集

更新日期：2026-08-12

为 `anthropic/claude-opus-5 [high]` 与 `openai/gpt-5-6-luna [max]` 的互补性实验准备的任务子集。筛选方法沿用 [opus/sol 互补子集](deepswe-opus-sol-complementary-subsets.md) 与 [luna/v4-flash 互补子集](deepswe-luna-v4flash-complementary-subset.md)。清单文件：[`wip/data/selection/complementary-opus-luna-max.txt`](../data/selection/complementary-opus-luna-max.txt)，前 5 题为 opus 强方向，后 5 题为 luna 强方向。

## 定位与用途边界

这是按公开结果构造的**机制探测池**，不是无偏 benchmark。它适合检验路由、双模型协作等机制能否捕获已知的互补收益，不适合做模型排名或估计两模型在总体任务分布上的互补性。正式实验前仍需用内部 harness 对两配置各跑至少 4 次，只有复现互补性的题才进入 `complementary-core`。

本清单上两配置的官方通过数恰好相同：opus-high 与 luna-max 均为 21/40（52.5%）；逐题 oracle 为 38/40（95%），理论 headroom 明确且不存在整体强弱差异。

## 数据口径与筛选规则

- 数据源：`wip/data/official-v1.1/trials.json`（2026-08-07 下载快照），config 为 `mini_swe_agent_claude_opus_5_high` 与 `mini_swe_agent_gpt_5_6_luna_max`。
- 过滤条件：`source=deep-swe`、`eval_scope=full`、`included_in_score=true` 且 `errored=false`。每格为 `通过次数/有效重复数`，通常每格 4 次。
- 主阈值：强侧通过率 ≥ 0.75、弱侧 ≤ 0.25。证据分级为 A：4/4 vs 0/4；B：4/4 vs 1/4 或 3/4 vs 0/4；C：3/4 vs 1/4。`koota-query-predicates` 的 3/3 vs 0/4 单列 A⁻。
- 家族佐证：opus-5 与 luna 均合并各自 5 档 effort（通常 n=20）；要求弱侧家族 ≤ 10/20，且强侧家族通过率高于弱侧。
- 与 `05_sample_confirm` 隔离；`01_stable`、`v1-delta` 评分敏感和 `05_sample_dev` 只作质量标记，不自动剔除。
- 两方向各取 5 题，A 档全收，B 档优先强侧满格、家族差距和仓库/语言分散。

## 推荐子集（10 题）

| # | 任务 | 方向 | 档 | opus high | luna max | opus 家族 | luna 家族 | 语言 | 标记 |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | `helm-array-merge-strategies` | opus 强 | A | 4/4 | 0/4 | 14/20 | 1/20 | go | 评分敏感（Δ +0.20） |
| 2 | `obsidian-linter-scoped-ignore-markers` | opus 强 | A | 4/4 | 0/4 | 19/20 | 3/20 | typescript | 已在 05_sample_dev；评分敏感（Δ −0.10） |
| 3 | `dasel-html-document-format` | opus 强 | B | 4/4 | 1/4 | 20/20 | 1/20 | go | 已在 05_sample_dev；评分敏感（Δ +0.12） |
| 4 | `python-statemachine-state-data-scoping` | opus 强 | B | 4/4 | 1/4 | 16/20 | 2/20 | python | 与既有互补清单重叠† |
| 5 | `pest-character-class-coalescing` | opus 强 | B | 3/4 | 0/4 | 18/20 | 0/20 | rust |  |
| 6 | `bandit-interprocedural-taint-checks` | luna 强 | A | 0/4 | 4/4 | 5/20 | 8/20 | python | 家族差距较小；评分敏感（Δ −0.10） |
| 7 | `meriyah-explicit-resource-declarations` | luna 强 | A | 0/4 | 4/4 | 0/20 | 9/20 | typescript | 与 luna/v4-flash 清单重叠† |
| 8 | `koota-deferred-mutation-buffer` | luna 强 | B | 0/4 | 3/4 | 1/20 | 8/20 | typescript |  |
| 9 | `scc-bounded-memory-spilling` | luna 强 | B | 1/4 | 4/4 | 7/20 | 13/20 | go | 评分敏感（Δ +0.17） |
| 10 | `superjson-error-stack-serialization` | luna 强 | B | 1/4 | 4/4 | 3/20 | 11/20 | typescript | 未进 01_stable‡；与 luna/v4-flash 清单重叠† |

opus 强方向的两个 A 档在隔离 confirm 后全部纳入；B 档优先 `dasel`、`python-statemachine` 两道强侧 4/4 题，再以家族差距最大的 `pest` 补足。luna 强方向两个 A 档全收；B 档选择 `koota-deferred`、`scc`、`superjson`，淘汰家族佐证弱的 `ink`、家族不佐证的 `optique` 和评分变化极端的 `vulture`。

语言分布：typescript 4、go 3、python 2、rust 1；10 题来自 10 个不同仓库。强方向内也没有仓库重复。

† `python-statemachine` 在 luna/v4-flash 清单中是 flash 强题，本清单中是 opus 强题，均体现 luna 弱；`meriyah`、`superjson` 在两份清单中均为 luna 强题。机制调试池之间允许重叠，但并行实验应注明可能的调试经验迁移。

‡ `superjson` 未进稳定池是因为个别其他 config 无有效重复（`minimum_effective_repeats = 0`）；总体错误率 0.025、verifier timeout 为 0，不直接损害本文两格，但应保留质量标记。

## 替补名单

| 任务 | 方向 | 档 | opus high | luna max | 家族 | 标记 |
| --- | --- | --- | ---: | ---: | --- | --- |
| `kea-atomic-signal-selectors` | opus 强 | B | 3/4 | 0/4 | 12/20 vs 0/20 | 首位替补；无主要质量标记 |
| `textual-kitty-key-phases` | opus 强 | B | 3/4 | 0/4 | 15/20 vs 0/20 | 无主要质量标记 |
| `happy-dom-deterministic-intersectionobserver` | opus 强 | B | 3/4 | 0/4 | 11/20 vs 2/20 | opus 家族仅略过半 |
| `koota-query-predicates` | opus 强 | A⁻ | 3/3 | 0/4 | 15/17 vs 0/20 | 未进 01_stable；3 次 verifier timeout |
| `ink-grid-box-layout` | luna 强 | B | 0/4 | 3/4 | 2/20 vs 4/20 | luna 家族仅 4/20，档位依赖强 |
| `vulture-persistent-analysis-cache` | luna 强 | B | 0/4 | 3/4 | 0/20 vs 10/20 | 评分极敏感（Δ −0.60），仅作末位替补 |

luna 强方向在以上两题之后没有其他通过家族佐证的主阈值候选；若入选题确认失败，宁可缩小核心池，也不应把 `optique` 当作同等证据的替补。

## 完整候选扫描记录（21 题）

| 任务 | 方向 | 档 | opus high | luna max | opus 家族 | luna 家族 | 处置 |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `clack-async-autocomplete-options` | opus 强 | A | 4/4 | 0/4 | 17/20 | 1/20 | confirm |
| `helm-array-merge-strategies` | opus 强 | A | 4/4 | 0/4 | 14/20 | 1/20 | 入选 |
| `obsidian-linter-scoped-ignore-markers` | opus 强 | A | 4/4 | 0/4 | 19/20 | 3/20 | 入选 |
| `koota-query-predicates` | opus 强 | A⁻ | 3/3 | 0/4 | 15/17 | 0/20 | 替补（质量标记） |
| `dasel-html-document-format` | opus 强 | B | 4/4 | 1/4 | 20/20 | 1/20 | 入选 |
| `happy-dom-deterministic-intersectionobserver` | opus 强 | B | 3/4 | 0/4 | 11/20 | 2/20 | 替补 |
| `kea-atomic-signal-selectors` | opus 强 | B | 3/4 | 0/4 | 12/20 | 0/20 | 替补 |
| `pest-character-class-coalescing` | opus 强 | B | 3/4 | 0/4 | 18/20 | 0/20 | 入选 |
| `pwntools-tube-multiplexing` | opus 强 | B | 4/4 | 1/4 | 14/15 | 3/20 | 未进 01_stable；9 次 verifier timeout |
| `python-statemachine-state-data-scoping` | opus 强 | B | 4/4 | 1/4 | 16/20 | 2/20 | 入选 |
| `textual-kitty-key-phases` | opus 强 | B | 3/4 | 0/4 | 15/20 | 0/20 | 替补 |
| `fastapi-deprecation-response-headers` | opus 强 | C | 3/4 | 1/4 | 17/20 | 4/20 | confirm 且 C 档 |
| `katex-multicolumn-array-spans` | opus 强 | C | 3/4 | 1/4 | 12/20 | 2/20 | C 档 |
| `bandit-interprocedural-taint-checks` | luna 强 | A | 0/4 | 4/4 | 5/20 | 8/20 | 入选 |
| `meriyah-explicit-resource-declarations` | luna 强 | A | 0/4 | 4/4 | 0/20 | 9/20 | 入选 |
| `ink-grid-box-layout` | luna 强 | B | 0/4 | 3/4 | 2/20 | 4/20 | 替补（家族佐证弱） |
| `koota-deferred-mutation-buffer` | luna 强 | B | 0/4 | 3/4 | 1/20 | 8/20 | 入选 |
| `optique-conditional-option-dependencies` | luna 强 | B | 0/4 | 3/4 | 9/20 | 7/20 | 家族不佐证 |
| `scc-bounded-memory-spilling` | luna 强 | B | 1/4 | 4/4 | 7/20 | 13/20 | 入选 |
| `superjson-error-stack-serialization` | luna 强 | B | 1/4 | 4/4 | 3/20 | 11/20 | 入选（质量标记） |
| `vulture-persistent-analysis-cache` | luna 强 | B | 0/4 | 3/4 | 0/20 | 10/20 | 替补（评分极敏感） |

两侧扫描都使用完整 5 档家族佐证，但具体配对与家族汇总共享数据，家族列不是独立复现。清单仍须经内部 harness 的重复确认后才能用于正式机制结论。
