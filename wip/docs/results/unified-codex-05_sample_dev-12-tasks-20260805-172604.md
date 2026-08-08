# unified-codex-05_sample_dev-12-tasks-20260805-172604 结果分析

分析日期：2026-08-05。

原始工件：

- [job result](../../../jobs/unified-codex-05_sample_dev-12-tasks-20260805-172604/result.json)
- [job config](../../../jobs/unified-codex-05_sample_dev-12-tasks-20260805-172604/config.json)
- [run manifest](../../../jobs/.agent-eval-manifests/unified-codex-05_sample_dev-12-tasks-20260805-172604.json)
- [全部 trial](../../../jobs/unified-codex-05_sample_dev-12-tasks-20260805-172604/)

## 结论

本次 job 调用了 canonical `05_sample_dev.txt` 的全部 12 个任务，每题两次，共 24 个 trial。24 个 Agent workflow 均正常完成并记录为 `outcome=completed`、`deliverable=true`，没有 Pier exception、retry、watchdog timeout、provider/network 异常或空 patch。

但两个 `skrub-duration-encoding` verifier 都在 pytest 启动阶段因 Polars 原生段错误退出，没有运行任何测试。grader 把 2,914 个缺失 node 全部机械记为失败，Pier 因为仍生成了 `reward.json` 而把它们当作普通 reward 0。综合 Agent 和 verifier 工件，这两个 trial 应归类为 verifier/task-environment invalid，而不是模型零分。

- Pier raw Trial-level Pass@1：`11 / 24 = 45.83%`。
- 排除两个 Skrub verifier-invalid trial：`11 / 22 = 50.00%`。
- 机械保留 Skrub 两个零分时，12 题 task-level any-pass 为 `7 / 12 = 58.33%`；该口径错误地把未评分任务当成两次失败，不建议作为正式 pass@2。
- 有有效评分的 11 个任务中，7 个至少一次通过：`7 / 11 = 63.64%`；canonical task coverage 为 `11 / 12 = 91.67%`，因此不能给出完整 12 题的有效 task-level pass@2。
- 4 个有效任务两次均通过：`adaptix-name-mapping-aliases`、`pebble-durability-wait-apis`、`sqlite-utils-safe-import-checkpoints`、`valibot-recursive-schema-composition`。
- 3 个任务一过一败：`mnamer-daemon-watch-lifecycle`、`scriggo-method-declarations`、`tengo-destructuring-bindings`。
- 4 个有效任务两次均失败：`anko-typed-variable-bindings`、`bandit-incremental-cache-control`、`dasel-html-document-format`、`obsidian-linter-scoped-ignore-markers`。Skrub 单独标为未评分。

按 [DeepSWE 计分口径核查](../deepswe-pass-rate-and-leaderboard-scoring.md)，verifier/task image 的原生崩溃应从有效分母排除。正式引用本 job 时应同时报告 Pier raw、有效 trial 口径和 task coverage，不能只引用 `45.83%` 或 `7/12`。

## 运行配置

| 项目 | 值 |
|---|---|
| 开始时间 | 2026-08-05 17:26:22 CST |
| 结束时间 | 2026-08-05 21:44:22 CST |
| 总 wall-clock | 约 4 小时 18 分钟 |
| Pier | `0.3.0` |
| Canonical 任务数 | 12 |
| 每任务 trials | 2 |
| 总 trials | 24 |
| 并发 | 2 |
| Workflow | `single / single / direct` |
| Agent adapter | Codex，benchmark mode，permissions bypass |
| 模型 | `gpt-5.6-luna`，effort `xhigh` |
| Reviewer | 无 |
| Runtime | `deep-swe/agent-runtime:12129eb84c44eb9d` |
| Runtime digest | `12129eb84c44eb9d0f90ae8ae9c999c439b132e37c5ed92c0be5c946bd58b708` |
| Runtime image ID | `sha256:854a1eedc3d79fdff96bc1bd848b9d4a0015af381cd886f1ac2e3da1771f1e89` |
| Runtime platform | `linux/amd64`，manifest 匹配 |
| Task hard timeout | 5400 秒 |
| Workflow soft deadline | 5100 秒，cleanup reserve 300 秒 |
| Event-silence watchdog | 900 秒 |
| 每个 turn 内 Agent 尝试 | 最多 2 次 |
| Review 上限 | 0 |
| Agent network | provider-only：`api.openai.com`、`auth.openai.com`、`chatgpt.com` |
| Git commit | `97d0241ce9ec4aab0359928ef085da6fb0088c32`，dirty worktree |

Run manifest 中的 dirty 状态包括 `05_sample_dev.txt` 及其 `.bk` 的修改，以及当时未跟踪的上一份 dev 结果分析文档。Job config、manifest 与实际执行目录都包含相同的 12 个任务，没有上一轮 OpenCode job 的缺题问题。

## 汇总指标

| 指标 | Pier raw 24 trials | 排除 2 个 Skrub invalid trials |
|---|---:|---:|
| Reward | 11/24（45.83%） | 11/22（50.00%） |
| Task-level any-pass | 7/12（58.33%，机械口径） | 7/11（63.64%），coverage 11/12 |
| Macro F2P | 88.10% | 96.11% |
| Macro P2P | 91.66% | 99.99% |
| Macro partial | 91.29% | 99.59% |

两个全零 Skrub trial 显著拉低了 raw macro 指标，尤其 P2P 从有效 trial 的 99.99% 降至 91.66%。这进一步说明 raw macro 不是本次模型回归程度的可靠描述。

| 资源指标 | 值 |
|---|---:|
| Agent 执行时间合计 | 约 7 小时 35 分钟 |
| 平均 / 中位 Agent 时间 | 18 分 58 秒 / 14 分 44 秒 |
| 平均 / 中位 trial 时间 | 20 分 27 秒 / 15 分 54 秒 |
| Verifier 时间合计 | 约 30 分 30 秒 |
| 记录的总 input / cache / output tokens | 243,433,147 / 0 / 1,091,680 |
| 平均 / 中位 input tokens | 10,143,048 / 6,307,947 |
| 平均 / 中位 output tokens | 45,487 / 39,366 |
| 记录的 cost | 无（`null`） |

F2P、P2P 和 partial 是 Pier 对 trial 的等权均值，不是汇总所有 node 后的 micro average。Unified Codex wrapper 将每个 trial 记录为一个 modifier turn，因此 `n_agent_steps=1`、`toolUses=0` 不表示 Agent 没有使用工具，也不能与 OpenCode 原生 steps 直接比较。Input token 未记录 cache token，cost 为空；usage 只适合本 job 内诊断。

## Task 级结果

下表只依据 verifier 工件；Skrub 显示 Pier 写入的 raw reward，但不把它解释为有效解题失败。

| Task | Trial 1 | Trial 2 | 有效 any-pass |
|---|---|---|---:|
| `tengo-destructuring-bindings` | `2mxyJTH`: 0，F2P 88/91，P2P 132/132，98.65% | `DWMQZpE`: 1，91/91，132/132 | 1 |
| `valibot-recursive-schema-composition` | `7ESHAkw`: 1，10/10，209/209 | `XLZ9Tsa`: 1，10/10，209/209 | 1 |
| `sqlite-utils-safe-import-checkpoints` | `SxSURYX`: 1，60/60，1038/1038 | `63BJCdH`: 1，60/60，1038/1038 | 1 |
| `pebble-durability-wait-apis` | `ZvGmaXZ`: 1，59/59，44/44 | `sshcwgU`: 1，59/59，44/44 | 1 |
| `bandit-incremental-cache-control` | `UCiowre`: 0，87/88，275/275，99.72% | `qtuejnD`: 0，87/88，275/275，99.72% | 0 |
| `scriggo-method-declarations` | `SvCJG2B`: 1，48/48，1049/1049 | `R6HGyYk`: 0，46/48，1049/1049，99.82% | 1 |
| `adaptix-name-mapping-aliases` | `r7J9mm3`: 1，44/44，2738/2738 | `KJVF6pR`: 1，44/44，2738/2738 | 1 |
| `anko-typed-variable-bindings` | `V6hLdF3`: 0，5/9，94/94，96.12% | `dUSR4VY`: 0，7/9，94/94，98.06% | 0 |
| `mnamer-daemon-watch-lifecycle` | `72DMRtj`: 1，51/51，319/319 | `WQeE8Aj`: 0，50/51，319/319，99.73% | 1 |
| `skrub-duration-encoding` | `32eb5o6`: verifier segfault，raw 0，0/130，0/2784 | `zDh6uft`: verifier segfault，raw 0，0/130，0/2784 | 未评分 |
| `obsidian-linter-scoped-ignore-markers` | `fUKS2TA`: 0，33/33，1132/1133，99.91% | `zxeNkgC`: 0，32/33，1132/1133，99.83% | 0 |
| `dasel-html-document-format` | `wKRK7FB`: 0，144/146，1012/1012，99.83% | `YjNoNuA`: 0，142/146，1012/1012，99.65% | 0 |

## Skrub verifier-invalid 事件

两个 Skrub trial 的证据高度一致：

1. 两个 Agent 都在任务容器内发现 pytest 在 Polars setup/import 路径发生 segmentation fault。`32eb5o6` 还记录了最小 Polars duration API 调用同样崩溃，但 pandas 定向验证以及 21 个 focused tests/doctests 能通过；`zDh6uft` 也只能完成 pandas 路径验证。
2. Separate verifier 应用各自非空 patch 和隐藏测试后，`/app/test.sh base` 与 `/app/test.sh new` 都直接以 `Segmentation fault` 退出，没有生成 base/new JUnit XML，也没有任何真实测试结果。
3. 两次 verifier 分别只运行约 26 秒和 28 秒。Grader 随后把 manifest 中全部 2,784 个 P2P 与 130 个 F2P 标成 `missing from report`，得到 0/2914；它没有记录实际失败断言。
4. Pier 看到 grader 正常写出的 `reward.json`，因此 `n_errors=0`、两个 reward 都为 0。这说明当前错误提升边界存在缺口：test runner 的 native crash 和报告全缺失没有升级为 verifier exception。

这里不能根据 patch 功能是否完整来恢复一个估计分数；正确处理是把两次 trial 标为 unscored，并在修复 task image 的 Polars 运行环境后建立独立补充 job。原地 resume 会删除现有诊断目录，不建议执行。

后记（2026-08-08）：复查确认崩溃是宿主机环境问题——Apple Silicon 上 Docker Desktop 以 Rosetta 模拟 linux/amd64 时，polars 主线 x86_64 wheel 在特定 SIMD 路径原生段错误（全部 6 个本地 job 的 13 个 skrub trial 同签名失败，官方 x86_64 基础设施正常）。权衡修复成本与可比性后，决定不修复镜像，将 `skrub-duration-encoding` 从 sample-dev 运行清单移除（12 题 → 11 题），任务定义保持原样。详见 [wip/data/README.md](../../data/README.md) 的「本机运行排除」一节；本文建议 2 中的"修复后补充 job"路径不再执行。

## 有效失败分布与稳定性

排除两个 Skrub invalid trial 后，有 11 个有效失败 trial：

- 9 个完整保留 P2P；其中 7 个只差不超过 3 个 F2P，是二元 reward 下的明确近失。
- 两个 Obsidian trial 都回归同一个 P2P，说明 scoped marker 实现稳定地破坏了 indented code block 的既有行为。
- Bandit 两次都只差同一个 F2P，属于本批最清晰的稳定近失。
- Anko、Bandit、Obsidian、Dasel 两次均未通过；Tengo、Scriggo、Mnamer 一过一败，仍表现出明显采样方差。
- 24 个 trial 都生成非空 patch，合计 199 次文件触达、16,780 行新增、2,030 行删除。失败不是未交付导致，而是实现遗漏、行为回归或 Skrub 环境失效。

## 四个有效的两次均失败任务

### 1. anko-typed-variable-bindings

两个 trial 都保留 94/94 P2P，但分别只通过 5/9 和 7/9 F2P。两者都没有稳定阻止明显的 typed declaration/type-mismatch，例如 `var x: int64 = "hello"`、`var s: string = 10` 和多变量声明中混入错误类型。

`V6hLdF3` 还在后续 assignment、if/else 控制流、错误返回值必须为 `nil` 等路径失效；`dUSR4VY` 已覆盖更多赋值流程，但多值/解构声明仍绕过约束。共同失败说明类型约束没有被绑定到所有 declaration/assignment 执行路径。

### 2. bandit-incremental-cache-control

两个 trial 都得到完全相同的 87/88 F2P、275/275 P2P，只失败 `TestCacheFileSizeStats.test_cache_stats_shows_cache_file_size_bytes`。`--cache-stats` 输出缺少规范要求的 `cache_file_size_bytes` 字段。

这是稳定、可复现且修复面很小的近失；其余 incremental cache、warm/import/export/prune 等测试均已通过。

### 3. obsidian-linter-scoped-ignore-markers

`fUKS2TA` 通过全部 33 个 F2P，`zxeNkgC` 通过 32/33，但两者都失败同一个 P2P：indented code block 内的 marker 应被忽略，代码块内 bare URL 也应保持不变，实际却被改写成 `<http://...>`。

`zxeNkgC` 还失败 nested scoped disables：关闭内层另一个 rule 后，外层 `no-bare-urls` disable 没有恢复生效。这里不能用接近 100% 的 F2P 覆盖替代 reward；共同 P2P 回归证明新功能与既有 code-block 保护边界不兼容。

### 4. dasel-html-document-format

两个 trial 都保留 1012/1012 P2P，但失败侧不同：

- `wKRK7FB` 只漏一个实际场景（CTRF 同时记录 parent/subtest 两个 node）：遇到 `table` 时应隐式关闭开放的 `p`，但 `p` 中的 `Intro` 文本被丢失。
- `YjNoNuA` 漏两个实际场景：嵌套列表中隐式 `li` 关闭产生 3 个而不是 2 个外层 `li`；writer 无法把同名元素 slice 写成多个 `<p>`。

两次都非常接近通过，但没有出现共同失败节点，说明 HTML reader/writer 的不同边界会随实现路径变化。

## 一过一败任务的失败侧

- Tengo `2mxyJTH`：失败 3 个 deeply nested/default F2P。缺失的外层数组项或 map default 进入嵌套 pattern 时，被当作 `int`/`string` 继续索引并报 `not indexable`，没有按规范懒惰应用 default。
- Scriggo `R6HGyYk`：失败 `method on bool defined type`，运行时对 bool receiver 调用了 `reflect.Value.Int` 并 panic；同题另一 trial 全过。
- Mnamer `WQeE8Aj`：只失败 `--batch-size 0`。规范要求本轮不处理文件，实际源文件已被移动，说明零值被错误解释为“不限量”而非零配额。

## 与上一份 sample-dev job 的对照

[opencode-deepseek-v4-flash-05_sample_dev-20260803-205511](opencode-deepseek-v4-flash-05_sample_dev-20260803-205511.md) 当前结果树只有 11 个任务、22 个 trial，缺少 Skrub；它还经历过按异常类型原地 resume，6 个原 trial 被替换，当前 3 个异常中需要排除两个外部提前终止、保留一个真实 Agent timeout。因此它不是干净的预注册基线。

| 口径 | 上一份 OpenCode job 当前树 | 本 job |
|---|---:|---:|
| Canonical task invoked | 11/12 | 12/12 |
| Raw reward | 8/22（36.36%） | 11/24（45.83%） |
| Evidence-scored trial rate | 8/20（40.00%） | 11/22（50.00%） |
| Scored task any-pass | 7/11（63.64%） | 7/11（63.64%） |
| Scored canonical task coverage | 11/12 | 11/12（Skrub verifier invalid） |

| Task | 上一份 OpenCode job 通过次数 | 本 job 通过次数 |
|---|---:|---:|
| `tengo-destructuring-bindings` | 1 | 1 |
| `valibot-recursive-schema-composition` | 1 | 2 |
| `sqlite-utils-safe-import-checkpoints` | 0 | 2 |
| `pebble-durability-wait-apis` | 0 | 2 |
| `bandit-incremental-cache-control` | 0 | 0 |
| `scriggo-method-declarations` | 1 | 1 |
| `adaptix-name-mapping-aliases` | 1 | 2 |
| `anko-typed-variable-bindings` | 1 | 0 |
| `mnamer-daemon-watch-lifecycle` | 2 | 1 |
| `skrub-duration-encoding` | 未运行 | 未评分 |
| `obsidian-linter-scoped-ignore-markers` | 0 | 0 |
| `dasel-html-document-format` | 1 | 0 |

在共同且有效评分的 11 题上，本 job 有 11 个通过 trial，上一份当前结果树有 8 个；但 task any-pass 都是 7/11。本 job 新覆盖 SQLite-utils 和 Pebble，失去 Anko 和 Dasel。

这个差异不能归因于模型或 unified runtime：上一份 job 使用不同 Agent/model/runtime，并经过选择性 resume，当前结果树不是原始采样；本 job 又有一个任务因 verifier 环境完全未评分。两者的 usage/cost 事件语义也不同，不应做直接成本效率比较。

## 建议

1. 正式记录本 job 时同时报告 Pier raw `11/24=45.83%`、evidence-scored `11/22=50.00%`、scored task any-pass `7/11=63.64%` 和 canonical task coverage `11/12`。
2. 修复 Skrub task image 的 Polars 原生崩溃，并增加运行前最小 Polars duration/import smoke test；修复后以独立补充 job 重跑 Skrub，不覆盖本 job 工件。
3. Verifier 应在 test command 非零退出且报告完全缺失时写入明确的 verifier exception，而不是让 grader 把全部 manifest node 记成普通失败。这能避免 Pier `n_errors=0` 掩盖 native crash。
4. 将 Bandit 的 `cache_file_size_bytes`、Obsidian 的 indented-code P2P 回归、Anko 的声明/多值类型约束作为稳定回归项；Dasel、Tengo、Scriggo、Mnamer 的近失边界也适合定向补测。
5. 若要进行正式系统横评，应重新运行 canonical 12 题并固定 runtime、异常排除规则和每题尝试数；不要把经过 resume 的上一份 OpenCode job 与本 job 当作等价基线。
