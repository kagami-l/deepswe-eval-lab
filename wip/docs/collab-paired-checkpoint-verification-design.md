# Collab 初始 Patch 配对验证设计

状态：设计已确认，待实现。

确认日期：2026-08-07。

## 背景

结果报告
[collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833](results/collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833.md)
的第 7 条建议指出：若要判断 reviewer 是否提升 verifier 分数，不能继续比较两个独立随机 job，
而应保存同一个 modifier initial checkpoint，并比较它直接提交与经过 review-loop 后提交的结果。

当前 collab runtime 已经在 Git 中创建 initial 和 revision checkpoint，但 Pier 只验证最终 `HEAD`。
现有 round 目录中的 patch 也只是运行日志，没有版本化、可恢复的 checkpoint 产物契约。因此当前数据
无法稳定回答以下问题：

- 同一个 initial patch 直接提交时能否通过 verifier；
- reviewer 引发的 revision 是修好了、破坏了，还是没有改变正式 reward；
- 每轮 revision 对 F2P、P2P 和正式 reward 的边际影响；
- reviewer/runtime 失败是否会改变对 reviewer 实际价值的判断。

本设计将所有 collab eval 升级为 checkpoint 配对验证，同时保持 reviewer 对 verifier 结果完全盲测。

## 目标

1. 对同一个 modifier initial patch 构造 no-review 与 review-loop 的配对反事实。
2. 验证 initial、每个实际改变 patch 的 revision，以及 terminal/final checkpoint。
3. 不向 modifier 或 reviewer 暴露 verifier 分数、隐藏测试或 verifier 日志。
4. 复用 DeepSWE/Pier 的正式 separate-verifier 评分路径，不复制 task grader。
5. 保留 Pier 对 final submission 的正常评分，并只补评其他唯一 checkpoint。
6. 支持长任务中断后的幂等恢复，不重新调用模型或重新生成 patch。
7. 为一个指定的旧 collab job 提供独立、严格、可删除的回溯入口。
8. 同时报告真实部署口径的 intention-to-treat 和诊断性质的 completed-protocol 子集。

## 非目标

- 本次不设计正式实验的任务规模、统计功效或数据收集计划。
- 本次不加入与 review-loop 等计算预算的 modifier-only continuation 第三支。
- 本次不让 agent 根据 verifier 反馈继续修复。
- 本次不改变 single-agent eval 的验证语义。
- 本次不提供跨 job 的全局 verifier cache。
- 本次不把旧 round 目录的启发式解析混入新 job 的正常恢复路径。
- 本次不为所有历史 collab runtime 布局提供通用 importer。

## 核心实验定义

实验单位是一个成功产生 initial checkpoint 的 collab trial。主 estimand 是：允许 reviewer 和由其触发的
modifier revision 使用额外计算预算后，相对于同一个 initial patch 直接提交，正式 verifier reward 改变了多少。

对每个 eligible trial：

```text
no-review score = V(initial checkpoint)
review-loop score = V(terminal checkpoint)
paired delta = V(terminal checkpoint) - V(initial checkpoint)
round delta[r] = V(revision-r) - V(parent checkpoint)
```

该估计衡量 reviewer treatment 的边际价值，不声称与“把相同预算继续给 modifier”计算公平。若未来要回答
计算效率问题，应另加 modifier-only continuation 第三支，不改变本设计的主配对。

## 运行流程

所有 `run_agent_eval.py eval ... --agent collab ...` 自动执行配对验证，不增加 paired mode flag。
single-agent eval 仍只验证一个 final patch。

```text
modifier initial
  -> initial checkpoint
  -> review-loop
       -> changed revision checkpoint(s)
       -> terminal checkpoint
  -> Pier 自带 verifier 验证 terminal/final patch
  -> host-side checkpoint completion
       -> 导入并校验 Pier final result
       -> direct Pier verifier runner 补评其他唯一 checkpoint
       -> 写入 trial 级配对结果
       -> 写入 job 级汇总
```

### 为什么不创建两个实际 agent 分支

no-review 支没有后续 agent 行为，它只需要 initial patch 的 verifier 分数。因此不复制工作区或 agent session：

- initial checkpoint 是不可变 baseline；
- 原 modifier session 继续执行 review-loop；
- review-loop 完成后再验证所有冻结 checkpoint；
- no-review 与 review-loop 共享完全相同的 initial patch bytes。

这保留了当前 runtime 的 modifier session continuity，也消除了重新生成 initial patch 带来的随机性。

### Verifier 盲测

所有补充 verifier 都在完整 review-loop 结束后运行：

- verifier reward、日志和耗时不进入 reviewer/modifier prompt；
- verifier 阶段不占 agent workflow budget；
- reviewer 无法读取 separate verifier 环境或隐藏测试；
- checkpoint delta 只用于事后分析，不驱动后续 revision。

## Checkpoint 语义

### 需要评分的状态

- `initial`：modifier 首次成功实现后的可信 checkpoint；
- `revision-N`：reviewer 触发且确实改变 patch 的第 N 个 revision checkpoint；
- `terminal`：workflow 结束时最后可信 checkpoint，是某个已有 checkpoint 的 alias。

以下状态不创建新的评分对象：

- 纯 review round；
- reviewer approve 后没有 revision；
- no-change revision；
- 与已有 checkpoint patch SHA 相同的 alias。

### 最后可信 checkpoint

任何 workflow outcome 都必须将 final submission 固定为最后可信 checkpoint。Runtime 返回前需要把 HEAD 和
tracked worktree 恢复到 terminal commit，确保以下内容完全一致：

- checkpoint index 的 `terminalCheckpointId`；
- Pier `pre_artifacts.sh` 从 base 到 `HEAD` 提取的 `model.patch`；
- Pier final verifier 实际评分的 patch；
- paired summary 中的 treatment final。

Reviewer timeout、invalid output、revision failure 或 post-checkpoint infrastructure failure 不得让未提交的
半成品进入 final patch。它们按 intention-to-treat 使用最后可信 checkpoint。

## Checkpoint 产物契约

新 collab runtime 在每次 checkpoint 时立即导出 patch 和更新版本化 index，而不是在 job 结束后从 round
目录名推断。

建议路径：

```text
<trial>/agent/system/checkpoints/
├── index.json
└── patches/
    ├── initial.patch
    ├── revision-1.patch
    └── revision-2.patch
```

`index.json` schema version 1 的概念结构：

```json
{
  "schemaVersion": 1,
  "baseCommit": "<git sha>",
  "terminalCheckpointId": "revision-2",
  "checkpoints": [
    {
      "checkpointId": "initial",
      "parentCheckpointId": null,
      "kind": "initial",
      "ordinal": 0,
      "commit": "<git sha>",
      "patchPath": "patches/initial.patch",
      "patchSha256": "<sha256>",
      "changed": true,
      "originRound": "00-modify",
      "createdAfterReviewRound": null
    },
    {
      "checkpointId": "revision-1",
      "parentCheckpointId": "initial",
      "kind": "revision",
      "ordinal": 1,
      "commit": "<git sha>",
      "patchPath": "patches/revision-1.patch",
      "patchSha256": "<sha256>",
      "changed": true,
      "originRound": "02-revise",
      "createdAfterReviewRound": 1
    }
  ]
}
```

约束：

- index 使用临时文件加 rename 原子更新；
- patch SHA 在写入时计算，host completion 再次校验；
- checkpoint ID、parent 和 ordinal 构成单链；
- terminal 必须引用 index 中已有 checkpoint；
- patch 必须能应用到记录的 base commit；
- agent `rounds/` 目录保持运行日志语义，事后 verifier 不回写其中。

## Verifier 执行策略

### Final checkpoint

Pier 正常执行 final verifier。Host-side completion 仅在以下条件全部满足时复用其 reward：

1. `artifacts/model.patch` SHA 与 terminal checkpoint patch SHA 相同；
2. task checksum、base commit、verifier 配置和 verifier image fingerprint 匹配；
3. Pier final verifier 正常完成；
4. reward 文件存在且可解析；
5. 没有 verifier exception。

Reward `0` 是有效评分，不触发重跑。如果上述条件不满足，direct runner 将 terminal 作为缺失 checkpoint
补评，并记录未复用原因。

### 非 final checkpoint

Pier 0.3.0 没有公开的 `verify-artifact` 命令。实现使用一个窄的 `PierCheckpointVerifier` adapter，固定
`datacurve-pier==0.3.0`，通过 Pier 内部的 `Trial._verify_once()` 进入与正式评分相同的路径：

- 解析原 task verifier 配置；
- 从原 task tests build context 创建 fresh separate verifier environment；
- 使用 Pier `ArtifactHandler` 上传已冻结的 `model.patch`；
- 使用 Pier `Verifier.verify()` 执行测试并解析 reward；
- 使用原 task/job 的 verifier env、timeout、resource 和 image 配置。

它绕过 agent setup、agent run、`pre_artifacts.sh` 和 job bookkeeping，但不重写或绕过 verifier 评分逻辑。
Checkpoint patch 已经冻结，因此不需要再启动一个 apply-patch 模拟 agent 环境。

### Pier 私有接口风险

私有接口风险被限制在一个 adapter 内：

- `wip/pyproject.toml` 和 lock 固定 `datacurve-pier==0.3.0`；
- 启动时校验 Python package 版本；
- 校验外部 `pier --version` 与 Python package 版本一致；
- 校验依赖的私有方法存在且参数结构符合预期；
- 不兼容时 fail closed，不尝试猜测新语义；
- run/paired manifest 记录 Pier 版本和 adapter schema version；
- 长期可将 adapter 替换为未来的 Pier public verify-artifact interface，而不改变上层模块。

### Conformance test

两层验证 direct runner 与 Pier final verifier 的一致性：

1. 自动化 contract tests 校验固定版本、私有方法结构、artifact upload 和 result mapping；
2. one-task 人工 smoke 时可加 `--checkpoint-verifier-conformance`，强制 direct runner 重验一次 final patch，
   并要求 reward 与 Pier final reward 一致。

Conformance flag 只用于 smoke 或 Pier 升级验收。正式 job 不重复验证 final checkpoint。

## 深模块与 seam

### Runtime CheckpointCatalog 模块

Runtime 增加一个深的 `CheckpointCatalog` 模块。它的 interface 只暴露 checkpoint capture 和 terminal
finalization；实现隐藏：

- Git patch 导出；
- patch SHA；
- checkpoint parent/ordinal；
- versioned index；
- 原子写入；
- terminal alias；
- terminal worktree restoration。

`DirectCollaborationEngine` 只在 initial/revision/final 语义点调用该模块，不自行拼装 index。

### Host PairedCompletion 模块

Host 侧核心 interface：

```python
complete_collab_job(job_path, options, verifier) -> PairedSummary
```

该深模块隐藏：

- job/trial 发现；
- checkpoint schema 和 hash 校验；
- Pier final result 导入；
- unique checkpoint 去重；
- job-local cache；
- verifier concurrency 和 retry；
- trial result 落盘；
- coverage 和汇总生成；
- resume 幂等性。

CLI 只解析参数、调用该 interface、打印摘要并设置退出码。

### CheckpointVerifier seam

验证 seam 的小 interface：

```python
verify_checkpoint(request) -> VerificationRecord
```

至少有两个 adapter：

- production `PierCheckpointVerifier`；
- 自动化测试使用的 fake verifier adapter。

Pier 私有实现、Docker/Pier 环境创建和 artifact upload 知识只能存在于 production adapter。

### LegacyBackfill 模块

Legacy round 推断放在独立模块。它只负责把一个已知旧布局转换为 schema v1 checkpoint catalog，之后调用
相同的 `complete_collab_job`。新 job 的 resume 绝不调用 legacy parser。

## 命令界面

### 正常 eval

日常命令形态不变：

```bash
uv run python scripts/run_agent_eval.py eval \
  --task-list one_task.txt \
  --agent collab \
  --modifier codex \
  --reviewer opencode \
  --n-attempts 1 \
  --n-concurrent 1
```

对 collab，launcher 在 Pier job 完成后自动调用 paired completion。无需 `--paired` 或
`--verification-mode paired`。

可选参数：

```text
--checkpoint-verifier-concurrency N
--checkpoint-verifier-conformance
```

未指定 checkpoint verifier concurrency 时复用 `--n-concurrent`。

### 恢复新格式 job

```bash
uv run python scripts/run_agent_eval.py paired resume \
  --job-path jobs/<job-name>
```

`resume`：

- 不调用 modifier/reviewer；
- 不重新生成 patch；
- 校验 run manifest、checkpoint index 和 patch SHA；
- 导入已存在的成功结果和 cache；
- 只补跑缺失或允许重试的 verifier；
- 重新生成派生汇总；
- 不修改 Pier `result.json`；
- 完整 job 上执行时不启动 verifier，是幂等 no-op。

不公开独立的 `paired verify` 或 `paired summarize`。验证和汇总都属于 completion/resume 的内部行为。

### 回溯旧 job

```bash
uv run python scripts/run_agent_eval.py paired backfill \
  --job-path jobs/collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833
```

第一版只保证支持 `20260806-224833` 的已知布局：

- 第一个 review round 的 `patch.diff` 作为 initial；
- 后续 review 前 patch 作为前一轮 revision 后 checkpoint；
- `final/patch.diff` 作为 terminal 候选；
- 按 patch SHA 去重并建立 parent 单链；
- 用原 summary/result 校验 base、round 和 terminal 一致性。

Backfill 在写文件前完成全 job compatibility scan。任何 trial 不符合已知 profile 时 fail closed，不生成半套
catalog。成功后只新增 `<job>/paired/` 和 `<trial>/paired/` 或 checkpoint catalog 文件，不修改、删除原文件。

`paired resume` 遇到没有 versioned index 的 job 时不会自动猜测 round 布局，必须显式 backfill。

## 产物布局

Pier job 本身就是实验根目录，不增加额外外层 experiment 目录：

```text
jobs/<job-name>/
├── result.json
├── config.json
├── paired/
│   ├── manifest.json
│   ├── pairs.jsonl
│   ├── pairs.csv
│   └── summary.json
└── <task>__<trial-id>/
    ├── result.json
    ├── verifier/
    ├── artifacts/model.patch
    ├── agent/system/
    │   ├── rounds/
    │   └── checkpoints/
    │       ├── index.json
    │       └── patches/*.patch
    └── paired/checkpoints/
        ├── initial/
        │   ├── result.json
        │   ├── artifacts/model.patch
        │   └── verifier/
        └── revision-1/
            ├── result.json
            ├── artifacts/model.patch
            └── verifier/
```

当 terminal 复用 Pier final result 时，paired checkpoint result 记录 `source = "pier-final"` 和原 verifier
路径引用，不复制整个 verifier 目录。

## Cache、并发与 retry

### Cache

第一版 cache 只在 job 内共享，支持：

- resume；
- terminal/final alias 去重；
- 同一 job 内完整 fingerprint 相同的 checkpoint 去重。

Cache key 至少包含：

```text
task checksum
base commit
patch SHA-256
Pier version
verifier config digest
verifier image/build-context digest or stable identity
adapter schema version
```

不在第一版跨 job 复用，避免跨 runtime/task config 误命中和掩盖 verifier nondeterminism。

### 并发

- 默认 checkpoint verifier concurrency 等于 eval 的 `--n-concurrent`；
- 可用 `--checkpoint-verifier-concurrency` 单独覆盖；
- concurrency 只限制 direct verifier environments，不改变 Pier agent/final verifier concurrency。

### Timeout 和 retry

Direct runner 读取原 task verifier timeout、job override、max timeout 和 multiplier。Infrastructure attempt
最多两次，与 Pier 0.3.0 verifier timeout retry 次数一致。

允许 retry：

- verifier environment start failure；
- verifier timeout；
- artifact transfer failure；
- verifier log download failure；
- 缺失、空或损坏 reward artifact。

不允许 retry：

- 正常 reward `0`；
- 已成功、fingerprint 匹配的 cached result。

每次 attempt 独立记录状态、开始/结束时间、耗时、异常类型和异常消息。

## Failure 与退出语义

### Pair eligibility

只有成功产生、校验并可应用 initial checkpoint 的 trial 才是 eligible pair。没有 initial patch 的
modifier failure/empty patch 不进入分母，但必须进入 coverage 统计。

### Workflow failure

Reviewer/revision/runtime treatment 内部失败不排除 eligible trial：

- final 回退到最后可信 checkpoint；
- initial 与 terminal 相同则 delta 为 0；
- 该 pair 进入 intention-to-treat；
- 该 pair 通常不进入 completed-protocol。

### Verifier failure

Verifier infrastructure failure 在 retry 后仍无 reward 时：

- checkpoint 状态为 missing/error；
- pair 无完整主结果；
- job paired coverage 不完整；
- `eval` 或 `paired resume` 返回非零；
- 所有 generation 和成功 verification 产物保留；
- 输出明确提示再次执行 `paired resume`。

## 分析口径

### Intention-to-treat 主结果

所有 eligible 且 initial/terminal 都有有效 verifier score 的 pair 进入主分析，无论 reviewer 是否正常结束。
该口径回答：实际选择启用 review-loop 后，包括其 runtime 失败在内，整体能带来多少收益。

### Completed-protocol 次结果

只有以下条件成立的 pair 进入次要子集：

- 存在有效 initial checkpoint；
- 配置允许的 attempt retry 后，所有影响流程的 review round 最终都有有效解析结果；
- 所有被要求的 revision 最终正常完成；
- workflow outcome 是 `approved` 或 `max_reviews_reached`。

`max_reviews_reached` 是协议允许的正常终点，应纳入。某个 attempt 失败但在配置允许的 retry 中恢复，不会
排除该 pair。

以下 outcome/reason 只进入 intention-to-treat：

- `degraded`；
- reviewer 最终 timeout/process failure；
- invalid review output 未恢复；
- revision failure；
- post-checkpoint infrastructure failure。

Verifier infrastructure error 不决定 completed-protocol 身份，只决定该 pair 是否有完整评分。

Completed-protocol 只能帮助区分 review 逻辑与 runtime 健康度，不能替代主结果，因为排除困难任务上的 runtime
失败可能系统性高估 reviewer 收益。

### Job 汇总

至少输出：

- total trials；
- eligible / verified / missing pair coverage；
- initial 与 terminal pass rate；
- improved (`0 -> 1`)；
- harmed (`1 -> 0`)；
- unchanged；
- mean paired reward delta；
- 每个实际 revision 的 parent-to-child delta；
- intention-to-treat 汇总；
- completed-protocol 汇总；
- task-clustered bootstrap 95% CI；
- verifier infrastructure error 分类；
- final reuse/direct fallback 数量。

正式 reward 是唯一主指标。F2P、P2P、partial score 和 round delta 是诊断指标。Revision-round delta 的分母
只包含被 reviewer 选择进入该轮 revision 的 trial，存在选择偏差，不作独立因果结论。

## 自动化测试

### TypeScript runtime

- initial checkpoint patch/index；
- 多 revision parent/ordinal；
- no-change revision 不产生 checkpoint；
- approve 后 terminal alias；
- max-reviews final revision；
- reviewer/revision/timeout/infrastructure failure 回退最后可信 checkpoint；
- terminal restore 后 `HEAD`、final patch 和 index 一致；
- index 原子写入和 patch SHA；
- binary patch/apply-check。

### Python schema/completion

- checkpoint schema version 和路径安全；
- parent 单链、ordinal、terminal、hash 校验；
- Pier final fingerprint 匹配时复用；
- final hash/config mismatch 时 direct fallback；
- unique checkpoint 去重；
- job-local cache；
- reward `0` 不 retry；
- infrastructure retry 与 attempt history；
- incomplete coverage 非零状态；
- fake verifier 下的 concurrency；
- resume 幂等性；
- ITT/completed-protocol 分类；
- pair JSONL/CSV/summary；
- CLI 参数和 single-agent 不回归。

### Pier adapter contract

- 固定 Pier version；
- CLI/package version 一致性；
- 私有 method structure guard；
- task/job verifier 配置映射；
- artifact upload 和 reward mapping；
- adapter 不启动 agent 或读取 agent credentials。

### Legacy backfill

- 已知 `20260806-224833` synthetic layout；
- initial/revision/final 提取；
- SHA 去重和 terminal alias；
- 不支持布局 fail closed；
- 全 job 预扫描失败时无部分写入；
- 原 job 文件不被修改。

## 人工 Smoke 交接

实现过程中不启动真实模型 smoke。用户在自动化测试通过后，人工使用
[`wip/one_task.txt`](../one_task.txt) 中的 `abs-module-cache-flags`，参考
[`tmp/smoke.md`](../../tmp/smoke.md) 的两个 collab 方向：

1. OpenCode/DeepSeek modifier + Codex reviewer；
2. Codex modifier + OpenCode/DeepSeek reviewer。

实际 smoke 去掉 `--dry-run`。建议其中一个 job 增加 `--checkpoint-verifier-conformance`。

Smoke 验收项：

- initial checkpoint index 和 patch 存在；
- terminal checkpoint 与 Pier final patch SHA 一致；
- 每个 changed revision 有一个 checkpoint；
- Pier final result 正常导入；
- 非 final unique checkpoint 都有 direct verifier result；
- paired coverage 为 `1/1`；
- paired summary 能展示 initial、terminal 和 delta；
- conformance job 的 direct final reward 与 Pier final reward 一致；
- 完整 job 执行 `paired resume` 为 no-op，不再次启动 verifier。

用户在 smoke 完成后通知结果，再进行 smoke 结果验收和后续修复。

## 实现顺序

1. 实现 runtime `CheckpointCatalog`、可信 terminal restore 和 TypeScript 测试。
2. 实现 Python checkpoint schema 与纯校验测试。
3. 固定 Pier 0.3.0，实作 `PierCheckpointVerifier` adapter 和 contract tests。
4. 实现 `complete_collab_job`、final import、cache、retry、concurrency 和 trial 产物。
5. 将 paired completion 接到现有 collab `eval`，保持 single eval 不变。
6. 增加 `paired resume`。
7. 增加 job 级 pair table、ITT/completed-protocol summary 和诊断指标。
8. 实现严格限定的 `paired backfill`。
9. 运行全部自动化测试并准备人工 smoke 命令与检查清单。

## 已确认的关键决策

- Reviewer treatment 可使用额外计算预算；不做等预算第三支。
- Verifier 完全事后、盲测、不反馈 agent。
- 主指标是正式 reward 的 paired delta。
- 主分析是 intention-to-treat；completed-protocol 仅为次要诊断。
- 所有 collab eval 默认验证 initial、changed revisions 和 final。
- Pier 自带 verifier 继续验证 final；direct runner 只补其他唯一 checkpoint。
- 使用固定 Pier 0.3.0 的内部 verifier path，不使用 apply-patch 模拟 agent。
- 新格式通过 versioned checkpoint index，不从 round 目录猜测。
- 恢复入口收敛为 `paired resume`；历史入口为 `paired backfill`。
- Job 本身是实验根；新增 namespaced paired 产物，不改 Pier `result.json`。
- Cache 第一版只限 job-local。
- Smoke 由用户在实现完成后人工启动，不属于自动化实现步骤。
