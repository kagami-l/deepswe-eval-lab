# opus-high 与 v4-flash-max 能力互补任务子集

更新日期：2026-08-12

为 `anthropic/claude-opus-5 [high]` 与 `deepseek/deepseek-v4-flash [max]` 的互补性实验准备的任务子集。筛选方法沿用 [opus/sol 互补子集](deepswe-opus-sol-complementary-subsets.md) 与 [luna/v4-flash 互补子集](deepswe-luna-v4flash-complementary-subset.md)。清单文件：[`wip/data/selection/complementary-opus-v4flash.txt`](../data/selection/complementary-opus-v4flash.txt)，前 5 题为 opus 强方向，后 5 题为 v4-flash 强方向。

## 定位与用途边界

这是按公开结果构造的**机制探测池**，不是无偏 benchmark。它适合检验路由、双模型协作等机制能否捕获已知的互补收益，不能用于模型排名或估计总体任务分布上的互补性。正式实验前仍需用内部 harness 对两配置各跑至少 4 次，只有复现互补性的题才进入 `complementary-core`。

本清单上 opus-high 为 21/40（52.5%），v4-flash-max 为 19/40（47.5%）；逐题 oracle 为 38/40（95%）。两配置只差 2 次通过，基本对齐；相对较强的单配置，oracle headroom 为 42.5 个百分点。

## 数据口径与筛选规则

- 数据源：`wip/data/official-v1.1/trials.json`（2026-08-07 下载快照），config 为 `mini_swe_agent_claude_opus_5_high` 与 `mini_swe_agent_deepseek_v4_flash_max`。
- 过滤条件：`source=deep-swe`、`eval_scope=full`、`included_in_score=true` 且 `errored=false`。每格为 `通过次数/有效重复数`，通常每格 4 次。
- 主阈值：强侧通过率 ≥ 0.75、弱侧 ≤ 0.25。证据分级为 A：4/4 vs 0/4；B：4/4 vs 1/4 或 3/4 vs 0/4；C：3/4 vs 1/4。`koota-query-predicates` 的 3/3 vs 0/4 单列 A⁻。
- 家族佐证：opus-5 合并 5 档 effort（通常 n=20）。opus 强题要求 opus 家族 > 10/20；v4-flash 强题要求 opus 家族 ≤ 10/20。v4-flash 只有 max 一个 config，无法从强侧或弱侧做家族佐证，因此两方向的证据强度不对称。
- 与 `05_sample_confirm` 隔离；`01_stable`、`v1-delta` 评分敏感和 `05_sample_dev` 只作质量标记，不自动剔除。严重 verifier 不稳定可覆盖档位优先级。
- 两方向各取 5 题。A 档原则上全收，但 `pwntools-tube-multiplexing` 因 9 次 verifier timeout 被稳定 B 档替换；v4-flash 强方向在主阈值下恰好只有 5 题，全部纳入。

## 推荐子集（10 题）

| # | 任务 | 方向 | 档 | opus high | v4-flash max | opus 家族 | 语言 | 标记 |
| --- | --- | --- | --- | ---: | ---: | ---: | --- | --- |
| 1 | `expr-try-catch-errors` | opus 强 | A | 4/4 | 0/4 | 18/20 | go |  |
| 2 | `langchain-request-coalescing` | opus 强 | A | 4/4 | 0/4 | 18/20 | python | 未进 01_stable†；评分敏感（Δ +0.13） |
| 3 | `participle-grammar-conflict-analysis` | opus 强 | A | 4/4 | 0/4 | 19/20 | go | 未进 01_stable†；评分敏感（Δ −0.14） |
| 4 | `testem-bail-on-test-failure` | opus 强 | A | 4/4 | 0/4 | 13/20 | javascript | 评分敏感（Δ −0.12） |
| 5 | `opa-rego-rule-profiling` | opus 强 | B | 4/4 | 1/4 | 19/20 | go |  |
| 6 | `bandit-interprocedural-taint-checks` | v4-flash 强 | A | 0/4 | 4/4 | 5/20 | python | 评分敏感（Δ −0.10） |
| 7 | `optique-conditional-option-dependencies` | v4-flash 强 | A | 0/4 | 4/4 | 9/20 | typescript |  |
| 8 | `httpx-streaming-json-iteration` | v4-flash 强 | B | 0/4 | 3/4 | 2/20 | python |  |
| 9 | `koota-deferred-mutation-buffer` | v4-flash 强 | B | 0/4 | 3/4 | 1/20 | typescript |  |
| 10 | `prometheus-transactional-reload-status` | v4-flash 强 | B | 1/4 | 4/4 | 5/20 | typescript | 评分敏感（Δ +0.10）；与 luna/v4-flash 清单重叠‡ |

opus 强方向排除 confirm 中的 `clack`，保留 4 道有效格均为 4/4 vs 0/4 的 A 档；第五道不用同为 A 档但 verifier timeout 严重的 `pwntools`，改取稳定、家族 19/20 且无主要质量标记的 `opa`。v4-flash 强方向的 5 道主阈值候选全部纳入，其中 `httpx`、`koota-deferred` 的强侧只有 3/4，内部确认时优先观察复现。

语言分布：go 3、python 3、typescript 3、javascript 1；10 题来自 10 个不同仓库，两个方向内也没有仓库重复。

† `langchain` 未进稳定池是因为 `minimum_effective_repeats = 3`，总体有 2 次 verifier timeout；`participle` 是因为 `minimum_effective_repeats = 2`，但 verifier timeout 为 0。两题在本文具体配对的格子均有完整 4 次有效重复，故保留并标记。

‡ `prometheus-transactional-reload-status` 在 luna/v4-flash 清单中也是 v4-flash 强题。机制调试池允许重叠，但并行实验应注明可能的调试经验迁移。

## 替补名单

| 任务 | 方向 | 档 | opus high | v4-flash max | opus 家族 | 标记 |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `numba-stencil-boundary-modes` | opus 强 | B | 4/4 | 1/4 | 19/20 | 首位替补；无主要质量标记 |
| `valibot-recursive-schema-composition` | opus 强 | B | 4/4 | 1/4 | 20/20 | 已在 05_sample_dev |
| `kombu-virtual-queue-dead-lettering` | opus 强 | B | 4/4 | 1/4 | 15/20 | 无主要质量标记 |
| `koota-pair-relation-tracking` | opus 强 | B | 4/4 | 1/4 | 14/20 | 无主要质量标记 |
| `obsidian-linter-link-format-conversion` | v4-flash 强 | D | 0/4 | 2/4 | 1/20 | **放宽主阈值**；首位应急替补 |
| `oxvg-structural-selector-preservation` | v4-flash 强 | D | 1/4 | 2/4 | 2/20 | **放宽主阈值**；评分敏感（Δ −0.10） |

v4-flash 强方向没有未入选的 A/B/C 档候选。若确认跑中有题未复现，首选缩小核心池；只有必须维持 5+5 平衡时才使用 D 档（v4-flash 2/4）的应急替补，并与严格核心分开报告。

## 完整候选扫描记录（28 题）

| 任务 | 方向 | 档 | opus high | v4-flash max | opus 家族 | 处置 |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `clack-async-autocomplete-options` | opus 强 | A | 4/4 | 0/4 | 17/20 | confirm |
| `expr-try-catch-errors` | opus 强 | A | 4/4 | 0/4 | 18/20 | 入选 |
| `langchain-request-coalescing` | opus 强 | A | 4/4 | 0/4 | 18/20 | 入选（质量标记） |
| `participle-grammar-conflict-analysis` | opus 强 | A | 4/4 | 0/4 | 19/20 | 入选（质量标记） |
| `pwntools-tube-multiplexing` | opus 强 | A | 4/4 | 0/4 | 14/15 | 排除（9 次 verifier timeout） |
| `testem-bail-on-test-failure` | opus 强 | A | 4/4 | 0/4 | 13/20 | 入选 |
| `koota-query-predicates` | opus 强 | A⁻ | 3/3 | 0/4 | 15/17 | 替补（未进 01_stable；3 次 verifier timeout） |
| `adaptix-name-mapping-aliases` | opus 强 | B | 4/4 | 1/4 | 20/20 | 替补（已在 05_sample_dev） |
| `go-critic-doc-link-checker` | opus 强 | B | 3/4 | 0/4 | 14/20 | confirm |
| `happy-dom-deterministic-intersectionobserver` | opus 强 | B | 3/4 | 0/4 | 11/20 | 替补 |
| `kombu-single-active-consumer-priority` | opus 强 | B | 4/4 | 1/4 | 17/20 | confirm |
| `kombu-virtual-queue-dead-lettering` | opus 强 | B | 4/4 | 1/4 | 15/20 | 替补 |
| `koota-pair-relation-tracking` | opus 强 | B | 4/4 | 1/4 | 14/20 | 替补 |
| `numba-stencil-boundary-modes` | opus 强 | B | 4/4 | 1/4 | 19/20 | 替补 |
| `opa-rego-rule-profiling` | opus 强 | B | 4/4 | 1/4 | 19/20 | 入选 |
| `skrub-duration-encoding` | opus 强 | B | 4/4 | 1/4 | 18/20 | 评分极敏感（Δ +0.38） |
| `sqlite-utils-safe-import-checkpoints` | opus 强 | B | 4/4 | 1/4 | 15/20 | 替补（已在 05_sample_dev） |
| `textual-kitty-key-phases` | opus 强 | B | 3/4 | 0/4 | 15/20 | 替补 |
| `valibot-recursive-schema-composition` | opus 强 | B | 4/4 | 1/4 | 20/20 | 替补（已在 05_sample_dev） |
| `bandit-incremental-cache-control` | opus 强 | C | 3/4 | 1/4 | 15/20 | C 档；已在 05_sample_dev；评分敏感 |
| `fastapi-deprecation-response-headers` | opus 强 | C | 3/4 | 1/4 | 17/20 | confirm 且 C 档 |
| `kea-atomic-signal-selectors` | opus 强 | C | 3/4 | 1/4 | 12/20 | C 档 |
| `pest-character-class-coalescing` | opus 强 | C | 3/4 | 1/4 | 18/20 | C 档 |
| `bandit-interprocedural-taint-checks` | v4-flash 强 | A | 0/4 | 4/4 | 5/20 | 入选 |
| `optique-conditional-option-dependencies` | v4-flash 强 | A | 0/4 | 4/4 | 9/20 | 入选 |
| `httpx-streaming-json-iteration` | v4-flash 强 | B | 0/4 | 3/4 | 2/20 | 入选 |
| `koota-deferred-mutation-buffer` | v4-flash 强 | B | 0/4 | 3/4 | 1/20 | 入选 |
| `prometheus-transactional-reload-status` | v4-flash 强 | B | 1/4 | 4/4 | 5/20 | 入选 |

完整扫描中 opus 强 23 题、v4-flash 强 5 题。opus 家族列能佐证“opus 是否普遍强/弱”，但 v4-flash 没有 effort 家族数据；因此内部重复确认尤其不能省略。
