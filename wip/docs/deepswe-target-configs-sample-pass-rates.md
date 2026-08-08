# 四个内部目标配置在抽样子集上的官方通过率

更新日期：2026-08-08

内部实验当前主要测试四个模型配置：`claude-opus-5 [high]`、`gpt-5-6-sol [max]`、`gpt-5-6-luna [xhigh]`、`deepseek-v4-flash [max]`。本文从官方公开数据中提取这四个配置在 `05_sample_dev`、`05_sample_confirm`、`05_sample_rest` 三层抽样任务上的逐任务通过率，用于判断现有子集对这四个目标配置的区分能力。结论：**现有子集对这四个配置区分度已经很好，无需基于它们重新筛选**；本文数据只作诊断参考，不应反过来用于选题（见文末说明）。

## 数据口径

- 数据源：`wip/data/official-v1.1/trials.json`（2026-08-07 下载的官网快照，对应官方 2026-08-06 数据）。四个配置对应官方 config `mini_swe_agent_claude_opus_5_high`、`mini_swe_agent_gpt_5_6_sol_max`、`mini_swe_agent_gpt_5_6_luna_xhigh`、`mini_swe_agent_deepseek_v4_flash_max`。
- 过滤条件与主筛选一致：`source=deep-swe`、`eval_scope=full`、`included_in_score=true` 且 `errored=false`。
- 每格为 `通过次数/有效重复数`。官方每个 `(task, config)` 名义 4 次重复，本文覆盖的任务全部为 4 次。
- **spread**：该任务上四个配置通过率的最大值减最小值（极差）。0 表示四个配置在该任务上表现完全相同（无区分度），1.00 表示至少有一个配置全过、另一个全不过（区分度最强）。由于每格只有 4 次重复，通过率只有 0、0.25、0.50、0.75、1.00 五档，spread 同样按 0.25 步进。
- **全高分**：四个配置通过率全部不低于 0.75，即该任务对这四个配置接近天花板，预期贡献的区分信息很少。
- 抽样清单取自工作区当前状态：`05_sample_dev.txt` 为 11 题（`skrub-duration-encoding` 已移入 `host-excluded.txt`，不再参与本轮；`04_core.txt` 仍为 30 题）。

注意统计噪声：单格通过率的标准误在 p=0.5 时约为 ±0.25，观测到的 spread 有相当一部分来自 4 次重复的随机波动，不能把逐格数字当精确值解读。

## 05_sample_dev（11 题）

| 任务 | opus-5 high | sol max | luna xhigh | v4-flash max | spread | 备注 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `tengo-destructuring-bindings` | 3/4 | 4/4 | 2/4 | 2/4 | 0.50 |  |
| `valibot-recursive-schema-composition` | 4/4 | 4/4 | 4/4 | 1/4 | 0.75 |  |
| `sqlite-utils-safe-import-checkpoints` | 4/4 | 4/4 | 3/4 | 1/4 | 0.75 |  |
| `pebble-durability-wait-apis` | 4/4 | 4/4 | 4/4 | 2/4 | 0.50 |  |
| `bandit-incremental-cache-control` | 3/4 | 4/4 | 3/4 | 1/4 | 0.75 |  |
| `scriggo-method-declarations` | 4/4 | 3/4 | 3/4 | 4/4 | 0.25 | 全高分 |
| `adaptix-name-mapping-aliases` | 4/4 | 4/4 | 0/4 | 1/4 | 1.00 |  |
| `anko-typed-variable-bindings` | 4/4 | 2/4 | 1/4 | 3/4 | 0.75 |  |
| `mnamer-daemon-watch-lifecycle` | 4/4 | 4/4 | 4/4 | 3/4 | 0.25 | 全高分 |
| `obsidian-linter-scoped-ignore-markers` | 4/4 | 4/4 | 2/4 | 3/4 | 0.50 |  |
| `dasel-html-document-format` | 4/4 | 4/4 | 0/4 | 2/4 | 1.00 |  |
| **层均值** | **0.95** | **0.93** | **0.59** | **0.52** | **0.64** |  |

spread ≥ 0.5 的任务 9/11；全高分任务 2。

## 05_sample_confirm（12 题）

| 任务 | opus-5 high | sol max | luna xhigh | v4-flash max | spread | 备注 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `arcane-drift-detection-baselines` | 4/4 | 4/4 | 4/4 | 3/4 | 0.25 | 全高分 |
| `tengo-callable-instance-isolation` | 3/4 | 4/4 | 3/4 | 2/4 | 0.50 |  |
| `mobly-grouped-test-barriers` | 4/4 | 4/4 | 4/4 | 4/4 | 0.00 | 全高分 |
| `fastapi-deprecation-response-headers` | 3/4 | 3/4 | 2/4 | 1/4 | 0.50 |  |
| `anko-default-function-arguments` | 2/4 | 4/4 | 3/4 | 3/4 | 0.50 |  |
| `prometheus-typed-label-sorting` | 4/4 | 4/4 | 3/4 | 3/4 | 0.25 | 全高分 |
| `kombu-single-active-consumer-priority` | 4/4 | 4/4 | 3/4 | 1/4 | 0.75 |  |
| `textual-richlog-follow-state` | 2/4 | 4/4 | 4/4 | 3/4 | 0.50 |  |
| `tomlkit-toml-table-converters` | 4/4 | 4/4 | 1/4 | 4/4 | 0.75 |  |
| `cliffy-config-file-parsing` | 4/4 | 3/4 | 1/4 | 3/4 | 0.75 |  |
| `go-critic-doc-link-checker` | 3/4 | 3/4 | 3/4 | 0/4 | 0.75 |  |
| `clack-async-autocomplete-options` | 4/4 | 0/4 | 0/4 | 0/4 | 1.00 |  |
| **层均值** | **0.85** | **0.85** | **0.65** | **0.56** | **0.54** |  |

spread ≥ 0.5 的任务 9/12；全高分任务 3。

## 05_sample_rest（6 题）

| 任务 | opus-5 high | sol max | luna xhigh | v4-flash max | spread | 备注 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `fd-deterministic-multi-key-sorting` | 2/4 | 4/4 | 4/4 | 3/4 | 0.50 |  |
| `dateutil-rfc5545-timezone-interop` | 3/4 | 2/4 | 3/4 | 2/4 | 0.25 |  |
| `yaegi-go-embed-directives` | 4/4 | 4/4 | 3/4 | 2/4 | 0.50 |  |
| `httpx-multipart-response-parsing` | 3/4 | 3/4 | 3/4 | 2/4 | 0.25 |  |
| `opa-rego-rule-profiling` | 4/4 | 3/4 | 2/4 | 1/4 | 0.75 |  |
| `bandit-interprocedural-taint-checks` | 0/4 | 4/4 | 3/4 | 4/4 | 1.00 |  |
| **层均值** | **0.67** | **0.83** | **0.75** | **0.58** | **0.54** |  |

spread ≥ 0.5 的任务 4/6；全高分任务 0。

## 简要分析

**整体排序**。在 29 题（三层并集）上的平均通过率：sol max 0.88 ≈ opus-5 high 0.85 > luna xhigh 0.65 > v4-flash max 0.55。两个强配置接近，luna xhigh 明显落后于同族的 sol max，v4-flash max 最弱。

**子集区分能力**。三层合计 22/29 题 spread ≥ 0.5，说明现有子集主要靠“强配置对（opus-5 high、sol max）与后两名拉开差距”提供区分度。区分度最弱的是 5 个全高分任务，尤其 `mobly-grouped-test-barriers` 四配置 16/16 全过，在公开口径下零区分；但换 harness 后若某个内部 agent system 在这类题上失败，反而是框架层面的强信号，因此保留它们仍有意义。

**强配置对之间的分辨力偏弱**。opus-5 high 与 sol max 在 dev 层均值高达 0.95/0.93，接近饱和；两者差距 ≥ 0.5 的任务全部三层合计只有 6 题：`anko-typed-variable-bindings`、`anko-default-function-arguments`、`textual-richlog-follow-state`、`fd-deterministic-multi-key-sorting`，以及两道方向相反的极端题——`clack-async-autocomplete-options`（仅 opus-5 全过，其余全不过）和 `bandit-interprocedural-taint-checks`（仅 opus-5 全不过）。如果内部实验的主要问题是"opus-5 系统 vs sol 系统谁更强"，预期需要依赖重复次数和配对比较，而不是靠题目数量；dev 层对这一对的天花板效应比 confirm 层更明显。

**逐配置的失败特征**。luna xhigh 有 4 题通过率 ≤ 0.25（`adaptix-name-mapping-aliases`、`dasel-html-document-format`、`tomlkit-toml-table-converters`、`cliffy-config-file-parsing`），是它与 sol max 差距的主要来源；v4-flash max 的弱势更均匀地分布在各题上。

**噪声提醒**。以上所有"某题上 A 比 B 强"的逐题结论都基于每格 4 次重复，单格 ±0.25 的波动足以翻转 0.5 的差距；层均值和跨题聚合结论相对可靠，逐题结论只能作为待验证的假设。

## 与筛选主线的关系

本文只是把官方数据按内部目标配置切片做诊断，不改变 [任务子集筛选方案](deepswe-discriminative-subset-selection.md) 的主线。特别地：

1. 不应基于本文数据重新选题或调整 `confirm` 组——那会把这四个配置在公开数据中的具体强弱模式"调入"子集（与 leave-target-model-out 原则相反），且每任务仅 16 次 trial 的选题依据噪声过大。
2. 官方数据全部来自 `mini-swe-agent` harness，内部实验换用其他 agent system 后，本文逐题通过率只是代理指标，预期会有偏移。
3. 若后续要提高对强配置对的灵敏度，合理途径是预登记地从核心池调整 `dev` 组构成并在运行前提交，而不是事后按结果换题。
