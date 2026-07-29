# DeepSWE 数据集 v1 与 v1.1 的区别

核查日期：2026-07-29

## 结论

**v1.1 没有更换或扩充题目集合；它保留 v1 的同一批 113 个长程软件工程任务，主要重做了 agent 执行、提交物提取、隔离验证和逐测试判分，并修复了部分依赖漂移及 flaky tests。** 官方将其概括为 “same tasks, cleaner signal”。[DeepSWE v1.1 官方发布说明](https://deepswe.datacurve.ai/blog/deepswe-v1-1)

**当前本地 `/Users/kgm/Projects/merico/deep-swe` 是 v1.1，而且更准确地说，是包含 v1.1 发布提交及后续兼容性更新的官方 `main`，不是停在最初的 v1.1 发布快照。** 本地 `HEAD` 与 `origin/main` 都是 `e016041a6ccf8da29906afc9a3f5a8df940a1f78`，其祖先包含官方题为 `DeepSWE V1.1` 的提交 `8cae5984d5dd0ee37445beff0e928dc10c331116`。[v1.1 发布提交](https://github.com/datacurve-ai/deep-swe/commit/8cae5984d5dd0ee37445beff0e928dc10c331116) [本地 HEAD 对应的官方提交](https://github.com/datacurve-ai/deep-swe/commit/e016041a6ccf8da29906afc9a3f5a8df940a1f78)

## 版本与发布时间

| 项目 | v1 | v1.1 |
| --- | --- | --- |
| 官方发布文 | 2026-05-26 | 2026-06-14 |
| Git 标识 | annotated tag `v1.0.0`（tag 创建于 2026-06-05） | commit `8cae5984…`，提交说明 `DeepSWE V1.1` |
| 数据集 manifest 名称 | `datacurve/deep-swe` | `datacurve/deep-swe-1-1` |
| 任务数 | 113 | 113，同一组任务 |

来源：[v1 官方发布文](https://deepswe.datacurve.ai/blog/deepswe) [v1.0.0 release/tag](https://github.com/datacurve-ai/deep-swe/releases/tag/v1.0.0) [v1.1 官方发布文](https://deepswe.datacurve.ai/blog/deepswe-v1-1) [v1.1 manifest 变更](https://github.com/datacurve-ai/deep-swe/commit/8cae5984d5dd0ee37445beff0e928dc10c331116#diff-715546fc38dc274f56594bed06f33981c415c86aed4c2561bbcaa064063968b5)

## 实质区别

| 维度 | v1 | v1.1 |
| --- | --- | --- |
| 题目内容 | 113 个任务 | **仍是相同 113 个任务**；本地对两个版本目录名、`task_id`、上游仓库、语言和 `base_commit_hash` 的集合比较均无差异 |
| Agent 的 Git 环境 | 旧构建方式处于 detached HEAD，且官方后来专门检查了未来 Git 历史可能泄露实现的风险 | 将任务起点设为 `main`，删除起点之后的 branch/tag/reflog 历史；要求 agent 在 feature branch 工作并提交 |
| 提交物 | verifier 在 agent 工作目录内直接处理工作区变化 | `pre_artifacts.sh` 只提取从 base commit 到最终 `HEAD` 的**已提交 diff**，作为 `model.patch` |
| 验证隔离 | agent 与 verifier 没有当前版本的强隔离 | 在全新 verifier 容器中应用 `model.patch` 和隐藏测试，agent 看不到也不能污染该容器 |
| 判分粒度 | `test.sh` 根据 base/new 测试命令的整体退出码写二值 `reward.txt` | `config.json` 明列 F2P/P2P test node IDs；`grader.py` 按节点判定，缺失/跳过也算失败，并输出 binary reward 与分项/partial 统计到 `reward.json` |
| 测试产物 | 以命令退出码和原始输出为主 | 统一产生 CTRF 逐测试报告、`reward.json`、`ctrf.json`、raw log 和 framework-native reports |
| 稳定性修正 | 原始依赖和测试状态 | 官方说明修复了 dependency drift，并移除了部分任务中的 flaky tests |
| 防投机能力 | 可以通过修改测试框架、删测试或提前退出等方式影响整体退出码 | 只验证已提交 patch，且逐节点报告；预期测试缺失会成为失败，以上捷径更难奏效 |

来源：[官方 v1.1“同题、隔离验证、CTRF、自然 Git 环境、依赖/flaky 修复”说明](https://deepswe.datacurve.ai/blog/deepswe-v1-1#what-changed) [v1.1 大型变更提交](https://github.com/datacurve-ai/deep-swe/commit/8cae5984d5dd0ee37445beff0e928dc10c331116) [v1 的示例 task.toml](https://github.com/datacurve-ai/deep-swe/blob/v1.0.0/tasks/abs-stepped-slices/task.toml) [v1.1 的示例 task.toml](https://github.com/datacurve-ai/deep-swe/blob/8cae5984d5dd0ee37445beff0e928dc10c331116/tasks/abs-stepped-slices/task.toml) [v1.1 grader](https://github.com/datacurve-ai/deep-swe/blob/8cae5984d5dd0ee37445beff0e928dc10c331116/tasks/abs-stepped-slices/tests/grader.py)

代码差分还能量化这次重构：v1.1 为全部 113 个任务分别新增了 `pre_artifacts.sh`、`tests/Dockerfile`、`tests/config.json` 和 `tests/grader.py`，并修改全部 113 个 `task.toml`、agent 环境 Dockerfile、`tests/test.sh`、reference solve script 和 instruction；instruction 的一致性新增内容是要求从 `main` 建分支并在完成后提交。28 个任务的 `test.patch` 另有小幅修订。[v1.0.0 到 v1.1 发布提交的官方比较](https://github.com/datacurve-ai/deep-swe/compare/v1.0.0...8cae5984d5dd0ee37445beff0e928dc10c331116)

## 为什么当前本地仓库可判定为 v1.1

只读核查得到以下相互独立的标志：

1. `git merge-base --is-ancestor 8cae598… HEAD` 成功；即当前 `main` 包含官方 v1.1 发布提交。
2. `tasks/dataset.toml` 的 dataset name 是 `datacurve/deep-swe-1-1`。
3. 113/113 个 `task.toml` 的 agent image 都以 `-v1.1` 结尾，并设置独立 verifier 环境。
4. 113/113 个任务都具有 `pre_artifacts.sh`、`tests/Dockerfile`、`tests/config.json` 和 `tests/grader.py`，正好对应 v1.1 的执行/判分结构。
5. README 明确写着 “Since v1.1, grading uses Harbor's separate verifier environment”。[当前官方 README](https://github.com/datacurve-ai/deep-swe/blob/e016041a6ccf8da29906afc9a3f5a8df940a1f78/README.md) [当前 manifest](https://github.com/datacurve-ai/deep-swe/blob/e016041a6ccf8da29906afc9a3f5a8df940a1f78/tasks/dataset.toml) [当前示例 task.toml](https://github.com/datacurve-ai/deep-swe/blob/e016041a6ccf8da29906afc9a3f5a8df940a1f78/tasks/abs-stepped-slices/task.toml)

一个容易误判的点是：当前 113 个 `task.toml` 写的是 `schema_version = "1.3"`，而 v1.1 发布快照中写的是 `schema_version = "1.1"`。这里的 `schema_version` 是 **Harbor task 文件格式版本**，不是 DeepSWE 数据集版本；官方后来用提交 `8e948e1…` 把所有 task schema 升到 1.3、把 `allow_internet = false` 改为 `network_mode = "no-network"`，数据集仍是 DeepSWE v1.1。[后续 Harbor schema/network_mode 兼容提交](https://github.com/datacurve-ai/deep-swe/commit/8e948e1f31b52dba7e4ca68ee1a0c8c617120fe2)

## 使用上的含义

- v1 与 v1.1 的**题目难度/覆盖面名义上相同**，但运行与判分协议不同，所以报告结果时必须标版本，不能把两版分数当成同一实验协议下的直接续表。
- 官方对 10 个两版都运行的 configuration 做了比较：总体 pass rate 和头部排序接近，但个别 configuration 和单题变化可以明显；这也说明“同题”不等于“得分必然相同”。[官方结果影响比较](https://deepswe.datacurve.ai/blog/deepswe-v1-1#impact-on-results)
- 官网数据浏览页把 `v1.1` 标为 `latest`；当前应优先使用 v1.1，只有复现旧榜单时才固定到 `v1.0.0`。[DeepSWE 官方数据页](https://deepswe.datacurve.ai/data/tasks)

## 核查方法边界

本文的版本差异只采用 Datacurve 官方网站、官方 GitHub 仓库及其本地 clone 的 Git 对象作为证据。有关 113 个 task identity/base commit 未变化、文件数量和本地 HEAD 的结论，是对 `v1.0.0`、`8cae598…` 与当前 `HEAD` 做只读 Git/文件统计得到的；未把第三方审计或二手文章作为版本事实来源。
