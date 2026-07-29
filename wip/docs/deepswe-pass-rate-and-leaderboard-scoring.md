# DeepSWE v1.1 通过率与榜单计分口径核查

核查日期：2026-07-29。本文只使用 DeepSWE 官方网页、官网发布的前端 JavaScript 和官网 JSON 工件。复算所用本地快照为 `wip/data/official-v1.1/`；其中 `trials.json` SHA-256 为 `7844056bade4cee4a2c2964c9582bf7eb1344735a28695cae7d419055656417a`，`leaderboard-live.json` 为 `d5fc4531d5b005c6e0040a82ddafe63225b1c172015cd499f2ec866f16f91cf1`，后者 `generated_at` 为 `2026-07-25T03:13:49.273952+00:00`。

## 结论

1. 数据页默认的 task × model-effort 单元格通过率为：

   ```text
   n_errors = count(errored && !passed)
   pass_rate = n_passed / (n_trials - n_errors)
   ```

   也就是 errored rollout 会显示在 `Trials` 和 `Errors` 计数里，但不进入通过率分母。当前官方快照中所有 `errored=true` 行也都恰好满足 `passed=false`、`included_in_score=false`，所以该前端公式在当前数据上等价于 `passed / included_in_score`。这是当前数据不变量，不应把它误写成前端直接读取了 `included_in_score`。[官方数据页](https://deepswe.datacurve.ai/data/v1.1) [官方数据页前端 bundle](https://deepswe.datacurve.ai/assets/index-BShjC0cc.js) [官方逐 trial 数据](https://deepswe.datacurve.ai/artifacts/v1.1/trials.json)

2. `leaderboard-live.json` 的自描述 `unit` 已明确定义：

   ```text
   pass@1 = n_passed / n_attempted
   pass@4 = n_tasks_passed_any / n_tasks_attempted
   ```

   `n_attempted` 是计分 rollout 数，不是固定的 `113 × 4 = 452`；`n_tasks_attempted` 是至少有一次计分 rollout 的 task 数，也不一定是 113。这里的 `pass@4` 是“每 task 最多四次公开 rollout 中至少一次通过”的任务比例，不是从单次成功率套用组合公式得到的估计量。[官方实时榜单 JSON](https://deepswe.datacurve.ai/artifacts/v1.1/leaderboard-live.json)

3. 错误规则是：context-window failure 与 agent timeout 作为计分失败；provider、verifier、network 类错误从分母排除。当前 `trials.json` 中 `context_window_exceeded` 42 条和 `agent_timeout` 93 条均为 `included_in_score=true`；后者有 89 条失败、4 条最终通过。148 条排除行均为 `errored=true`、`included_in_score=false`，类别为 `model_routing_404`、`provider_timeout`、`verifier_timeout`、`unclassified_exception`、`upstream_provider_error` 或 `rate_limit`。[官方实时榜单 JSON](https://deepswe.datacurve.ai/artifacts/v1.1/leaderboard-live.json) [官方逐 trial 数据](https://deepswe.datacurve.ai/artifacts/v1.1/trials.json)

4. JSON 没有 `rank` 或独立的 `score` 字段。官网把 `row.pass_rate` 作为图中纵轴的 “DeepSWE score”，配置行按 `pass_rate` 降序；榜单表显示的百分比由 `ci_passed / ci_attempted` 计算，当前 50 行的这两个字段分别都等于 `n_passed`、`n_attempted`，且 `pass_rate == pass_at_1`。因此当前榜单 score 就是上述 pooled attempt pass@1。[官方榜单前端 bundle](https://deepswe.datacurve.ai/assets/live-leaderboard-2Apwhl2l.js) [官方实时榜单 JSON](https://deepswe.datacurve.ai/artifacts/v1.1/leaderboard-live.json)

5. 官网榜单默认的 `Best` 视图有一个重要细节：它不是为每个模型选择观测 `pass_rate` 最大的 effort，而是按 `none < minimal < low < medium < high < xhigh < max` 选择最高可用 reasoning effort，然后再按该配置的 `pass_rate` 降序。切换到 `All effort levels` 才会展示并排序所有配置。故若要复刻官网默认模型榜单，不能简单对每个模型做 `argmax(pass_rate)`。[官方榜单前端 bundle](https://deepswe.datacurve.ai/assets/live-leaderboard-2Apwhl2l.js)

## 数据页 task/config 单元格

默认轴是 task × model effort，`model effort` 的键由 `model + reasoning_effort` 构成；选择 `Base model` 后会把同一模型所有 effort 的逐 trial 结果合并计算，而不是先算各 effort 通过率再平均。行、列汇总也都是先加总 `n_passed` 与有效分母再相除，即微平均。[官方数据页前端 bundle](https://deepswe.datacurve.ai/assets/index-BShjC0cc.js)

`Show` 选项的行为如下：

- `All trials`（默认）：保留全部行，计数 errors，但从通过率分母扣除 `errored && !passed`。
- `Exclude errored`：聚合前过滤所有 `errored` 行；当前快照得到的通过率与默认模式相同，但 trial/error 展示计数不同。
- `Only passed`：聚合前只保留 `passed` 行，因此非空单元格的通过率必为 100%；它是结果浏览过滤器，不是正式计分视图。

两个带排除错误的单元格复算：

| task | config | 原始 trials | 通过 | 排除错误 | 有效分母 | 页面通过率 |
|---|---|---:|---:|---:|---:|---:|
| `awilix-async-container-initialization` | `mini_swe_agent_claude_fable_5_high` | 4 | 1 | 1 (`model_routing_404`) | 3 | `1/3 = 33.33%`（页面整数显示 33%） |
| `pwntools-tube-multiplexing` | `mini_swe_agent_claude_opus_5_max` | 4 | 2 | 2 (`verifier_timeout`) | 2 | `2/2 = 100%` |

这也验证了不能用 `passed / raw trial rows` 复刻热力图。

## 榜单 pass@1 / pass@4 复算

### 示例 A：Claude Opus 5 / max

`trials.json` 中该 config 有 449 条原始记录：444 条计分、5 条排除错误（4 个 `verifier_timeout`、1 个 `unclassified_exception`），另有 3 个相对于 113 × 4 的缺失 rollout。计分记录中 327 条通过；113 个 task 至少有一次计分尝试，其中 100 个至少通过一次。

```text
pass@1 = 327 / 444 = 0.7364864864864865
pass@4 = 100 / 113 = 0.8849557522123894
```

与 `leaderboard-live.json` 的 `n_passed=327`、`n_attempted=444`、`n_tasks_passed_any=100`、`n_tasks_attempted=113` 及两项比率完全一致。

### 示例 B：Claude Opus 4.8 / max

该 config 有 452 条原始记录：429 条计分、23 条排除错误（21 个 `provider_timeout`、2 个 `upstream_provider_error`）。只有 111 个 task 留有至少一次计分尝试，其中 88 个至少通过一次；`ofetch-per-origin-circuit-breaker` 与 `superjson-error-stack-serialization` 没有计分尝试，因而不进入 pass@4 分母。

```text
pass@1 = 253 / 429 = 0.5897435897435898
pass@4 = 88 / 111 = 0.7927927927927928
```

同样与官方榜单行完全一致。特别是 pass@4 不能写成 `88/113`。

## 对筛选脚本的直接含义

- 主计分输入继续使用 `source=deep-swe`、`eval_scope=full`、`included_in_score=true`；为防数据异常，最好同时断言 `errored=false`。这与当前官方榜单分母一致。
- task/config 通过率应由逐 trial 的计分行复算，不要用原始行数作分母，也不要把缺失 rollout 补成失败。
- 若以官网 leaderboard 交叉核验，配置级校验应同时检查四个计数：`n_passed`、`n_attempted`、`n_tasks_passed_any`、`n_tasks_attempted`，再比较 pass@1/pass@4。
- 用公开数据做 task 区分度时，task 的 pass rate 是有效 attempts 的微平均。后续把“框架 + 模型”作为整体 agent 时可以沿用同一计分口径；collab agent 也应作为一个新 config 独立重复运行。这个评测定义不会改变当前的 task 筛选原则，但正式对比时不要借用官网默认 `Best` 的最高-effort选择规则，应预先固定每个整体 agent 的配置。

## 官方一手来源

- [DeepSWE v1.1 数据页](https://deepswe.datacurve.ai/data/v1.1)
- [数据页当前官方前端 bundle](https://deepswe.datacurve.ai/assets/index-BShjC0cc.js)
- [榜单当前官方前端 bundle](https://deepswe.datacurve.ai/assets/live-leaderboard-2Apwhl2l.js)
- [官方 trials.json](https://deepswe.datacurve.ai/artifacts/v1.1/trials.json)
- [官方 leaderboard-live.json](https://deepswe.datacurve.ai/artifacts/v1.1/leaderboard-live.json)

注：带内容哈希的前端 bundle URL 会随官网重新部署变化；公式的长期可复核基准应以冻结的 JSON 哈希和本文记录的当前 bundle 为准。
