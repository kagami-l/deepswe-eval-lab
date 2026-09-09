# Opus high 与 Astra medium / xhigh 的共同低分任务集

更新日期：2026-09-08

本次筛选“两配置都表现较弱”的任务，沿用此前互补筛选中弱侧的阈值：**每侧官方二元总分/通过率 ≤ 25%，且各有至少 3 次有效重复**。本次所有命中任务的目标格都完整为 4 次，即每侧至多 1/4。保留全部命中题，不强行凑成 10 题，不施加方向平衡或仓库配额。

**“低分”指官方总分，不代表功能分项也低。** 官方快照未发布 Astra 的 F2P、P2P、partial（不是零分）；部分 Opus 记录总分为 0，但分项接近满分。因此本报告可以确认“两侧最终通过率低”，无法确认“两侧功能完成度都低”。

## 结果与清单

| 配对 | 共同低分任务 | 其中两侧均 0/4 | Opus high 合计 | Astra 合计 |
| --- | ---: | ---: | ---: | ---: |
| Opus high + Astra medium | 13 | 8 | 4/52（7.69%） | 2/52（3.85%） |
| Opus high + Astra xhigh | 12 | 9 | 3/48（6.25%） | 1/48（2.08%） |

- medium：[13 题主清单](../data/selection/joint-low-opus-astra-medium.txt)、[8 题零通过子集](../data/selection/joint-low-opus-astra-medium-zero-pass.txt)、[证据 JSON](../data/selection/joint-low-opus-astra-medium.json)。
- xhigh：[12 题主清单](../data/selection/joint-low-opus-astra-xhigh.txt)、[9 题零通过子集](../data/selection/joint-low-opus-astra-xhigh-zero-pass.txt)、[证据 JSON](../data/selection/joint-low-opus-astra-xhigh.json)。

主清单先列两侧零通过任务，再列其他低分任务，各组按 task ID 排序；零通过清单是对应主清单的子集。JSON 保存输入哈希、逐 trial ID、有效次数、五档家族计数、分项均值及非空数量、质量和重叠标记。这些独立清单不覆盖历史互补池或主线抽样。

xhigh 的 12 题全部包含在 medium 的 13 题中。唯一差异是 `effect-sse-httpapi-streaming`：Opus high 为 1/4，Astra medium 为 1/4，Astra xhigh 为 3/4，所以仅进入 medium 共同低分池。`meriyah` 则从 medium 的 1/4 变为 xhigh 的 0/4，使 xhigh 零通过子集多 1 题；这是公开小样本观察，不构成升档收益/退化结论。

## 数据口径与筛选规则

使用 2026-09-08 下载的官方 v1.1 快照，70 个 config、31,617 次 rollout、113 个任务，榜单 generated_at 为 2026-09-03T22:24:37.984682+00:00。目标配置为 `mini_swe_agent_claude_opus_5_high`，分别配对 `mini_swe_agent_gpt_6_astra_medium`、`mini_swe_agent_gpt_6_astra_xhigh`。

1. 只计 `source=deep-swe`、`eval_scope=full`、`included_in_score=true` 且 `errored=false`。以 `passed` 统计通过数，所有有效记录进入分母；不能因原始异常存在就排除，也不能将缺失分项填零。
2. 全部 113 题逐题扫描，两侧各至少 3 次有效重复，且各自通过率 ≤ 25%。本次主清单中 `reward`、`score_value` 均完整，均值与通过率一致。
3. 扣除 `host-excluded.txt`；沿用机制探索线不硬性隔离 confirm 的决策。本次两组全部命中题都不属于 host-excluded、dev 或 confirm，因此无需额外删除。
4. 两模型各汇总 low/medium/high/xhigh/max 五档，仅作为佐证：所有入选题的双方家族通过率均 ≤ 50%。不强制家族也 ≤ 25%，因为用户指定的是具体 effort 配置；例如 `arktype` 为 Opus 8/20、Astra 6/20，仍满足目标格的双低条件。家族包含目标档，并非独立复现；JSON 另列其他四档计数。
5. 稳定性与评分敏感作为质量标记，不自动剔除。当前稳定条件按 28 个 base model 的覆盖门槛 27、每 config 最少有效重复 3、错误率 ≤ 5%、verifier timeout ≤ 1 重算；历史主线输出不改写。评分 delta 使用最新 `v1-delta.json`，阈值 `|delta| ≥ 0.10`。

## 全部任务的三配置对照

下表共 13 题；xhigh 清单只去掉 `effect`。每格为通过次数 / 有效重复数，家族列为五档合计。

| 任务 | Opus high | Astra medium | Astra xhigh | Opus 家族 | Astra 家族 | 标记 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `bandit-structured-nosec-directives` | 0/4 | 0/4 | 0/4 | 3/20 | 0/20 | — |
| `gql-incremental-graphql-delivery` | 0/4 | 0/4 | 0/4 | 1/20 | 0/20 | 未过稳定条件 |
| `ink-grid-box-layout` | 0/4 | 0/4 | 0/4 | 2/20 | 0/20 | — |
| `obsidian-linter-auto-table-of-contents` | 0/4 | 0/4 | 0/4 | 2/20 | 0/20 | 评分敏感 Δ -0.1389 |
| `obsidian-linter-link-format-conversion` | 0/4 | 0/4 | 0/4 | 1/20 | 0/20 | — |
| `sqlfmt-create-table-ddl-formatting` | 0/4 | 0/4 | 0/4 | 4/20 | 1/20 | 评分敏感 Δ -0.1944 |
| `termenv-preserve-ansi-resets` | 0/4 | 0/4 | 0/4 | 3/20 | 0/20 | 未过稳定条件 |
| `vulture-persistent-analysis-cache` | 0/4 | 0/4 | 0/4 | 0/20 | 0/20 | 评分敏感 Δ -0.6667 |
| `arktype-json-schema-refs-dependencies` | 1/4 | 0/4 | 1/4 | 8/20 | 6/20 | 评分敏感 Δ +0.1111 |
| `effect-sse-httpapi-streaming` | 1/4 | 1/4 | 3/4 | 7/20 | 9/20 | — |
| `igel-persist-feature-schema` | 1/4 | 0/4 | 0/4 | 8/20 | 0/20 | — |
| `meriyah-explicit-resource-declarations` | 0/4 | 1/4 | 0/4 | 0/20 | 2/20 | — |
| `prometheus-transactional-reload-status` | 1/4 | 0/4 | 0/4 | 5/20 | 0/20 | — |

两组都包含 `obsidian-linter` 仓库的两个不同任务，未因仓库重复丢弃满足条件的题；因此集合规模不代表独立仓库数量。准确语言分布和仓库数见证据 JSON。

## 分项得分：不能与总分混为一谈

Astra medium、xhigh 在这批任务的 F2P、P2P、partial 均为缺失，无法做双侧分项低分筛选。下面只报告 Opus high 的可用分项；本表每个均值均来自 4 条有效记录，各 trial 等权，不按测试数量加权。

| 任务 | Opus F2P 均值 | Opus P2P 均值 | Opus partial 均值 |
| --- | ---: | ---: | ---: |
| `bandit-structured-nosec-directives` | 97.10% | 99.29% | 98.86% |
| `gql-incremental-graphql-delivery` | 97.06% | 99.88% | 99.82% |
| `ink-grid-box-layout` | 93.00% | 100.00% | 97.64% |
| `obsidian-linter-auto-table-of-contents` | 67.68% | 100.00% | 98.87% |
| `obsidian-linter-link-format-conversion` | 97.92% | 100.00% | 99.90% |
| `sqlfmt-create-table-ddl-formatting` | 95.31% | 88.10% | 88.28% |
| `termenv-preserve-ansi-resets` | 92.14% | 100.00% | 97.75% |
| `vulture-persistent-analysis-cache` | 97.92% | 98.64% | 98.59% |
| `arktype-json-schema-refs-dependencies` | 94.00% | 100.00% | 99.91% |
| `effect-sse-httpapi-streaming` | 98.40% | 100.00% | 99.36% |
| `igel-persist-feature-schema` | 43.75% | 100.00% | 48.08% |
| `meriyah-explicit-resource-declarations` | 95.92% | 100.00% | 100.00% |
| `prometheus-transactional-reload-status` | 58.33% | 99.39% | 93.04% |

例如 `bandit-structured-nosec-directives` 两侧都 0/4，但 Opus F2P 平均约 97.10%；`gql` 的 Opus F2P 约 97.06%，也可能只是少数关键测试阻止通过。`igel` 的 Opus F2P 43.75%、partial 48.08%，在 Opus 侧体现了较低功能完成度，但 Astra 分项未知，不能据此认定两侧分项均低。这里的低总分池可用来研究共同失败、关键边界或协作修复，不等价于“两边几乎什么都没做成”的池。

## 质量标记与使用建议

- `gql-incremental-graphql-delivery` 有 2 次 verifier timeout，未过当前稳定条件；`termenv-preserve-ansi-resets` 的其他 config 最少仅 1 次有效重复，也未过稳定条件。本文目标三配置在这些题上仍各有 4 次有效重复。medium 其余 11 题、xhigh 其余 10 题满足当前稳定条件。
- 两组共同的评分敏感题有 `arktype`（Δ +0.1111）、`obsidian-linter-auto-table-of-contents`（−0.1389）、`sqlfmt`（−0.1944）、`vulture`（−0.6667）。尤其 `vulture` 在两模型全五档均为 0/20，但评分版本变化极大；它适合审计评分与失败原因，不能据零通过直接认定为纯粹能力缺口。建议主结果附带去掉这些标记题的敏感性分析。
- “零通过”表示当前每侧 4 次均失败，不能证明未来成功概率为零；同样没有验证两模型失败在相同测试节点。内部运行前应确认目标配置，记录有效评分和基础设施错误，并逐题查看 verifier 输出。
- 可以先用 8/9 题零通过子集探测协作是否能突破公开双失败，再用完整 13/12 题池观察结果是否稳健。两模型各题至少 4 次内部重复：medium 主池共 104 次 trial，xhigh 主池共 96 次。若要同题比较 effort，可在 13 题联合池上同时运行 Opus high、Astra medium、Astra xhigh，共 156 次 trial；Opus 结果无需为两个配对重复运行。

内部确认和工件逐条审计尚未开展。本次产物是基于公开结果构造的机制探测集合，不用于总体模型排名，也不能据筛选池分数估计两模型的整体协作收益。
