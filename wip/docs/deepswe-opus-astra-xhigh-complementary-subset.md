# Opus high 与 Astra xhigh 能力互补任务子集

更新日期：2026-09-08

为 `anthropic/claude-opus-5 [high]` 与 `openai/gpt-6-astra [xhigh]` 准备的互补机制探测池，沿用 [Astra medium 配对](deepswe-opus-astra-complementary-subset.md)、[Astra high 配对](deepswe-opus-astra-high-complementary-subset.md) 和 [opus/sol 子集](deepswe-opus-sol-complementary-subsets.md) 的筛选方式。

- [推荐运行清单：10 题](../data/selection/complementary-opus-astra-xhigh.txt)：前 5 题 Opus 强，后 5 题 Astra 强。
- [完整候选池：20 题](../data/selection/complementary-opus-astra-xhigh-candidates.txt)：前 12 题 Opus 强，后 8 题 Astra 强，包含替补，不是平衡池。
- [机器可读证据及输入哈希](../data/selection/complementary-opus-astra-xhigh.json)：全部候选、逐 effort 计数、质量标记、处置及三档交叉对照。这些是手工决选清单，不由主筛选脚本自动更新。

## 推荐结果与数据口径

推荐池为 **9 道 A 档、1 道 B 档，10 个不同仓库**。Opus high 为 **21/40（52.5%）**，Astra xhigh 为 **20/40（50%）**；逐题选择公开通过率更高配置的经验 oracle 为 **40/40（100%）**，相对最佳固定配置高 47.5 个百分点。两方向各 5 题，无需放宽阈值或提拔 C 档。

使用 2026-09-08 下载的官方 v1.1 快照（70 config、31,617 次 rollout、113 题；榜单 generated_at 为 2026-09-03T22:24:37.984682+00:00）。目标配置为 `mini_swe_agent_claude_opus_5_high`、`mini_swe_agent_gpt_6_astra_xhigh`。仅计 `source=deep-swe`、`eval_scope=full`、`included_in_score=true`、`errored=false`，以 `passed` 统计通过数，有效记录都进入分母，不因携带原始异常而排除。

oracle 是 `mean(max(p_opus(task), p_astra(task)))`，为选题数据内的乐观参考，不等于实际协作通过率或未来表现保证。内部 harness 确认实验尚未运行；此池用于机制探测，不用于总体模型排名。

## 筛选规则与候选数量

1. 扫描全部 113 题：强侧 ≥ 75%、弱侧 ≤ 25%，每格至少 3 次有效重复。本次全部命中格均有 4 次，命中 20 题（Opus 强 12、Astra 强 8）。
2. A = 4/4 vs 0/4；B = 4/4 vs 1/4 或 3/4 vs 0/4；C = 3/4 vs 1/4。单侧 Fisher p 分别约 0.014、0.071、0.243，仅用来分级，未校正方向选择和多题扫描。
3. 合并双方 low/medium/high/xhigh/max 五档，要求弱侧家族通过率 ≤ 50%、强侧家族通过率更高。20 题全部通过；家族汇总包含目标档，不能作为独立复现。
4. 扣除本机排除任务；按 opus/sol 文档 2026-08-13 的机制探索线决策，confirm 不再硬性排除，但必须标记。本次无 host-excluded 或 dev 命中；`go-critic-doc-link-checker` 属于 confirm，仅列入完整候选和替补，推荐 10 题与 confirm 无交集。若用 20 题候选池开展机制实验，应注明包含 confirm 任务。
5. 两方向各取 5 题，A 优先，再以 B 补足。Opus 有 7 道 A，按质量、家族差距及仓库分散决选 5 道；Astra 有 4 道 A，全收，再从两道 B 中取 1 道。
6. 质量标记按最新快照重算：28 个 base model 的覆盖门槛为 27，每 config 至少 3 次有效重复，错误率 ≤ 5%，verifier timeout ≤ 1。评分敏感用最新 `v1-delta.json` 的 `|delta| ≥ 0.10`。质量标记不自动淘汰，历史主线输出不改写。

## 推荐 10 题

| 任务 | 方向 | 档 | Opus high | Astra xhigh | Opus 家族 | Astra 家族 | 语言 / 标记 |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `wazero-multi-module-snapshots` | opus 强 | A | 4/4 | 0/4 | 19/20 | 0/20 | go；未过稳定条件 |
| `ts-pattern-match-each` | opus 强 | A | 4/4 | 0/4 | 17/20 | 0/20 | typescript；— |
| `python-statemachine-state-data-scoping` | opus 强 | A | 4/4 | 0/4 | 16/20 | 0/20 | python；— |
| `helm-array-merge-strategies` | opus 强 | A | 4/4 | 0/4 | 14/20 | 0/20 | go；评分敏感 Δ +0.1667 |
| `testem-bail-on-test-failure` | opus 强 | A | 4/4 | 0/4 | 13/20 | 0/20 | javascript；评分敏感 Δ -0.1111 |
| `httpx-streaming-json-iteration` | astra 强 | A | 0/4 | 4/4 | 2/20 | 20/20 | python；— |
| `koota-deferred-mutation-buffer` | astra 强 | A | 0/4 | 4/4 | 1/20 | 19/20 | typescript；— |
| `bandit-interprocedural-taint-checks` | astra 强 | A | 0/4 | 4/4 | 5/20 | 19/20 | python；评分敏感 Δ -0.1111 |
| `optique-conditional-option-dependencies` | astra 强 | A | 0/4 | 4/4 | 9/20 | 19/20 | typescript；Opus 其他四档 9/16 |
| `oxvg-structural-selector-preservation` | astra 强 | B | 1/4 | 4/4 | 2/20 | 18/20 | rust；— |

语言分布：Go 2、Python 3、TypeScript 3、JavaScript 1、Rust 1；10 题来自 10 个不同仓库。

Opus 强方向与 medium/high 两份清单完全一致。未纳入的两道 A 档依次为 `participle` 和 `koota-pair`：前者与 `wazero` 家族同为 19/20 vs 0/20，但同时带稳定性和评分敏感标记；后者的家族差距较小（14/20 vs 3/20），且会与 Astra 主选 `koota-deferred` 重复仓库。因此保留五道已选题，未简单按“所有 A 档全收”扩大方向规模。这是质量与多样性取舍，不表示同档题之间已证实统计优劣。

Astra 四道 A 档为 `httpx`、`koota-deferred`、`bandit`、`optique`。第 5 席在同为 4/4 vs 1/4 的 `oxvg`、`scc` 间取前者：家族差距为 18/20 vs 2/20（80 个百分点），高于 scc 的 20/20 vs 7/20（65 个百分点）；oxvg 不带评分敏感标记，并引入 Rust。scc 是首位替补。

## 与 medium / high 的差异

本池与 medium 清单重叠 **9 题**，只把 `scc` 换为 `oxvg`；与 high 清单重叠 **8 题**，以 `koota-deferred`、`optique` 替换 `scc`、`csstree`。三份推荐清单的联合池仍为 **12 题**。

| 任务 | Astra medium | Astra high | Astra xhigh |
| --- | ---: | ---: | ---: |
| `koota-deferred-mutation-buffer` | 4/4 | 3/4 | 4/4 |
| `optique-conditional-option-dependencies` | 4/4 | 3/4 | 4/4 |
| `oxvg-structural-selector-preservation` | 3/4 | 4/4 | 4/4 |
| `scc-bounded-memory-spilling` | 4/4 | 4/4 | 4/4 |
| `csstree-shorthand-expansion-compression` | 2/4 | 4/4 | 2/4 |

`scc` 在三档均为 4/4，本次换出只是同档候选决选；`csstree` 在 xhigh 回到 2/4，未达到强侧 75% 阈值。每格仅 4 次重复，这些起伏不能证明 effort 升档必然增益或退化。

固定各题池，在同一官方快照上交叉统计：

| 固定的 10 题池 | Opus high | Astra medium | Astra high | Astra xhigh |
| --- | ---: | ---: | ---: | ---: |
| medium 推荐池 | 21/40 | 20/40 | 18/40 | 20/40 |
| high 推荐池 | 23/40 | 17/40 | 20/40 | 18/40 |
| xhigh 推荐池 | 21/40 | 19/40 | 18/40 | 20/40 |

| 固定的 10 题池 | Opus + medium oracle | Opus + high oracle | Opus + xhigh oracle |
| --- | ---: | ---: | ---: |
| medium 推荐池 | 40/40 | 38/40 | 40/40 |
| high 推荐池 | 37/40 | 40/40 | 38/40 |
| xhigh 推荐池 | 39/40 | 38/40 | 40/40 |

不能直接比较各自筛选池上的成绩来判断 effort 的真实收益。严格 effort 对照应固定同一个题池，做独立重复；上表仍来自参与选题的公开记录，不是独立测试集。

## 质量和家族证据的边界

- `wazero` 是推荐池唯一未过稳定条件的题：错误率 2/280 ≈ 0.71%，verifier timeout 0；来自其他配置 `claude-opus-4-8 [max]` 的 2 次 provider timeout。目标两格及双方五档家族都完整，故保留。
- 推荐池评分敏感题为 `helm`（Δ +0.1667）、`testem`（−0.1111）、`bandit`（−0.1111）。移除这 3 题后余 7 题，Opus:Astra 为 3:4；若再移除 `wazero`，余 6 题、方向 2:4。应单列敏感性分析，不能悄悄改变主池。
- 替补中 `participle` 的错误率为 4/280 ≈ 1.43%、最少有效重复 2，`superjson` 为 5/279 ≈ 1.79%、最少有效重复 0；verifier timeout 均为 0，缺失来自其他配置的 provider timeout。评分敏感替补为 `participle`（Δ −0.1225）、`query-persist`（−0.1667）、`scc`（+0.1389）。
- JSON 保留去掉目标档后的其他四档计数。`optique` 为 Opus 9/16 vs Astra 15/16，方向仍一致，但 Opus 其他四档超过 50%；它不是“Opus 全系都做不出”。推荐池其余题在该口径下仍满足弱侧 ≤ 50% 且家族方向一致。
- 末位替补 `effect` 的全家族仅为 Opus 7/20 vs Astra 9/20，去掉目标档后两侧同为 6/16；虽通过沿用的家族规则，佐证主要来自目标格，证据较弱。目标配对又为 C 档，必须与 A/B 主池分开报告。

## 完整候选和处置（20 题）

| 任务 | 方向 | 档 | Opus high | Astra xhigh | Opus 家族 | Astra 家族 | 处置 |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `participle-grammar-conflict-analysis` | opus 强 | A | 4/4 | 0/4 | 19/20 | 0/20 | Opus 首位替补，A 档；与 wazero 家族同为 19/20 vs 0/20，但同时带稳定性和评分敏感标记 |
| `wazero-multi-module-snapshots` | opus 强 | A | 4/4 | 0/4 | 19/20 | 0/20 | 入选第 1 题 |
| `ts-pattern-match-each` | opus 强 | A | 4/4 | 0/4 | 17/20 | 0/20 | 入选第 2 题 |
| `python-statemachine-state-data-scoping` | opus 强 | A | 4/4 | 0/4 | 16/20 | 0/20 | 入选第 3 题 |
| `helm-array-merge-strategies` | opus 强 | A | 4/4 | 0/4 | 14/20 | 0/20 | 入选第 4 题 |
| `testem-bail-on-test-failure` | opus 强 | A | 4/4 | 0/4 | 13/20 | 0/20 | 入选第 5 题 |
| `koota-pair-relation-tracking` | opus 强 | A | 4/4 | 0/4 | 14/20 | 3/20 | Opus 次位替补，A 档；家族差距小于主选五题，且与 Astra 主选 koota-deferred 同仓库 |
| `pest-character-class-coalescing` | opus 强 | B | 3/4 | 0/4 | 18/20 | 0/20 | Opus 第三替补，B 档；家族 18/20 vs 0/20，但强侧为 3/4 |
| `happy-dom-deterministic-intersectionobserver` | opus 强 | B | 3/4 | 0/4 | 11/20 | 0/20 | Opus 第五替补，B 档；强侧 3/4，Opus 家族仅 11/20，其他四档 8/16 |
| `query-persist-restored-query-state` | opus 强 | B | 4/4 | 1/4 | 19/20 | 9/20 | Opus 第四替补，B 档；强侧 4/4，家族 19/20 vs 9/20；评分敏感 |
| `go-critic-doc-link-checker` | opus 强 | B | 3/4 | 0/4 | 14/20 | 6/20 | Opus 第六替补，B 档；强侧 3/4，家族差距 14/20 vs 6/20；属于 confirm，机制线允许但需标记 |
| `onedump-dump-encryption-pipeline` | opus 强 | B | 3/4 | 0/4 | 13/20 | 8/20 | Opus 第七替补，B 档；强侧 3/4，家族差距较小（13/20 vs 8/20） |
| `httpx-streaming-json-iteration` | astra 强 | A | 0/4 | 4/4 | 2/20 | 20/20 | 入选第 6 题 |
| `koota-deferred-mutation-buffer` | astra 强 | A | 0/4 | 4/4 | 1/20 | 19/20 | 入选第 7 题 |
| `bandit-interprocedural-taint-checks` | astra 强 | A | 0/4 | 4/4 | 5/20 | 19/20 | 入选第 8 题 |
| `optique-conditional-option-dependencies` | astra 强 | A | 0/4 | 4/4 | 9/20 | 19/20 | 入选第 9 题 |
| `oxvg-structural-selector-preservation` | astra 强 | B | 1/4 | 4/4 | 2/20 | 18/20 | 入选第 10 题 |
| `scc-bounded-memory-spilling` | astra 强 | B | 1/4 | 4/4 | 7/20 | 20/20 | Astra 首位替补，B 档；与 oxvg 同为 4/4 vs 1/4，但家族差距较小且评分敏感 |
| `superjson-error-stack-serialization` | astra 强 | C | 1/4 | 3/4 | 3/20 | 17/20 | Astra 次位替补，C 档；家族佐证强，目标强侧仅 3/4，且未过稳定条件 |
| `effect-sse-httpapi-streaming` | astra 强 | C | 1/4 | 3/4 | 7/20 | 9/20 | Astra 第三替补，C 档；家族差距仅 9/20 vs 7/20，去掉目标档后双方均为 6/16 |

完整候选池保留所有通过主阈值和家族条件的 20 题，包含两道未主选的 A 档和两道 C 档。Opus 替补顺序为 `participle` → `koota-pair` → `pest` → `query-persist` → `happy-dom` → `go-critic` → `onedump`；Astra 为 `scc` → `superjson` → `effect`。替补顺序综合证据与质量，不是自动排名；confirm 任务 `go-critic` 的使用应注明机制线接触情况。

## 内部确认

先冻结清单和证据哈希，用内部 harness 对两个目标配置各做每题至少 4 次独立重复（共 80 次 trial），固定模型、effort、预算和 timeout，分开记录有效评分及基础设施错误。仅在互补方向复现后评估路由/协作的实际收益。若对三档 effort 做完整同题对照，可在 12 题联合池上运行 Opus high 与 Astra medium/high/xhigh，共 4 × 12 × 4 = 192 次 trial。

公开重复数较少、题目按结果挑选且三档共享模型家族，因此须报告筛选偏差。替补仍需确认；若无法复现，允许缩小确认池，不继续放宽阈值凑题。
