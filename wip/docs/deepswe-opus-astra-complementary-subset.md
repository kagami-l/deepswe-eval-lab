# Opus high 与 Astra medium 能力互补任务子集

更新日期：2026-09-08

为 `anthropic/claude-opus-5 [high]` 与 `openai/gpt-6-astra [medium]` 准备的 10 题互补机制探测池，沿用 [opus/sol 互补子集](deepswe-opus-sol-complementary-subsets.md) 的主阈值、证据分级与双侧家族佐证。

- [推荐运行清单：10 题](../data/selection/complementary-opus-astra-medium.txt)：前 5 题 Opus 强，后 5 题 Astra 强。
- [家族佐证后的完整候选池：16 题](../data/selection/complementary-opus-astra-medium-candidates.txt)：前 9 题 Opus 强，后 7 题 Astra 强；包括替补，不能当作方向平衡池。
- [机器可读证据与输入哈希](../data/selection/complementary-opus-astra-medium.json)：保留全部 18 道主阈值命中题、逐 effort 计数、质量指标及入选/淘汰原因。以上清单为手工决选，不由主筛选脚本自动更新。

## 结论与口径

推荐池为 **9 道 A 档、1 道 B 档，10 个不同仓库**；无需引入 C 档或放宽强弱阈值。Opus high 为 **21/40（52.5%）**，Astra medium 为 **20/40（50%）**；逐题选择公开通过率较高配置的经验 oracle 为 **40/40（100%）**，比最佳固定配置高 47.5 个百分点。

这里的 oracle 是 `mean(max(p_opus(task), p_astra(task)))`，是在同一份选题数据上计算的乐观参考，不是双模型实际协作通过率，也不是未来表现的保证。此池用于探测路由/协作能否捕获已知差异，不用于模型总体排名。内部 harness 的确认实验尚未运行。

数据取自 2026-09-08 下载的官方 v1.1 快照（70 个 config、31,617 次 rollout、113 题；榜单 generated_at 为 2026-09-03T22:24:37.984682+00:00）。主配置是 `mini_swe_agent_claude_opus_5_high` 和 `mini_swe_agent_gpt_6_astra_medium`。只计 `source=deep-swe`、`eval_scope=full`、`included_in_score=true`、`errored=false`，以 `passed` 统计通过次数，不能仅按异常字段删行。目标配置在所有 18 道候选上各有 4 次有效重复，本文 10 题两侧各有 40 次。

## 筛选规则

1. 扫描全部 113 题：强侧通过率 ≥ 0.75、弱侧 ≤ 0.25；至少 3 次有效重复，本次所有命中格均为 4 次。得到 Opus 强 11 题、Astra 强 7 题。
2. 沿用 A（4/4 vs 0/4）、B（4/4 vs 1/4 或 3/4 vs 0/4）、C（3/4 vs 1/4）分级；对应单侧 Fisher p 分别约 0.014、0.071、0.243。这些值未校正扫描和方向选择，不作显著性结论。
3. 合并两模型各自 low/medium/high/xhigh/max 五档：弱侧家族通过率 ≤ 50%，强侧家族通过率严格高于弱侧。剔除 `anko-typed-variable-bindings`、`abs-module-cache-flags`，留下 Opus 强 9 题、Astra 强 7 题。
4. 扣除 `host-excluded.txt`；沿用 opus/sol 文档 2026-08-13 的机制探索线决策，不再硬性隔离 confirm，但保留重叠标记。本次 18 道命中题均不在 host-excluded 或 confirm；推荐 10 题也不在 dev。
5. 方向各取 5 题，优先 A，再 B。旧规则中的“A 档全收”在本次 Opus 方向有 6 道 A、名额只有 5 个时无法同时满足；同档综合质量标记、家族佐证及仓库/语言分散决选，未选的 A 作为首位替补，理由见下文。
6. 稳定性和评分敏感仅作质量标记，不自动淘汰。评分 delta 使用最新 `v1-delta.json`（9 个共享配置），不复制旧报告中的数值。历史 `01_stable` 不改写；当前质量按同样规则重新统计：28 个 base model 的覆盖门槛为 `ceil(28 × 17/18) = 27`，每 config 至少 3 个有效重复，错误率 ≤ 5%，verifier timeout ≤ 1。

## 推荐 10 题

| 任务 | 方向 | 档 | Opus high | Astra medium | Opus 家族 | Astra 家族 | 语言 / 标记 |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `wazero-multi-module-snapshots` | opus 强 | A | 4/4 | 0/4 | 19/20 | 0/20 | go；未过稳定条件 |
| `ts-pattern-match-each` | opus 强 | A | 4/4 | 0/4 | 17/20 | 0/20 | typescript；— |
| `python-statemachine-state-data-scoping` | opus 强 | A | 4/4 | 0/4 | 16/20 | 0/20 | python；— |
| `helm-array-merge-strategies` | opus 强 | A | 4/4 | 0/4 | 14/20 | 0/20 | go；评分敏感 Δ +0.1667 |
| `testem-bail-on-test-failure` | opus 强 | A | 4/4 | 0/4 | 13/20 | 0/20 | javascript；评分敏感 Δ -0.1111 |
| `httpx-streaming-json-iteration` | astra 强 | A | 0/4 | 4/4 | 2/20 | 20/20 | python；— |
| `koota-deferred-mutation-buffer` | astra 强 | A | 0/4 | 4/4 | 1/20 | 19/20 | typescript；— |
| `bandit-interprocedural-taint-checks` | astra 强 | A | 0/4 | 4/4 | 5/20 | 19/20 | python；评分敏感 Δ -0.1111 |
| `optique-conditional-option-dependencies` | astra 强 | A | 0/4 | 4/4 | 9/20 | 19/20 | typescript；Opus 其他 effort 9/16 |
| `scc-bounded-memory-spilling` | astra 强 | B | 1/4 | 4/4 | 7/20 | 20/20 | go；评分敏感 Δ +0.1389 |

语言分布：Go 3、Python 3、TypeScript 3、JavaScript 1；10 题来自 10 个不同仓库。

Opus 方向选择 `wazero`、`ts-pattern`、`python-statemachine`、`helm`、`testem`。6 道 A 档中，`participle` 与 `wazero` 的家族计数同为 19/20 vs 0/20，也都因其他配置重复不足带稳定性标记，但 `participle` 还带评分敏感标记，因此保留 `wazero`、将 `participle` 置于首位替补。保留 `testem` 也提供 JavaScript 覆盖；这是一项手工决选，并非声称它在统计上比 `participle` 更强。推荐 Opus 方向的 5 题在 Astra 全五档均为 0/20。

Astra 方向 4 道 A 档全部纳入，第 5 席取 B 档 `scc`。`superjson` 同为 4/4 vs 1/4、家族差距稍大（17/20 vs 3/20，而 scc 为 20/20 vs 7/20），但它有其他配置重复不足的标记，并会使该方向 5 题中的 3 题集中在 TypeScript。`scc` 满足当前稳定条件、Astra 家族 20/20，并补充 Go；其评分敏感标记仍需报告。

## 质量与家族证据的边界

- `wazero` 的全池错误率为 2/280 ≈ 0.71%，verifier timeout 为 0；未过稳定条件仅因 `claude-opus-4-8 [max]` 有 2 次 provider timeout、只余 2 次有效重复。目标两格和双方五档家族均完整，故保留。
- 推荐池评分敏感题为 `helm`（Δ +0.1667）、`testem`（−0.1111）、`bandit-interprocedural`（−0.1111）、`scc`（+0.1389）。应分别报告含/不含评分敏感题的结果；移除后方向变为 3:3。若同时移除稳定性标记的 `wazero`，余 5 题，方向为 2:3，不再强求平衡。
- `participle` 全池错误率 4/280 ≈ 1.43%，最少有效重复为 2，verifier timeout 为 0；`superjson` 为 5/279 ≈ 1.79%，最少有效重复为 0，verifier timeout 为 0。均为其他配置的 provider timeout，不影响本文目标两格，但列入替补时仍保留标记。
- 家族汇总含目标配置本身，不是独立复现。证据 JSON 另存去掉目标配置后的其他四档计数。特别是 `optique`：全家族为 Opus 9/20 vs Astra 19/20，去掉目标档后为 9/16 vs 15/16；方向仍一致，但 Opus 其他档位已超过 50%，不能将它描述为“Opus 全系都做不出”。其余推荐题去掉目标档后仍满足弱侧 ≤ 50% 且家族方向一致。

## 全部主阈值候选及处置（18 题）

| 任务 | 方向 | 档 | Opus high | Astra medium | Opus 家族 | Astra 家族 | 处置 |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `helm-array-merge-strategies` | opus 强 | A | 4/4 | 0/4 | 14/20 | 0/20 | 入选第 4 题 |
| `participle-grammar-conflict-analysis` | opus 强 | A | 4/4 | 0/4 | 19/20 | 0/20 | Opus 首位替补；与 wazero 同为家族 19/20 vs 0/20，但同时有稳定性和评分敏感标记 |
| `python-statemachine-state-data-scoping` | opus 强 | A | 4/4 | 0/4 | 16/20 | 0/20 | 入选第 3 题 |
| `testem-bail-on-test-failure` | opus 强 | A | 4/4 | 0/4 | 13/20 | 0/20 | 入选第 5 题 |
| `ts-pattern-match-each` | opus 强 | A | 4/4 | 0/4 | 17/20 | 0/20 | 入选第 2 题 |
| `wazero-multi-module-snapshots` | opus 强 | A | 4/4 | 0/4 | 19/20 | 0/20 | 入选第 1 题 |
| `abs-module-cache-flags` | opus 强 | B | 4/4 | 1/4 | 19/20 | 16/20 | 排除：弱侧 Astra 家族 16/20 > 50%，移除目标档后两家族同为 15/16 |
| `anko-typed-variable-bindings` | opus 强 | B | 4/4 | 1/4 | 15/20 | 12/20 | 排除：弱侧 Astra 家族 12/20 > 50%，移除目标档后两家族同为 11/16 |
| `happy-dom-deterministic-intersectionobserver` | opus 强 | B | 3/4 | 0/4 | 11/20 | 0/20 | Opus 第四替补；强侧 3/4，Opus 家族仅 11/20，去掉目标档后为 8/16 |
| `koota-entity-snapshot-rollback` | opus 强 | B | 4/4 | 1/4 | 19/20 | 9/20 | Opus 第三替补；4/4 vs 1/4，但家族差距较小，且与 Astra 方向 koota 题同仓库 |
| `pest-character-class-coalescing` | opus 强 | B | 3/4 | 0/4 | 18/20 | 0/20 | Opus 次位替补；家族强佐证，主配对强侧仅 3/4，优先级低于 A 档 |
| `bandit-interprocedural-taint-checks` | astra 强 | A | 0/4 | 4/4 | 5/20 | 19/20 | 入选第 8 题 |
| `httpx-streaming-json-iteration` | astra 强 | A | 0/4 | 4/4 | 2/20 | 20/20 | 入选第 6 题 |
| `koota-deferred-mutation-buffer` | astra 强 | A | 0/4 | 4/4 | 1/20 | 19/20 | 入选第 7 题 |
| `optique-conditional-option-dependencies` | astra 强 | A | 0/4 | 4/4 | 9/20 | 19/20 | 入选第 9 题 |
| `scc-bounded-memory-spilling` | astra 强 | B | 1/4 | 4/4 | 7/20 | 20/20 | 入选第 10 题 |
| `superjson-error-stack-serialization` | astra 强 | B | 1/4 | 4/4 | 3/20 | 17/20 | Astra 首位替补；与 scc 同为 4/4 vs 1/4，家族差距稍大，但未过稳定条件且增加 TypeScript 集中度 |
| `oxvg-structural-selector-preservation` | astra 强 | C | 1/4 | 3/4 | 2/20 | 18/20 | Astra 次位替补；家族强佐证，但主配对为 C 档 |

16 题候选池是家族规则后的全集，不包含 `anko`、`abs-module`。Opus 替补顺序为 `participle` → `pest` → `koota-entity-snapshot` → `happy-dom`；Astra 替补顺序为 `superjson` → `oxvg`。`oxvg` 为 C 档，即使家族差异明显也应单独标记，不能作为与 A/B 等强的证据。`koota-entity-snapshot` 的官方语言元数据为 Python，原样保留，不据仓库名称改写。

## 实验使用

先冻结推荐清单和证据哈希，用内部 harness 对两配置各做每题至少 4 次独立重复（共 80 次 trial）。模型、effort、预算和 timeout 固定；按官方一致口径记录有效评分与基础设施错误。需要确认实际主配置的方向能否复现，不能用家族结果替代。再用复现的任务评估路由或协作能获得多少收益；使用结果仍应报告筛选偏差与质量标记的敏感性分析。

已有互补清单里的 `helm`、`python-statemachine`、`testem`、`httpx`、`koota-deferred`、`bandit`、`optique`、`scc` 可以帮助复用实验组织经验，但历史结果来自其他搭档；不能直接作为 Astra medium 的内部确认。若替补也未复现，应缩小确认池，而不是继续放宽阈值凑足 10 题。
