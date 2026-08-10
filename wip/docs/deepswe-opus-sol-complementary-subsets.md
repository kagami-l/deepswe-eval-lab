# opus-high 与 sol-xhigh / sol-max 能力互补任务子集

更新日期：2026-08-09

为 `anthropic/claude-opus-5 [high]` 与 `openai/gpt-5-6-sol [xhigh]`、`[max]` 两组配对的互补性实验准备的任务子集，方法沿用 [luna/v4-flash 互补子集](deepswe-luna-v4flash-complementary-subset.md)。清单文件：

- 配对一（vs sol-xhigh）：[`wip/data/selection/complementary-opus-sol-xhigh.txt`](../data/selection/complementary-opus-sol-xhigh.txt)
- 配对二（vs sol-max）：[`wip/data/selection/complementary-opus-sol-max.txt`](../data/selection/complementary-opus-sol-max.txt)

均为前 5 题 opus 强方向、后 5 题 sol 强方向。两份清单重叠 8 题，联合池 12 题。**若两组只先做一组，推荐优先 sol-xhigh 配对**，理由见文末[优先级推荐](#xhigh-vs-max优先级推荐)。

## 定位与用途边界

与 luna/v4-flash 子集相同：这是**机制探测池**，不是无偏 benchmark。题目按结果挑选，只能用于检验路由、双模型协作等机制能否吃到已知的互补收益，不能用于模型排名或声称两模型总体互补性大小。oracle 路由在两份子集上的理论上限分别约 95%（38/40）与 97.5%（39/40），单配置约 50%，headroom 明确。详细论述见 luna/v4-flash 文档的同名章节，不再重复。

## 数据口径

- 数据源：`wip/data/official-v1.1/trials.json`（2026-08-07 下载快照），config 为 `mini_swe_agent_claude_opus_5_high`、`mini_swe_agent_gpt_5_6_sol_xhigh`、`mini_swe_agent_gpt_5_6_sol_max`。
- 过滤条件与主筛选一致：`source=deep-swe`、`eval_scope=full`、`included_in_score=true` 且 `errored=false`。每格为 `通过次数/有效重复数`，官方每格 4 次重复（个别格因 errored 剔除不足 4）。
- **家族列**：与 luna/v4-flash 子集的关键差异是**两侧都有完整 5 档 effort 家族**（opus-5 全 5 档 n=20、sol 全 5 档 n=20），家族佐证可以双向做，两个方向的证据强度对称——这是该配对证据条件优于 luna/v4-flash 配对的地方。

## 筛选思路

与 luna/v4-flash 文档第 1–3、5–8 步完全一致（候选阈值 ≥0.75 / ≤0.25，Fisher 档位 A ≈ 0.014 / B ≈ 0.071 / C ≈ 0.243，噪声基线分析原样适用；质量标记；confirm 隔离；方向各 5 题；内部确认待做）。差异只有第 4 步家族佐证，本次为**双侧规则**：入选题要求弱方向一侧的家族通过率也低（≤ 10/20），强方向一侧的家族口径同向。因此淘汰了若干"格子达标但家族不佐证"的候选（`abs-module-cache-flags`、`query-persist-restored-query-state`、`happy-dom-deterministic-intersectionobserver`），它们更像单一档位的抽样波动而非模型级差异。

confirm 隔离在本次同样触发：`clack-async-autocomplete-options` 在两组配对里都是 opus 强 A 档（4/4 vs 0/4），但属于 `05_sample_confirm`，为避免污染 confirm 组的未接触状态被排除，不列入替补。

## 推荐子集一：opus-high vs sol-xhigh（10 题）

| # | 任务 | 方向 | 档 | opus high | sol xhigh | opus 家族 | sol 家族 | 语言 | 标记 |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | `koota-pair-relation-tracking` | opus 强 | A | 4/4 | 0/4 | 14/20 | 0/20 | typescript |  |
| 2 | `participle-grammar-conflict-analysis` | opus 强 | A | 4/4 | 0/4 | 19/20 | 1/20 | go | 未进 01_stable†；评分敏感（Δ −0.14） |
| 3 | `python-statemachine-state-data-scoping` | opus 强 | A | 4/4 | 0/4 | 16/20 | 1/20 | python | 与 luna/v4-flash 清单重叠‡ |
| 4 | `testem-bail-on-test-failure` | opus 强 | A | 4/4 | 0/4 | 13/20 | 0/20 | javascript | 评分敏感（Δ −0.12） |
| 5 | `pest-character-class-coalescing` | opus 强 | B | 3/4 | 0/4 | 18/20 | 0/20 | rust |  |
| 6 | `bandit-interprocedural-taint-checks` | sol 强 | A | 0/4 | 4/4 | 5/20 | 17/20 | python | 评分敏感（Δ −0.10） |
| 7 | `koota-deferred-mutation-buffer` | sol 强 | A | 0/4 | 4/4 | 1/20 | 13/20 | typescript |  |
| 8 | `csstree-shorthand-expansion-compression` | sol 强 | B | 1/4 | 4/4 | 2/20 | 15/20 | javascript |  |
| 9 | `httpx-streaming-json-iteration` | sol 强 | B | 0/4 | 3/4 | 2/20 | 17/20 | python |  |
| 10 | `scc-bounded-memory-spilling` | sol 强 | B | 1/4 | 4/4 | 7/20 | 16/20 | go | 评分敏感（Δ +0.17） |

sol 强方向 B 档三选二时取 `csstree`、`httpx`、`scc` 而非 `ink-grid-box-layout`：`scc` 的家族差距更大（7/20 vs 16/20），`ink` 的 sol 家族仅 9/20（收益依赖高档 effort），列为首位替补。

语言分布：python 3、typescript 2、javascript 2、go 2、rust 1；10 题分属 9 个仓库（`pmndrs/koota` 出现 2 次，但方向相反——koota 仓库本身不预测方向，属任务级而非仓库级互补，保留并注明）。

## 推荐子集二：opus-high vs sol-max（10 题）

| # | 任务 | 方向 | 档 | opus high | sol max | opus 家族 | sol 家族 | 语言 | 标记 |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | `helm-array-merge-strategies` | opus 强 | A | 4/4 | 0/4 | 14/20 | 2/20 | go | 评分敏感（Δ +0.20） |
| 2 | `koota-pair-relation-tracking` | opus 强 | A | 4/4 | 0/4 | 14/20 | 0/20 | typescript |  |
| 3 | `participle-grammar-conflict-analysis` | opus 强 | A | 4/4 | 0/4 | 19/20 | 1/20 | go | 未进 01_stable†；评分敏感（Δ −0.14） |
| 4 | `testem-bail-on-test-failure` | opus 强 | A | 4/4 | 0/4 | 13/20 | 0/20 | javascript | 评分敏感（Δ −0.12） |
| 5 | `python-statemachine-state-data-scoping` | opus 强 | B | 4/4 | 1/4 | 16/20 | 1/20 | python | 与 luna/v4-flash 清单重叠‡ |
| 6 | `bandit-interprocedural-taint-checks` | sol 强 | A | 0/4 | 4/4 | 5/20 | 17/20 | python | 评分敏感（Δ −0.10） |
| 7 | `koota-deferred-mutation-buffer` | sol 强 | A | 0/4 | 4/4 | 1/20 | 13/20 | typescript |  |
| 8 | `optique-conditional-option-dependencies` | sol 强 | A | 0/4 | 4/4 | 9/20 | 10/20 | typescript | 档位特长题§ |
| 9 | `csstree-shorthand-expansion-compression` | sol 强 | B | 1/4 | 4/4 | 2/20 | 15/20 | javascript |  |
| 10 | `httpx-streaming-json-iteration` | sol 强 | B | 0/4 | 3/4 | 2/20 | 17/20 | python |  |

opus 强方向第 5 席在 `python-statemachine`（4/4 vs 1/4）与 `pest`（3/4 vs 0/4）两个同档 B 之间接近掷硬币，取前者是因为强侧满格 4/4 对路由捕获收益更直接；`pest` 为首位替补。

语言分布：typescript 3、python 3、javascript 2、go 2；10 题分属 9 个仓库（koota 2 次，方向相反）。

† `participle` 未进稳定池的原因是 `minimum_effective_repeats = 2`（个别其他 config 有效重复不足），其错误率 0.02、verifier timeout 为 0，不直接影响本文两格的可信度，保留使用但注明。

‡ `python-statemachine-state-data-scoping` 同时是 luna/v4-flash 互补子集的 flash 强题（v4-flash 与 opus 都能做、luna 与 sol 都做不出）。两个子集同为机制调试池，重叠本身无纯度问题，但若两条实验线并行，对该题的调试会互相影响，报告时注明。

§ `optique` 的双侧家族都不明显同向（opus 家族 9/20、sol 家族 10/20），即互补性只存在于 opus-high vs sol-max 这两个具体档位、而非模型级。作为机制探测（路由对象就是具体 config）仍然成立，但它是全部 20 题里内部确认复现风险最高的一题，按 A 档全收原则保留。

## 两份子集的关系

8 题重叠（koota-pair、participle、testem、python-statemachine、bandit、koota-deferred、csstree、httpx），联合池共 12 题（配对一另有 pest、scc，配对二另有 helm、optique）。内部确认时 opus-high 只需在联合 12 题上跑一轮（4 次重复），即可同时服务两组配对；sol-xhigh、sol-max 各跑自己配对的 10 题（或都跑 12 题以便交叉比对，边际成本约多 2 题 × 4 次）。

## 替补名单

若确认跑中有题未复现互补性，按方向递补（仍需复跑确认）：

**配对一（vs sol-xhigh）**

| 任务 | 方向 | 档 | opus high | sol xhigh | 标记 |
| --- | --- | --- | ---: | ---: | --- |
| `koota-query-predicates` | opus 强 | A⁻ | 3/3 | 0/4 | 未进 01_stable（min_eff_repeats=3 且 3 次 verifier timeout）；第三个 koota 题；p ≈ 0.029 |
| `onedump-dump-encryption-pipeline` | opus 强 | B | 3/4 | 0/4 | 家族佐证好（13/20 vs 2/20）；与 luna/v4-flash 清单重叠 |
| `dasel-html-document-format` | opus 强 | B | 4/4 | 1/4 | 已在 05_sample_dev；评分敏感（Δ +0.12）；sol 家族 9/20 中等 |
| `ink-grid-box-layout` | sol 强 | B | 0/4 | 3/4 | sol 家族仅 9/20 |
| `arktype-json-schema-refs-dependencies` | sol 强 | C | 1/4 | 3/4 | 家族差距小（8/20 vs 11/20）；评分敏感（Δ +0.10） |

**配对二（vs sol-max）**

| 任务 | 方向 | 档 | opus high | sol max | 标记 |
| --- | --- | --- | ---: | ---: | --- |
| `pest-character-class-coalescing` | opus 强 | B | 3/4 | 0/4 | 家族佐证极强（18/20 vs 0/20） |
| `koota-query-predicates` | opus 强 | B | 3/3 | 1/4 | 同上（未进 01_stable、第三个 koota） |
| `scc-bounded-memory-spilling` | sol 强 | B | 1/4 | 4/4 | 评分敏感（Δ +0.17） |
| `ink-grid-box-layout` | sol 强 | B | 0/4 | 3/4 | sol 家族仅 9/20 |
| `superjson-error-stack-serialization` | sol 强 | C | 1/4 | 3/4 | 未进 01_stable（良性，见 luna 文档）；luna/v4-flash 清单中为 luna 强题 |

## 完整候选扫描记录

未入选原因：`confirm` = 属于 05_sample_confirm 被隔离；`家族不佐证` = 弱方向家族通过率 > 10/20；`C 档` = 证据不足仅作替补。

**配对一：opus-high vs sol-xhigh（18 题命中）**

| 任务 | 方向 | 档 | opus high | sol xhigh | opus 家族 | sol 家族 | 处置 |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `clack-async-autocomplete-options` | opus 强 | A | 4/4 | 0/4 | 17/20 | 2/20 | confirm |
| `koota-pair-relation-tracking` | opus 强 | A | 4/4 | 0/4 | 14/20 | 0/20 | 入选 |
| `koota-query-predicates` | opus 强 | A⁻ | 3/3 | 0/4 | 15/17 | 1/20 | 替补（质量标记、仓库重复） |
| `participle-grammar-conflict-analysis` | opus 强 | A | 4/4 | 0/4 | 19/20 | 1/20 | 入选 |
| `python-statemachine-state-data-scoping` | opus 强 | A | 4/4 | 0/4 | 16/20 | 1/20 | 入选 |
| `testem-bail-on-test-failure` | opus 强 | A | 4/4 | 0/4 | 13/20 | 0/20 | 入选 |
| `abs-module-cache-flags` | opus 强 | B | 4/4 | 1/4 | 19/20 | 13/20 | 家族不佐证 |
| `dasel-html-document-format` | opus 强 | B | 4/4 | 1/4 | 20/20 | 9/20 | 替补 |
| `onedump-dump-encryption-pipeline` | opus 强 | B | 3/4 | 0/4 | 13/20 | 2/20 | 替补 |
| `pest-character-class-coalescing` | opus 强 | B | 3/4 | 0/4 | 18/20 | 0/20 | 入选 |
| `happy-dom-deterministic-intersectionobserver` | opus 强 | C | 3/4 | 1/4 | 11/20 | 12/20 | C 档且家族不佐证 |
| `bandit-interprocedural-taint-checks` | sol 强 | A | 0/4 | 4/4 | 5/20 | 17/20 | 入选 |
| `koota-deferred-mutation-buffer` | sol 强 | A | 0/4 | 4/4 | 1/20 | 13/20 | 入选 |
| `csstree-shorthand-expansion-compression` | sol 强 | B | 1/4 | 4/4 | 2/20 | 15/20 | 入选 |
| `httpx-streaming-json-iteration` | sol 强 | B | 0/4 | 3/4 | 2/20 | 17/20 | 入选 |
| `ink-grid-box-layout` | sol 强 | B | 0/4 | 3/4 | 2/20 | 9/20 | 替补 |
| `scc-bounded-memory-spilling` | sol 强 | B | 1/4 | 4/4 | 7/20 | 16/20 | 入选 |
| `arktype-json-schema-refs-dependencies` | sol 强 | C | 1/4 | 3/4 | 8/20 | 11/20 | C 档，替补 |

**配对二：opus-high vs sol-max（19 题命中）**

| 任务 | 方向 | 档 | opus high | sol max | opus 家族 | sol 家族 | 处置 |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `clack-async-autocomplete-options` | opus 强 | A | 4/4 | 0/4 | 17/20 | 2/20 | confirm |
| `helm-array-merge-strategies` | opus 强 | A | 4/4 | 0/4 | 14/20 | 2/20 | 入选 |
| `koota-pair-relation-tracking` | opus 强 | A | 4/4 | 0/4 | 14/20 | 0/20 | 入选 |
| `participle-grammar-conflict-analysis` | opus 强 | A | 4/4 | 0/4 | 19/20 | 1/20 | 入选 |
| `testem-bail-on-test-failure` | opus 强 | A | 4/4 | 0/4 | 13/20 | 0/20 | 入选 |
| `koota-query-predicates` | opus 强 | B | 3/3 | 1/4 | 15/17 | 1/20 | 替补（质量标记、仓库重复） |
| `pest-character-class-coalescing` | opus 强 | B | 3/4 | 0/4 | 18/20 | 0/20 | 替补 |
| `python-statemachine-state-data-scoping` | opus 强 | B | 4/4 | 1/4 | 16/20 | 1/20 | 入选 |
| `query-persist-restored-query-state` | opus 强 | B | 4/4 | 1/4 | 19/20 | 14/20 | 家族不佐证 |
| `happy-dom-deterministic-intersectionobserver` | opus 强 | C | 3/4 | 1/4 | 11/20 | 12/20 | C 档且家族不佐证 |
| `bandit-interprocedural-taint-checks` | sol 强 | A | 0/4 | 4/4 | 5/20 | 17/20 | 入选 |
| `koota-deferred-mutation-buffer` | sol 强 | A | 0/4 | 4/4 | 1/20 | 13/20 | 入选 |
| `optique-conditional-option-dependencies` | sol 强 | A | 0/4 | 4/4 | 9/20 | 10/20 | 入选（档位特长题§） |
| `csstree-shorthand-expansion-compression` | sol 强 | B | 1/4 | 4/4 | 2/20 | 15/20 | 入选 |
| `httpx-streaming-json-iteration` | sol 强 | B | 0/4 | 3/4 | 2/20 | 17/20 | 入选 |
| `ink-grid-box-layout` | sol 强 | B | 0/4 | 3/4 | 2/20 | 9/20 | 替补 |
| `scc-bounded-memory-spilling` | sol 强 | B | 1/4 | 4/4 | 7/20 | 16/20 | 替补 |
| `arktype-json-schema-refs-dependencies` | sol 强 | C | 1/4 | 3/4 | 8/20 | 11/20 | C 档，替补 |
| `superjson-error-stack-serialization` | sol 强 | C | 1/4 | 3/4 | 3/20 | 14/20 | C 档，替补 |

两份扫描共享 opus 一侧，且 sol-xhigh 与 sol-max 高度相关（同模型相邻档位），因此两份扫描在 8 题上一致是预期结果，不构成相互独立的证据。

## xhigh vs max：优先级推荐

**推荐优先做 opus-high + sol-xhigh 配对。**

官方 113 题全量口径（scored trials）：

| config | 整体通过率 | 平均成本/trial | 每次通过成本 |
| --- | ---: | ---: | ---: |
| claude-opus-5 [high] | 72.8%（327/449） | $6.08 | $8.35 |
| gpt-5-6-sol [xhigh] | 70.7%（319/451） | $4.70 | $6.65 |
| gpt-5-6-sol [max] | 72.7%（327/450） | $8.39 | $11.54 |

sol 家族的边际收益曲线：low 45.4%（$1.07）→ medium 61.1%（$1.86）→ high 69.4%（$3.47）→ xhigh 70.7%（$4.70）→ max 72.7%（$8.39）。xhigh → max 花 1.78 倍成本换 +2.0pp。

理由：

1. **互补结构几乎相同**：sol 强方向的候选两组高度一致（bandit、koota-deferred、csstree、httpx、ink、scc、arktype 共有；max 仅多出 optique 和 superjson，前者是复现风险最高的档位特长题、后者是 C 档）；opus 强方向 max 多 helm、少若干 B 档。两份 10 题清单重叠 8 题——换用 max 并不能探测到明显更多互补信号。
2. **实验成本**：互补实验的主要开销是大量重复（内部确认 2 配置 × 10–12 题 × 4 次，之后的机制实验轮次更多），sol 侧 xhigh 比 max 便宜 44%（子集任务上实测 $4.90 vs $9.44/trial）。
3. **结论的生产意义**：opus-high 为 $6.08/trial。用 sol-xhigh（$4.70）配对，路由/协作机制若有效，结论形式是"以不高于单 opus 的成本拿到更高通过率"；换 sol-max（$8.39，比 opus 还贵 38%）后只能得到"更贵但更强"，对机制的说服力弱得多。
4. **max 的相对优点仅在能力对齐**：max 与 opus-high 整体通过率完全对齐（72.7% vs 72.8%），"纯互补、无强弱"的解释最干净，且 sol 强方向 A 档多一题。但 xhigh 与 opus-high 的差距也只有 2.1pp，本就接近对齐，这点优势不值 78% 的成本溢价。

建议顺序：先跑 xhigh 配对的内部确认与机制实验；若之后需要回答"互补收益是否随 effort 升档消失"，再补 max 配对——届时 opus-high 在联合 12 题上的确认结果可直接复用，只需增补 sol-max 一侧的重复。
