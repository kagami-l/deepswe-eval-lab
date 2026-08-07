# Collab 阶段 Patch 事后配对评分设计

状态：设计已确认，待实现。

确认日期：2026-08-07。

## 背景

结果报告
[collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833](results/collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833.md)
的第 7 条建议指出：若要判断 reviewer 是否提升 verifier 分数，不能继续比较两个独立随机 job，
而应对同一个 modifier initial patch 比较直接提交与经过 review-loop 后提交的结果。

当前 collab runtime 已经保存了完成该分析所需的 patch：

- 第一个 `rounds/*-review/patch.diff` 是 reviewer 介入前的 initial patch；
- 后续 `rounds/*-review/patch.diff` 是此前 revision 完成后的 patch；
- `final/patch.diff` 和 Pier `artifacts/model.patch` 表示最终提交 patch；
- Pier 已在正常 `eval` 中验证 `artifacts/model.patch`。

因此不需要创建两个实际 agent 分支，也不需要在正常 `eval` 中增加补充 verifier。正常 `eval` 继续只负责
生成 patch 和验证 final submission；用户在 job 完成后，显式运行独立的 `score-patches` 命令，对已冻结的
initial、revision 和 final patch 统一执行事后评分与配对分析。

这种分离使额外 verifier 的超时、环境故障和 Pier 私有接口变化不会影响昂贵的 agent generation job，
同时保持 reviewer 对 verifier 结果完全盲测。

## 已确认的方案摘要

```text
run_agent_eval.py eval ... --agent collab
  -> 现有流程生成并保存各阶段 patch
  -> Pier 正常验证 artifacts/model.patch
  -> eval 结束，不自动启动额外 verifier

run_agent_eval.py score-patches --job-path jobs/<job-name>
  -> 校验 job 与 trial 布局
  -> 发现 initial / revision / final stage patch
  -> 按完整 fingerprint 去重
  -> 默认用 direct Pier runner 重新评分 final
  -> 评分其他 unique stage patch
  -> 比较 rescored final 与 eval final
  -> 写入 patch score、pair table、coverage 与统计汇总
```

## 目标

1. 对同一个 modifier initial patch 构造 no-review 与 review-loop 的配对反事实。
2. 评分 initial、每个可观察到的 changed revision，以及 final patch。
3. 默认重复评分 final，持续验证事后 direct runner 与正式 Pier eval verifier 的一致性。
4. 不向 modifier 或 reviewer 暴露 verifier 分数、隐藏测试或 verifier 日志。
5. 复用 DeepSWE/Pier 的正式 separate-verifier 路径，不复制 task grader。
6. 不修改 collab runtime 和正常 `eval` 的生命周期、失败语义或退出码。
7. 支持 `score-patches` 中断后的幂等重入，不重新调用模型或重新生成 patch。
8. 同时报告 intention-to-treat 主结果和 completed-protocol 诊断子集。
9. 第一版验证并支持当前 collab round layout 以及指定历史 job `20260806-224833`。

## 非目标

- 本次不设计正式实验的任务规模、统计功效或数据收集计划。
- 本次不加入与 review-loop 等计算预算的 modifier-only continuation 第三支。
- 本次不让 agent 根据 verifier 反馈继续修复。
- 本次不修改 collab runtime 的 patch 落盘行为。
- 本次不增加 versioned checkpoint catalog 或 `checkpoints/index.json`。
- 本次不把事后评分自动接入 `eval`。
- 本次不提供 `paired resume`、`paired backfill` 或其他维护子命令。
- 本次不提供跨 job 的全局 verifier cache。
- 本次不为所有历史 collab runtime 布局提供通用 importer。

## 核心实验定义

实验单位是一个成功产生 initial patch 的 collab trial。主 estimand 是：允许 reviewer 和由其触发的 modifier
revision 使用额外计算预算后，相对于同一个 initial patch 直接提交，正式 verifier reward 改变了多少。

对每个 eligible trial：

```text
no-review score = V(initial patch)
review-loop score = V(final patch)
paired delta = V(final patch) - V(initial patch)
revision delta[r] = V(revision-r patch) - V(parent patch)
```

该估计衡量 reviewer treatment 的边际价值，不声称与“把相同预算继续给 modifier”计算公平。若未来要回答
计算效率问题，应另加 modifier-only continuation 第三支，不改变本设计的主配对。

### 为什么不创建两个实际 agent 分支

no-review 支没有后续 agent 行为，只需要 initial patch 的 verifier 分数。因此：

- 不复制工作区；
- 不复制或重放 modifier session；
- 不重新生成 initial patch；
- 原 modifier session 正常完成 review-loop；
- job 完成后对已落盘的同一 initial patch bytes 进行评分。

“no-review”在这里是同一 initial patch 直接提交给 verifier 的评分反事实，不是另一个真实运行的 agent branch。

### Verifier 盲测

`score-patches` 只能对已结束的 job 运行：

- reward、日志和耗时不进入 reviewer/modifier prompt；
- verifier 阶段不占 agent workflow budget；
- reviewer 无法读取 separate verifier 环境或隐藏测试；
- patch delta 只用于事后分析，不驱动后续 revision。

## 输入与阶段 Patch 发现

### 支持的输入

命令输入是一个现有 Pier job 目录，而不是单独的 patch 文件：

```text
jobs/<job-name>/
├── result.json
├── config.json
└── <task>__<trial-id>/
    ├── result.json
    ├── artifacts/model.patch
    ├── verifier/
    └── agent/system/
        ├── rounds/
        │   ├── 01-review/patch.diff
        │   ├── 03-review/patch.diff
        │   └── 05-review/patch.diff
        └── final/patch.diff
```

第一版只承诺支持当前 collab runtime 的已知布局，并以
`collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833` 作为历史兼容 fixture。其他旧 job 只有在通过
同一严格布局校验时才可处理；不根据相似文件名猜测未知布局。

设计期对该历史 job 的只读核对结果：

- 24/24 trial 都存在第一个 review 前 patch；
- 24/24 的 `final/patch.diff` 与 `artifacts/model.patch` SHA 一致；
- 按 review patch 加必要的 changed final 映射后，24/24 的可观察 stage 数与 `summary.result.checkpoints` 数一致；
- 9 个 trial 的 initial 与 final 相同，其中 8 个首轮 approve、1 个首轮 review 失败后 degraded；其余 15 个发生 revision。

### 阶段映射

按 round 序号排序后：

1. 第一个 `*-review/patch.diff` 映射为 `initial`；
2. 此后每个 `*-review/patch.diff` 映射为上一轮成功 revision 后的 `revision-N`；
3. `final/patch.diff` 映射为 `final`；
4. 如果 final 相对最后一个 review patch 发生变化，它同时表示最后一次 revision 的结果；
5. stage 之间内容 SHA 相同时保留 stage alias，但只执行一次 verifier。

映射必须结合 trial result、round metadata、review/revision count 和 outcome 校验。目录序号只能用于排序，不能
单独作为语义依据。

### Final patch 身份

Pier 正式 eval 实际评分的是 `artifacts/model.patch`。开始评分前必须要求：

```text
SHA256(agent/system/final/patch.diff)
  == SHA256(artifacts/model.patch)
```

只有相等时，二者才被视为同一个 final stage。若不相等，说明 runtime 日志中的 final 与正式提交不是同一个
patch，命令必须在启动 verifier 前 fail closed，不能任选其一继续分析。

### 全 job compatibility scan

`score-patches` 在启动任何 verifier 前完成所选 trial 的只读扫描：

- job 确实来自 collab agent；
- 必需的 job/trial result 和配置可读取；
- round 序号、kind、metadata 和 summary 自洽；
- initial 和 final patch 存在且非空；
- final patch SHA 一致；
- patch 能安全读取，路径没有逃逸 trial；
- task、base commit 和 verifier 配置可解析。

不符合支持 profile 属于 layout incompatibility，而不是 verifier failure。默认对整个选择集 fail closed，不写入
部分评分；使用 `--trial` 时只扫描和处理匹配 trial。

## Verifier 执行策略

### 评分身份不是只有 patch SHA

在 task、base、verifier 配置和运行环境固定时，direct runner 只需要额外输入冻结的 patch，不需要重放 agent。
但 verifier 结果不能抽象成 patch 文本的无条件纯函数。评分 fingerprint 至少包含：

```text
task checksum
base commit
patch SHA-256
Pier version
verifier config digest
verifier image/build-context identity
adapter schema version
```

所有去重、缓存和 final 一致性比较都使用完整 fingerprint；patch SHA 只是其中一项。

### Direct Pier runner

Pier 0.3.0 没有公开的 `verify-artifact` 命令。实现使用一个窄的 `PierPatchVerifier` adapter，固定
`datacurve-pier==0.3.0`，通过 Pier 内部的 `Trial._verify_once()` 进入与正式评分相同的路径：

- 解析原 task/job verifier 配置；
- 从原 task tests build context 创建 fresh separate verifier environment；
- 使用 Pier `ArtifactHandler` 上传已冻结的 `model.patch`；
- 使用 Pier `Verifier.verify()` 执行测试并解析 reward；
- 使用原 task/job 的 verifier env、timeout、resource 和 image 配置。

它绕过 agent setup、agent run、`pre_artifacts.sh` 和 Pier job bookkeeping，但不重写或绕过 verifier 评分逻辑。
因此不需要 apply-patch 模拟 agent，也不需要自建 Docker 评分流程。

### 默认重新评分 final

默认情况下，final patch 与其他 stage patch 一样进入 direct runner。每个 trial 同时记录：

```text
evalFinalReward
rescoredFinalReward
finalConformance = matched | mismatched | unavailable
```

要求比较 Pier 正式 eval 的 canonical reward 与 direct runner 的 canonical reward，并保存完整 normalized reward
payload 的差异，供 F2P/P2P 等诊断。默认重复评分的目的不是替代 Pier 正式结果，而是持续确认后补评分路径没有
发生版本、配置、artifact upload 或 result mapping 漂移。

完整且 fingerprint 匹配的 direct final 结果可在同一次 `score-patches` 的后续幂等重入中复用；“默认重新评分”
是指相对原 `eval` 至少执行一次 direct final verifier。需要再次执行可使用 `--force`。

### 跳过 final 重评

用户可显式指定：

```text
--reuse-final-score
```

此时不启动 direct final verifier，而是复用 Pier eval 已有 final reward。复用仍要求 final patch SHA、task、base、
verifier 配置和 image identity 均可验证；否则 fail closed。输出记录：

```text
finalScoreSource = eval
finalConformance = skipped
```

该 flag 只减少 verifier 成本，不从 stage/pair 输出中删除 final。

### Final 不一致

如果 direct final 与 eval final reward 不一致：

- 不因为 reward 不同而自动重试；
- 保留全部 eval/direct 评分产物和差异；
- trial 标记为 `nonconformant`；
- job conformance coverage 标记不完整；
- 命令返回非零；
- 该 pair 不进入 conformant primary summary，但进入独立 sensitivity/diagnostic 表。

在查明是 verifier nondeterminism、环境身份错误还是 adapter 漂移之前，不静默选择其中一个 final reward 作为正式
配对结论。需要调查性复跑时由用户显式使用 `--force`。

### Pier 私有接口风险

私有接口风险集中在一个 adapter 内：

- `wip/pyproject.toml` 和 lock 固定 `datacurve-pier==0.3.0`；
- 启动时校验 Python package 版本；
- 校验外部 `pier --version` 与 Python package 版本一致；
- 校验依赖的私有方法存在且参数结构符合预期；
- 不兼容时 fail closed，不猜测新语义；
- score manifest 记录 Pier 版本和 adapter schema version；
- 未来可替换为 Pier public verify-artifact interface，而不改变上层模块。

## 深模块与 seam

### PatchDiscovery 模块

核心 interface：

```python
discover_trial_patches(trial_path) -> TrialPatchSet
```

该深模块隐藏：

- 当前 collab layout 识别；
- round metadata 与 summary 交叉校验；
- initial/revision/final stage 映射；
- final/model.patch 身份校验；
- SHA 和完整 scoring identity 构造；
- stage alias 与 parent 关系；
- eligibility 和 incompatibility 诊断。

CLI 和 scoring implementation 不自行解析 `rounds/` 目录名。未来 runtime layout 变化时，只修改或替换 discovery
implementation，不把兼容分支散落在 verifier、summary 和 CLI 中。

### PatchScoring 模块

Host 侧核心 interface：

```python
score_patch_job(job_path, options, verifier) -> PatchScoreSummary
```

该深模块隐藏：

- job/trial 发现和 compatibility preflight；
- PatchDiscovery 调用；
- unique fingerprint 去重；
- job-local cache；
- verifier concurrency 和 infrastructure retry；
- final conformance；
- trial score 落盘；
- pair construction、coverage 和统计汇总；
- 幂等重入和退出状态。

CLI 只解析参数、调用该 interface、打印摘要并返回状态码。

### PatchVerifier seam

验证 seam 的小 interface：

```python
verify_patch(request) -> VerificationRecord
```

有两个 adapter：

- production `PierPatchVerifier`；
- 自动化测试使用的 fake verifier adapter。

Pier 私有实现、environment 创建、artifact upload 和 reward mapping 知识只能存在于 production adapter。

## 命令界面

唯一新增命令：

```bash
uv run python wip/scripts/run_agent_eval.py score-patches \
  --job-path jobs/<job-name>
```

参数：

```text
--job-path PATH          必需；现有 Pier job 目录
--trial GLOB             可选；只扫描和评分匹配的 trial，用于 verifier-only smoke
--concurrency N          可选；direct verifier environment 并发，默认 2
--reuse-final-score      可选；跳过 direct final verifier，复用已校验的 eval final
--force                  可选；忽略已有 direct score cache，重新执行适用的 verifier
```

`--force` 不覆盖 `--reuse-final-score`：两者同时出现时，非-final patch 强制重评，final 仍复用 eval score。

命令不调用 modifier/reviewer，不重新生成 patch，不修改正常 `eval` 的任何结果。重复运行时只补齐缺失、损坏或
允许重试的评分并重新生成派生汇总；完整、fingerprint 匹配的 job 上是幂等 no-op。

不提供 `backfill`：指定历史 job 与未来 job 都经同一个 `score-patches` interface。是否支持由严格 discovery
profile 决定，而不是由命令名称决定。

## 产物布局

Pier job 本身就是分析根目录，不增加额外 experiment 外层目录。新增产物使用 `patch-scores` namespace，
不回写 `agent/system/rounds/`，不修改 Pier `result.json`：

```text
jobs/<job-name>/
├── result.json
├── config.json
├── patch-scores/
│   ├── manifest.json
│   ├── stages.jsonl
│   ├── stages.csv
│   ├── pairs.jsonl
│   ├── pairs.csv
│   └── summary.json
└── <task>__<trial-id>/
    ├── result.json
    ├── artifacts/model.patch
    ├── agent/system/rounds/...
    ├── agent/system/final/patch.diff
    └── patch-scores/
        ├── stages.json
        └── results/<fingerprint-id>/
            ├── result.json
            ├── artifacts/model.patch
            └── verifier/
```

`stages.json` 保存 stage 到 immutable source patch、parent stage、SHA、fingerprint 和 canonical result 的映射。
相同 fingerprint 的多个 stage 只保存一套 verifier result。Final result 另记录 eval result 引用和 conformance
comparison，不复制或修改原 verifier 目录。

机器可读产物保留在 gitignored 的 `jobs/` 中。人工分析报告继续写入 `wip/docs/results/`，相对链接引用 job
产物。

## Cache、并发与 retry

### Cache

第一版 cache 只在 job 内共享，用于：

- 中断后重入；
- stage alias 去重；
- 同一 job 内完整 fingerprint 相同的 patch 去重。

不跨 job 复用，避免不同 task/runtime 配置误命中和掩盖 verifier nondeterminism。

只有状态成功、result 可解析且 fingerprint 完整匹配的记录才能跳过。仅凭目录或 `reward.json` 存在不能视为
cache hit。

### 并发

- 默认 `--concurrency 2`；
- 并发只限制 direct verifier environments；
- 不影响已经完成的 Pier agent/final verifier；
- job/trial 汇总写入由单一协调器串行完成，避免并发写坏 manifest。

### Timeout 和 retry

Direct runner 读取原 task verifier timeout、job override、max timeout 和 multiplier。Infrastructure attempt
最多两次，与 Pier 0.3.0 verifier timeout retry 次数一致。

允许 retry：

- verifier environment start failure；
- verifier timeout；
- artifact transfer failure；
- verifier log download failure；
- 缺失、空或损坏 reward artifact。

不允许自动 retry：

- 正常 reward `0`；
- direct final 与 eval final reward 不一致；
- 已成功且 fingerprint 匹配的 cached result。

每次 attempt 独立记录状态、开始/结束时间、耗时、异常类型和异常消息。

## Failure 与退出语义

### Pair eligibility

只有成功产生、校验并可应用 initial patch 的 trial 才是 eligible pair。没有 initial patch 的 modifier failure 或
empty patch 不进入 paired denominator，但必须进入 coverage 统计。

### Workflow failure

Reviewer/revision/runtime treatment 内部失败不排除 eligible trial：

- eval 保存的 final submission 是 review-loop treatment 的实际结果；
- initial 与 final 相同则 delta 为 0；
- 该 pair 进入 intention-to-treat；
- 该 pair 通常不进入 completed-protocol。

离线 scorer 不尝试修复、恢复或重新解释 runtime worktree，只评分 eval 已经落盘并正式提交的 patch。

### 退出状态

以下情况返回非零，同时保留已经完成的有效产物：

- layout incompatibility 或 final patch 身份不一致；
- verifier infrastructure retry 耗尽，导致必要 stage 缺分；
- 默认 final conformance 出现 mismatch/unavailable；
- manifest、cache 或 result 损坏且无法安全重建。

正常 reward `0`、reviewer degraded 或 paired delta 为负都不是命令失败。

指定 `--reuse-final-score` 时，`finalConformance = skipped` 是用户选择的正常状态，只要 final score 能被安全复用，
不会导致非零退出。

## 分析口径

### Intention-to-treat 主结果

所有 eligible、initial/final 都有有效 score 且 final conformance 满足所选模式的 pair 进入主分析，无论 reviewer
workflow 是否正常结束。该口径回答：实际选择启用 review-loop 后，包括其 runtime 失败在内，整体带来多少收益。

默认模式要求 direct final 与 eval final matched；`--reuse-final-score` 模式使用已校验身份的 eval final，并明确
标记 conformance skipped。Nonconformant pair 不静默混入主结果。

### Completed-protocol 次结果

只有以下条件成立的 pair 进入诊断子集：

- 存在有效 initial patch；
- 配置允许的 attempt retry 后，所有影响流程的 review round 最终都有有效解析结果；
- 所有被要求的 revision 最终正常完成；
- workflow outcome 是 `approved` 或 `max_reviews_reached`。

`max_reviews_reached` 是协议允许的正常终点，应纳入。某个 attempt 失败但在允许 retry 中恢复，不排除该 pair。

以下 outcome/reason 只进入 intention-to-treat：

- `degraded`；
- reviewer 最终 timeout/process failure；
- invalid review output 未恢复；
- revision failure；
- post-checkpoint infrastructure failure。

Verifier infrastructure error 不决定 completed-protocol 身份，只决定该 pair 是否具有完整评分。Completed-protocol
只能帮助区分 review 逻辑与 runtime 健康度，不能替代主结果。

### Job 汇总

至少输出：

- total / selected trials；
- eligible / verified / missing pair coverage；
- final conformance matched / mismatched / skipped / unavailable；
- initial 与 final pass rate；
- improved (`0 -> 1`)；
- harmed (`1 -> 0`)；
- unchanged；
- 不一致对 2×2 表及对应 task/trial 清单；
- mean paired reward delta；
- 每个实际 revision 的 parent-to-child delta；
- intention-to-treat 汇总；
- completed-protocol 汇总；
- McNemar 或 exact paired sign test；
- task-clustered bootstrap 95% CI；
- verifier infrastructure error 分类；
- unique/scored/cached patch 数量。

正式 reward 是唯一主指标。F2P、P2P、partial score 和 revision delta 是诊断指标。Revision delta 的分母只包含
被 reviewer 选择进入该轮 revision 的 trial，存在选择偏差，不作独立因果结论。首轮 approve、degraded before
revision 或 no-change revision 可能产生 `initial == final`，其 paired delta 为 0。

## 自动化测试

### Patch discovery 与 layout

- 当前 runtime 的 initial/revision/final 映射；
- final revision 没有下一轮 review 时由 final patch 补齐；
- stage SHA alias 和 parent 关系；
- final patch 与 `artifacts/model.patch` 身份校验；
- trial result、round metadata 和 revision count 交叉校验；
- modifier failure/empty patch eligibility；
- 未知、不完整或路径逃逸布局 fail closed；
- 全选择集 preflight 失败时不产生部分 score。

### Patch scoring

- unique fingerprint 去重；
- job-local cache 与幂等重入；
- 默认 direct final re-score；
- `--reuse-final-score` 安全复用；
- final matched/mismatched/unavailable；
- reward `0` 不 retry；
- infrastructure retry 与 attempt history；
- incomplete coverage 非零状态；
- fake verifier 下的 concurrency；
- ITT/completed-protocol 分类；
- McNemar inputs、pair JSONL/CSV 和 summary；
- 原 eval/result/round 文件不被修改；
- CLI 参数与既有 `eval` 不回归。

### Pier adapter contract

- 固定 Pier version；
- CLI/package version 一致性；
- 私有 method structure guard；
- task/job verifier 配置映射；
- artifact upload 和 reward mapping；
- direct final 与 Pier fixture result 一致；
- adapter 不启动 agent 或读取 agent credentials。

## 人工 Smoke 交接

实现过程中不启动真实模型 smoke。用户在自动化测试通过后，人工使用
[`wip/one_task.txt`](../one_task.txt) 中的 `abs-module-cache-flags`，参考
[`tmp/smoke.md`](../../tmp/smoke.md) 的两个 collab 方向：

1. OpenCode/DeepSeek modifier + Codex reviewer；
2. Codex modifier + OpenCode/DeepSeek reviewer。

每个 smoke job 的正常 `eval` 完成后，人工执行：

```bash
uv run python wip/scripts/run_agent_eval.py score-patches \
  --job-path jobs/<smoke-job-name> \
  --concurrency 1
```

Smoke 验收项：

- `eval` 行为、退出状态和原始产物与改造前一致；
- discovery 正确识别 initial、changed revisions 和 final；
- final patch 与 Pier `artifacts/model.patch` SHA 一致；
- initial、revision 和 final unique patch 都有 direct verifier result；
- direct final reward 与 Pier eval final reward 一致；
- paired coverage 为 `1/1`；
- summary 展示 initial、final、delta 和 conformance；
- 完整 job 再次执行 `score-patches` 为幂等 no-op；
- 指定 `--reuse-final-score --force` 时 final 仍不启动 direct verifier。

用户在 smoke 完成后通知结果，再进行 smoke 结果验收和后续修复。

## 实现顺序

1. 在 `wip/agent_eval/cli.py` 增加顶层 `score-patches` 命令及参数测试。
2. 实现 `PatchDiscovery`、当前 layout preflight 和 synthetic fixture 测试。
3. 固定 Pier 0.3.0，实现 `PierPatchVerifier` adapter 和 contract tests。
4. 实现 `PatchScoring`、fingerprint/cache、并发、retry 和 trial 产物。
5. 实现默认 final re-score、`--reuse-final-score` 和 conformance 退出语义。
6. 实现 job 级 stage/pair table、ITT/completed-protocol、McNemar 和 bootstrap 汇总。
7. 用 fixture 验证 `20260806-224833` layout，不在实现过程中启动真实 verifier/model smoke。
8. 运行全部自动化测试并准备人工 smoke 命令与检查清单。
9. Phase 0 执行：人工 smoke 通过后，对 `20260806-224833` 执行首次全量 `score-patches`
   （可先用 `--trial` 对单个多 revision trial 做 verifier-only 预检），核对 final conformance 覆盖。
10. Phase 0 交付：基于 `patch-scores` 汇总在 `wip/docs/results/` 撰写配对分析文档
    （不一致对 2×2 表、每轮 revision delta 轨迹、ITT 与 completed-protocol 汇总），
    并据其方向决定后续新 collab job 的扩样规模。

## 已确认的关键决策

- Reviewer treatment 可使用额外计算预算；不做等预算第三支。
- 配对来自同一 trial 的 initial 与 final，不创建两个实际 agent 分支。
- Verifier 完全事后、盲测、不反馈 agent。
- 正常 `eval` 不变，不自动启动补充 verification。
- 唯一新增入口是顶层 `score-patches`，不增加 `paired` 命令组或 `backfill`。
- `score-patches` 对 initial、changed revisions 和 final 统一评分。
- 默认 direct re-score final 并与 Pier eval final 比较；`--reuse-final-score` 可显式跳过。
- 主指标是正式 reward 的 paired delta；主分析是 intention-to-treat。
- Completed-protocol、F2P/P2P 和 revision delta 仅用于诊断。
- 使用固定 Pier 0.3.0 的内部 verifier path，不使用 apply-patch 模拟 agent。
- 当前 round layout 是严格校验的输入 profile，不增加 runtime checkpoint catalog。
- Job 本身是分析根；新增 namespaced `patch-scores` 产物，不改 Pier `result.json` 或 round 日志。
- Cache 第一版只限 job-local，身份使用完整 scoring fingerprint。
- Smoke 由用户在实现完成后人工启动，不属于自动化实现步骤。
