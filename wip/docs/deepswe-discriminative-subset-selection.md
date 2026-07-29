# DeepSWE v1.1：高区分度任务子集的公开数据与筛选方案

更新日期：2026-07-29

## 结论

`https://deepswe.datacurve.ai/data/v1.1` **可以作为筛选依据，而且公开数据比网页表格本身更有用**：官网直接暴露任务索引、22,586 条逐 trial 结果、实时榜单汇总，以及每个 trial 的 trajectory、模型 patch、agent log 和 verifier 输出的下载规则。因此，DeepSWE v1.1 足以构造一个证据较强的“模型区分度”候选池。

但它**不能直接证明 task 对不同 agent 有区分度**：当前 v1.1 的 22,586 条公开 full-benchmark rollout 全部使用 `mini-swe-agent`，差异来自 18 个 base model、50 个 model × reasoning-effort configuration。对 agent 的区分度只能先做代理推断，再用“同一模型、不同 agent”的本地小规模 pilot 实测。[官方数据页](https://deepswe.datacurve.ai/data/v1.1) [官方逐 trial 索引](https://deepswe.datacurve.ai/artifacts/v1.1/trials.json) [官方 README](https://github.com/datacurve-ai/deep-swe/blob/e016041a6ccf8da29906afc9a3f5a8df940a1f78/README.md)

建议不要直接复刻 SWE-bench Pro 的单一 `mixed` 规则。DeepSWE 每个 `(task, config)` 原则上有 4 次重复，适合同时衡量：

1. 难度是否避开全过/全不过；
2. 强弱模型是否在该题上有稳定的排序差；
3. 差异来自 configuration 之间，还是同一 configuration 的随机波动；
4. trial 是否因 provider/verifier 错误被排除；
5. 最终抽样是否覆盖语言、仓库和任务规模。

## 官网实际公开了什么

### 机器可读入口

| 资源 | 主要用途 |
| --- | --- |
| [`tasks.json`](https://deepswe.datacurve.ai/artifacts/v1.1/tasks.json) | 113 个任务的 ID、标题、描述、语言、仓库、仓库 URL、base commit、prompt 字符数 |
| [`trials.json`](https://deepswe.datacurve.ai/artifacts/v1.1/trials.json) | 每次 rollout 的结果、配置、分项分数、错误、成本、tokens、steps、时长和 artifact 可用性 |
| [`leaderboard-live.json`](https://deepswe.datacurve.ai/artifacts/v1.1/leaderboard-live.json) | configuration 级 pass@1/pass@4、重复运行置信区间、成本/tokens/steps/时长汇总 |
| [`release.json`](https://deepswe.datacurve.ai/artifacts/v1.1/release.json) | 每个 trial 的 trajectory、patch、agent log、verifier 文件的 CloudFront URL 模板 |
| [`v1-delta.json`](https://deepswe.datacurve.ai/artifacts/v1.1/v1-delta.json) | 同一批 rollout 在 v1 与 v1.1 判分下的 config/task 变化，可标记判分敏感题 |

本次核查固定到 2026-07-25 生成的官网快照，SHA-256 如下：

| 文件 | SHA-256 |
| --- | --- |
| `trials.json` | `7844056bade4cee4a2c2964c9582bf7eb1344735a28695cae7d419055656417a` |
| `tasks.json` | `bae967f6472943564c3fc5232fba3c8e0ac465c1be5ccf9dd4895d4ee9df6242` |
| `leaderboard-live.json` | `d5fc4531d5b005c6e0040a82ddafe63225b1c172015cd499f2ec866f16f91cf1` |
| `release.json` | `0b77963ed8c54ef40c5f744ade178b54bfae2662ed94f9235cee85eb542bdc85` |
| `v1-delta.json` | `f6b2c0ef38dd34a3361929e383caa5f8255151f3596d3391f5922531bf2d3f58` |

### trial 字段

`trials.json` 每行包括：

- 身份与配置：`trial_name`、`task_name`、`source`、`eval_scope`、`model`、`provider`、`harness`、`config`、`reasoning_effort`；
- 结果：`reward`、`passed`、`errored`、`outcome`、`included_in_score`、`score_value`；
- v1.1 分项：`f2p_total/passed`、`p2p_total/passed`、`f2p`、`p2p`、`partial`；
- 效率：`n_agent_steps`、`cost_usd`、input/cache/output tokens、`peak_context_tokens`、agent/trial duration；
- 诊断：`error_category`、`exception`、`metrics_source`；
- 原始工件：trajectory、patch、agent log、verifier output 是否存在，以及 verifier 文件清单。

这意味着网页中的 pass rate、平均成本、平均 steps、平均 tokens、peak context 和时长都可以离线重算，而不是依赖页面截图。[官方逐 trial 索引](https://deepswe.datacurve.ai/artifacts/v1.1/trials.json)

### 配置覆盖与重复次数

当前快照覆盖 113 个 task、18 个 base model、50 个 configuration。所有公开 trial 的 harness 都是 `mini-swe-agent`。模型与 effort 覆盖如下：[官方逐 trial 索引](https://deepswe.datacurve.ai/artifacts/v1.1/trials.json)

| Base model | Config 数 | Reasoning effort |
| --- | ---: | --- |
| `claude-fable-5` | 5 | low, medium, high, xhigh, max |
| `claude-opus-4-8` | 5 | low, medium, high, xhigh, max |
| `claude-opus-5` | 5 | low, medium, high, xhigh, max |
| `claude-sonnet-4-6` | 1 | high |
| `claude-sonnet-5` | 5 | low, medium, high, xhigh, max |
| `gemini-3-1-pro-preview` | 1 | high |
| `gemini-3-5-flash` | 1 | medium |
| `gemini-3-6-flash` | 1 | high |
| `glm-5-2` | 2 | high, max |
| `gpt-5-4` | 1 | xhigh |
| `gpt-5-5` | 4 | low, medium, high, xhigh |
| `gpt-5-6-luna` | 5 | low, medium, high, xhigh, max |
| `gpt-5-6-sol` | 5 | low, medium, high, xhigh, max |
| `gpt-5-6-terra` | 5 | low, medium, high, xhigh, max |
| `grok-4-5` | 1 | high |
| `kimi-k2-7-code` | 1 | default |
| `kimi-k3` | 1 | max |
| `muse-spark-1-1` | 1 | xhigh |

名义覆盖应为 `113 × 50 × 4 = 22,600`，实际为 22,586，缺 14 个 rollout；22,438 个进入分数，148 个错误 trial 被排除。缺失只出现在 6 个 configuration：Opus 5 max 缺 3、Opus 5 xhigh 缺 1、Luna max 缺 4、Terra low 缺 3、Terra medium 缺 2、Terra max 缺 1。逐 task 最多缺 5 个 rollout，且每个 task 仍出现全部 50 个 configuration。

148 个排除错误由 `model_routing_404=73`、`provider_timeout=36`、`verifier_timeout=30`、`unclassified_exception=5`、`upstream_provider_error=3`、`rate_limit=1` 组成。官网榜单的口径明确把 context-window failure 和 agent timeout 记为失败，但排除 provider/verifier/network error；筛选脚本必须使用 `included_in_score`，不能把 `errored` 当普通 fail。[官方实时榜单](https://deepswe.datacurve.ai/artifacts/v1.1/leaderboard-live.json) [官方逐 trial 索引](https://deepswe.datacurve.ai/artifacts/v1.1/trials.json)

### 原始 trial 是否足够公开

足够用于审计。22,586 行中：

- trajectory：22,585；
- model patch：22,585；
- agent log：22,586；
- verifier output：22,555。

`release.json` 给出公开 CloudFront 模板，例如：

```text
https://d3ujjcmjq6o8v6.cloudfront.net/v1.1/trial-artifacts/{trial_name}/agent/trajectory.json
https://d3ujjcmjq6o8v6.cloudfront.net/v1.1/trial-artifacts/{trial_name}/artifacts/model.patch
https://d3ujjcmjq6o8v6.cloudfront.net/v1.1/trial-artifacts/{trial_name}/agent/mini-swe-agent.txt
https://d3ujjcmjq6o8v6.cloudfront.net/v1.1/trial-artifacts/{trial_name}/verifier/test-stdout.txt
```

本次对首条 trial 的四类 URL 均实际得到 HTTP 200。[官方 release 描述](https://deepswe.datacurve.ai/artifacts/v1.1/release.json)

原始 patch/trajectory 很适合事后解释某题为什么区分模型，但不建议把其语义内容用于主筛选：这样容易把公开模型的具体失败模式“调入”子集，并增加 post-hoc selection bias。主筛选只使用结果、错误率、静态任务元数据和不泄露实现内容的规模特征。

## 与 SWE-bench Pro 219 题方案的关系

之前的 [SWE-bench Pro 219 题方案](../../../SWE-bench_Pro-os/docs/research/swe-bench-pro-high-quality-mixed-219.md) 用“九份结果至少一过一败 + 高覆盖 + dated run 也 mixed”来降低 missing 和配置差异。

DeepSWE 可保留三个思想：高覆盖、mixed、按难度/语言/仓库分层；但应升级两点：

1. 同一 config 有 4 次重复，不能只把“出现过一次 pass 和一次 fail”当成模型差异；那也可能只是 trial 随机性。
2. 50 个 config 并非 50 个独立模型。多个模型有 5 档 effort，若直接池化会过度加权这些模型家族。

因此，DeepSWE 应以 `(task, config)` 的重复 pass rate 为基础，并在 base-model 层等权或分层，而不是把 22,438 次有效 rollout 当成独立模型票数。

## 推荐筛选方案

### 第 0 层：冻结输入与评分口径

保存上述 JSON、SHA-256、下载时间、筛选脚本版本；只使用 `eval_scope=full`、`source=deep-swe`、`included_in_score=true`。保留 errored trial 计数作为质量字段，但不进入 pass/fail 分母。

对每个 `(task, config)` 计算：有效重复数 `n`、pass rate `p_tc`、错误数。对每个 base model 先在其 effort configs 内汇总，再让 18 个 base model 等权。另保留“50 config 等权”的敏感性结果；只有两种口径结论一致的题才进入核心池。

### 第 1 层：稳定性硬过滤

建议核心池满足：

- 至少 17/18 个 base model 有有效结果；
- 每个纳入的 `(task, config)` 至少 3 个有效重复；
- task 级排除错误率不高于 5%；
- verifier timeout 不超过 1 次；超过者进入“基础设施敏感”标记，不进入核心池；
- oracle/nop 本地控制继续满足预期。

当前 verifier-timeout 高发题应先排除或单列诊断池：`koota-composite-trait-aspects` 11 次、`pwntools-tube-multiplexing` 9 次、`boa-hierarchical-evaluation-cancellation` 4 次、`koota-query-predicates` 3 次。[官方逐 trial 索引](https://deepswe.datacurve.ai/artifacts/v1.1/trials.json)

`v1-delta.json` 还显示同一 rollout 重判后 38/113 题的绝对 pass-rate 变化至少 0.10，5 题大于 0.20。它不等于 v1.1 题目有问题——v1.1 本来就在修复判分——但建议把 `|delta| ≥ 0.10` 标为“scoring-sensitive”，在最终结果中做含/不含该组的敏感性分析，而不是盲目硬删。[官方 v1/v1.1 delta](https://deepswe.datacurve.ai/artifacts/v1.1/v1-delta.json) [v1.1 官方发布说明](https://deepswe.datacurve.ai/blog/deepswe-v1-1)

### 第 2 层：模型区分度过滤

建议同时要求三个指标：

1. **非极端难度**：base-model 等权平均 pass rate 在 `[0.20, 0.80]`；核心区可收紧到 `[0.30, 0.70]`。
2. **强弱端分离**：至少 3 个 base model 的 task pass rate `≤0.25`，且至少 3 个 `≥0.75`；核心区可用 4/4。
3. **正区分度**：task 的 config pass-rate 向量与各 config 的全榜总体能力做 item-rest correlation；去掉该 task 后计算总体能力，要求相关系数至少 `0.30`。这排除“弱模型反而稳定通过、强模型反而稳定失败”的强模型特异题。

还应计算：

- configuration 间方差（模型/effort 差异）；
- configuration 内平均二项方差（同 config 重复波动）；
- 区分信噪比：`between-config variance / (between + within variance)`。

优先选择“configuration 间差异大、同 configuration 重复较稳定”的题，而不是仅靠 pooled pass rate 接近 0.5。

基于当前哈希做的一次**探索性**计算（每个 base model 先选一个公开最佳 configuration，故有 post-hoc 偏差）得到：

- 覆盖 ≥17、均值 0.2–0.8、低端 ≥3、高端 ≥3：79 题；
- 均值 0.3–0.7、低端 ≥4、高端 ≥4：55 题；
- 再加 item-rest correlation ≥0.3：48 题。

这 48 题可以视为第一版 `model-core` 候选池的规模预期，但正式清单应改用“base model 内 effort 等权 + leave-target-model-out”重算，不能直接把探索性 48 题当最终 benchmark。

### 第 3 层：建立两个不同用途的池

#### A. `model-core`

目标是快速复现模型能力排序。使用第 0–2 层的严格条件，并按以下维度分层：

- 难度：0.20–0.40、0.40–0.60、0.60–0.80；
- 语言：Go 34、Python 34、TypeScript 35、JavaScript 5、Rust 5 的全量占比；
- 仓库：同一 repo 在小子集中最多 1 题，必要时最多 2 题；
- 静态规模：prompt 字符数、gold patch changed files/lines、F2P/P2P test 数量各按分位组平衡。

`tasks.json` 提供语言、仓库与 prompt 长度；gold patch 和 F2P/P2P 配置来自官方任务仓库。静态规模只用于同层候选间平衡，不应凌驾于区分度和稳定性。[官方任务索引](https://deepswe.datacurve.ai/artifacts/v1.1/tasks.json) [官方任务仓库](https://github.com/datacurve-ai/deep-swe/tree/e016041a6ccf8da29906afc9a3f5a8df940a1f78/tasks)

#### B. `agent-probe`

目标是比较不同 agent 在同一模型下的工作方式。官网没有不同 harness 的历史结果，所以不要声称该池已被公开数据验证。先从稳定、非极端题中按任务形态最大化多样性：

- 多文件/跨模块改动与局部修复；
- 不同语言与构建/test framework；
- 不同 gold patch 规模；
- 不同 F2P/P2P 比例；
- 不同 prompt 长度与 agent step/peak-context 压力。

然后用固定模型跑至少两个 agent、每题每 agent 4 次。只把出现稳定 agent 差异且无 verifier 异常的题升级到正式 `agent-core`；pilot 数据与最终确认数据必须分开。

### 第 4 层：小规模抽样与实验设计

第一轮建议 12–16 题，而不是一次定死 24 题：

- `model-core` 8–12 题：三个难度层近似等额；
- `agent-probe` 4 题：与 model-core 不重叠，最大化静态形态多样性；
- 每个 `(task, model/agent)` 跑 4 次，保持与官网重复数一致；
- 模型比较固定 agent；agent 比较固定模型、effort、预算、timeout 和网络策略；
- task 顺序随机化，保存固定随机种子；结果使用 task-paired 比较，并同时报告 pass rate、partial/F2P/P2P、成本、steps 和超时/排除数。

若第一轮能稳定重现预期排序，再按相同配额扩展到 24 或 32 题。最好预先生成互斥的 `dev` 与 `confirm` block：dev 用于调 runner、预算和阈值，confirm 只运行一次用于报告。

## 防止筛选泄漏与选择偏差

1. **Leave-target-model-out**：评估模型 M 时，筛选难度和区分度不使用 M 的 trial；更保守时连同同一 provider/model family 一并留出。
2. **不要把 effort 当独立模型**：先在 base-model 内汇总或分层，避免 5 档 effort 的家族获得五倍权重。
3. **mini-swe-agent 选择偏差**：公开数据全来自 mini-swe-agent。若比较它和另一个 agent，主确认池应只依赖静态分层或留出的模型结果；不能根据 mini-swe-agent 的具体 trajectory 失败模式挑题。
4. **冻结后再跑**：候选规则、清单、顺序、hash、随机种子、预算都应在目标模型/agent 运行前提交到 Git。
5. **区分开发与确认**：用一块任务调参数，再在互斥任务块上报告；不能在同一 12 题上反复调整 agent 后仍把它当无偏比较。
6. **公开解与训练污染**：任务、reference solution、模型 patch 和 trajectory 均公开。报告应说明目标模型发布日期/训练截止信息（如果提供），并把结果解释为当前公开 benchmark 上的系统表现，不宣称完全无污染的泛化能力。

## 建议下一步

先实现一个可复现的离线筛选脚本，输入固定的 `tasks.json`、`trials.json`、本地 task 元数据，输出：

- 每题 coverage/error/difficulty/discrimination/within-run variance；
- `model-core` 宽松池和严格池；
- `scoring-sensitive`、`infrastructure-sensitive` 标记；
- 两组互斥的 12–16 题抽样方案及 SHA-256。

在目标模型尚未参与筛选的前提下，优先使用 leave-target-model-out 版本；随后用同一个固定模型做不同 agent 的 4-repeat pilot，再决定哪些题能组成真正的 `agent-core`。
