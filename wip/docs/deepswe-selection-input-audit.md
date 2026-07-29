# DeepSWE v1.1 任务筛选输入核查

核查日期：2026-07-29（Asia/Shanghai）

## 结论

DeepSWE 官网公开的数据足以做第一阶段的“稳定性 + 难度 + 模型/配置区分度”筛选，并且可以冻结成可复现快照。当前 v1.1 快照有 113 个任务、22,586 个 rollout；其中 22,438 个进入计分，148 个因外部或基础设施错误被排除。

关键边界是：公开 rollout 的 `harness` 全部为 `mini-swe-agent`。因此它们直接证明的是“固定框架下，不同 model + reasoning effort 配置”的任务区分度，不能直接证明某题能够区分其他 agent 框架，更不能证明 coder-reviewer 协作带来的增益。把“框架 + 模型 + effort + 协作拓扑”作为一个完整 agent system（一个 treatment）来比较，不改变当前预筛选主线；只需把公开筛选结果视为候选池，再用实际 agent systems 的本地重复实验验证。

## 官方机器可读入口与快照哈希

官网的 [数据浏览页](https://deepswe.datacurve.ai/data/v1.1) 表示其展示每个 `(task, model)` rollout 的结果；首页同时明确说明[所有榜单模型统一运行在 mini-swe-agent 上](https://deepswe.datacurve.ai/)。本次直接读取以下官方 JSON，而不是从网页表格反向抓取：

| 文件 | SHA-256（本次核查） | 用途 |
| --- | --- | --- |
| [`tasks.json`](https://deepswe.datacurve.ai/artifacts/v1.1/tasks.json) | `bae967f6472943564c3fc5232fba3c8e0ac465c1be5ccf9dd4895d4ee9df6242` | 任务目录与静态元数据 |
| [`trials.json`](https://deepswe.datacurve.ai/artifacts/v1.1/trials.json) | `7844056bade4cee4a2c2964c9582bf7eb1344735a28695cae7d419055656417a` | 主筛选输入：逐次 rollout 结果与遥测 |
| [`leaderboard-live.json`](https://deepswe.datacurve.ai/artifacts/v1.1/leaderboard-live.json) | `d5fc4531d5b005c6e0040a82ddafe63225b1c172015cd499f2ec866f16f91cf1` | configuration 级汇总交叉核验 |
| [`release.json`](https://deepswe.datacurve.ai/artifacts/v1.1/release.json) | `0b77963ed8c54ef40c5f744ade178b54bfae2662ed94f9235cee85eb542bdc85` | trajectory、patch、log、verifier 文件 URL 模板 |
| [`v1-delta.json`](https://deepswe.datacurve.ai/artifacts/v1.1/v1-delta.json) | `f6b2c0ef38dd34a3361929e383caa5f8255151f3596d3391f5922531bf2d3f58` | 同一批共享 rollout 在 v1/v1.1 评分下的差异 |

这些 URL 指向可更新的线上资源，而不是内容寻址对象。后续脚本应读取本地快照、校验 SHA-256，并把输入哈希写入输出 manifest；官网内容变化时先人工审阅差异，不应静默重算并覆盖既有选集。

`leaderboard-live.json` 自带 `generated_at = 2026-07-25T03:13:49.273952+00:00`。`release.json` 只定义公开工件的 CloudFront base URL 和路径模板，不是完整实验 manifest，也没有生成时间。

## JSON 结构和关键字段

五个 JSON 的根节点都是对象，不是裸数组。筛选脚本必须显式读取 `rows` 或相应字段。

### `tasks.json`

顶层字段为 `scope`、`n_tasks`、`rows`。`n_tasks = 113`，每个 `rows[]` 包含：

- 身份与代码版本：`id`、`repository`、`repository_url`、`base_commit_hash`
- 展示信息：`problem_title`、`display_description`
- 分层信息：`language`、`prompt_characters`

当前快照覆盖 91 个仓库、5 种语言：TypeScript 35、Go 34、Python 34、JavaScript 5、Rust 5，和[官方方法说明](https://deepswe.datacurve.ai/blog/deepswe)一致。该文件不包含语义类别、reference patch 规模或 verifier node 数；如需这些静态特征，应从同一官方仓库的任务目录读取，并只用于平衡抽样或人工审计，不宜当作通过率区分度的替代品。

### `trials.json`

顶层字段为 `scope`、`n_trials`、`rows`。当前 `n_trials = len(rows) = 22,586`。行级字段可分为：

- rollout 身份：`trial_name`、`task_name`、`source`、`eval_scope`
- system 配置：`model`、`provider`、`harness`、`config`、`reasoning_effort`
- 结果：`reward`、`passed`、`errored`、`outcome`、`included_in_score`、`score_value`
- verifier 分项：`f2p_total`、`f2p_passed`、`f2p`、`p2p_total`、`p2p_passed`、`p2p`、`partial`
- 效率遥测：`cost_usd`、输入/缓存/输出 token、`peak_context_tokens`、`n_agent_steps`、agent/trial duration 和起止时间
- 错误诊断：`error_category`、`exception`
- 工件状态：`has_trajectory`、`has_model_patch`、`has_agent_log`、`has_verifier_output`、`verifier_files`、`critique`、`metrics_source`

虽然顶层 `scope` 的文字允许 DeepSWE 与 cross-benchmark 记录，当前 22,586 行全部满足 `source=deep-swe`、`eval_scope=full`、`harness=mini-swe-agent`。因此仍应在代码中显式过滤这些值，避免将来官方追加其他 scope 后改变分母。

### 其他三个文件

- `leaderboard-live.json`：`rows[]` 以 `harness + model + reasoning_effort` 的 `config` 汇总，提供 pass@1、pass@4、重复运行置信区间，以及成本、tokens、duration、steps。其 `unit` 明确：context-window failure 和 agent timeout 算失败；provider、verifier、network error 排除。适合交叉核验，不应替代逐 trial 计算。
- `v1-delta.json`：`configs[]` 和 `tasks[]` 给出 `v1`、`current`、`delta` 及各自分母。官方 `scope` 明确这是相同 rollout 的重新评分比较：v1 使用 exit-code，v1.1 使用 node-id。可作为“评分敏感”标签，而不应默认删除相关任务。
- `release.json`：定义 `trajectory`、`model_patch`、`agent_log`、`verifier_output`、`verifier_file` 路径模板。轨迹和 patch 适合后续抽样人工复核，但若用目标系统公开轨迹的失败类型来选题，会引入事后选择偏差。

## 当前快照的一致性检查

| 检查项 | 结果 |
| --- | ---: |
| 任务 / base model / config | 113 / 18 / 50 |
| 总 rollout | 22,586 |
| `included_in_score=true` 且 `errored=false` | 22,438 |
| 排除错误 | 148 |
| 计分 pass / fail | 11,551 / 10,887 |
| 唯一 `trial_name` | 22,586 |
| 未在 `tasks.json` 出现的 `task_name` | 0 |
| 同名 config 映射到多个 model/harness/effort | 0 |

148 个排除错误全部满足 `errored=true`、`included_in_score=false`，分类为：`model_routing_404` 73、`provider_timeout` 36、`verifier_timeout` 30、`unclassified_exception` 5、`upstream_provider_error` 3、`rate_limit` 1。不存在“已计分但 errored”或“未计分但未 errored”的记录。

以 `task × config` 为 cell，共 5,650 个 cell。原始重复数分布为：5,638 个 cell 有 4 次、11 个有 3 次、1 个只有 1 次；若仅保留计分 rollout，则 5,517 / 115 / 9 / 7 / 2 个 cell 分别有 4 / 3 / 2 / 1 / 0 次有效重复。因而“每个 config 至少 3 个有效重复”是有实际筛除作用的稳定性条件，不能只检查任务总 trial 数。

公开工件标志的可用数为：trajectory 22,585、model patch 22,585、agent log 22,586、verifier output 22,555。部分遥测也允许缺失：F2P/P2P/partial 各缺 31，cost 和 peak context 各缺 93，steps 缺 1。脚本不能把这些可空字段无条件转换为数字；稳定性主筛选应依赖 outcome/include/error，分项测试数优先从任务 verifier 配置读取。

`v1-delta.json` 中有 38/113 个任务满足 `abs(delta) >= 0.10`，5 个满足 `abs(delta) > 0.20`；10 个共享 config 均没有达到 `abs(delta) >= 0.10`。这说明评分变化整体不大，但个别题很敏感，适合在最终报告中单列敏感性分析。

## 适合落成脚本的逐层口径

建议每层都保留全部派生指标、`passed_layer_*` 布尔值和明确的排除原因；后层只在前层结果上继续筛选。

1. **L0：冻结与完整性。** 校验五个输入哈希；断言 task ID、trial ID 唯一且 join 完整；主分析只取 `source=deep-swe`、`eval_scope=full`。计分分母只取 `included_in_score=true && errored=false`，但所有排除行仍进入 task 错误率与 verifier-timeout 统计。
2. **L1：运行稳定性。** 建议要求至少覆盖 17/18 个 base model、每个纳入分析的 config 至少 3 个有效重复、task 总错误率不高于 5%、verifier timeout 不超过 1 次。保留每条条件的独立失败原因。
3. **L2：宽区分池。** task 平均通过率位于 `[0.20, 0.80]`；至少 3 个 base model 的通过率 `<= 0.25`，且至少 3 个 `>= 0.75`。同时检查 config 等权与 base-model 等权平均值。
4. **L3：核心区分池。** 将平均通过率收紧到 `[0.30, 0.70]`，强弱端数量收紧到至少 4/4，并要求 config 级 item-rest correlation `>= 0.30`。item-rest 应将当前题排除后计算每个 config 的其余题能力，避免机械的 part-whole correlation。
5. **L4：排序而非再硬删。** 优先高 item-rest correlation、高 config 间方差、低重复噪声、难度接近 0.5 的题；`abs(v1.1-v1 delta) >= 0.10` 只标记，不自动删除。若计算“signal ratio”，重复噪声应使用 cell 均值的估计方差（约 `p(1-p)/n`）或直接从 0/1 重复观测估计，而不是未除以重复数的单次 Bernoulli 方差。
6. **L5：平衡抽样与冻结。** 按语言、仓库、难度带、reference patch 规模平衡；小样本中优先一个仓库一题。固定 seed，输出互斥的 dev/confirm 两组，以及完整 manifest。dev 用于接通 agent 和调整运行参数；confirm 列表、阈值、预算和重复数在观察目标系统结果前冻结。

当前 50 个 config 并非对 18 个 base model 均匀采样：多个新模型有 5 档 effort，部分模型只有 1 档。因此：

- config 等权视图最接近“`mini-swe-agent + model + effort` 是一个完整系统”的定义；
- base-model 等权视图防止某些模型因为有 5 档 effort 而在选题时获得 5 倍权重；
- 最稳妥的硬筛选要求两种口径都满足，并在输出中同时保留两套指标；
- 若后续目标系统使用了公开数据中的同一模型，增加 leave-target-model-out 或 leave-family-out 敏感性检查，可降低针对已知目标表现选题的风险。

## 对完整 agent system 与 collab agent 评测的影响

用户后续把单 agent（框架 + 模型）和 collab agent（coder + reviewer + 编排方式）各自视为一个整体 treatment，这会简化实验解释：若目标只是回答“哪个完整系统效果更好”，不必强行做模型效应与框架效应的全因子拆解。每个 system 只需在相同 task、版本、预算规则、timeout 和重复策略下做配对比较。

但公开数据不能跨越以下边界：

- 它可以证明题目在固定 `mini-swe-agent` 下具有模型/effort 区分度；
- 它不能证明题目对 Codex CLI、Claude Code、自研框架等 scaffold 有区分度；
- 它没有 coder-reviewer 协作 rollout，无法直接估计 review、返工、通信或角色分工收益；
- mini-swe-agent 的 cost、steps、tokens 不应作为其他框架或 collab 的硬筛选条件，因为协作本身会系统性改变这些量。

因此当前方案无需推倒重来，但结论措辞应是“公开数据支持的高区分度候选池”。先在 dev 块上以实际候选 systems 做同题重复试跑，检查框架/协作之间是否有足够的 task-level variance 和可接受的基础设施错误；随后保持 confirm 块不变做确认。若根据 dev 结果新增“agent-probe”题，应另建补充池并预先登记规则，不能在看过 confirm 结果后追选最有利的题。

## 官方来源

- [DeepSWE 首页与当前 leaderboard](https://deepswe.datacurve.ai/)
- [DeepSWE v1.1 数据浏览页](https://deepswe.datacurve.ai/data/v1.1)
- [DeepSWE 官方方法、质量控制与 mini-swe-agent 说明](https://deepswe.datacurve.ai/blog/deepswe)
- [DeepSWE 官方 GitHub 仓库](https://github.com/datacurve-ai/deep-swe)
- 上表列出的五个官方 v1.1 JSON 端点
