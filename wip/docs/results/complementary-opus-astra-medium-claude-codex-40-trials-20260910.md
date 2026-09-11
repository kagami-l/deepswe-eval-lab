# Claude → Codex：Opus/Astra 互补任务集 4 次重复汇总

统计日期：2026-09-10。范围为 complementary-opus-astra-medium.txt 的 10 题、每题 4 次，共 40 个 trial。

**Initial 24/40（60%）→ Final 21/40（52.5%），净减 3 次通过，即 −7.5 个百分点。4 次修好、7 次改坏；修好来自历史 Astra 强题，全部回退来自历史 Opus 强题。** 最稳定的负向模式是 ts-pattern 四次从通过变为失败，而不是随机分散的退化。

## 数据范围与完整性

| Job 后缀 | 次数/题 | 运行并发 | Initial | Final | 原始评分对照 |
|---|---:|---:|---:|---:|---|
| [20260909-141135](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-141135/patch-scores/pairs.csv) | 1 | 1 | 5/10 | 5/10 | 3 matched，7 unavailable |
| [20260909-225214](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/patch-scores/pairs.csv) | 2 | 2 | 12/20 | 10/20 | 20 matched，0 unavailable |
| [20260910-113555](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260910-113555/patch-scores/pairs.csv) | 1 | 1 | 7/10 | 6/10 | 10 matched，0 unavailable |

- 模型与工作流配置完全一致：Modifier = Claude Code / claude-opus-5 / high；Reviewer = Codex / gpt-6-astra / medium。每题 task_checksum 跨运行一致。第二组运行并发为 2，其余为 1；并发可能影响耗时/超时，因此不把组间时间差全部归因于模型。
- Runtime 镜像为 `deep-swe/agent-runtime:86d93103f53a80a1`，Codex CLI/SDK 0.153.4、Claude Agent SDK 0.3.266、cligent 0.27.0。最多 3 轮 review、每 turn 最多 2 次尝试；任务硬超时 5400 秒，清理预留 300 秒，事件静默超时 900 秒。
- 139 个不同 patch 均有成功补评分，覆盖 155 条阶段记录；40/40 对完整，无 verifierErrors，无 final conformance mismatch。
- 最新一组中断后以并发 3 续评，复用 12 个成功缓存，新增评分 23 个，合计 35 个不同 patch。缓存复用没有造成缺失评分。
- 第一组 7 个原始 verifier 构建异常已通过补评补齐；可对照的其余 33 个 final 全部 matched。本报告按全部 40 对计算，不照搬脚本因缺少原始对照而过滤后的统计。
- 不纳入最初错误版本、重启前未完成等其他 job；initial 是同一个 collab 运行中首次审查前的 patch，不是独立 single-agent 实验。
- [40 行 trial 汇总](complementary-opus-astra-medium-claude-codex-40-trials-20260910.csv)；[Initial/Final 测试明细](complementary-opus-astra-medium-claude-codex-40-trials-20260910-initial-final-tests.csv)；[机器可读汇总](complementary-opus-astra-medium-claude-codex-40-trials-20260910.json)。R1 为第一组，R2/R3 为第二组每题按启动时间排列的两次执行，R4 为第三组；它们不是四次同步启动的全局实验。

## 逐题结果

历史强侧来自筛选任务时的 mini-swe-agent 数据，不代表当前 Claude Code/Codex 的单体基线。

| Task | 历史强侧 | Initial | Final | 四次 Final（R1/R2/R3/R4） | 修好 / 改坏 |
|---|---|---:|---:|---|---:|
| `wazero-multi-module-snapshots` | Opus | 4/4 | 2/4 | 1 / 0 / 0 / 1 | 0 / 2 |
| `ts-pattern-match-each` | Opus | 4/4 | 0/4 | 0 / 0 / 0 / 0 | 0 / 4 |
| `python-statemachine-state-data-scoping` | Opus | 2/4 | 2/4 | 0 / 0 / 1 / 1 | 0 / 0 |
| `helm-array-merge-strategies` | Opus | 2/4 | 1/4 | 0 / 0 / 0 / 1 | 0 / 1 |
| `testem-bail-on-test-failure` | Opus | 4/4 | 4/4 | 1 / 1 / 1 / 1 | 0 / 0 |
| `httpx-streaming-json-iteration` | Astra | 1/4 | 3/4 | 1 / 1 / 1 / 0 | 2 / 0 |
| `koota-deferred-mutation-buffer` | Astra | 0/4 | 1/4 | 0 / 0 / 1 / 0 | 1 / 0 |
| `bandit-interprocedural-taint-checks` | Astra | 4/4 | 4/4 | 1 / 1 / 1 / 1 | 0 / 0 |
| `optique-conditional-option-dependencies` | Astra | 2/4 | 2/4 | 0 / 0 / 1 / 1 | 0 / 0 |
| `scc-bounded-memory-spilling` | Astra | 1/4 | 2/4 | 1 / 0 / 1 / 0 | 1 / 0 |

## Initial → Final 变化

| 转移 | 次数 | 比例/解释 |
|---|---:|---|
| 通过 → 通过 | 17 | 24 次初始成功中的 17 次保留 |
| 失败 → 通过 | 4 | 初始失败 16 次中的 25% |
| 通过 → 失败 | 7 | 初始成功 24 次中的 29.2% |
| 失败 → 失败 | 12 | 初始失败中的 75% |

- 修好：httpx 2 次、koota 1 次、scc 1 次。全部属于历史 Astra 强侧，说明 reviewer 确实可以补上其中部分实现缺口。
- 改坏：ts-pattern 4 次、wazero 2 次、helm 1 次。全部属于历史 Opus 强侧；修复弱项的收益被强项回退抵消。
- 历史 Opus 强的 5 题：16/20 → 9/20（−35 个百分点）；历史 Astra 强的 5 题：8/20 → 12/20（+20 个百分点）。
- bandit、testem 稳定保持 4/4；ts-pattern 稳定从 4/4 降到 0/4。其余 7 题 final 四次有波动，稳定性弱于另一方向。
- 75 次已评分的中间修订转移为：4 次 0→1、7 次 1→0、39 次 1→1、25 次 0→0。未见 binary reward 下降后再恢复的记录。
- 5 次 timeout degraded 均纳入全量统计，其中 scc 和 koota 各有一次 0→1。若只看完整协议、排除超时交付，会丢掉实际有效的修复；该子集是 24/35 → 19/35，不应替代全量结果。

## Reviewer 行为、耗时与两方向比较

- 40 次 outcome：24 max_reviews_reached（60%）、11 approved（27.5%）、5 timeout degraded（12.5%）。
- 共 114 次有效 review：103 revise（90.4%）、11 approve（9.6%）；总 revisionCount 99。多数任务持续收到修订要求，最终因轮数或预算耗尽交付。
- 11 次 approved 中只有 3 次 final 通过；8 次失败包含全部 4 次 ts-pattern 回退、2 次 wazero 回退，以及未修好的 python-statemachine/httpx 各一次。reviewer 的“已解决”判断与隐藏评分存在明显错位。
- 模型 turn wall time 合计 33.86 小时：Modifier 30.96 小时、Reviewer 2.91 小时。平均每 trial Modifier 46.43 分钟、Reviewer 4.36 分钟；初始修改平均 20.34 分钟，完整协作合计平均 50.79 分钟。它们是角色执行时间之和，不是 job 墙钟耗时，不含构建及 verifier。
- 不报告完整 token/美元成本：Modifier 的 143 个 usageReports 槽位中 139 个 complete、4 个缺少 tokens；Reviewer 的 114 个槽位全部 partial，缺失/不完整不能当作零。

| 指标（各 40 trials） | Codex → Claude | Claude → Codex |
|---|---:|---:|
| Initial 通过 | 20/40（50%） | 24/40（60%） |
| Final 通过 | 25/40（62.5%） | 21/40（52.5%） |
| 净变化 | +12.5 pp | −7.5 pp |
| 修好 / 改坏 | 5 / 0 | 4 / 7 |
| Review 中 revise 占比 | 39/73（53.4%） | 103/114（90.4%） |
| Revision 总数 | 38 | 99 |
| 平均角色执行时间之和 | 31.92 分钟 | 50.79 分钟 |

该方向 initial 高 10 pp，final 却低 10 pp。观测上它更频繁要求修改，也让 Modifier 花更多时间处理反馈；但这是不同执行方向、不同初始 patch、不同并发历史的描述性比较，不能把所有差异直接归因于 reviewer 模型。两方向同名 R 编号也不表示共享随机种子，不应当作严格配对样本。

## 典型修复与回退证据

1. **ts-pattern：四次重复的语义偏移。** 初始 patch 四次通过；Codex 四次均要求处理 `.narrow()` 后的运行时类型安全问题，其中有审查明确要求编译函数保留原始输入类型。修订后，隐藏测试要求的收窄函数类型 `(input: 'b' | 'c') => number[]` 不再满足，第 799 行 TS2344 导致整套 85 个 F2P 测试没有运行。四次最终 F2P 均 0/85、P2P 6/6，随后却全部获批。这是明确的评分回退链条；并不自动证明 reviewer 提出的所有类型安全问题都无效，仍需另行裁定公开需求的语义。[保留原始输入类型的审查意见](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/ts-pattern-match-each__p5ZyuSX/agent/system/rounds/03-review/review.json)；[最终类型失败](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260910-113555/ts-pattern-match-each__9WtRgUX/verifier/test-stdout.txt)

2. **wazero：压缩约束解释引入新的报错路径。** 两次初始通过的样本在修订后跌至 77/78；同一个增量基线测试失败：单字节增量压缩大小无法严格小于已有基线，代码返回“重新捕获 full snapshot”的错误。reviewer 曾明确要求不能满足大小约束时返回错误，与另一方向通过放宽这一路径修好 wazero 的现象相呼应。它揭示的是约束解释冲突与评分风险，不能只靠 binary reward 判定压缩设计优劣。[审查意见](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/wazero-multi-module-snapshots__i4T9k3w/agent/system/rounds/01-review/review.json)；[失败证据](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/wazero-multi-module-snapshots__i4T9k3w/verifier/reports/new-ctrf.json)

3. **helm：反复调整 chart scope 后丢失已通过行为。** `xBhbtRW` initial 和 revision-1 都通过，revision-2 起下降；最终 F2P 46/47、P2P 12/12，失败项为子 chart 的 append 结果：测试期望首元素 `c1`，实际变为 `from-parent`。reviewer 持续报告重复合并和 chart scope 问题，但修复没有保持既有评分通过。[审查意见](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/helm-array-merge-strategies__xBhbtRW/agent/system/rounds/03-review/review.json)；[失败证据](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/helm-array-merge-strategies__xBhbtRW/verifier/reports/new-ctrf.json)

4. **httpx：有重复出现的有效修复。** 第二组两次 initial 失败，第一次修订后均通过；审查涉及 JSON 数组不能在 EOF 前逐项产出、解析异常未关闭流等问题。虽然 binary reward 已通过，后面仍持续 revise 到轮数上限，说明更多 review 不一定带来额外评分收益。[首轮审查](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/httpx-streaming-json-iteration__UFBmthT/agent/system/rounds/01-review/review.json)

5. **超时交付也可能保留有价值的修复。** scc `6dBJxmY` 与 koota `Wkq9Kmb` 都是在第一次修订后由 0 变为 1，最终以 timeout degraded 交付；不应把它们当作评分失败或从实验分母中删去。

## 逐 trial 的 Initial / Final F2P、P2P

每行是一条 trial，F2P/P2P 为通过数/总数；同一任务的四次执行按 R1–R4 排在一起。Trial ID 链接到对应的补评阶段结果。

### wazero-multi-module-snapshots

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [BdjyeYM](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-141135/wazero-multi-module-snapshots__BdjyeYM/patch-scores/stages.json) | 78/78 | 2/2 | 78/78 | 2/2 | 1 → 1 |
| R2 | [KPPe9xz](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/wazero-multi-module-snapshots__KPPe9xz/patch-scores/stages.json) | 78/78 | 2/2 | 77/78 | 2/2 | 1 → 0 |
| R3 | [i4T9k3w](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/wazero-multi-module-snapshots__i4T9k3w/patch-scores/stages.json) | 78/78 | 2/2 | 77/78 | 2/2 | 1 → 0 |
| R4 | [jWXWkep](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260910-113555/wazero-multi-module-snapshots__jWXWkep/patch-scores/stages.json) | 78/78 | 2/2 | 78/78 | 2/2 | 1 → 1 |

### ts-pattern-match-each

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [UoNHwZA](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-141135/ts-pattern-match-each__UoNHwZA/patch-scores/stages.json) | 85/85 | 6/6 | 0/85 | 6/6 | 1 → 0 |
| R2 | [MSgp3BT](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/ts-pattern-match-each__MSgp3BT/patch-scores/stages.json) | 85/85 | 6/6 | 0/85 | 6/6 | 1 → 0 |
| R3 | [p5ZyuSX](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/ts-pattern-match-each__p5ZyuSX/patch-scores/stages.json) | 85/85 | 6/6 | 0/85 | 6/6 | 1 → 0 |
| R4 | [9WtRgUX](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260910-113555/ts-pattern-match-each__9WtRgUX/patch-scores/stages.json) | 85/85 | 6/6 | 0/85 | 6/6 | 1 → 0 |

### python-statemachine-state-data-scoping

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [M8tgWGA](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-141135/python-statemachine-state-data-s__M8tgWGA/patch-scores/stages.json) | 70/72 | 1286/1286 | 70/72 | 1286/1286 | 0 → 0 |
| R2 | [nCMz8HC](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/python-statemachine-state-data-s__nCMz8HC/patch-scores/stages.json) | 70/72 | 1286/1286 | 70/72 | 1286/1286 | 0 → 0 |
| R3 | [HHUQ2me](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/python-statemachine-state-data-s__HHUQ2me/patch-scores/stages.json) | 72/72 | 1286/1286 | 72/72 | 1286/1286 | 1 → 1 |
| R4 | [rCZqrRc](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260910-113555/python-statemachine-state-data-s__rCZqrRc/patch-scores/stages.json) | 72/72 | 1286/1286 | 72/72 | 1286/1286 | 1 → 1 |

### helm-array-merge-strategies

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [SPFKWu8](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-141135/helm-array-merge-strategies__SPFKWu8/patch-scores/stages.json) | 47/47 | 10/12 | 47/47 | 10/12 | 0 → 0 |
| R2 | [xUQkRLr](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/helm-array-merge-strategies__xUQkRLr/patch-scores/stages.json) | 47/47 | 10/12 | 47/47 | 10/12 | 0 → 0 |
| R3 | [xBhbtRW](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/helm-array-merge-strategies__xBhbtRW/patch-scores/stages.json) | 47/47 | 12/12 | 46/47 | 12/12 | 1 → 0 |
| R4 | [DqVdis4](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260910-113555/helm-array-merge-strategies__DqVdis4/patch-scores/stages.json) | 47/47 | 12/12 | 47/47 | 12/12 | 1 → 1 |

### testem-bail-on-test-failure

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [YJ7WNtR](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-141135/testem-bail-on-test-failure__YJ7WNtR/patch-scores/stages.json) | 90/90 | 489/489 | 90/90 | 489/489 | 1 → 1 |
| R2 | [WHHG6Gv](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/testem-bail-on-test-failure__WHHG6Gv/patch-scores/stages.json) | 90/90 | 489/489 | 90/90 | 489/489 | 1 → 1 |
| R3 | [RhNwZe5](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/testem-bail-on-test-failure__RhNwZe5/patch-scores/stages.json) | 90/90 | 489/489 | 90/90 | 489/489 | 1 → 1 |
| R4 | [Pp6Kmv4](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260910-113555/testem-bail-on-test-failure__Pp6Kmv4/patch-scores/stages.json) | 90/90 | 489/489 | 90/90 | 489/489 | 1 → 1 |

### httpx-streaming-json-iteration

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [PxKpipL](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-141135/httpx-streaming-json-iteration__PxKpipL/patch-scores/stages.json) | 108/108 | 1404/1404 | 108/108 | 1404/1404 | 1 → 1 |
| R2 | [UFBmthT](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/httpx-streaming-json-iteration__UFBmthT/patch-scores/stages.json) | 107/108 | 1404/1404 | 108/108 | 1404/1404 | 0 → 1 |
| R3 | [kadJLus](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/httpx-streaming-json-iteration__kadJLus/patch-scores/stages.json) | 107/108 | 1404/1404 | 108/108 | 1404/1404 | 0 → 1 |
| R4 | [YAPqLS7](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260910-113555/httpx-streaming-json-iteration__YAPqLS7/patch-scores/stages.json) | 107/108 | 1404/1404 | 107/108 | 1404/1404 | 0 → 0 |

### koota-deferred-mutation-buffer

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [UPFdjrk](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-141135/koota-deferred-mutation-buffer__UPFdjrk/patch-scores/stages.json) | 69/71 | 128/128 | 70/71 | 128/128 | 0 → 0 |
| R2 | [DEVNTi6](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/koota-deferred-mutation-buffer__DEVNTi6/patch-scores/stages.json) | 70/71 | 128/128 | 70/71 | 128/128 | 0 → 0 |
| R3 | [Wkq9Kmb](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/koota-deferred-mutation-buffer__Wkq9Kmb/patch-scores/stages.json) | 70/71 | 128/128 | 71/71 | 128/128 | 0 → 1 |
| R4 | [2e7fzRu](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260910-113555/koota-deferred-mutation-buffer__2e7fzRu/patch-scores/stages.json) | 67/71 | 128/128 | 67/71 | 128/128 | 0 → 0 |

### bandit-interprocedural-taint-checks

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [SNNhDSU](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-141135/bandit-interprocedural-taint-che__SNNhDSU/patch-scores/stages.json) | 66/66 | 293/293 | 66/66 | 293/293 | 1 → 1 |
| R2 | [rYaxLjJ](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/bandit-interprocedural-taint-che__rYaxLjJ/patch-scores/stages.json) | 66/66 | 293/293 | 66/66 | 293/293 | 1 → 1 |
| R3 | [QtXSxTw](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/bandit-interprocedural-taint-che__QtXSxTw/patch-scores/stages.json) | 66/66 | 293/293 | 66/66 | 293/293 | 1 → 1 |
| R4 | [HwGSpWh](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260910-113555/bandit-interprocedural-taint-che__HwGSpWh/patch-scores/stages.json) | 66/66 | 293/293 | 66/66 | 293/293 | 1 → 1 |

### optique-conditional-option-dependencies

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [TDXVJCn](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-141135/optique-conditional-option-depen__TDXVJCn/patch-scores/stages.json) | 35/36 | 2034/2034 | 35/36 | 2034/2034 | 0 → 0 |
| R2 | [prND3MS](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/optique-conditional-option-depen__prND3MS/patch-scores/stages.json) | 35/36 | 2034/2034 | 35/36 | 2034/2034 | 0 → 0 |
| R3 | [dGM7BuJ](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/optique-conditional-option-depen__dGM7BuJ/patch-scores/stages.json) | 36/36 | 2034/2034 | 36/36 | 2034/2034 | 1 → 1 |
| R4 | [iMWi7DP](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260910-113555/optique-conditional-option-depen__iMWi7DP/patch-scores/stages.json) | 36/36 | 2034/2034 | 36/36 | 2034/2034 | 1 → 1 |

### scc-bounded-memory-spilling

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [6dBJxmY](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-141135/scc-bounded-memory-spilling__6dBJxmY/patch-scores/stages.json) | 30/31 | 286/286 | 31/31 | 286/286 | 0 → 1 |
| R2 | [rkNzpqL](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/scc-bounded-memory-spilling__rkNzpqL/patch-scores/stages.json) | 28/31 | 286/286 | 28/31 | 286/286 | 0 → 0 |
| R3 | [3xEsBgf](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260909-225214/scc-bounded-memory-spilling__3xEsBgf/patch-scores/stages.json) | 31/31 | 286/286 | 31/31 | 286/286 | 1 → 1 |
| R4 | [WptkiJ6](../../../jobs/collab-claude-codex-complementary-opus-astra-medium-10-tasks-20260910-113555/scc-bounded-memory-spilling__WptkiJ6/patch-scores/stages.json) | 28/31 | 286/286 | 28/31 | 286/286 | 0 → 0 |

### F2P/P2P 汇总

合计列直接累加测试数，因此测试多的任务权重大；等权平均先计算每条 trial 的比例，再对 40 条取平均。

| 阶段 | F2P 合计 | P2P 合计 | F2P trial 等权平均 | P2P trial 等权平均 |
|---|---:|---:|---:|---:|
| Initial | 2712/2736 | 23756/23760 | 98.81% | 99.17% |
| Final | 2374/2736 | 23756/23760 | 88.89% | 99.17% |

ts-pattern 的大幅 F2P 下降主要来自编译失败后新增测试整套无结果，不能解释为 340 个运行时断言逐项执行失败；它仍是当前评分契约下真实的 final 失败。

## 结论与后续实验

- 当前证据支持：该方向能补齐部分 Astra 强项，但同时在 Opus 强项中引入更大的回退，净效果为负。四次都发生的 ts-pattern 回退值得优先处理，单纯增加重复次数或审查轮数未必有帮助。
- 比“reviewer 更严格”更具体的问题是：审查要求如何与公开需求的精确契约对齐，以及 Modifier 如何在修改时保留已有行为。可以在新任务上检验要求 reviewer 给出明确需求依据、保留修改前公开测试和类型断言的做法。
- 不应使用隐藏评分来选择这些 benchmark 的最佳 checkpoint 后仍报告为原始盲测成绩；initial/final 配对评分是事后分析，不是本轮运行时的选择依据。
- 40 次来自同一批 10 题，仅 10 个任务簇；7 次回退集中在 3 题，其中 4 次属于同一题。不能视为 40 个独立任务，也不据此宣称两个 reviewer 在一般任务上的优劣。
- 当前缺少同预算单模型自审对照，无法把所有收益/损失单独归因于异模型协作；报告保留全部超时样本，并区分运行并发变化，避免按成功条件筛选实验。
- 另一方向详见 [Codex → Claude 40 次报告](complementary-opus-astra-medium-codex-claude-40-trials-20260910.md)。
