# DeepSWE v1.1：单任务执行流程与多任务指标

核查日期：2026-07-29。依据 DeepSWE 当前仓库、Pier 0.3.0 源码及官网 v1.1 artifacts。

## 三个统计层级

- **trial / rollout**：一个 config 对一个 task 的一次独立尝试。
- **cell**：同一 `(task, config)` 的若干重复 trial；官方计划为 4 次。
- **evaluation round / job**：同一 config 在 N 个 task、每题 R 次上的全部 `N × R` 个 trial。

DeepSWE 官网的 config 是 `harness + model + reasoning_effort`。本地比较完整 agent system 时，应进一步冻结并记录 agent 版本、coder/reviewer 模型、编排、预算、timeout、网络和工具设置。

## 一个 trial 的完整流程

1. Pier 读取 `task.toml`、`instruction.md`、基础镜像、资源和 timeout。agent 只能看到任务说明与工作仓库，不会获得 `solution/` 和隐藏 verifier 内容。
2. Pier 启动 agent 环境，仓库位于 `/app` 且处于指定 base commit。agent 调用模型、查看和修改代码、运行可用测试并提交最终工作。
3. agent 结束后，Pier 在 agent 环境执行 `pre_artifacts.sh`。DeepSWE 用 `git diff --binary BASE_COMMIT HEAD` 生成 `/logs/artifacts/model.patch`，因此只有进入最终 `HEAD` 的提交会被评分；未提交修改不会进入 patch。
4. Pier 收集 agent log、trajectory 与 `model.patch`。v1.1 使用 `environment_mode=separate`，随后停止 agent 环境并启动独立 verifier 环境。
5. verifier 从干净 base state 开始，应用 `model.patch`；patch 缺失等价于 base state，patch 无法应用得到 `reward=0` 和 `apply_failed=1`。之后 verifier 应用隐藏 `tests/test.patch`。
6. task 的 `tests/test.sh` 运行测试套件并生成 CTRF 或 JUnit 报告；`grader.py` 只读取 `config.json` 白名单中的 F2P/P2P node。缺失、skipped 和失败 node 都不算通过，重复 node 使用最坏状态。
7. 二元 reward 为 1 的条件是：F2P 非空、全部 F2P 通过、全部 P2P 通过。否则 reward 为 0；partial 只用于诊断，不改变主 reward。
8. Pier 下载 verifier 输出并写出 trial result、异常、耗时、tokens、成本、steps 以及 artifact 可用性。

来源：[DeepSWE README](https://github.com/datacurve-ai/deep-swe/blob/e016041a6ccf8da29906afc9a3f5a8df940a1f78/README.md)、本仓库 `pre_artifacts.sh`、`tests/grader.py`，以及 [Pier 0.3.0](https://github.com/datacurve-ai/pier/tree/v0.3.0)。

## 单个 trial 的结果指标

### 身份与配置

`trial_name`、`task_name`、`source`、`model`、`provider`、`harness`、`config`、`reasoning_effort`。它们回答“谁在什么任务上、以什么配置运行”。

### 主结果和异常

- `reward` / `score_value`：0 或 1，主排名分数。
- `passed`：reward 是否为 1。
- `outcome`：pass、普通 fail、timeout 等结果分类。
- `errored`：是否发生 provider/verifier/network 等外部或基础设施异常，不应与正常解题失败混为一谈。
- `included_in_score`：官网公平性过滤后的分母标志；复刻官网分数时以它为准。
- `error_category`、`exception`：异常类别与详情。

### verifier 分项

- `f2p_total/passed`、`f2p`：新增需求对应的 fail-to-pass 测试通过情况，体现功能完成度。
- `p2p_total/passed`、`p2p`：原来应通过的回归测试保留情况。
- `partial = (f2p_passed + p2p_passed) / (f2p_total + p2p_total)`：所有白名单 node 的通过比例。

`partial=0.95` 仍可能是 `reward=0`，因为主 reward 要求所有 F2P/P2P 都通过。不同 task 的 node 数差异很大，跨题直接把 node 汇总会让测试多的 task 获得更大权重。

### 效率和过程

`cost_usd`，input/cache/output tokens，`peak_context_tokens`，`n_agent_steps`，agent/trial duration，以及起止时间。成本和 tokens 用于预算效率；steps 受框架定义影响；peak context 反映上下文压力；agent duration 更接近解题时间，trial duration 还包含环境和 verifier 开销。

### 可审计工件

`model.patch`、trajectory、agent log、`reward.json`、`ctrf.json`、`test-stdout.txt`、`run.log` 和框架原生 reports。它们用于解释失败、复查评分和诊断基础设施问题，不是额外得分项。

## 一个 config 处理 N=10 个 task

设每题重复 R 次，则计划 trial 数为 `10 × R`。

### R=1：一次 10 题小跑

产生 10 个 trial。应至少汇总：

- `n_planned=10`、`n_completed`、`n_attempted`、`n_excluded_errors`、错误类别与 coverage；
- `n_passed`、`n_failed`；
- DeepSWE 口径 `Pass@1 = n_passed / n_attempted`；
- reward/F2P/P2P/partial 的 task 等权均值或分布；
- total/mean/median cost、tokens、steps、agent/trial duration；
- 每题明细和 artifact 链接。

只有一次尝试时没有可解释的 Pass@4，也无法估计同一 system 的随机波动。Pier 默认 Mean metric 会把没有 reward 的异常 trial 当 0；官网 leaderboard 则排除指定外部错误。因此正式报告宜同时保存 raw job mean 和按预注册错误策略得到的 scored Pass@1。

例：10 题中 6 pass、3 正常 fail、1 provider error。官网式分数为 `6/9=66.7%`，同时报告 coverage `9/10` 和 excluded error `1`；不能只报 `6/10=60%` 而隐藏错误性质。

### R=4：对齐官网重复策略

计划 40 个 trial。除上述指标外，还可得到：

- 每题 cell pass rate：`p_t = passed_t / attempted_t`；
- pooled Pass@1：`sum_t passed_t / sum_t attempted_t`；
- 官网式 Pass@4：`至少一次通过的 task 数 / 至少一次有效尝试的 task 数`；
- 每题重复稳定性、全过/全败/混合的 task 数；
- 四个 whole-round pass rate 及 run-to-run 标准误/置信区间；
- task-paired 的 config 差值，适合比较两个 agent systems。

官网 Pass@4 是经验 any-pass 比例。Pier 通用 pass@k 使用 `1 - C(n-c,k)/C(n,k)` 后再对 task 平均；当每题恰好 `n=k=4` 时，两者都退化为“只要四次中至少一次通过就是 1”，但在运行数大于 4、缺失或异常处理不同时不可混用。

## 推荐的 10 题报告结构

主表报告 correctness、coverage/error 和 efficiency 三组，不用 partial 替代 pass：

```text
planned / scored / excluded errors
n_passed / Pass@1 / （R=4 时）Pass@4
macro F2P / macro P2P / macro partial
total cost + median cost/task
total tokens + median output tokens/task
median steps / peak context / agent duration
```

另附 10 题逐题表。比较不同完整 agent systems 时，在相同 task、R、预算、timeout 和错误规则下做 task-paired 比较；collab system 的 coder、reviewer 和编排总成本全部计入同一个 trial。

## 官方数据来源

- [trials.json](https://deepswe.datacurve.ai/artifacts/v1.1/trials.json)
- [leaderboard-live.json](https://deepswe.datacurve.ai/artifacts/v1.1/leaderboard-live.json)
- [DeepSWE v1.1 数据页](https://deepswe.datacurve.ai/data/v1.1)
