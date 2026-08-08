# Collab `score-patches` 实现 Review

- 评审时间：2026-08-08 11:39:58（Asia/Shanghai）
- 评审范围：提交 `64104d8`（评审时为 staged changes，基线 `99d0d9c`）
- 规格来源：`wip/docs/collab-paired-checkpoint-verification-design.md`
- 评审方式：Standards 与 Spec 双轴 review

涉及文件（12 个，约 +4,849/−7）：

- `wip/agent_eval/cli.py`
- `wip/agent_eval/fixture_collab.py`
- `wip/agent_eval/patch_discovery.py`
- `wip/agent_eval/patch_scoring.py`
- `wip/agent_eval/patch_verifier.py`
- 对应 Python 测试
- `wip/pyproject.toml`、`wip/uv.lock`
- `wip/docs/results/collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833-paired-rescore.md`

## 结论

实现方向与模块划分基本符合方案，但暂不建议按当前状态继续作为已完成实现交付。

Spec 轴发现 3 个 P1、2 个 P2 和 1 个 scope 问题。其中三个 P1 可能导致：

- 包含 modifier failure/empty patch 的整个 job 无法评分；
- `task.toml` 改变后错误复用旧 cache；
- 带 job-level artifacts 的 patch 使用与正式 eval 不同的评分输入。

Standards 轴另有 1 个文档化依赖边界冲突和 1 个非阻塞代码气味。

## Standards

### [Hard] 本地 Pier 依赖与 WIP 环境文档冲突

位置：

- `wip/pyproject.toml:6-8`
- `wip/uv.lock`
- 对照 `wip/README.md:3-5`、`wip/README.md:25-26`

本次改动将 `datacurve-pier==0.3.0` 安装进本地 WIP 环境，并把完整依赖图写入
`uv.lock`。但 `wip/README.md` 明确规定该环境“不重复安装 Pier”，并说明本地环境
不包含 `datacurve-pier`。

这与新设计要求固定 Pier Python package 存在张力。需要明确选择并同步文档：

1. 保留当前实现，更新 `wip/README.md`，说明 `score-patches` 需要本地固定 Pier；或
2. 保留既有环境边界，把私有 adapter 放进 Pier tool environment 执行。

### [Judgement] 评分状态使用较多裸字符串

位置：

- `wip/agent_eval/patch_discovery.py:40`
- `wip/agent_eval/patch_verifier.py:53`
- `wip/agent_eval/patch_scoring.py:111-112`

`stage_id`、verification status、score source、conformance 等状态都用裸字符串表示，
后续逻辑重复比较 `"final"`、`"success"`、`"missing"`、`"matched"`、`"skipped"`。

这是 possible Primitive Obsession，不阻塞功能；可用 `Literal` type alias 或 enum
集中领域词汇并减少非法状态。

## Spec Findings

### [P1] 真实 modifier failure/empty-patch layout 会被误判为不兼容

位置：

- `wip/agent_eval/patch_discovery.py:229-263`
- `wip/agents/deep_swe_collab/runtime/src/direct-engine.ts:406-415`
- `wip/agents/deep_swe_collab/runtime/src/direct-engine.ts:542-545`
- `wip/agent_eval/fixture_collab.py:148-217`

设计要求 modifier failure 或 empty patch 不进入 paired denominator，但必须以
ineligible trial 进入 coverage。

真实 runtime 无论 initial modifier 是否成功，都会在 `finalize()` 中写出
`agent/system/final/patch.diff`。Discovery 却只有在“没有 review round 且 final 文件
不存在”时才返回 `eligible=False`。因此真实失败 trial 会继续落入：

- `no review rounds with a pre-review patch`；
- empty/missing final/model patch；
- `LayoutError`；
- 全 job compatibility scan 失败。

现有 `make_failed_modifier_trial()` fixture 没有生成 runtime 必写的 final 文件，所以
测试通过但没有覆盖真实布局。

建议：根据 summary outcome、initial checkpoint/round 状态和 patch 内容判断是否产生
initial patch；fixture 必须复现真实 finalize 产物。

### [P1] `task.toml` 改变后可能错误命中旧 cache

位置：

- `wip/agent_eval/patch_discovery.py:197-199`
- `wip/agent_eval/patch_scoring.py:148-169`
- `wip/agent_eval/patch_scoring.py:172-189`
- `wip/agent_eval/patch_verifier.py:261`

Fingerprint 直接使用旧 `result.json.task_checksum`，但没有根据当前 task 目录重算并
核对 checksum；`build_context_digest()` 又只 hash `tests/`。Direct runner 则会通过
`Task(task_dir=...)` 读取当前 `task.toml`。

因此仅修改 `task.toml` 中的 verifier image、user 或 environment 配置时：

- direct runner 行为发生变化；
- tests build-context digest 不变；
- 旧 recorded task checksum 仍被写入 fingerprint；
- 已成功 cache 可能被错误复用。

建议：重算当前完整 task checksum 并与 eval 记录值 fail-closed 校验；或把 effective
task/verifier environment config 纳入 fingerprint。应补 `task.toml` 改变导致 cache
失效的测试。

### [P1] Direct runner 未复用规定路径，并遗漏 job-level artifacts

位置：

- `wip/agent_eval/patch_discovery.py:379-383`
- `wip/agent_eval/patch_scoring.py:287-297`
- `wip/agent_eval/patch_verifier.py:261-346`

设计要求 adapter 通过 Pier `Trial._verify_once()` 进入正式评分路径，并复用原
task/job verifier 配置。

当前实现自行组装 `EnvironmentFactory`、`ArtifactHandler` 和 `Verifier`。Discovery
只保留 environment/verifier/timeout 配置，没有保留 `TrialConfig.artifacts`；scorer
也没有传入 `config.artifacts`，所以 adapter 只上传 task artifacts 和默认空的
`extra_artifacts`。

带额外 artifact 的 eval 会使用不同评分输入。默认 final 重评通常能把问题暴露为
conformance mismatch，但 `--reuse-final-score` 会跳过该保护，initial/revision 可能
静默得到错误分数。

建议优先复用 `Trial._verify_once()`；若继续使用窄重实现，则必须完整复现 trial
artifacts、source/target artifact path convention、environment delete 等语义，并把
所有影响评分的配置纳入 fingerprint。对于无法冻结的额外 stage artifact，应该
fail closed，而不是混用 final artifact。

### [P2] 损坏的 success cache 无法通过普通重入修复

位置：`wip/agent_eval/patch_scoring.py:251-275`

Cache scan 只检查：

- `status == "success"`；
- fingerprint 是 object；
- `fingerprintId` 与目录名一致。

它没有检查 `rewards` 是否为 object，也没有验证 canonical `reward` 是否存在且类型
合法。一个 fingerprint 正确但 `rewards` 缺失/损坏的 success record 仍会命中 cache，
之后 pair 被标记 incomplete。再次运行 `score-patches` 仍命中同一损坏 cache，只能
依靠 `--force` 手工绕过，与设计中的“普通重入补齐损坏评分”不符。

建议：cache hit 前完整验证 result schema 和 canonical reward；损坏记录自动转为
pending work。补一个不使用 `--force` 即可恢复的测试。

### [P2] Summary 缺少完整二元结果 2×2 表

位置：`wip/agent_eval/patch_scoring.py:366-408`

设计要求输出配对二元结果的 2×2 表。当前 summary 只有：

- improved (`0 -> 1`)；
- harmed (`1 -> 0`)；
- unchanged。

这会把 `0 -> 0` 与 `1 -> 1` 合并，无法恢复完整四格表。McNemar p 和 discordant
task/trial 清单已经存在且计算正确。

建议额外输出四个显式计数：`failedBoth`、`improved`、`harmed`、`passedBoth`。

### [Scope] 在人工 smoke 前提交了完整历史 job 分析

位置：

- `wip/docs/results/collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833-paired-rescore.md:19-43`
- `wip/docs/results/collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833-paired-rescore.md:135-136`

设计与用户约定是：实现过程中不启动真实模型 smoke，自动化测试完成后由用户人工
运行 two-direction smoke，再通知验收。实现顺序也要求只用 fixture 验证历史 layout，
不启动真实 verifier/model smoke。

新增报告却声称已经完成 49 次真实 verifier、24/24 final conformance matched，且
“等价性与幂等性已在真实 job 上验收”。如果这不是用户另行授权的 verifier-only
运行，应把该结果报告从当前实现交付中移除，待人工 smoke 后再提交；至少不能把
历史 job replay 表述成用户约定的 smoke 验收。

## 正面观察

- CLI 入口保持为单层 `score-patches`，没有重新引入 `paired` 命令组或 backfill。
- `PatchDiscovery`、`PatchScoring`、`PatchVerifier` 的职责总体集中，CLI 没有泄漏
  round layout 或 Pier 私有实现知识。
- 默认 final direct re-score、`--reuse-final-score`、conformance 非零退出、ITT 与
  completed-protocol 主次口径均有相应测试。
- SHA alias、full fingerprint、并发上限、retry、reward 0 不重试、幂等 cache、
  McNemar 与 task-clustered bootstrap 均已实现。
- 对目标历史 job 的 discovery read-only test 覆盖 24 个 trial，并验证了 9 个
  `initial == final` trial。

## 验证结果

| 检查项 | 结果 |
| --- | --- |
| staged Python 文件 Ruff | 通过 |
| `agent_eval` unittest | 76/76 通过 |
| `git diff --cached --check` | 通过 |
| 全仓 Ruff | 被未 staged 的既有 `scripts/official_trials_to_pier_jobs.py:20` unused import 阻塞，与本次改动无关 |
| 真实 verifier | Review 过程中未启动；仅只读检查已有 `jobs/.../patch-scores` 产物 |

## 建议处理顺序

1. 修复 modifier failure/empty-patch eligibility，并让 fixture 复现真实 runtime layout。
2. 修复 task identity/fingerprint，保证 task 配置变化不会命中旧 cache。
3. 收敛 direct Pier 路径并处理 job-level/额外 artifacts。
4. 修复损坏 success cache 的自动恢复。
5. 补完整 2×2 summary。
6. 同步 `wip/README.md` 的 Pier 依赖说明。
7. 确认历史 job 分析是否经过用户授权；再决定是否保留结果报告。

## 汇总

- Standards：2 项；最严重的是 Pier 依赖模型与文档化环境边界冲突。
- Spec：6 项；最严重的是 modifier-failure 处理、task/cache identity 和 direct
  verifier artifact 口径三个 P1。

---

## 处理情况

- 处理时间：2026-08-08
- 修复提交：`c94c171`（基线 `64104d8`，另有 review 文档提交 `d7861d9`）
- 验证：`agent_eval` unittest 84/84 通过；`agent_eval/` Ruff 通过

| 条目 | 处理 | 说明 |
| --- | --- | --- |
| [P1] modifier failure/empty-patch eligibility | 已修 | 改判据 + fixture 复现真实布局 + 真实数据回归 |
| [P1] `task.toml` 变更命中旧 cache | 已修 | fingerprint 新增 `taskConfigDigest` |
| [P1] direct runner 路径与 artifacts | 部分采纳 | artifacts fail closed；`_verify_once()` 一节改为同步设计文档 |
| [P2] 损坏 success cache 无法自动恢复 | 已修 | cache hit 增加 canonical reward 校验 |
| [P2] summary 缺完整 2×2 | 已修 | 新增 `twoByTwo` 四格计数 |
| [Standards] Pier 依赖与文档冲突 | 已修 | 按选项 1 更新 `wip/README.md` |
| [Standards] 裸字符串 primitive obsession | 不处理 | judgement 项，改动面大于收益 |
| [Scope] 历史 job 分析 | 保留报告 + 修措辞 | 该运行为人工授权行为，见下 |

### [P1] modifier failure/empty-patch eligibility

Review 结论成立，且已在真实数据上复现。评审引用的 `wip/agents/deep_swe_collab/` 是过时副本，
但活代码 `wip/agents/deep_swe_agent/runtime/src/direct-engine.ts:605` 的 `finalize()` 同样在失败路径
执行，无条件写出空的 `final/patch.diff`、`final/git-status.txt` 和 `artifacts/model.patch`。

修复前对真实 trial
`jobs/unified-collab-05_sample_confirm-12-tasks-20260804-200817/tomlkit-toml-table-converters__b8DBQ5j`
（outcome `timeout`、0 checkpoint）执行 discovery 会抛
`LayoutError: no review rounds with a pre-review patch`，并因全 job fail-closed 使整个 job 无法评分。

改为以 summary 的 checkpoint 列表为判据：

- 零 checkpoint 且 final/model patch 均为空 → `eligible=False`、`ineligible_reason=no_initial_patch`，进入 coverage；
- 零 checkpoint 却存在 review/revision round 或非空 final patch → 自相矛盾布局，fail closed。

`make_failed_modifier_trial()` 现在复现真实 finalize 产物（空 patch 文件、空 `checkpoints`、
非 deliverable outcome），并新增针对上述真实 trial 的回归测试。

### [P1] `task.toml` 变更命中旧 cache

结论成立。fingerprint 新增 `taskConfigDigest`（当前 `task.toml` 内容摘要），与 eval 记录的
`taskChecksum` 并存：前者描述 adapter 实际读取的定义，后者描述 eval 当时的 task。新增测试验证
修改 `task.toml` 后只有该 task 的 patch 重新评分，其他 task 仍命中 cache。

### [P1] direct runner 路径与 artifacts

拆分处理：

- **artifacts 部分已修**。`TrialPatchSet` 保留 `TrialConfig.artifacts`；任一 eligible trial 声明了
  job-level artifacts 即 fail closed（这些文件产自已销毁的 agent 容器，无法从冻结 patch 复现）。
  补充事实：目标历史 job 全部 24 个 trial 的 `config.artifacts` 均为 `[]`，task 级
  `artifacts = ["/logs/artifacts/model.patch"]` 本就已正确传入，因此既有结论不受影响。
- **`Trial._verify_once()` 部分未按原样采纳**。`Trial` 无法脱离完整 agent/environment 配置构造，
  事后评分既无 agent 也不需要它。经确认后改为同步规格：设计文档现描述 adapter 复用
  `_verify_once()` 在 separate 模式下所走的同一条内部链路，并说明不直接调用的原因。

### [P2] 损坏 success cache

结论成立。cache hit 现在额外要求 `rewards` 为 object 且 canonical `reward` 为合法数值；
不满足者视同不存在，由普通重入自动补跑，无需 `--force`。新增对应测试。

### [P2] 完整 2×2

结论成立。summary 的 ITT 与 completed-protocol 口径均新增 `twoByTwo`
（`failedBoth` / `improved` / `harmed` / `passedBoth`），四格之和等于 complete pair 数。

### [Standards] Pier 依赖与文档冲突

按选项 1 处理：保留本地固定 `datacurve-pier==0.3.0`，更新 `wip/README.md` 说明
`score-patches` 需要进程内导入 Pier、版本被钉死并在启动时 fail-closed 校验，
同时修正"本地环境不安装 datacurve-pier"的过期表述。

### [Standards] 裸字符串

不处理。属 judgement 项、不影响正确性；改为 enum/Literal 需改动三个模块及全部测试断言。

### [Scope] 历史 job 分析

**该运行是人工授权行为，报告保留。** Phase 0（对历史 job 的 verifier-only 回放）是用户在设计
定稿时要求补入实现顺序第 9–10 步的交付项；两次运行均由用户亲自执行并回报结果，实现过程中
未自行启动任何模型或 verifier。

采纳其措辞意见：报告开头与结尾已明确区分"历史 job 的 verifier-only 回放（已完成）"与
"设计验收清单中的两方向 collab smoke（尚未执行）"，避免把前者表述为后者的验收。

### 附带影响

fingerprint 结构变更使目标历史 job 已有的 49 份 cache 记录不再匹配：数据未删除、既有结论
（task 与 verifier 均未变化）依然成立，但若重新执行 `score-patches`，将重新评分全部 unique patch。

### 未处理的既有问题

全仓 Ruff 仍被 `wip/scripts/official_trials_to_pier_jobs.py:20` 的 unused import 阻塞。该问题来自
更早的提交 `c06bc74`，与本次改动无关，未一并修改以免混淆 diff。
