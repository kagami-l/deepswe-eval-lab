# DeepSWE Collab 实现 Review

- 评审时间：2026-07-30 17:38:01（Asia/Shanghai）
- 评审对象：`wip/agents/deep_swe_collab`
- 评审版本：`819084e`（`Add DeepSWE collab agent with Modifier/Reviewer runtime`）
- 评审范围：方案的当前实现；按约定，不包含 auth 处理

## 结论

实现整体结构合理，和方案中的“修改 → 审查 → 修订 → 最终交付”基本一致。

正式运行评测前，建议优先处理以下四项：

1. 修复 `npm test` 入口。
2. 保留初始可信 checkpoint，并把后续基础设施异常降级为可交付结果。
3. 显式指定或准确记录实际使用的 model/effort。
4. 统一 `max_reviews=0` 在 Python 和 Node runtime 中的语义。

完成上述修改后，可以开始小规模 smoke evaluation。lockfile 和 agent 自提交归一化可在扩大评测规模前处理。

## Findings

### [P1] `npm test` 当前必然失败

位置：`wip/agents/deep_swe_collab/runtime/package.json:9`

当前脚本为：

```json
"test": "npm run build && node --test dist/"
```

Node.js v22 会把 `dist/` 当作模块路径，而不是在该目录下自动发现测试，因此报错：

```text
Cannot find module .../dist
```

测试本身没有问题，手动执行以下命令时 22 个测试全部通过：

```bash
node --test dist/*.test.js
```

建议修改为：

```json
"test": "npm run build && node --test dist/*.test.js"
```

### [P1] 初始 checkpoint 成功后发生基础设施异常，会丢失可交付结果和真实用量

相关位置：

- `wip/agents/deep_swe_collab/runtime/src/direct-engine.ts:248`
- `wip/agents/deep_swe_collab/runtime/src/main.ts:110`

Reviewer workspace 的复制、清理等操作可能抛出未被 engine 捕获的异常。例如，在磁盘空间不足时，`cp -a` 可能失败。

这些异常最终进入 `main.ts` 的统一 catch，并生成一个全新的 `checkpoint_failed` summary：

- `deliverable: false`
- checkpoints 为空
- usage 全部归零
- 已成功创建的 Modifier checkpoint 被遗忘

这与方案中的“存在可信 checkpoint 时，后续审查、修订或超时失败应 degraded delivery”不一致，也会污染评测费用和 token 统计。

建议让 engine 捕获初始化完成后的基础设施异常。只要存在可信 checkpoint，就通过 `finalize("degraded", ...)` 交付；`main.ts` 的 catch 主要处理初始化或首个可信 checkpoint 建立之前的失败。

### [P1] 默认允许不指定 model/effort，正式评测结果无法稳定复现

位置：`wip/agents/deep_swe_collab/pier_agent.py:99`

两个角色的 model 和 effort 默认都是 `None`。这种情况下实际使用 adapter/provider 当时的默认配置，而 summary 中记录的仍是 `null`。

这会导致：

- 不同时间运行可能落到不同的默认模型；
- 结果中无法确认实际使用了哪个模型；
- 单 agent 与 collab 的效果和成本比较可能失真。

建议在正式评测模式中要求显式传入 `modifier_model`、`reviewer_model`，最好也显式传入 effort。另一种方案是从 cligent 初始化事件中读取最终解析后的模型并写入 summary，但显式配置更简单可靠。

### [P2] `max_reviews=0` 在 Python 层合法，在 Node runtime 中非法

相关位置：

- `wip/agents/deep_swe_collab/pier_agent.py:141`
- `wip/agents/deep_swe_collab/runtime/src/main.ts:78`

Python wrapper 明确接受 `max_reviews >= 0`，DirectEngine 中也包含零轮审查的逻辑；但 Node runtime 使用只接受正数的通用解析器。

因此，传入 `--ak max_reviews=0` 会通过 Python 校验，却在 runtime 的配置解析阶段失败，并且不会产生 summary。

建议为 `maxReviews` 使用单独的非负整数解析器。保留零轮模式也便于通过同一套代码执行 modifier-only 对照实验。

### [P2] 提交了 lockfile，但构建派生镜像时没有使用

位置：`wip/agents/deep_swe_collab/pier_agent.py:217`

当前实现动态生成 `package.json` 后执行：

```bash
npm install --omit=dev
```

仓库中的 `package-lock.json` 没有进入派生镜像的安装过程。直接依赖虽然固定了版本，但传递依赖仍可能随时间变化。

建议正式批量评测前携带 lockfile 并执行：

```bash
npm ci --omit=dev
```

也可以预先构建、固定版本的 runtime 基础镜像。

### [P2] Modifier 自己 commit 时，checkpoint 记录和文件过滤不完整

位置：`wip/agents/deep_swe_collab/runtime/src/direct-engine.ts:487`

当前只有 harness 创建 commit 时才把 commit 加入 `checkpoints`。如果 Modifier 自己提交，虽然实现容忍 HEAD 发生变化，但存在两个问题：

- 该 commit 不会进入 checkpoint trace；
- 如果 Modifier 已执行 `git add -A`，baseline untracked 文件可能已进入 commit，后续 `stageAllExcept()` 无法将其移除。

这是相对边缘的问题，可以晚于 smoke test 处理。更稳妥的做法是不要直接信任 agent commit：发现 HEAD 改变后，将其归一化为 working tree 变更，再由 harness 过滤、提交并记录。

## 验证结果

| 检查项 | 结果 |
| --- | --- |
| TypeScript 编译 | 通过 |
| TypeScript 测试（手动运行 `node --test dist/*.test.js`） | 22/22 通过 |
| Python 单元测试 | 12/12 通过 |
| Ruff | 通过 |
| `git show --check --oneline HEAD` | 通过 |
| 官方入口 `npm test` | 失败，原因见 Finding 1 |

## 建议实施顺序

1. 修复 `npm test`。
2. 修复初始 checkpoint 后异常的 degraded delivery 和 usage 保留。
3. 要求显式配置 model/effort，或记录 resolved model。
4. 修复 `max_reviews=0` 的跨层契约。
5. 运行小规模 smoke evaluation。
6. 在扩大评测规模前引入 lockfile 安装，并处理 agent 自提交归一化。

## 处理记录（2026-07-30）

前 4 项已处理完毕，后 2 项按建议推迟。

| Finding | 状态 | 处理方式 |
| --- | --- | --- |
| [P1] `npm test` 失败 | ✅ 已修复 | test script 改为 `node --test dist/*.test.js` |
| [P1] checkpoint 后基础设施异常丢失结果 | ✅ 已修复 | 引擎级 backstop：`run()` 包裹 `execute()`，存在可信 checkpoint 时未捕获异常 → `finalize('degraded', 'infrastructure', ...)` 交付该 checkpoint；checkpoint 建立前的异常 → `checkpoint_failed`，但同样经引擎 finalize 产出完整 summary（usage、baseCommit 不再归零）。计数器提升为实例字段供 finalize 读取；`trace()` 防御化；`degraded_reason` 新增 `infrastructure`（设计文档 §13 与 README 已同步） |
| [P1] model/effort 默认 None 不可复现 | ✅ 已处理（采用备选方案） | `CligentRunner` 从每轮 cligent `init` 事件捕获 provider 实际解析的模型，按角色首值记入 summary（`modifier.actualModel` / `reviewer.actualModel`），比强制显式配置覆盖面更全（连显式配置被 provider 改写也能如实记录）；README 同时注明正式评测应显式指定 model/effort |
| [P2] `max_reviews=0` 跨层契约不一致 | ✅ 已修复 | `main.ts` 新增非负整数解析器 `optionalCount` 用于 `maxReviews`；新增 `main.test.ts` 契约测试（0 合法、负数/小数拒绝）；README 标注 `max_reviews=0` 为 modifier-only matched-pipeline 对照组 |
| [P2] lockfile 未用于派生镜像 | ⏸ 推迟 | 按建议在扩大评测规模前处理；候选方案：将 `package-lock.json` 内嵌进 install step（fingerprint 顺带覆盖传递依赖）或预构建 runtime 基础镜像 |
| [P2] agent 自提交归一化 | ⏸ 推迟 | 按建议在 smoke 之后处理；采用 `git reset --mixed` 归一化为工作区变更再由 harness 过滤提交（同 SWE-bench Pro `normalize_patch` 做法）。prompt 已禁止 Modifier 自行 commit，`lastCheckpoint` 语义不受影响 |

处理后验证：`npm test` 30/30（新增 8 个测试：基础设施降级、checkpoint 前失败、
`maxReviews=0` 全链路、actualModel 捕获、`parseConfig` 契约）；Python unittest
23/23；ruff 通过。
