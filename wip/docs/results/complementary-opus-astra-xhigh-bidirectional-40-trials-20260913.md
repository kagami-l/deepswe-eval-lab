# Astra xhigh 双向协作：10 题 × 2 次 × 2 方向汇总

统计日期：2026-09-13。任务集为 `complementary-opus-astra-xhigh.txt`，每个方向 20 次，共 40 个 trial。

**Codex → Claude：9/20 → 11/20，净增 10 个百分点；Claude → Codex：18 个有效配对中 11/18 → 9/18，净减 11.11 个百分点。后者另有 2 次 Helm 首次实现超时、无补丁；按全部 20 次运行计，最终成功率为 9/20（45%）。这批数据尚未显示 xhigh 相比 medium 带来成功率收益。**

## 范围、配置与评分完整性

| 方向 | Job | 并发 | 完整配对 | 不可配对 | 不同补丁评分 | 阶段记录 | Final 对照 |
|---|---|---:|---:|---:|---:|---:|---|
| Codex → Claude | [123715](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/patch-scores/summary.json) | 1 | 20/20 | 0 | 32 | 51 | 20 matched |
| Claude → Codex | [123742](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/patch-scores/summary.json) | 2 | 18/20 | 2 | 53 | 65 | 18 matched |

- Astra = `gpt-6-astra / xhigh`，Claude Code = `claude-opus-5 / high`，互换 modifier/reviewer；每题 2 次。运行镜像均为 `deep-swe/agent-runtime:86d93103f53a80a1`，与 medium 报告一致。
- 最多 3 轮 review，每 turn 最多 2 次尝试；任务硬超时 5400 秒，清理预留 300 秒，可工作预算约 5100 秒；事件静默超时 900 秒。
- 两次补评均以 concurrency=2、force=false、reuseFinalScore=false 完成，exitCode=0、problems=[]、verifierErrors={}；85 个不同补丁评分成功，116 条阶段记录全部成功。38 个有效 final 与原始评分全部一致，没有 incompletePairs 或 mismatch。
- 两个 Helm trial 的 `no_initial_patch` 是原运行失败，非补评分缺漏：Claude 在首次实现阶段触及 total_deadline，约 85 分钟后退出，reviewCount=0、deliverable=false，final 补丁为空。补评分不能恢复不存在的 initial/final 配对。
- 文档和 CSV 保留全部 40 行；Helm 的配对 reward、F2P/P2P 标为 N/A，不能冒充实测 0 分。另设 operational_final_pass：无交付运行计未成功，因此全部运行的最终成功率分母仍为 20。脚本中名为 intentionToTreat 的汇总实际只含 18 个 eligible 配对，应与全部运行口径区分。
- 同一 task 的两次执行按启动时间标为 R1/R2，并非两个同步批次；两方向的 R 编号不代表共享随机种子。共同 task 的 task_checksum 在两个方向及历史 medium 比较中一致。
- 输出：[40 行 trial 明细 CSV](complementary-opus-astra-xhigh-bidirectional-40-trials-20260913.csv)；[完整机器可读汇总 JSON](complementary-opus-astra-xhigh-bidirectional-40-trials-20260913.json)。

## 初始与最终结果

| 指标 | Codex → Claude | Claude → Codex |
|---|---:|---:|
| 全部运行数 | 20 | 20 |
| 有效 initial/final 配对 | 20 | 18 |
| Initial 通过（配对口径） | 9/20（45%） | 11/18（61.11%） |
| Final 通过（配对口径） | 11/20（55%） | 9/18（50%） |
| 配对净变化 | +2，+10 pp | −2，−11.11 pp |
| Final 成功（全部运行口径） | 11/20（55%） | 9/20（45%） |
| 0 → 1 修好 | 2 | 2 |
| 1 → 0 退化 | 0 | 4 |
| 1 → 1 保持通过 | 9 | 7 |
| 0 → 0 仍未通过 | 9 | 5 |
| 无初始交付 | 0 | 2 |

Codex → Claude 保留全部 9 次初始通过，并修好 11 次初始失败中的 2 次（18.18%）。Claude → Codex 修好 7 次初始失败中的 2 次（28.57%），但损失 11 次初始通过中的 4 次（36.36%），因此净效果为负。两次无初始交付的 Helm 不纳入修好/退化转移。

## 按 task 汇总

历史强侧来自任务集筛选时的 mini-swe-agent 数据，不是当前 CLI 的独立单体基线。表中 I→F 表示通过次数/两次执行；Helm 的“无交付”不能解释为已评分的 0→0。

| Task | 历史强侧 | Codex → Claude I→F | 修好/退化 | Claude → Codex I→F | 修好/退化 |
|---|---|---:|---:|---:|---:|
| `wazero-multi-module-snapshots` | Opus | 0/2 → 2/2 | 2/0 | 2/2 → 1/2 | 0/1 |
| `ts-pattern-match-each` | Opus | 0/2 → 0/2 | 0/0 | 2/2 → 0/2 | 0/2 |
| `python-statemachine-state-data-scoping` | Opus | 0/2 → 0/2 | 0/0 | 2/2 → 1/2 | 0/1 |
| `helm-array-merge-strategies` | Opus | 0/2 → 0/2 | 0/0 | 两次无初始交付 | 0/0 |
| `testem-bail-on-test-failure` | Opus | 0/2 → 0/2 | 0/0 | 1/2 → 1/2 | 0/0 |
| `httpx-streaming-json-iteration` | Astra | 2/2 → 2/2 | 0/0 | 0/2 → 2/2 | 2/0 |
| `koota-deferred-mutation-buffer` | Astra | 2/2 → 2/2 | 0/0 | 0/2 → 0/2 | 0/0 |
| `bandit-interprocedural-taint-checks` | Astra | 2/2 → 2/2 | 0/0 | 2/2 → 2/2 | 0/0 |
| `optique-conditional-option-dependencies` | Astra | 1/2 → 1/2 | 0/0 | 1/2 → 1/2 | 0/0 |
| `oxvg-structural-selector-preservation` | Astra | 2/2 → 2/2 | 0/0 | 1/2 → 1/2 | 0/0 |

- Codex → Claude 的两次修好全部来自 wazero；历史 Opus 强的五题为 0/10 → 2/10，历史 Astra 强的五题为 9/10 → 9/10。ts-pattern、python-statemachine、helm、testem 仍各 0/2；这四题本批均未见新增通过。
- Claude → Codex 的两次修好全部来自 httpx；四次退化来自 ts-pattern 两次、wazero 一次、python-statemachine 一次。历史 Opus 强侧有效 8 对为 7/8 → 3/8（另 2 次 Helm 无交付），历史 Astra 强侧为 4/10 → 6/10。
- Codex → Claude 有五题 final 2/2、四题 0/2、一题 1/2；Claude → Codex 有两题 final 2/2、五题 1/2，ts-pattern/koota 各 0/2，Helm 两次无交付。两次重复仅是初步稳定性观察。

## F2P、P2P 与中间阶段

下表仅对有完整配对的 trial 计算，反向不含两次 Helm。宏平均为每条 trial 通过率的算术平均，微平均为汇总通过数/总数。两种方向包含的 task 不完全相同，尤其 P2P 不能脱离覆盖范围直接比较。

| 指标 | Codex → Claude（20 对） | Claude → Codex（18 对） |
|---|---:|---:|
| F2P 汇总/微平均 | 1137/1318 → 1139/1318（86.27% → 86.42%） | 1213/1224 → 1043/1224（99.10% → 85.21%） |
| F2P 宏平均 | 89.21% → 89.33% | 97.48% → 85.45% |
| P2P 汇总/微平均 | 11428/11432 → 11428/11432（99.97% → 99.97%） | 11408/11408 → 11408/11408（100.00% → 100.00%） |
| P2P 宏平均 | 98.33% → 98.33% | 100.00% → 100.00% |

- Codex → Claude 的 F2P 总通过数只增加 2，即两次 wazero 各补上 1 个测试；P2P 没有变化。两次 Helm 都是 F2P 47/47、P2P 10/12，仍无法获得 binary reward=1。
- Claude → Codex 的 F2P 总通过数净减 170：ts-pattern −170、python-statemachine −2、wazero −1、oxvg −1，httpx +3、koota +1。ts-pattern 的 0/85 是类型编译失败导致整套测试没有执行，并非 85 个独立运行时断言失败。
- binary 不变仍可能有部分变化：koota 的一条 trial 从 69/71 提升到 70/71；oxvg 的一条从 4/6 下降到 3/6，均仍为 0→0。
- 按不同 patch 的相邻阶段统计：Codex → Claude 共 12 次转移，2 次 0→1、7 次 1→1、3 次 0→0；Claude → Codex 共 35 次，2 次 0→1、4 次 1→0、18 次 1→1、11 次 0→0。没有 binary 退化后又恢复的样本。

## 典型变化与证据

1. **wazero：两个方向再现相反效果。** Codex → Claude 的 `exojTnd` 在 revision-1、`9H7Xt57` 在 revision-2 从 77/78 升到 78/78。反向 `2C94zCe` 在 revision-1 从 78/78 降到 77/78，最终报错是增量压缩 30 字节没有严格小于基线 30 字节。Codex 审查明确要求大小约束无法满足时返回错误，并指出原实现存在为压缩而丢弃变化的问题；这说明评分下降伴随需求解释/实现正确性的冲突，不能仅凭 reward 判定所有审查意见无效。[审查意见](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/wazero-multi-module-snapshots__2C94zCe/agent/system/rounds/01-review/review.json)；[最终失败日志](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/wazero-multi-module-snapshots__2C94zCe/verifier/test-stdout.txt)。

2. **ts-pattern：medium 时的退化模式仍在。** 两次初始都 85/85，`Do6HAPn` 在 revision-1、`DvfxCeq` 在 revision-2 降为 0/85。Codex 要求编译函数保留 `.narrow()` 前的原始输入类型；隐藏测试第 799 行要求函数输入为收窄后的 `b | c`，产生 TS2344，随后两次均获 approve。提高 effort 尚未消除这一重复出现的语义冲突。[编译函数类型审查](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/ts-pattern-match-each__DvfxCeq/agent/system/rounds/03-review/review.json)；[类型失败日志](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/ts-pattern-match-each__DvfxCeq/verifier/test-stdout.txt)。

3. **python-statemachine：首次修订移除了通过评分的 SCXML 数据接入。** `x3H4heG` 初始 72/72，revision-1 起 70/72。首轮 Codex 指出 SCXML 数据与 guards/assignments 使用的副本不一致；修改后初始补丁中 processor.py 对 state.datamodel 的数据接入不再存在，两个 SCXML 用例的 get_state_data 返回 None。第二轮审查接受了 modifier 的 SCXML 反驳，最终 approve，评分没有恢复。这是协作修订过程中丢失既有评分行为，不能简单概括为 reviewer 直接要求删除该功能。[首轮审查](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/python-statemachine-state-data-s__x3H4heG/agent/system/rounds/01-review/review.json)；[后续审查](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/python-statemachine-state-data-s__x3H4heG/agent/system/rounds/03-review/review.json)；[两项 SCXML 失败](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/python-statemachine-state-data-s__x3H4heG/verifier/test-stdout.txt)。

4. **httpx：修复收益重复出现。** `MA3axBr` 从 107/108、`nDKr7PL` 从 106/108，均在第一次修订后达到 108/108。首轮反馈涉及按块及时产出 JSON 元素、数值跨块解析、解析失败时关闭响应流和字符编码/BOM 校验。之后继续修订但 binary 不再增加，最终一条 approve、一条到 review 上限。[首轮审查 A](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/httpx-streaming-json-iteration__MA3axBr/agent/system/rounds/01-review/review.json)；[首轮审查 B](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/httpx-streaming-json-iteration__nDKr7PL/agent/system/rounds/01-review/review.json)。

## 评审行为、超时与耗时

| 指标 | Codex → Claude | Claude → Codex |
|---|---:|---:|
| approved | 13 | 6 |
| max_reviews_reached | 1 | 6 |
| 超时降级但有交付 | 6 | 6 |
| 首次实现超时无交付 | 0 | 2 |
| 有效 review 数 | 28 | 47 |
| 要求 revise | 15/28（53.57%） | 41/47（87.23%） |
| 完成修订数 | 12 | 35 |
| approved 中 Final 仍失败 | 6/13 | 4/6 |
| Final 与 Initial 补丁完全相同 | 12/20 | 1/18 |
| 平均首次实现耗时 | 18.67 分钟 | 30.88 分钟 |
| 平均 modifier 总耗时 | 24.77 分钟 | 59.46 分钟 |
| 平均 reviewer 总耗时 | 25.32 分钟 | 11.68 分钟 |
| 平均角色执行时间合计 | 50.10 分钟 | 71.14 分钟 |

- 两方向各有 6 次 timeout degraded（30%）；反向另有两次首次实现失败（10%），总计 8/20 次受超时影响。反向 Helm 失败发生在 Codex reviewer 启动前，不能归因为 xhigh 审查。
- 两方向的 6 次 degraded 各保留 3 个 final 成功，都没有改变 initial 的 binary reward。去掉这些记录会产生选择偏差：完整协议子集分别为 6/14 → 8/14、8/12 → 6/12，应作为补充而非替代全量结果。
- 反向四次通过转失败最终全部被 approve，说明这批审查的通过判断与隐藏评分仍有错位；同样，另一方向 13 次 approve 中也有 6 次失败。approve 不等同于评分通过。
- 耗时来自 summary.result.usage 的 wallMs（首次实现来自对应 metadata），涵盖中断尝试，反向平均值包括两次约 85 分钟无交付；是模型角色执行时间及其工具等待之和，不是 job 墙钟耗时，也不是纯推理时长。两 job 并发不同，依赖下载及测试等待会影响耗时，不把时间增量全部归因于 effort。
- 不给出完整 token/美元成本：Codex → Claude 的 modifier usage 槽位为 20 partial + 15 unavailable，reviewer 为 28 complete + 3 unavailable；反向 modifier 为 54 complete + 7 unavailable，reviewer 为 47 partial + 1 unavailable。缺失不能作为零。

## 与 medium 的共同 9 题比较

xhigh 集合用 oxvg 替换 medium 集合的 scc，以下排除两者，只比较共同 9 题；medium 每题 4 次（36 次），xhigh 每题 2 次（18 次）。全部运行的成功数分母包括无交付，反向 xhigh 的 initial 成功 10/18 表示 10 次运行产出已通过 initial 的补丁，另外 2 次 initial 不存在；不是 18 个实测 initial 配对。

| 方向/effort | 全部运行 Initial 成功 | 全部运行 Final 成功 | 净变化 | 平均角色时间/运行 |
|---|---:|---:|---:|---:|
| Codex → Claude / medium | 16/36（44.44%） | 21/36（58.33%） | +13.89 pp | 31.12 分钟 |
| Codex → Claude / xhigh | 7/18（38.89%） | 9/18（50.00%） | +11.11 pp | 46.23 分钟 |
| Claude → Codex / medium | 23/36（63.89%） | 19/36（52.78%） | -11.11 pp | 47.57 分钟 |
| Claude → Codex / xhigh | 10/18（55.56%） | 8/18（44.44%） | -11.11 pp | 69.64 分钟 |

两个方向在共同 9 题上的 final 观测成功率均比 medium 低 8.33 pp，平均角色时间分别从 31.12 增至 46.23 分钟、47.57 增至 69.64 分钟。这个结果支持“目前没有看到 xhigh 的收益”，但不足以证明 xhigh 更差：每题仅两次，历史并发不完全一致，重复不是独立任务样本，且有网络/依赖等待与运行预算截断。反向 Claude 初始实现本身也在波动，因此不能把所有 final 差异归因于 Astra reviewer。

相同 9 题、相同 task checksum 和 runtime 镜像控制了部分条件；筛选来自历史 mini-swe-agent，仍不代表当前 CLI 的单体表现。initial 是 collab 中首次审查前的 checkpoint，不是独立随机分配的 single-agent 对照；“协作净变化”同时包含额外修订时间。

建议：下一批维持相同任务和预算，补齐每题 4 次后再下总体结论；单独列出无交付及 timeout degraded。ts-pattern 类型契约、wazero 压缩约束、SCXML 数据语义应另做需求/评分一致性复核。若测试放宽时间预算，应作为单独实验条件，不能混入本批。

## 逐 trial Initial / Final 明细

同一 task 的两个方向共四行相邻；F2P/P2P 为通过数/总数，N/A 表示没有配对评分。Trial ID 链接到原始阶段评分（无交付链接到运行 summary）；完整路径、时间、角色耗时与 task checksum 见 CSV。

### wazero-multi-module-snapshots

| 方向 | 重复 / Trial | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward I→F | Review/修订 | 结束方式 |
|---|---|---:|---:|---:|---:|---|---:|---|
| Codex → Claude | R1 / [exojTnd](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/wazero-multi-module-snapshots__exojTnd/patch-scores/stages.json) | 77/78 | 2/2 | 78/78 | 2/2 | 0→1 | 3/2 | 批准 |
| Codex → Claude | R2 / [9H7Xt57](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/wazero-multi-module-snapshots__9H7Xt57/patch-scores/stages.json) | 77/78 | 2/2 | 78/78 | 2/2 | 0→1 | 3/2 | 批准 |
| Claude → Codex | R1 / [2C94zCe](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/wazero-multi-module-snapshots__2C94zCe/patch-scores/stages.json) | 78/78 | 2/2 | 77/78 | 2/2 | 1→0 | 3/2 | 批准 |
| Claude → Codex | R2 / [A5D5fFg](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/wazero-multi-module-snapshots__A5D5fFg/patch-scores/stages.json) | 78/78 | 2/2 | 78/78 | 2/2 | 1→1 | 3/2 | 批准 |

### ts-pattern-match-each

| 方向 | 重复 / Trial | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward I→F | Review/修订 | 结束方式 |
|---|---|---:|---:|---:|---:|---|---:|---|
| Codex → Claude | R1 / [oAcD6bk](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/ts-pattern-match-each__oAcD6bk/patch-scores/stages.json) | 0/85 | 6/6 | 0/85 | 6/6 | 0→0 | 1/0 | 批准 |
| Codex → Claude | R2 / [PdSaRgc](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/ts-pattern-match-each__PdSaRgc/patch-scores/stages.json) | 0/85 | 6/6 | 0/85 | 6/6 | 0→0 | 1/0 | 批准 |
| Claude → Codex | R1 / [Do6HAPn](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/ts-pattern-match-each__Do6HAPn/patch-scores/stages.json) | 85/85 | 6/6 | 0/85 | 6/6 | 1→0 | 2/1 | 批准 |
| Claude → Codex | R2 / [DvfxCeq](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/ts-pattern-match-each__DvfxCeq/patch-scores/stages.json) | 85/85 | 6/6 | 0/85 | 6/6 | 1→0 | 3/2 | 批准 |

### python-statemachine-state-data-scoping

| 方向 | 重复 / Trial | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward I→F | Review/修订 | 结束方式 |
|---|---|---:|---:|---:|---:|---|---:|---|
| Codex → Claude | R1 / [heQko4J](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/python-statemachine-state-data-s__heQko4J/patch-scores/stages.json) | 69/72 | 1286/1286 | 69/72 | 1286/1286 | 0→0 | 0/0 | 超时降级 |
| Codex → Claude | R2 / [wHLxKfM](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/python-statemachine-state-data-s__wHLxKfM/patch-scores/stages.json) | 69/72 | 1286/1286 | 69/72 | 1286/1286 | 0→0 | 1/1 | 超时降级 |
| Claude → Codex | R1 / [VkWcbzz](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/python-statemachine-state-data-s__VkWcbzz/patch-scores/stages.json) | 72/72 | 1286/1286 | 72/72 | 1286/1286 | 1→1 | 3/3 | 评审上限 |
| Claude → Codex | R2 / [x3H4heG](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/python-statemachine-state-data-s__x3H4heG/patch-scores/stages.json) | 72/72 | 1286/1286 | 70/72 | 1286/1286 | 1→0 | 3/2 | 批准 |

### helm-array-merge-strategies

| 方向 | 重复 / Trial | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward I→F | Review/修订 | 结束方式 |
|---|---|---:|---:|---:|---:|---|---:|---|
| Codex → Claude | R1 / [NHN2bxk](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/helm-array-merge-strategies__NHN2bxk/patch-scores/stages.json) | 47/47 | 10/12 | 47/47 | 10/12 | 0→0 | 0/0 | 超时降级 |
| Codex → Claude | R2 / [A5gmet9](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/helm-array-merge-strategies__A5gmet9/patch-scores/stages.json) | 47/47 | 10/12 | 47/47 | 10/12 | 0→0 | 2/1 | 批准 |
| Claude → Codex | R1 / [gS96Azj](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/helm-array-merge-strategies__gS96Azj/agent/system/summary.json) | N/A | N/A | N/A | N/A | N/A（无交付） | 0/0 | 超时无交付 |
| Claude → Codex | R2 / [Pr8iVqD](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/helm-array-merge-strategies__Pr8iVqD/agent/system/summary.json) | N/A | N/A | N/A | N/A | N/A（无交付） | 0/0 | 超时无交付 |

### testem-bail-on-test-failure

| 方向 | 重复 / Trial | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward I→F | Review/修订 | 结束方式 |
|---|---|---:|---:|---:|---:|---|---:|---|
| Codex → Claude | R1 / [GKZqnpP](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/testem-bail-on-test-failure__GKZqnpP/patch-scores/stages.json) | 89/90 | 489/489 | 89/90 | 489/489 | 0→0 | 1/0 | 批准 |
| Codex → Claude | R2 / [exHRW53](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/testem-bail-on-test-failure__exHRW53/patch-scores/stages.json) | 89/90 | 489/489 | 89/90 | 489/489 | 0→0 | 1/0 | 批准 |
| Claude → Codex | R1 / [thWQvjE](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/testem-bail-on-test-failure__thWQvjE/patch-scores/stages.json) | 90/90 | 489/489 | 90/90 | 489/489 | 1→1 | 2/1 | 超时降级 |
| Claude → Codex | R2 / [jYjxfWs](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/testem-bail-on-test-failure__jYjxfWs/patch-scores/stages.json) | 88/90 | 489/489 | 88/90 | 489/489 | 0→0 | 3/3 | 评审上限 |

### httpx-streaming-json-iteration

| 方向 | 重复 / Trial | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward I→F | Review/修订 | 结束方式 |
|---|---|---:|---:|---:|---:|---|---:|---|
| Codex → Claude | R1 / [D4VQpvK](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/httpx-streaming-json-iteration__D4VQpvK/patch-scores/stages.json) | 108/108 | 1404/1404 | 108/108 | 1404/1404 | 1→1 | 2/1 | 批准 |
| Codex → Claude | R2 / [m7AssqB](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/httpx-streaming-json-iteration__m7AssqB/patch-scores/stages.json) | 108/108 | 1404/1404 | 108/108 | 1404/1404 | 1→1 | 2/1 | 批准 |
| Claude → Codex | R1 / [MA3axBr](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/httpx-streaming-json-iteration__MA3axBr/patch-scores/stages.json) | 107/108 | 1404/1404 | 108/108 | 1404/1404 | 0→1 | 3/2 | 批准 |
| Claude → Codex | R2 / [nDKr7PL](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/httpx-streaming-json-iteration__nDKr7PL/patch-scores/stages.json) | 106/108 | 1404/1404 | 108/108 | 1404/1404 | 0→1 | 3/3 | 评审上限 |

### koota-deferred-mutation-buffer

| 方向 | 重复 / Trial | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward I→F | Review/修订 | 结束方式 |
|---|---|---:|---:|---:|---:|---|---:|---|
| Codex → Claude | R1 / [J9wXUtC](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/koota-deferred-mutation-buffer__J9wXUtC/patch-scores/stages.json) | 71/71 | 128/128 | 71/71 | 128/128 | 1→1 | 2/1 | 超时降级 |
| Codex → Claude | R2 / [sKNw6vA](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/koota-deferred-mutation-buffer__sKNw6vA/patch-scores/stages.json) | 71/71 | 128/128 | 71/71 | 128/128 | 1→1 | 3/3 | 评审上限 |
| Claude → Codex | R1 / [g5Ze4xv](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/koota-deferred-mutation-buffer__g5Ze4xv/patch-scores/stages.json) | 70/71 | 128/128 | 70/71 | 128/128 | 0→0 | 2/1 | 超时降级 |
| Claude → Codex | R2 / [3beCr9z](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/koota-deferred-mutation-buffer__3beCr9z/patch-scores/stages.json) | 69/71 | 128/128 | 70/71 | 128/128 | 0→0 | 2/1 | 超时降级 |

### bandit-interprocedural-taint-checks

| 方向 | 重复 / Trial | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward I→F | Review/修订 | 结束方式 |
|---|---|---:|---:|---:|---:|---|---:|---|
| Codex → Claude | R1 / [PpTucpZ](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/bandit-interprocedural-taint-che__PpTucpZ/patch-scores/stages.json) | 66/66 | 293/293 | 66/66 | 293/293 | 1→1 | 1/0 | 批准 |
| Codex → Claude | R2 / [fQYXnzE](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/bandit-interprocedural-taint-che__fQYXnzE/patch-scores/stages.json) | 66/66 | 293/293 | 66/66 | 293/293 | 1→1 | 1/0 | 批准 |
| Claude → Codex | R1 / [WtkyWqv](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/bandit-interprocedural-taint-che__WtkyWqv/patch-scores/stages.json) | 66/66 | 293/293 | 66/66 | 293/293 | 1→1 | 3/2 | 超时降级 |
| Claude → Codex | R2 / [cKZqnei](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/bandit-interprocedural-taint-che__cKZqnei/patch-scores/stages.json) | 66/66 | 293/293 | 66/66 | 293/293 | 1→1 | 3/3 | 评审上限 |

### optique-conditional-option-dependencies

| 方向 | 重复 / Trial | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward I→F | Review/修订 | 结束方式 |
|---|---|---:|---:|---:|---:|---|---:|---|
| Codex → Claude | R1 / [fXYT5Tk](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/optique-conditional-option-depen__fXYT5Tk/patch-scores/stages.json) | 35/36 | 2034/2034 | 35/36 | 2034/2034 | 0→0 | 1/0 | 批准 |
| Codex → Claude | R2 / [RJhGFjW](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/optique-conditional-option-depen__RJhGFjW/patch-scores/stages.json) | 36/36 | 2034/2034 | 36/36 | 2034/2034 | 1→1 | 1/0 | 批准 |
| Claude → Codex | R1 / [cPspgY6](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/optique-conditional-option-depen__cPspgY6/patch-scores/stages.json) | 36/36 | 2034/2034 | 36/36 | 2034/2034 | 1→1 | 3/3 | 评审上限 |
| Claude → Codex | R2 / [GZ9uWzt](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/optique-conditional-option-depen__GZ9uWzt/patch-scores/stages.json) | 35/36 | 2034/2034 | 35/36 | 2034/2034 | 0→0 | 3/3 | 评审上限 |

### oxvg-structural-selector-preservation

| 方向 | 重复 / Trial | Initial F2P | Initial P2P | Final F2P | Final P2P | Reward I→F | Review/修订 | 结束方式 |
|---|---|---:|---:|---:|---:|---|---:|---|
| Codex → Claude | R1 / [VTwe6P5](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/oxvg-structural-selector-preserv__VTwe6P5/patch-scores/stages.json) | 6/6 | 62/62 | 6/6 | 62/62 | 1→1 | 1/0 | 超时降级 |
| Codex → Claude | R2 / [4QqzfGN](../../../jobs/collab-codex-claude-complementary-opus-astra-xhigh-10-tasks-20260912-123715/oxvg-structural-selector-preserv__4QqzfGN/patch-scores/stages.json) | 6/6 | 62/62 | 6/6 | 62/62 | 1→1 | 1/0 | 超时降级 |
| Claude → Codex | R1 / [M6iQFmS](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/oxvg-structural-selector-preserv__M6iQFmS/patch-scores/stages.json) | 6/6 | 62/62 | 6/6 | 62/62 | 1→1 | 1/0 | 超时降级 |
| Claude → Codex | R2 / [uCrQXqk](../../../jobs/collab-claude-codex-complementary-opus-astra-xhigh-10-tasks-20260912-123742/oxvg-structural-selector-preserv__uCrQXqk/patch-scores/stages.json) | 4/6 | 62/62 | 3/6 | 62/62 | 0→0 | 2/1 | 超时降级 |

