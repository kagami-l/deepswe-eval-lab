# luna-xhigh 与 v4-flash-max 能力互补任务子集

更新日期：2026-08-08

为 `openai/gpt-5-6-luna [xhigh]` 与 `deepseek/deepseek-v4-flash [max]` 的互补性实验单独准备的任务子集。目标是找出"一个配置稳定做得出、另一个稳定做不出"的任务，两个方向都要覆盖。清单文件：[`wip/data/selection/complementary-luna-v4flash.txt`](../data/selection/complementary-luna-v4flash.txt)（前 5 题为 luna 强方向，后 5 题为 flash 强方向）。

## 定位与用途边界

这是一个**机制探测池**（mechanism probe），不是无偏 benchmark：

- 适用场景：检验路由、双模型协作等机制能否吃到已知的互补收益。oracle 路由在这些题上的理论上限接近 100%，单配置约 50%，headroom 明确。
- 不能用于：报模型排名（题目是按结果挑的）；声称"这两个模型总体互补性有多大"（互补性是被构造进子集的前提，不是子集能证明的结论）。合适的结论形式是："在公开数据显示互补的任务上，机制 X 捕获了其中多少收益"。
- 本子集与主线的 `model-core` / `05_sample_*` 各池用途互不替代；筛选主线见 [任务子集筛选方案](deepswe-discriminative-subset-selection.md)，四个内部目标配置在主线抽样上的表现见 [抽样子集通过率诊断](deepswe-target-configs-sample-pass-rates.md)。

## 数据口径

- 数据源：`wip/data/official-v1.1/trials.json`（2026-08-07 下载快照，对应官方 2026-08-06 数据），config 为 `mini_swe_agent_gpt_5_6_luna_xhigh` 与 `mini_swe_agent_deepseek_v4_flash_max`。
- 过滤条件与主筛选一致：`source=deep-swe`、`eval_scope=full`、`included_in_score=true` 且 `errored=false`。每格为 `通过次数/有效重复数`，官方每格 4 次重复。
- **luna 家族**列：gpt-5-6-luna 全部 5 档 effort 合并的通过数（n=20），用于佐证 luna 侧的逐题结论。v4-flash 官方只有 max 一个 config，无法做同样的佐证——**两个方向的证据强度天然不对称**，报告中需说明。

## 筛选思路

1. **候选生成**：在全部 113 题上扫描"一个配置通过率 ≥ 0.75 且另一个 ≤ 0.25"，两个方向分别记录。共命中 17 题（luna 强 10、flash 强 7）。
2. **噪声基线**：每格仅 4 次重复时，若某题上两配置真实水平完全相同，仅凭抽样波动被误判为"互补"的概率约 0.11–0.20；113 题全为零差异也会随机命中十几题，与实际命中数同量级。因此阈值本身不足以定选，必须按证据强度分级。
3. **证据分级**（Fisher 单侧检验）：
   - A 档：4/4 vs 0/4，p ≈ 0.014；
   - B 档：4/4 vs 1/4 或 3/4 vs 0/4，p ≈ 0.071；
   - C 档：3/4 vs 1/4，p ≈ 0.243——单独不构成证据，只作替补。
4. **家族佐证**：luna 侧结论要求 luna 家族 20 次口径同向（flash 强的题要求家族通过率也低，反之亦然）。
5. **质量标记**：叠加主线 `01_stable` 稳定池标记、`v1-delta` 评分敏感标记（`|delta| ≥ 0.10`）。带标记的题不自动剔除（flash 强方向可选题太少），但正式报告需做含/不含标记组的敏感性分析。
6. **与 confirm 组隔离**：本子集会被用于调试机制，故**排除所有属于 `05_sample_confirm` 的候选题**（`go-critic-doc-link-checker`、`tomlkit-toml-table-converters`、`kombu-single-active-consumer-priority`、`cliffy-config-file-parsing`），避免污染主线 confirm 组的未接触状态。与 `05_sample_dev` 重叠不构成问题。
7. **方向平衡**：两个方向各取 5 题，A 档全收、B 档补足；flash 强方向 A/B 档只有 4 题可用，从 C 档提拔 `anko-typed-variable-bindings` 补齐。
8. **内部确认（待做）**：用内部 harness 对两个配置在 10 题上各跑 4 次，只保留互补性复现的题进入正式 `complementary-core`。此步同时处理抽样噪声（winner's curse，预期部分题差距回归）和 mini-swe-agent → 内部 agent system 的口径迁移，不可省略。清单在运行前冻结提交。

## 推荐子集（10 题）

| # | 任务 | 方向 | 档 | luna xhigh | v4-flash max | luna 家族 | 语言 | 标记 |
| --- | --- | --- | --- | ---: | ---: | ---: | --- | --- |
| 1 | `meriyah-explicit-resource-declarations` | luna 强 | A | 4/4 | 0/4 | 9/20 | typescript |  |
| 2 | `superjson-error-stack-serialization` | luna 强 | A | 4/4 | 0/4 | 11/20 | typescript | 未进 01_stable† |
| 3 | `numba-stencil-boundary-modes` | luna 强 | B | 4/4 | 1/4 | 11/20 | python |  |
| 4 | `valibot-recursive-schema-composition` | luna 强 | B | 4/4 | 1/4 | 12/20 | typescript | 已在 05_sample_dev |
| 5 | `sqlfmt-create-table-ddl-formatting` | luna 强 | B | 3/4 | 0/4 | 5/20 | python | 评分敏感（Δ −0.20） |
| 6 | `eicrud-keyset-pagination-cursor` | flash 强 | A | 0/4 | 4/4 | 3/20 | typescript | 评分敏感（Δ −0.15） |
| 7 | `onedump-dump-encryption-pipeline` | flash 强 | A | 0/4 | 4/4 | 2/20 | go |  |
| 8 | `python-statemachine-state-data-scoping` | flash 强 | A | 0/4 | 4/4 | 2/20 | python |  |
| 9 | `prometheus-transactional-reload-status` | flash 强 | B | 1/4 | 4/4 | 3/20 | typescript | 评分敏感（Δ +0.10） |
| 10 | `anko-typed-variable-bindings` | flash 强 | C | 1/4 | 3/4 | 5/20 | go | C 档提拔；已在 05_sample_dev |

† `superjson` 未进稳定池的原因是 `minimum_effective_repeats`（个别其他 config 有效重复不足），其错误率 0.025、verifier timeout 为 0，不直接影响 luna/flash 两格的可信度，保留使用但注明。

语言分布：typescript 5、python 3、go 2；10 题分属 10 个不同仓库。本子集不做主线那种严格语言配额，多样性以"不集中在单一仓库/语言"为度。

注意 luna 家族列的含义差异：flash 强的 5 题 luna 家族全部 ≤ 5/20，说明 luna 全系（而非仅 xhigh 一档）都做不出，佐证很强；luna 强的题中 `meriyah`、`sqlfmt` 家族口径只有 9/20、5/20，说明是 xhigh 及部分高档 effort 才稳定做出，属于"高 effort 特长题"，在内部确认时更要关注是否复现。

## 替补名单

若确认跑中有题未复现互补性，按方向从下表递补（仍需复跑确认）：

| 任务 | 方向 | 档 | luna xhigh | v4-flash max | 标记 |
| --- | --- | --- | ---: | ---: | --- |
| `fastapi-implicit-head-options` | luna 强 | C | 3/4 | 1/4 |  |
| `sqlite-utils-safe-import-checkpoints` | luna 强 | C | 3/4 | 1/4 | 已在 05_sample_dev |
| `bandit-incremental-cache-control` | luna 强 | C | 3/4 | 1/4 | 评分敏感（Δ +0.10）；已在 05_sample_dev |
| `tomlkit-toml-table-converters` | flash 强 | B | 1/4 | 4/4 | **属于 05_sample_confirm，使用会污染 confirm，仅在别无选择时启用** |

flash 强方向在 confirm 组之外已无 A/B 档替补；若该方向减员且不愿动用 confirm 题，只能接受方向不平衡，并在报告中说明。

## 完整候选扫描记录（17 题）

未入选原因：`confirm` = 属于 05_sample_confirm 被隔离；`C 档` = 证据不足仅作替补。

| 任务 | 方向 | 档 | luna xhigh | v4-flash max | 处置 |
| --- | --- | --- | ---: | ---: | --- |
| `meriyah-explicit-resource-declarations` | luna 强 | A | 4/4 | 0/4 | 入选 |
| `superjson-error-stack-serialization` | luna 强 | A | 4/4 | 0/4 | 入选 |
| `numba-stencil-boundary-modes` | luna 强 | B | 4/4 | 1/4 | 入选 |
| `valibot-recursive-schema-composition` | luna 强 | B | 4/4 | 1/4 | 入选 |
| `sqlfmt-create-table-ddl-formatting` | luna 强 | B | 3/4 | 0/4 | 入选 |
| `go-critic-doc-link-checker` | luna 强 | B | 3/4 | 0/4 | confirm |
| `fastapi-implicit-head-options` | luna 强 | C | 3/4 | 1/4 | C 档，替补 |
| `sqlite-utils-safe-import-checkpoints` | luna 强 | C | 3/4 | 1/4 | C 档，替补 |
| `bandit-incremental-cache-control` | luna 强 | C | 3/4 | 1/4 | C 档，替补 |
| `kombu-single-active-consumer-priority` | luna 强 | C | 3/4 | 1/4 | confirm |
| `eicrud-keyset-pagination-cursor` | flash 强 | A | 0/4 | 4/4 | 入选 |
| `onedump-dump-encryption-pipeline` | flash 强 | A | 0/4 | 4/4 | 入选 |
| `python-statemachine-state-data-scoping` | flash 强 | A | 0/4 | 4/4 | 入选 |
| `prometheus-transactional-reload-status` | flash 强 | B | 1/4 | 4/4 | 入选 |
| `tomlkit-toml-table-converters` | flash 强 | B | 1/4 | 4/4 | confirm，列为替补 |
| `anko-typed-variable-bindings` | flash 强 | C | 1/4 | 3/4 | C 档提拔入选 |
| `cliffy-config-file-parsing` | flash 强 | C | 1/4 | 3/4 | confirm |
