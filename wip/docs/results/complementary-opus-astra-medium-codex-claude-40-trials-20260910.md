# Codex → Claude：Opus/Astra 互补任务集 4 次重复汇总

统计日期：2026-09-10。范围是 complementary-opus-astra-medium.txt 的 10 题、每题 4 次，共 40 个 trial。

**初始 patch 通过 20/40（50%），最终 patch 通过 25/40（62.5%），净增 12.5 个百分点。5 次修好、0 次最终改坏；收益集中于 wazero 4 次和 helm 1 次。** 这说明该方向在此子集上能稳定修好特定问题，同时保住 Astra 原有强项；尚不足以证明它能普遍恢复 Opus 擅长的能力。

## 数据范围与有效性

| Job 后缀 | 次数/题 | Initial | Final | 原始评分对照 |
|---|---:|---:|---:|---|
| [20260909-140937](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-140937/patch-scores/pairs.csv) | 1 | 5/10 | 6/10 | 1 matched，9 unavailable |
| [20260909-225200](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/patch-scores/pairs.csv) | 2 | 10/20 | 13/20 | 20 matched，0 unavailable |
| [20260910-113656](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260910-113656/patch-scores/pairs.csv) | 1 | 5/10 | 6/10 | 10 matched，0 unavailable |

- 三组的模型、effort、预算、runtime 和 workflowConfig 完全相同；每题 task_checksum 跨运行一致。Modifier：codex / gpt-6-astra / medium；Reviewer：claude / claude-opus-5 / high。
- Runtime 镜像均为 `deep-swe/agent-runtime:86d93103f53a80a1`，Codex CLI/SDK 0.153.4，Claude Agent SDK 0.3.266，cligent 0.27.0。每组并发 1，最多 3 轮 review；任务硬超时 5400 秒、预留清理 300 秒、静默超时 900 秒、每 turn 最多尝试 2 次。
- 78 个不同 patch 补评成功，覆盖 115 条阶段记录；40/40 initial–final 对完整，无 verifierErrors，无评分不一致。
- 第一组有 9 个 trial 的原始 verifier 镜像构建超时，但 patch 已完整保留并补评成功。本报告纳入全部 40 个有效补评对；没有照搬脚本因缺少原始评分对照而过滤后的 intentionToTreat/completedProtocol 汇总。31 个可对照的原始最终评分均 matched。
- 不纳入最初 Codex 版本错误的 job，以及重启前未完成的其他 job。初始分数是同一 collab 运行中、首次审查前的 patch 分数，不是另外安排的独立 single-agent 对照实验。
- [逐 trial 明细](complementary-opus-astra-medium-codex-claude-40-trials-20260910.csv)；[机器可读汇总](complementary-opus-astra-medium-codex-claude-40-trials-20260910.json)。R1 为第一组，R2/R3 按第二组每题的启动先后排列，R4 为第三组；这些编号不是全局同步进行的四轮。

## 逐题结果

“强侧”来自任务筛选时的历史 mini-swe-agent 数据，仅表示选题依据，不应当作当前 Claude Code 的单体基线。

| Task | 历史强侧 | Initial | Final | 四次 Final（R1/R2/R3/R4） | 总审查/修订轮数 |
|---|---|---:|---:|---|---:|
| `wazero-multi-module-snapshots` | Opus | 0/4 | 4/4 | 1 / 1 / 1 / 1 | 10/6 |
| `ts-pattern-match-each` | Opus | 0/4 | 0/4 | 0 / 0 / 0 / 0 | 4/0 |
| `python-statemachine-state-data-scoping` | Opus | 0/4 | 0/4 | 0 / 0 / 0 / 0 | 9/6 |
| `helm-array-merge-strategies` | Opus | 0/4 | 1/4 | 0 / 1 / 0 / 0 | 8/5 |
| `testem-bail-on-test-failure` | Opus | 0/4 | 0/4 | 0 / 0 / 0 / 0 | 4/0 |
| `httpx-streaming-json-iteration` | Astra | 4/4 | 4/4 | 1 / 1 / 1 / 1 | 7/3 |
| `koota-deferred-mutation-buffer` | Astra | 4/4 | 4/4 | 1 / 1 / 1 / 1 | 11/9 |
| `bandit-interprocedural-taint-checks` | Astra | 4/4 | 4/4 | 1 / 1 / 1 / 1 | 4/0 |
| `optique-conditional-option-dependencies` | Astra | 4/4 | 4/4 | 1 / 1 / 1 / 1 | 8/5 |
| `scc-bounded-memory-spilling` | Astra | 4/4 | 4/4 | 1 / 1 / 1 / 1 | 8/4 |

## 逐 trial 的 Initial / Final F2P、P2P

每行对应一次独立 trial；F2P、P2P 均为“通过数 / 测试总数”，不是四次执行的合计。Reward 为完整任务是否通过（0/1）。同一任务的四次执行按 R1–R4 相邻排列，编号含义见前文；Trial ID 链接指向该次补评的阶段结果。

[下载全部 40 行 F2P/P2P 明细 CSV](complementary-opus-astra-medium-codex-claude-40-trials-20260910-initial-final-tests.csv)。

### wazero-multi-module-snapshots

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [TsT8A3h](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-140937/wazero-multi-module-snapshots__TsT8A3h/patch-scores/stages.json) | 77/78 | 2/2 | 78/78 | 2/2 | 0 → 1 |
| R2 | [twxPKV5](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/wazero-multi-module-snapshots__twxPKV5/patch-scores/stages.json) | 77/78 | 2/2 | 78/78 | 2/2 | 0 → 1 |
| R3 | [K3p9Bt7](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/wazero-multi-module-snapshots__K3p9Bt7/patch-scores/stages.json) | 77/78 | 2/2 | 78/78 | 2/2 | 0 → 1 |
| R4 | [bYNHj9F](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260910-113656/wazero-multi-module-snapshots__bYNHj9F/patch-scores/stages.json) | 77/78 | 2/2 | 78/78 | 2/2 | 0 → 1 |

### ts-pattern-match-each

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [RcQxmE7](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-140937/ts-pattern-match-each__RcQxmE7/patch-scores/stages.json) | 0/85 | 6/6 | 0/85 | 6/6 | 0 → 0 |
| R2 | [GXKqmUv](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/ts-pattern-match-each__GXKqmUv/patch-scores/stages.json) | 0/85 | 6/6 | 0/85 | 6/6 | 0 → 0 |
| R3 | [CXtDMaw](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/ts-pattern-match-each__CXtDMaw/patch-scores/stages.json) | 0/85 | 6/6 | 0/85 | 6/6 | 0 → 0 |
| R4 | [pi8yfyQ](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260910-113656/ts-pattern-match-each__pi8yfyQ/patch-scores/stages.json) | 0/85 | 6/6 | 0/85 | 6/6 | 0 → 0 |

### python-statemachine-state-data-scoping

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [EcCdJRK](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-140937/python-statemachine-state-data-s__EcCdJRK/patch-scores/stages.json) | 69/72 | 1286/1286 | 69/72 | 1286/1286 | 0 → 0 |
| R2 | [7AAQY7A](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/python-statemachine-state-data-s__7AAQY7A/patch-scores/stages.json) | 69/72 | 1286/1286 | 69/72 | 1286/1286 | 0 → 0 |
| R3 | [Y29T8Fu](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/python-statemachine-state-data-s__Y29T8Fu/patch-scores/stages.json) | 69/72 | 1286/1286 | 69/72 | 1286/1286 | 0 → 0 |
| R4 | [PicsD9c](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260910-113656/python-statemachine-state-data-s__PicsD9c/patch-scores/stages.json) | 69/72 | 1286/1286 | 69/72 | 1286/1286 | 0 → 0 |

### helm-array-merge-strategies

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [BStaRaX](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-140937/helm-array-merge-strategies__BStaRaX/patch-scores/stages.json) | 47/47 | 10/12 | 47/47 | 10/12 | 0 → 0 |
| R2 | [v4UpsXx](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/helm-array-merge-strategies__v4UpsXx/patch-scores/stages.json) | 47/47 | 10/12 | 47/47 | 12/12 | 0 → 1 |
| R3 | [6LmMDnY](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/helm-array-merge-strategies__6LmMDnY/patch-scores/stages.json) | 47/47 | 10/12 | 47/47 | 10/12 | 0 → 0 |
| R4 | [e742jBw](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260910-113656/helm-array-merge-strategies__e742jBw/patch-scores/stages.json) | 47/47 | 10/12 | 47/47 | 10/12 | 0 → 0 |

### testem-bail-on-test-failure

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [adCSMim](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-140937/testem-bail-on-test-failure__adCSMim/patch-scores/stages.json) | 89/90 | 489/489 | 89/90 | 489/489 | 0 → 0 |
| R2 | [qFV92xc](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/testem-bail-on-test-failure__qFV92xc/patch-scores/stages.json) | 86/90 | 489/489 | 86/90 | 489/489 | 0 → 0 |
| R3 | [fVSkpt3](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/testem-bail-on-test-failure__fVSkpt3/patch-scores/stages.json) | 88/90 | 489/489 | 88/90 | 489/489 | 0 → 0 |
| R4 | [oXBZFZ2](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260910-113656/testem-bail-on-test-failure__oXBZFZ2/patch-scores/stages.json) | 89/90 | 489/489 | 89/90 | 489/489 | 0 → 0 |

### httpx-streaming-json-iteration

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [GYpL3jQ](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-140937/httpx-streaming-json-iteration__GYpL3jQ/patch-scores/stages.json) | 108/108 | 1404/1404 | 108/108 | 1404/1404 | 1 → 1 |
| R2 | [5LGsjGp](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/httpx-streaming-json-iteration__5LGsjGp/patch-scores/stages.json) | 108/108 | 1404/1404 | 108/108 | 1404/1404 | 1 → 1 |
| R3 | [u5kvKRP](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/httpx-streaming-json-iteration__u5kvKRP/patch-scores/stages.json) | 108/108 | 1404/1404 | 108/108 | 1404/1404 | 1 → 1 |
| R4 | [sz2uGEa](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260910-113656/httpx-streaming-json-iteration__sz2uGEa/patch-scores/stages.json) | 108/108 | 1404/1404 | 108/108 | 1404/1404 | 1 → 1 |

### koota-deferred-mutation-buffer

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [NpG5N86](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-140937/koota-deferred-mutation-buffer__NpG5N86/patch-scores/stages.json) | 71/71 | 128/128 | 71/71 | 128/128 | 1 → 1 |
| R2 | [u7EDEEp](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/koota-deferred-mutation-buffer__u7EDEEp/patch-scores/stages.json) | 71/71 | 128/128 | 71/71 | 128/128 | 1 → 1 |
| R3 | [n7RDf3P](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/koota-deferred-mutation-buffer__n7RDf3P/patch-scores/stages.json) | 71/71 | 128/128 | 71/71 | 128/128 | 1 → 1 |
| R4 | [6yqXeiL](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260910-113656/koota-deferred-mutation-buffer__6yqXeiL/patch-scores/stages.json) | 71/71 | 128/128 | 71/71 | 128/128 | 1 → 1 |

### bandit-interprocedural-taint-checks

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [KF2Ygu7](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-140937/bandit-interprocedural-taint-che__KF2Ygu7/patch-scores/stages.json) | 66/66 | 293/293 | 66/66 | 293/293 | 1 → 1 |
| R2 | [rHVXoPE](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/bandit-interprocedural-taint-che__rHVXoPE/patch-scores/stages.json) | 66/66 | 293/293 | 66/66 | 293/293 | 1 → 1 |
| R3 | [pj9wWXT](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/bandit-interprocedural-taint-che__pj9wWXT/patch-scores/stages.json) | 66/66 | 293/293 | 66/66 | 293/293 | 1 → 1 |
| R4 | [9tzWGif](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260910-113656/bandit-interprocedural-taint-che__9tzWGif/patch-scores/stages.json) | 66/66 | 293/293 | 66/66 | 293/293 | 1 → 1 |

### optique-conditional-option-dependencies

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [ps4gqAh](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-140937/optique-conditional-option-depen__ps4gqAh/patch-scores/stages.json) | 36/36 | 2034/2034 | 36/36 | 2034/2034 | 1 → 1 |
| R2 | [Eo63zxD](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/optique-conditional-option-depen__Eo63zxD/patch-scores/stages.json) | 36/36 | 2034/2034 | 36/36 | 2034/2034 | 1 → 1 |
| R3 | [9MoUos4](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/optique-conditional-option-depen__9MoUos4/patch-scores/stages.json) | 36/36 | 2034/2034 | 36/36 | 2034/2034 | 1 → 1 |
| R4 | [Hn8myvR](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260910-113656/optique-conditional-option-depen__Hn8myvR/patch-scores/stages.json) | 36/36 | 2034/2034 | 36/36 | 2034/2034 | 1 → 1 |

### scc-bounded-memory-spilling

| 重复 | Trial ID | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward（Initial → Final） |
|---|---|---:|---:|---:|---:|---|
| R1 | [pUf7krF](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-140937/scc-bounded-memory-spilling__pUf7krF/patch-scores/stages.json) | 31/31 | 286/286 | 31/31 | 286/286 | 1 → 1 |
| R2 | [DjuBjYs](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/scc-bounded-memory-spilling__DjuBjYs/patch-scores/stages.json) | 31/31 | 286/286 | 31/31 | 286/286 | 1 → 1 |
| R3 | [6akr8mY](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/scc-bounded-memory-spilling__6akr8mY/patch-scores/stages.json) | 31/31 | 286/286 | 31/31 | 286/286 | 1 → 1 |
| R4 | [A9cRpfA](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260910-113656/scc-bounded-memory-spilling__A9cRpfA/patch-scores/stages.json) | 31/31 | 286/286 | 31/31 | 286/286 | 1 → 1 |

### 全部 trial 的汇总口径

下表将 40 次执行的通过数和测试数直接相加；测试数量多的任务权重更高。

| 阶段 | F2P 合计 | P2P 合计 | F2P 按 trial 等权平均 | P2P 按 trial 等权平均 |
|---|---:|---:|---:|---:|
| Initial | 2372/2736 | 23752/23760 | 89.23% | 98.33% |
| Final | 2376/2736 | 23754/23760 | 89.36% | 98.75% |

F2P 净增加 4 条通过，来自 wazero 的四个 trial 各补齐 1 条；P2P 净增加 2 条通过，来自 helm 的一个 trial 补齐 2 条。两者共同带来完整任务通过数从 20/40 增至 25/40。

注意：ts-pattern 的 0/85 是类型检查失败后整套新增测试未运行，评分器将缺失结果记为失败；不表示 85 条运行时断言逐项执行失败。详见后文“失败与修复证据”。

## 协作收益与稳定性

| Initial → Final | 次数 | 含义 |
|---|---:|---|
| 通过 → 通过 | 20 | 保住全部初始成功 |
| 失败 → 通过 | 5 | 修好 wazero 4 次、helm 1 次 |
| 通过 → 失败 | 0 | 本样本未观察到最终回退 |
| 失败 → 失败 | 15 | 仍未达到完整通过 |

- 历史 Astra 强的 5 题：initial 和 final 均 20/20，重复结果完全一致。
- 历史 Opus 强的 5 题：initial 0/20，final 5/20。以初始失败为分母，修复率为 25%；其中 wazero 贡献 80% 的新增通过。
- 9/10 题在四次运行中最终结果完全一致。6 题稳定 4/4（5 个 Astra 强题加 wazero），3 题稳定 0/4；只有 helm 是 1/4。继续对相同题盲目重复，未必能消除这些固定失败。
- 四次观测中至少通过一次的题为 7/10；全部四次都通过的题为 6/10。前者是本次四样本的观测覆盖率，不是一次运行的成功率。
- 已评分的 35 次中间修订转移中，5 次 0→1、20 次 1→1、10 次 0→0，未见 1→0；这一结论只针对 binary reward，不能排除局部测试数量的波动或测试未覆盖的问题。
- 三个 timeout degraded 也保留在全量统计中。排除它们后 initial 18/37、final 23/37，仍净增 5 次。

## 审查行为与时间投入

- 40 个 trial 的结果：34 approved、3 max_reviews_reached、3 degraded（timeout）。达到轮数上限和超时交付不等于评分失败。
- 共 73 次有效 review：39 revise（53.4%）、34 approve（46.6%）；总 revisionCount 为 38。状态计数不等同于不同 patch 数，同一 patch 可在多轮出现。
- 34 个 approved 中，20 个 final 通过、14 个 final 失败，即 41.2% 的获批交付仍未通过 verifier。尤其 testem 与 ts-pattern 都是四次首轮 approve、无修订、四次失败。
- helm 唯一通过的一次最终状态反而是 max_reviews_reached：第一轮修订已经通过评分，但 reviewer 后续仍提出其他语义问题。reviewer 批准与隐藏测试通过衡量的是不同内容。
- 模型 turn wall time 合计约 21.28 小时：Modifier 8.90 小时，Reviewer 12.38 小时。平均每 trial 分别 13.35 / 18.57 分钟；Reviewer 占两角色 turn 总耗时约 58.2%。这些时间不含环境构建与 verifier，也不是与独立 single job 相比的因果开销估计。
- Modifier 初始实现阶段平均 8.46 分钟；完整协作 turn 平均 31.92 分钟。额外时间包含修订、审查及其中的重试。
- 不给出完整 token/美元总成本：Modifier 的 80 个 usageReports 槽位中 41 个 partial、39 个缺少 tokens；Reviewer 的 75 个槽位中 73 个 complete、2 个缺少 tokens。缺失不能按零处理；用现有日志计算完整成本会造成误导。

## 失败与修复证据

以下是对已有产物的事后分析，未修改任务、patch 或评分器，也未让 agent 接触隐藏测试后重跑。

1. **wazero：4/4 的稳定收益。** 两次在第一次修订后通过，两次在第二次修订后通过。最后一组的 review 定位到增量快照对普通变更和增量链错误报错、压缩表示不满足约束；修订后 verifier 从失败转为通过。收益应表述为该任务上的可重复修复，不能直接外推成普遍跨模型能力迁移。[审查证据](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260910-113656/wazero-multi-module-snapshots__bYNHj9F/agent/system/rounds/03-review/review.json)

2. **helm：1/4 通过，主要障碍之一是 lint 兼容性。** 最后一组 F2P 47/47，但 P2P 10/12；合法 annotations 被错误报为路径不存在。唯一通过的样本中，首轮 reviewer 同时指出子 chart 默认值重复和缺少 values.yaml 时的错误 lint 警告，revision-1 已通过，后续两次修订保持通过。[失败证据](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260910-113656/helm-array-merge-strategies__e742jBw/verifier/reports/new-ctrf.json)；[通过样本首轮审查](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-225200/helm-array-merge-strategies__v4UpsXx/agent/system/rounds/01-review/review.json)

3. **python-statemachine：0/4，边界返回值仍未补齐。** 最后一组 F2P 69/72、P2P 1286/1286；未声明 data 的 active state 返回 `{}`，隐藏测试要求 `None`，相关三项失败。此例表明高局部通过率与 binary reward 之间有明显差距。[失败日志](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260910-113656/python-statemachine-state-data-s__PicsD9c/verifier/reports/new.log)

4. **testem：0/4，四次首轮批准且未修订。** 最后一组 89/90，唯一失败是 invalid 配置警告不包含测试要求的 `invalid` 文本；中间两次还分别有 XUnit errors 属性或浏览器 abort 边界问题。需要将精确文案契约问题与主要功能缺失区分开，不能仅根据 0 分推断整项功能无效。[最后一组失败证据](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260910-113656/testem-bail-on-test-failure__oXBZFZ2/verifier/reports/new_ctrf.json)

5. **ts-pattern：0/4，四次是同一个类型检查关卡，而非 85 项运行时断言逐项失败。** 四次最终 patch 在隐藏测试第 799 行均遇到 TS2344：`Expect<Equal<typeof fn, (input: 'b' | 'c') => number[]>>` 不成立，Jest 因编译失败执行了 0 个新增测试，评分器将 85 项缺失结果记为失败。Reviewer 自己运行的 suite/type probes 未覆盖这一精确类型契约。应优先理解函数输入联合类型的收窄语义，再判断是实现问题还是任务文字与评分契约存在歧义；本报告没有完成后一项规范裁定。[编译失败证据](../../../jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260910-113656/ts-pattern-match-each__pi8yfyQ/verifier/test-stdout.txt)

## 结论的边界与下一步

- 数据支持“在这个刻意筛选的 10 题子集上，保住 Astra 强项，并稳定修复 wazero”，不支持“能普遍吸收 Opus 的全部优势”。Opus 强题中的 15/20 次初始失败仍失败。
- 40 次不是 40 个独立任务，只有 10 个任务簇；5 个正向对中 4 个来自同一题。不考虑任务相关性时，5 修好/0 改坏的双侧精确 McNemar 值也仅为 0.0625，不能宣称已有稳健的统计显著性。该值仅作描述，不用于跨任务推广。
- 0/20 初始成功被改坏是本次观测，不是未来风险为零的保证。
- initial 是同一协作流程内的对照；新增收益可能同时来自更多推理时间、反复实现和 reviewer 的反馈，当前设计无法单独分离“换模型审查”的因果贡献。若要分离，需要同预算自审/同模型 reviewer 对照。
- 下一步最有价值的是核对持续失败题的公开需求与精确接口/边界契约，尤其 ts-pattern 的类型约束、helm 的 lint 兼容性，以及 testem 的警告文案；将隐藏测试用于事后评估，不应反馈给同一基准任务的 agent 后再把结果算作盲测。
- 如果扩展实验，应增加新任务覆盖，并同步汇总另一方向；同一十题继续重复主要是在估计固定题的随机性。
