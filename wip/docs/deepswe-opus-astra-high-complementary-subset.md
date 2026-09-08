# Opus high 与 Astra high 能力互补任务子集

更新日期：2026-09-08

为 `anthropic/claude-opus-5 [high]` 与 `openai/gpt-6-astra [high]` 准备的互补机制探测池，沿用 [Astra medium 配对](deepswe-opus-astra-complementary-subset.md) 和 [opus/sol 子集](deepswe-opus-sol-complementary-subsets.md) 的阈值、证据分级、双侧家族佐证及质量标记。

- [推荐运行清单：10 题](../data/selection/complementary-opus-astra-high.txt)：前 5 题 Opus 强，后 5 题 Astra 强。
- [家族佐证后的候选池：19 题](../data/selection/complementary-opus-astra-high-candidates.txt)：前 10 题 Opus 强，后 9 题 Astra 强，包含替补，不是方向平衡池。
- [机器可读证据和输入哈希](../data/selection/complementary-opus-astra-high.json)：全部 20 道阈值命中题、逐 effort 计数、质量标记、处置及 medium/high 交叉对照。清单按证据手工决选，不由主筛选脚本自动更新。

## 推荐结果

**7 道 A 档、3 道 B 档，10 个不同仓库**，两方向各 5 题，全部目标格各有 4 次有效重复。Opus high 为 **23/40（57.5%）**，Astra high 为 **20/40（50%）**；逐题选取公开通过率更高配置的经验 oracle 为 **40/40（100%）**，相对最佳固定配置高 42.5 个百分点。没有放宽主阈值，也没有提拔 C 档。

oracle 为 `mean(max(p_opus(task), p_astra(task)))`，是选题数据内的乐观参考，不能当作双模型协作实测结果或未来上限。此池用来探测路由/协作能否利用已知差异；内部 harness 的确认实验尚未运行。

## 数据与规则

使用 2026-09-08 下载的官方 v1.1 快照（70 config、31,617 次 rollout、113 题；榜单 generated_at 为 2026-09-03T22:24:37.984682+00:00），目标配置为 `mini_swe_agent_claude_opus_5_high`、`mini_swe_agent_gpt_6_astra_high`。

1. 仅计 `source=deep-swe`、`eval_scope=full`、`included_in_score=true` 且 `errored=false`；以 `passed` 统计通过数，有效记录均进入分母，不按原始异常是否存在排除。
2. 在全部 113 题上扫描强侧 ≥ 75%、弱侧 ≤ 25%，每格至少 3 次有效重复；本次全部命中格均为 4 次。命中 20 题：Opus 强 11、Astra 强 9。
3. A = 4/4 vs 0/4；B = 4/4 vs 1/4 或 3/4 vs 0/4；C = 3/4 vs 1/4。单侧 Fisher p 约 0.014、0.071、0.243，仅作证据分级，未校正选方向和多题扫描。
4. 汇总双方 low/medium/high/xhigh/max 五档：要求弱侧家族 ≤ 50%，强侧家族通过率更高。仅 `kea-atomic-signal-selectors` 不通过（Opus 12/20 vs Astra 13/20，与目标格方向相反），剩 19 题：Opus 10、Astra 9。
5. 扣除本机排除任务；沿用 2026-08-13 的机制探索线决策，不再硬性隔离 confirm。本次 20 道候选均与 host-excluded、dev、confirm 无交集。
6. 方向各取 5 题，A 优先、B 补足；同档结合家族、质量及仓库/语言分散。Opus 有 6 道 A，沿用 medium 版的同档决选；Astra 仅 2 道 A，其余 3 席从 B 中优先取强侧 4/4。
7. 当前质量按主线规则重算：28 个 base model 的覆盖门槛为 27，每 config 最少有效重复 ≥ 3，错误率 ≤ 5%，verifier timeout ≤ 1；稳定性仅作标记。评分敏感以最新 `v1-delta.json` 的 `|delta| ≥ 0.10` 标记，历史主线输出保持原样。

## 推荐 10 题及逐题证据

| 任务 | 方向 | 档 | Opus high | Astra high | Opus 家族 | Astra 家族 | 语言 / 标记 |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `wazero-multi-module-snapshots` | opus 强 | A | 4/4 | 0/4 | 19/20 | 0/20 | go；未过稳定条件 |
| `ts-pattern-match-each` | opus 强 | A | 4/4 | 0/4 | 17/20 | 0/20 | typescript；— |
| `python-statemachine-state-data-scoping` | opus 强 | A | 4/4 | 0/4 | 16/20 | 0/20 | python；— |
| `helm-array-merge-strategies` | opus 强 | A | 4/4 | 0/4 | 14/20 | 0/20 | go；评分敏感 Δ +0.1667 |
| `testem-bail-on-test-failure` | opus 强 | A | 4/4 | 0/4 | 13/20 | 0/20 | javascript；评分敏感 Δ -0.1111 |
| `httpx-streaming-json-iteration` | astra 强 | A | 0/4 | 4/4 | 2/20 | 20/20 | python；— |
| `bandit-interprocedural-taint-checks` | astra 强 | A | 0/4 | 4/4 | 5/20 | 19/20 | python；评分敏感 Δ -0.1111 |
| `oxvg-structural-selector-preservation` | astra 强 | B | 1/4 | 4/4 | 2/20 | 18/20 | rust；— |
| `scc-bounded-memory-spilling` | astra 强 | B | 1/4 | 4/4 | 7/20 | 20/20 | go；评分敏感 Δ +0.1389 |
| `csstree-shorthand-expansion-compression` | astra 强 | B | 1/4 | 4/4 | 2/20 | 13/20 | javascript；— |

语言分布：Go 3、Python 3、TypeScript 1、JavaScript 2、Rust 1；10 个不同仓库。

Opus 方向与 medium 版完全相同，所选 5 题在 Astra 全五档均为 0/20。第 6 道 A 档 `participle` 作为首位替补：它与 `wazero` 同为家族 19/20 vs 0/20、都有其他配置有效重复不足的标记，但它另外还有评分敏感标记。保留 `testem` 也保留 JavaScript 覆盖；这是质量与多样性的决选，不表示二者统计上有显著优劣。

Astra 方向先收 `httpx`、`bandit` 两道 A 档，B 档选择强侧 4/4 的 `oxvg`、`scc`、`csstree`。`koota-deferred` 虽然家族差距更大（Astra 19/20 vs Opus 1/20），但 high 仅为 3/4，故置于首位替补；其余 `optique`、`awilix` 的目标强侧也为 3/4。4/4 vs 1/4 与 3/4 vs 0/4 同属 B 档、Fisher p 相同，这里的优先级基于强侧在池内更高的可捕获通过率，而非更强的统计显著性。

## 与 Astra medium 配对的关系

两个推荐池重叠 **8 题**，联合 **12 题**。Opus 强方向完全相同；Astra 强方向替换 2 题：

| 任务 | Astra medium | Astra high | high 清单处置 |
| --- | ---: | ---: | --- |
| `koota-deferred-mutation-buffer` | 4/4 | 3/4 | 由主选转为首位替补 |
| `optique-conditional-option-dependencies` | 4/4 | 3/4 | 由主选转为次位替补 |
| `oxvg-structural-selector-preservation` | 3/4 | 4/4 | 由 C 档替补进入 B 档主选 |
| `csstree-shorthand-expansion-compression` | 2/4 | 4/4 | medium 未达强侧阈值，high 进入 B 档主选 |

使用同一官方快照在两个固定题池上交叉统计：

| 固定题池 | Opus high | Astra medium | Astra high | Opus + medium oracle | Opus + high oracle |
| --- | ---: | ---: | ---: | ---: | ---: |
| medium 推荐 10 题 | 21/40 | 20/40 | 18/40 | 40/40 | 38/40 |
| high 推荐 10 题 | 23/40 | 17/40 | 20/40 | 37/40 | 40/40 |

这正说明按各档结果选题会偏向对应档位：不能拿两个不同推荐池的分数直接推断 effort 升档是否有收益。若做严格 effort 对照，可固定 8 题交集或 12 题联合池，并独立重复；两个池共享模型家族和公开结果，不是独立复现证据。

## 质量标记与家族边界

- 主池只有 `wazero` 未过稳定条件：2/280 ≈ 0.71% 的错误率、0 次 verifier timeout；原因是其他模型 `claude-opus-4-8 [max]` 的 2 次 provider timeout，目标格和双方五档家族均完整。
- 评分敏感题为 `helm`（Δ +0.1667）、`testem`（−0.1111）、`bandit`（−0.1111）、`scc`（+0.1389）。排除这 4 题后还剩 6 题、两方向 3:3；再排除 `wazero` 则剩 5 题、Opus:Astra 为 2:3。应将其作为敏感性分析，不能悄悄变更主池。
- 首位 Opus 替补 `participle` 错误率为 4/280 ≈ 1.43%，最少有效重复 2，verifier timeout 0；末位 Astra 替补 `superjson` 为 5/279 ≈ 1.79%，最少有效重复 0，verifier timeout 0。它们的错误均来自其他配置的 provider timeout，不直接损害目标两格，但替补时仍需标记。
- 家族汇总包含目标配置，不构成独立确认；JSON 同时提供去掉目标 high 档的其他四档计数。推荐 10 题在该口径下仍满足弱侧 ≤ 50% 且方向一致。`csstree` 的 Astra 其他四档为 9/16，家族佐证比 `httpx`、`oxvg`、`scc` 弱，应优先观察复现。
- 替补 `optique` 的 Opus 其他四档为 9/16，弱侧并非全系低；`awilix` 的 Astra 其他四档仅为 5/16，主要体现具体 high 档的公开样本优势，不能描述成 Astra 全系稳定擅长。

## 完整候选记录（20 题）

| 任务 | 方向 | 档 | Opus high | Astra high | Opus 家族 | Astra 家族 | 处置 |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `participle-grammar-conflict-analysis` | opus 强 | A | 4/4 | 0/4 | 19/20 | 0/20 | Opus 首位替补；与 wazero 家族计数相同，但同时带稳定性和评分敏感标记 |
| `wazero-multi-module-snapshots` | opus 强 | A | 4/4 | 0/4 | 19/20 | 0/20 | 入选第 1 题 |
| `ts-pattern-match-each` | opus 强 | A | 4/4 | 0/4 | 17/20 | 0/20 | 入选第 2 题 |
| `python-statemachine-state-data-scoping` | opus 强 | A | 4/4 | 0/4 | 16/20 | 0/20 | 入选第 3 题 |
| `helm-array-merge-strategies` | opus 强 | A | 4/4 | 0/4 | 14/20 | 0/20 | 入选第 4 题 |
| `testem-bail-on-test-failure` | opus 强 | A | 4/4 | 0/4 | 13/20 | 0/20 | 入选第 5 题 |
| `pest-character-class-coalescing` | opus 强 | B | 3/4 | 0/4 | 18/20 | 0/20 | Opus 次位替补；家族 18/20 vs 0/20，目标强侧只有 3/4，排在 A 档之后 |
| `happy-dom-deterministic-intersectionobserver` | opus 强 | B | 3/4 | 0/4 | 11/20 | 0/20 | Opus 第四替补；目标强侧 3/4，Opus 家族仅 11/20，其他四档为 8/16 |
| `koota-pair-relation-tracking` | opus 强 | B | 4/4 | 1/4 | 14/20 | 3/20 | Opus 第三替补；4/4 vs 1/4，家族 14/20 vs 3/20；强侧满格，但家族差距小于 pest |
| `onedump-dump-encryption-pipeline` | opus 强 | B | 3/4 | 0/4 | 13/20 | 8/20 | Opus 第五替补；目标强侧 3/4，家族差距较小（13/20 vs 8/20） |
| `kea-atomic-signal-selectors` | opus 强 | C | 3/4 | 1/4 | 12/20 | 13/20 | 排除：Astra 弱侧家族 13/20 > 50%，且高于 Opus 家族 12/20；其他四档方向也相反 |
| `httpx-streaming-json-iteration` | astra 强 | A | 0/4 | 4/4 | 2/20 | 20/20 | 入选第 6 题 |
| `bandit-interprocedural-taint-checks` | astra 强 | A | 0/4 | 4/4 | 5/20 | 19/20 | 入选第 7 题 |
| `koota-deferred-mutation-buffer` | astra 强 | B | 0/4 | 3/4 | 1/20 | 19/20 | Astra 首位替补；家族极强（19/20 vs 1/20），但 high 为 3/4；主池优先选强侧 4/4 的 B 档 |
| `oxvg-structural-selector-preservation` | astra 强 | B | 1/4 | 4/4 | 2/20 | 18/20 | 入选第 8 题 |
| `scc-bounded-memory-spilling` | astra 强 | B | 1/4 | 4/4 | 7/20 | 20/20 | 入选第 9 题 |
| `csstree-shorthand-expansion-compression` | astra 强 | B | 1/4 | 4/4 | 2/20 | 13/20 | 入选第 10 题 |
| `optique-conditional-option-dependencies` | astra 强 | B | 0/4 | 3/4 | 9/20 | 19/20 | Astra 次位替补；high 为 3/4，Opus 其他四档 9/16，弱侧证据更依赖 high 档 |
| `awilix-async-container-initialization` | astra 强 | B | 0/4 | 3/4 | 0/20 | 8/20 | Astra 第三替补；high 为 3/4，Astra 家族只有 8/20，其他四档 5/16，effort 依赖明显 |
| `superjson-error-stack-serialization` | astra 强 | C | 1/4 | 3/4 | 3/20 | 17/20 | Astra 第四替补；high 为 3/4，目标配对降至 C 档，且未过稳定条件 |

19 题候选池只剔除 `kea`。Opus 替补顺序为 `participle` → `pest` → `koota-pair` → `happy-dom` → `onedump`；Astra 为 `koota-deferred` → `optique` → `awilix` → `superjson`。`superjson` 为 C 档，应与 A/B 档分开报告。若同时扩展 `koota-pair` 与 `koota-deferred`，两题同属一个仓库、方向相反，需注明仓库重复。

## 内部确认

先冻结清单与证据哈希，用内部 harness 对两配置各做每题至少 4 次独立重复（10 题共 80 次 trial），固定模型、effort、预算和 timeout，分别记录有效评分与基础设施错误。只有目标配置互补性复现后，才据此评估路由或协作的实际收益。若同时确认 medium/high 两池，Opus high 可在 12 题联合池上运行，两个 Astra effort 则需分别运行；完整三配置同题对照为 3 × 12 × 4 = 144 次 trial。

清单用于机制探测，具有按公开结果选题带来的乐观偏差，不用于总体模型排名。替补仍须确认，确认不通过时允许缩小核心池，不继续放宽阈值凑题。
