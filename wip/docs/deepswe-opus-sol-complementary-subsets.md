# opus-high 与 sol 四个 effort 档位的能力互补任务子集

更新日期：2026-08-12

为 `anthropic/claude-opus-5 [high]` 与 `openai/gpt-5-6-sol` 四个 effort 档位配对的互补性实验准备的任务子集，方法沿用 [luna/v4-flash 互补子集](deepswe-luna-v4flash-complementary-subset.md)。清单文件：

- 配对一（vs sol-xhigh）：[`wip/data/selection/complementary-opus-sol-xhigh.txt`](../data/selection/complementary-opus-sol-xhigh.txt)
- 配对二（vs sol-max）：[`wip/data/selection/complementary-opus-sol-max.txt`](../data/selection/complementary-opus-sol-max.txt)
- 配对三（vs sol-high）：[`wip/data/selection/complementary-opus-sol-high.txt`](../data/selection/complementary-opus-sol-high.txt)
- 配对四（vs sol-medium）：[10 题平衡扩展](../data/selection/complementary-opus-sol-medium.txt)；[8 题严格核心](../data/selection/complementary-opus-sol-medium-strict.txt)

四份 10 题清单均为前 5 题 opus 强方向、后 5 题 sol 强方向。前三组都能完全遵守主筛选阈值；sol-medium 严格口径只有 3 道 sol 强题，因此 10 题清单最后 2 题是显式放宽项，另提供前 5 + 后 3 的 8 题严格核心。**若四组只先做一组，仍推荐优先 sol-xhigh 配对**；若专门比较较低 effort，推荐 high 作为主实验、medium 作为低成本压力测试。

## 定位与用途边界

与 luna/v4-flash 子集相同：这是**机制探测池**，不是无偏 benchmark。题目按结果挑选，只能用于检验路由、双模型协作等机制能否吃到已知的互补收益，不能用于模型排名或声称两模型总体互补性大小。xhigh、max、high 三份 10 题池的逐题 oracle 分别为 95%（38/40）、97.5%（39/40）、97.5%（39/40）；medium 的 8 题严格核心为 93.8%（30/32），10 题平衡扩展为 85%（34/40）。详细论述见 luna/v4-flash 文档的同名章节，不再重复。

## 数据口径

- 数据源：`wip/data/official-v1.1/trials.json`（2026-08-07 下载快照），config 为 `mini_swe_agent_claude_opus_5_high` 与 `mini_swe_agent_gpt_5_6_sol_medium`、`_high`、`_xhigh`、`_max`。
- 过滤条件与主筛选一致：`source=deep-swe`、`eval_scope=full`、`included_in_score=true` 且 `errored=false`。每格为 `通过次数/有效重复数`，官方每格 4 次重复（个别格因 errored 剔除不足 4）。
- **家族列**：与 luna/v4-flash 子集的关键差异是**两侧都有完整 5 档 effort 家族**（opus-5 全 5 档 n=20、sol 全 5 档 n=20），家族佐证可以双向做，两个方向的证据强度对称——这是该配对证据条件优于 luna/v4-flash 配对的地方。

## 筛选思路

与 luna/v4-flash 文档第 1–3、5–8 步完全一致（候选阈值 ≥0.75 / ≤0.25，Fisher 档位 A ≈ 0.014 / B ≈ 0.071 / C ≈ 0.243，噪声基线分析原样适用；质量标记；confirm 隔离；方向各 5 题；内部确认待做）。差异只有第 4 步家族佐证，本次为**双侧规则**：入选题要求弱方向一侧的家族通过率也低（≤ 10/20），强方向一侧的家族口径同向。因此淘汰了若干"格子达标但家族不佐证"的候选（`abs-module-cache-flags`、`query-persist-restored-query-state`、`happy-dom-deterministic-intersectionobserver`），它们更像单一档位的抽样波动而非模型级差异。

confirm 隔离在本次同样触发：`clack-async-autocomplete-options` 在两组配对里都是 opus 强 A 档（4/4 vs 0/4），但属于 `05_sample_confirm`，为避免污染 confirm 组的未接触状态被排除，不列入替补。

> **2026-08-13 决策更新**：自 candidates 扫描 job
> `collab-codex-claude-complementary-opus-sol-xhigh-candidates-18-tasks-20260813-215326`
> 起，机制探索线**不再刻意回避 confirm 任务**（本轮目标是尽量扩大互补任务池,
> `clack` 已随 18 题候选清单进入 collab 机制实验）。含义：`05_sample_confirm` 对
> collab/机制类实验的"未接触"隔离自该 job 起失效；confirm 组在主线 harness 对比中的
> 用途不受影响,但引用其结果时应注明该组任务曾进入机制调试线。

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

## 推荐子集三：opus-high vs sol-high（10 题）

| # | 任务 | 方向 | 档 | opus high | sol high | opus 家族 | sol 家族 | 语言 | 标记 |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | `helm-array-merge-strategies` | opus 强 | A | 4/4 | 0/4 | 14/20 | 2/20 | go | 评分敏感（Δ +0.20） |
| 2 | `kombu-virtual-queue-dead-lettering` | opus 强 | A | 4/4 | 0/4 | 15/20 | 4/20 | python |  |
| 3 | `koota-pair-relation-tracking` | opus 强 | A | 4/4 | 0/4 | 14/20 | 0/20 | typescript |  |
| 4 | `python-statemachine-state-data-scoping` | opus 强 | A | 4/4 | 0/4 | 16/20 | 1/20 | python | 与 luna/v4-flash 清单重叠‡ |
| 5 | `testem-bail-on-test-failure` | opus 强 | A | 4/4 | 0/4 | 13/20 | 0/20 | javascript | 评分敏感（Δ −0.12） |
| 6 | `bandit-interprocedural-taint-checks` | sol 强 | A | 0/4 | 4/4 | 5/20 | 17/20 | python | 评分敏感（Δ −0.10） |
| 7 | `httpx-streaming-json-iteration` | sol 强 | A | 0/4 | 4/4 | 2/20 | 17/20 | python |  |
| 8 | `csstree-shorthand-expansion-compression` | sol 强 | B | 1/4 | 4/4 | 2/20 | 15/20 | javascript |  |
| 9 | `optique-conditional-option-dependencies` | sol 强 | B | 0/4 | 3/4 | 9/20 | 10/20 | typescript | 档位特长题¶ |
| 10 | `superjson-error-stack-serialization` | sol 强 | B | 1/4 | 4/4 | 3/20 | 14/20 | typescript | 未进 01_stable†† |

opus 强方向在排除 confirm 后恰有 5 道 A 档，全部纳入；sol 强方向也恰有 5 道 A/B 档，无需提拔 C 档。按官方重复计，opus 为 22/40、sol-high 为 19/40，逐题 oracle 为 39/40（97.5%）。

语言分布：python 4、typescript 3、javascript 2、go 1；10 题来自 10 个不同仓库。与 sol-max 清单重叠 8 题，与 sol-xhigh 清单重叠 6 题。

¶ `optique` 在 high 档是 3/4，且 sol 家族只有 10/20，仍主要是具体档位特长；证据弱于本方向另外 4 题，内部确认时优先观察。

†† `superjson` 未进稳定池是因为 `minimum_effective_repeats = 0`（个别其他 config 无有效重复），错误率 0.025、verifier timeout 为 0；不直接损害本文两格，但需要保留质量标记。

## 推荐子集四：opus-high vs sol-medium（10 题平衡扩展；8 题严格核心）

| # | 任务 | 方向 | 档 | opus high | sol medium | opus 家族 | sol 家族 | 语言 | 标记 |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | `helm-array-merge-strategies` | opus 强 | A | 4/4 | 0/4 | 14/20 | 2/20 | go | 评分敏感（Δ +0.20） |
| 2 | `kombu-virtual-queue-dead-lettering` | opus 强 | A | 4/4 | 0/4 | 15/20 | 4/20 | python |  |
| 3 | `koota-pair-relation-tracking` | opus 强 | A | 4/4 | 0/4 | 14/20 | 0/20 | typescript |  |
| 4 | `python-statemachine-state-data-scoping` | opus 强 | A | 4/4 | 0/4 | 16/20 | 1/20 | python | 与 luna/v4-flash 清单重叠‡ |
| 5 | `testem-bail-on-test-failure` | opus 强 | A | 4/4 | 0/4 | 13/20 | 0/20 | javascript | 评分敏感（Δ −0.12） |
| 6 | `httpx-streaming-json-iteration` | sol 强 | A | 0/4 | 4/4 | 2/20 | 17/20 | python |  |
| 7 | `csstree-shorthand-expansion-compression` | sol 强 | C | 1/4 | 3/4 | 2/20 | 15/20 | javascript | C 档提拔 |
| 8 | `superjson-error-stack-serialization` | sol 强 | C | 1/4 | 3/4 | 3/20 | 14/20 | typescript | C 档提拔；未进 01_stable†† |
| 9 | `bandit-interprocedural-taint-checks` | sol 强 | D | 0/4 | 2/4 | 5/20 | 17/20 | python | **放宽主阈值**；评分敏感（Δ −0.10） |
| 10 | `koota-deferred-mutation-buffer` | sol 强 | D | 0/4 | 2/4 | 1/20 | 13/20 | typescript | **放宽主阈值** |

这里不能把 10 题都当作与前三组同强度的证据：按主阈值（强侧 ≥ 3/4、弱侧 ≤ 1/4）扫描，排除 confirm 并要求家族佐证后，sol 强方向只有 `httpx`、`csstree`、`superjson` 3 题。故：

- **严格核心**是表中前 8 题（5 道 opus 强、3 道 sol 强），不追求方向等量，另存为 [`complementary-opus-sol-medium-strict.txt`](../data/selection/complementary-opus-sol-medium-strict.txt)；opus 为 22/32、sol-medium 为 10/32，逐题 oracle 为 30/32（93.8%）。
- **平衡扩展**是清单文件中的全部 10 题。D 档定义为 2/4 vs 0/4：Fisher 单侧 p ≈ 0.214，统计证据不比 C 档更差，但强侧仅 50%，没有达到机制探测池原定的 ≥ 75% 操作阈值。选择 `bandit`、`koota-deferred` 是因为 sol 家族佐证分别为 17/20、13/20，且在更高 effort 清单中方向一致。全部 10 题上 opus 为 22/40、sol-medium 为 14/40，逐题 oracle 为 34/40（85%）。

语言分布：python 4、typescript 3、javascript 2、go 1；10 题来自 9 个仓库（两个 koota 题方向相反）。与 sol-high 清单重叠 9 题，仅以 `koota-deferred` 替换 `optique`，适合做 effort 降档对照；但正式报告必须把严格核心与含 D 档的结果分开给出。

## 四份子集的关系

xhigh 与 max 两份仍重叠 8 题、联合 12 题。新增 high 与 medium 两份重叠 9 题、联合 11 题；相对原 xhigh/max 联合池，high 新增 `kombu-virtual-queue-dead-lettering`、`superjson-error-stack-serialization`，medium 不再增加其他题。四份清单的总联合池为 14 题：

`bandit`、`csstree`、`helm`、`httpx`、`kombu-virtual`、`koota-deferred`、`koota-pair`、`optique`、`participle`、`pest`、`python-statemachine`、`scc`、`superjson`、`testem`。

若四组都做内部确认，opus-high 只需在联合 14 题上跑一轮（4 次重复）；各 sol 档位跑自己的 10 题。若 high/medium 的目标是严格同题 effort 对照，可直接用两份清单的 9 题交集，或让两档都跑 11 题联合池，避免题目组成变化混入 effort 效应。

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

**配对三（vs sol-high）**

| 任务 | 方向 | 档 | opus high | sol high | 标记 |
| --- | --- | --- | ---: | ---: | --- |
| `pest-character-class-coalescing` | opus 强 | B | 3/4 | 0/4 | 家族佐证极强（18/20 vs 0/20） |
| `participle-grammar-conflict-analysis` | opus 强 | B | 4/4 | 1/4 | 未进 01_stable；评分敏感（Δ −0.14） |
| `onedump-dump-encryption-pipeline` | opus 强 | B | 3/4 | 0/4 | 家族佐证好（13/20 vs 2/20） |
| `koota-query-predicates` | opus 强 | A⁻ | 3/3 | 0/4 | 未进 01_stable；同仓库题重复 |
| `scc-bounded-memory-spilling` | sol 强 | C | 1/4 | 3/4 | 唯一未入选且有家族佐证的 sol 强候选；评分敏感（Δ +0.17） |

**配对四（vs sol-medium）**

| 任务 | 方向 | 档 | opus high | sol medium | 标记 |
| --- | --- | --- | ---: | ---: | --- |
| `anko-typed-variable-bindings` | opus 强 | A | 4/4 | 0/4 | 已在 05_sample_dev；家族 15/20 vs 6/20 |
| `participle-grammar-conflict-analysis` | opus 强 | A | 4/4 | 0/4 | 未进 01_stable；评分敏感（Δ −0.14） |
| `dasel-html-document-format` | opus 强 | A | 4/4 | 0/4 | 已在 05_sample_dev；评分敏感（Δ +0.12）；sol 家族 9/20 |
| `pest-character-class-coalescing` | opus 强 | B | 3/4 | 0/4 | 家族佐证极强（18/20 vs 0/20） |
| `awilix-async-container-initialization` | sol 强 | D | 0/4 | 2/4 | 仅作平衡扩展的下一替补；sol 家族仅 5/20 |

sol-medium 严格核心的 sol 强方向没有未入选替补；若 `httpx`、`csstree` 或 `superjson` 未复现，应优先缩小严格核心，而不是把 D 档包装成等价替补。

## 完整候选扫描记录

未入选原因：`confirm` = 属于 05_sample_confirm 被隔离；`家族不佐证` = 弱方向家族通过率 > 10/20，或强侧家族通过率没有高于弱侧；`C 档` = 证据不足仅作替补。

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

**配对三：opus-high vs sol-high（19 题命中）**

| 任务 | 方向 | 档 | opus high | sol high | opus 家族 | sol 家族 | 处置 |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `clack-async-autocomplete-options` | opus 强 | A | 4/4 | 0/4 | 17/20 | 2/20 | confirm |
| `helm-array-merge-strategies` | opus 强 | A | 4/4 | 0/4 | 14/20 | 2/20 | 入选 |
| `kombu-virtual-queue-dead-lettering` | opus 强 | A | 4/4 | 0/4 | 15/20 | 4/20 | 入选 |
| `koota-pair-relation-tracking` | opus 强 | A | 4/4 | 0/4 | 14/20 | 0/20 | 入选 |
| `python-statemachine-state-data-scoping` | opus 强 | A | 4/4 | 0/4 | 16/20 | 1/20 | 入选 |
| `testem-bail-on-test-failure` | opus 强 | A | 4/4 | 0/4 | 13/20 | 0/20 | 入选 |
| `koota-query-predicates` | opus 强 | A⁻ | 3/3 | 0/4 | 15/17 | 1/20 | 替补（质量标记、仓库重复） |
| `langchain-request-coalescing` | opus 强 | B | 4/4 | 1/4 | 18/20 | 10/20 | 替补（未进 01_stable、评分敏感） |
| `onedump-dump-encryption-pipeline` | opus 强 | B | 3/4 | 0/4 | 13/20 | 2/20 | 替补 |
| `opa-template-string-reconstruction` | opus 强 | B | 4/4 | 1/4 | 18/19 | 11/20 | 家族不佐证 |
| `participle-grammar-conflict-analysis` | opus 强 | B | 4/4 | 1/4 | 19/20 | 1/20 | 替补 |
| `pest-character-class-coalescing` | opus 强 | B | 3/4 | 0/4 | 18/20 | 0/20 | 替补 |
| `eicrud-keyset-pagination-cursor` | opus 强 | C | 3/4 | 1/4 | 12/20 | 5/20 | C 档 |
| `bandit-interprocedural-taint-checks` | sol 强 | A | 0/4 | 4/4 | 5/20 | 17/20 | 入选 |
| `httpx-streaming-json-iteration` | sol 强 | A | 0/4 | 4/4 | 2/20 | 17/20 | 入选 |
| `csstree-shorthand-expansion-compression` | sol 强 | B | 1/4 | 4/4 | 2/20 | 15/20 | 入选 |
| `optique-conditional-option-dependencies` | sol 强 | B | 0/4 | 3/4 | 9/20 | 10/20 | 入选（档位特长题） |
| `superjson-error-stack-serialization` | sol 强 | B | 1/4 | 4/4 | 3/20 | 14/20 | 入选 |
| `scc-bounded-memory-spilling` | sol 强 | C | 1/4 | 3/4 | 7/20 | 16/20 | C 档，替补 |

**配对四：opus-high vs sol-medium（22 题命中）**

| 任务 | 方向 | 档 | opus high | sol medium | opus 家族 | sol 家族 | 处置 |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `anko-typed-variable-bindings` | opus 强 | A | 4/4 | 0/4 | 15/20 | 6/20 | 替补 |
| `dasel-html-document-format` | opus 强 | A | 4/4 | 0/4 | 20/20 | 9/20 | 替补 |
| `helm-array-merge-strategies` | opus 强 | A | 4/4 | 0/4 | 14/20 | 2/20 | 入选 |
| `kombu-virtual-queue-dead-lettering` | opus 强 | A | 4/4 | 0/4 | 15/20 | 4/20 | 入选 |
| `koota-pair-relation-tracking` | opus 强 | A | 4/4 | 0/4 | 14/20 | 0/20 | 入选 |
| `participle-grammar-conflict-analysis` | opus 强 | A | 4/4 | 0/4 | 19/20 | 1/20 | 替补（质量标记） |
| `python-statemachine-state-data-scoping` | opus 强 | A | 4/4 | 0/4 | 16/20 | 1/20 | 入选 |
| `testem-bail-on-test-failure` | opus 强 | A | 4/4 | 0/4 | 13/20 | 0/20 | 入选 |
| `koota-query-predicates` | opus 强 | A⁻ | 3/3 | 0/4 | 15/17 | 1/20 | 替补（质量标记、仓库重复） |
| `clack-async-autocomplete-options` | opus 强 | B | 4/4 | 1/4 | 17/20 | 2/20 | confirm |
| `eicrud-keyset-pagination-cursor` | opus 强 | B | 3/4 | 0/4 | 12/20 | 5/20 | 替补 |
| `onedump-dump-encryption-pipeline` | opus 强 | B | 3/4 | 0/4 | 13/20 | 2/20 | 替补 |
| `pest-character-class-coalescing` | opus 强 | B | 3/4 | 0/4 | 18/20 | 0/20 | 替补 |
| `aiomonitor-task-snapshots-diff` | opus 强 | B | 4/4 | 1/4 | 20/20 | 13/20 | 家族不佐证 |
| `mobly-grouped-test-barriers` | opus 强 | B | 4/4 | 1/4 | 16/20 | 15/20 | confirm 且家族不佐证 |
| `opa-template-string-reconstruction` | opus 强 | B | 4/4 | 1/4 | 18/19 | 11/20 | 家族不佐证 |
| `tomlkit-toml-table-converters` | opus 强 | B | 4/4 | 1/4 | 20/20 | 13/20 | confirm 且家族不佐证 |
| `textual-kitty-key-phases` | opus 强 | C | 3/4 | 1/4 | 15/20 | 11/20 | C 档且家族不佐证 |
| `httpx-streaming-json-iteration` | sol 强 | A | 0/4 | 4/4 | 2/20 | 17/20 | 入选 |
| `csstree-shorthand-expansion-compression` | sol 强 | C | 1/4 | 3/4 | 2/20 | 15/20 | C 档提拔入选 |
| `superjson-error-stack-serialization` | sol 强 | C | 1/4 | 3/4 | 3/20 | 14/20 | C 档提拔入选 |
| `igel-persist-feature-schema` | sol 强 | C | 1/4 | 3/4 | 8/20 | 8/20 | 家族不佐证 |

medium 的 22 题是严格主阈值命中记录，不含平衡扩展的两个 D 档。`bandit-interprocedural-taint-checks`（0/4 vs 2/4，家族 5/20 vs 17/20）与 `koota-deferred-mutation-buffer`（0/4 vs 2/4，家族 1/20 vs 13/20）仅因方向补齐而另行加入 10 题清单。

四份扫描共享 opus-high 一侧，sol 四档又来自同一模型家族，因此重叠只能用于降低实验成本或设计 effort 对照，不能视为独立复现证据。

## high vs medium：使用建议

**主实验优先用 sol-high；sol-medium 更适合作为低成本压力测试或 effort 消融。** high 的两个方向均能以 A/B 档各取 5 题，逐题 oracle 97.5%，且 10 个仓库无重复；medium 只有 3 道严格 sol 强题，平衡扩展的 oracle 降到 85%，机制失败与互补信号不足更难区分。

medium 的优点是官方全量平均成本仅 $1.86/trial，约为 high 的 $3.47/trial 的 54%，且两份 10 题清单重叠 9 题。因此合理顺序是先用 high 验证机制是否能捕获明确互补性，再在 9 题交集或 11 题联合池上把 sol effort 降到 medium，观察收益随成本下降如何衰减；若直接从 medium 开始，主结论只报 8 题严格核心，10 题平衡扩展作为敏感性分析。

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
