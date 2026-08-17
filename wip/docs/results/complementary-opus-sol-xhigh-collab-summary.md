# opus/sol 互补子集 collab 实验总结（两方向合并）

分析日期：2026-08-11；2026-08-12 并入 B 方向
[第二轮扩样](collab-codex-claude-complementary-opus-sol-xhigh-10-tasks-20260811-190656.md)
（B 方向合并至 40 对,总账更新至 195 对,见"B 方向扩样合并"与"读数三"）。

本文合并 [A: opus 改,sol 审](collab-claude-codex-complementary-opus-sol-xhigh-10-tasks-20260810-154536.md)
与 [B: sol 改,opus 审](collab-codex-claude-complementary-opus-sol-xhigh-10-tasks-20260810-154601.md)
在 [opus/sol 互补子集（配对一）](../deepswe-opus-sol-complementary-subsets.md)上的结果,
回答本实验的核心问题：**表现最强的模型配对能否让 review-loop 协助得更好**。前序实验见
[luna/v4-flash 总结](complementary-luna-v4flash-collab-summary.md)。

## 实验设置

- 子集：10 题（5 opus 强 + 5 sol 强），双侧 effort 家族佐证（证据条件优于 luna/v4-flash
  子集）；官方口径 oracle ≈ 95%、单配置 ≈ 50%。
- 两方向 collab：opus-5 high ↔ sol xhigh 互换 modifier/reviewer，每题 2 次（初筛规模）,
  multiplier 1.5、watchdog 1200 秒；`score-patches` 配对评分,conformance 双向 40/40 matched。
- 运行史：两 job 因模型额度中断过一次并 resume；A 方向另有 1 次网络故障重跑与 1 次
  用户决定的 pest trial 删除重跑（原目录归档），细节见各方向文档的透明记录。

## 总结果

| | A: opus 改,sol 审 | B: sol 改,opus 审 |
|---|---:|---:|
| 正式 reward | 12/20（60%） | 11/20（55%） |
| initial（单体代理） | 60% | 45% |
| final | 60% | 55% |
| 修好 / 修坏 | 3 / 3（净 0） | **2 / 0（净 +10pp）** |
| Reviewer verdict | 85% revise,92% blocking findings | 50% revise,23% blocking |
| Outcome | 12 max_reviews / 7 approved / 1 degraded | 17 approved / 3 max_reviews |

## B 方向扩样合并（2026-08-12 增补）

第二轮扩样与第一轮配置相同（并发 2→3,已判定不影响可合并性）。合并 40 对：

| B 方向 | 第一轮 | 第二轮 | **合并（n=4）** |
|---|---:|---:|---:|
| initial → final | 45% → 55% | 40% → 40% | **42.5% → 47.5%** |
| 修好 / 修坏 | 2 / 0 | 1 / 1 | **3 / 1（净 +5pp）** |
| 符号检验 | — | — | p ≈ 0.625,不显著 |
| opus reviewer capture（opus 强格子） | 1/10 | 1/10 | **2/20 = 10%** |
| opus reviewer harm（通过 initial） | 0/9 | 1/8 | **1/17 ≈ 6%** |

第一轮的"净正零破坏"未能延续：第二轮 scc `FDKdUkJ`（31/31 → 28/31）是 opus reviewer
的第一次破坏,位置精确落在 reviewer 弱格子（scc 为 sol 强题）。"opus 零破坏"据此修正为
"低破坏但非零"。opus reviewer 的两例 capture（psm 69/72→72/72、participle 89/91→91/91）
均为 opus 强题上的真跨模型迁移、均为补齐式——**capture 类型规律在强 reviewer 上同样
成立,但速率止步 10%**。"安全 review-loop"假设降级为：opus 式克制审查是 harm 最低的
配置（6% vs sol 33%）,但不是零,且净收益不显著。

## 读数一：内部确认与 oracle——双强配对的互补结构保存得最好

| Task | 官方方向 | 内部 opus | 内部 sol | 判定 |
|---|---|---:|---:|---|
| `koota-pair-relation-tracking` | opus 强 | 1/2 | 0/2 | ✓（弱化） |
| `participle-grammar-conflict-analysis` | opus 强 | 2/2 | 0/2 | ✓ |
| `pest-character-class-coalescing` | opus 强 | 2/2 | 0/2 | ✓ |
| `python-statemachine-state-data-scoping` | opus 强 | 2/2 | 0/2 | ✓ |
| `testem-bail-on-test-failure` | opus 强 | 2/2 | 0/2 | ✓ |
| `bandit-interprocedural-taint-checks` | sol 强 | **2/2** | 2/2 | **反转 → 双强**（跨 harness 第三次翻脸） |
| `csstree-shorthand-expansion-compression` | sol 强 | 0/2 | 2/2 | ✓ |
| `httpx-streaming-json-iteration` | sol 强 | 0/2 | 1/2 | ✓（弱化） |
| `koota-deferred-mutation-buffer` | sol 强 | 0/2 | 2/2 | ✓ |
| `scc-bounded-memory-spilling` | sol 强 | 1/2 | 2/2 | ✓（弱化） |

- **9/10 题互补结构存活**（luna/v4-flash 为 6/10），唯一失效的 bandit 又是它——该题在
  三个实验里三种不同方向的官方↔内部反转,应从后续机制池中移除。
- **内部 oracle ≈ 90%**（luna/v4-flash 为 62.5%）,单 opus 60%、单 sol 45%。headroom
  30–45pp,是所有配对中最大、最干净的。

## 读数二：capture 与 harm——四种 reviewer 完整对照

| Reviewer | 强格子 capture | 弱格子 harm（对通过 initial） | revise 率 |
|---|---:|---:|---:|
| v4-flash max | 3/18 = 17% | 2/13 = 15% | ~56% |
| codex luna xhigh | 0/14 = 0% | 0/16 = 0% | 87% |
| **sol xhigh** | **3/7 = 43%** | **3/9 = 33%** | 85% |
| **opus-5 high** | 1/10 = 10% | **0/9 = 0%** | 50% |

- **"最强配对协助得更好"在 capture 侧成立**：sol reviewer 43% 是全场最高,三例全部
  一轮 revision 完成修复。
- **harm 侧同步放大**：sol 在自己不会做的 opus 强题上改坏 3 个满分 patch（33%）。
  **pest 自然实验**是最有说服力的单点证据：opus 三次 initial 全部 104/104,review loop
  运行的两次全被改坏,唯一存活的是 review 因基础设施故障未运行的那次。
- **B 方向是七个方向-配置中第一个净正且零破坏的**（+10pp,CI [0, +0.25]）。opus 的
  克制审查（50% revise、23% blocking）直接换来零破坏,代价是 capture 只有 10%
  （testem 上"没拦"、koota-pair 上"教不会"各占一半）。

## 读数三：195 对机制总账（含 B 方向第二轮）

| Job | 对数 | 修好 | 修坏 |
|---|---:|---:|---:|
| confirm c→o（224833） | 24 | 1 | 1 |
| rest c→o / o→c | 18 / 16 | 0 / 1 | 0 / 1 |
| luna 互补 c→o / o→c | 39 / 38 | 3 / 1 | 2 / 0 |
| opus-sol A | 20 | 3 | 3 |
| opus-sol B 第一轮 / 第二轮 | 20 / 20 | 2 / 1 | 0 / 1 |
| opus-sol B [candidates 扫描轮](collab-codex-claude-complementary-opus-sol-xhigh-candidates-18-tasks-20260813-215326.md)（2026-08-14 增补） | 36 | 1 | 1 |
| opus-sol B [candidates 第二轮](collab-codex-claude-complementary-opus-sol-xhigh-candidates-18-tasks-20260814-100738.md)（2026-08-14 增补） | 36 | 4 | 2 |
| **合计** | **267** | **17** | **11** |

三条规律至今零反例：

1. **修好 17 例全部是广义补齐式**（candidates 两轮新增 5 例,初始缺口最大的是
   onedump 76/82;bandit `mcvgbyY` 案例是首例"修复 initial 的 P2P 存量破坏"）,
   路线级失败（≈0 F2P 或大缺口）在任何 reviewer 下零捕获。opus reviewer 在
   **验证过的强格子**的真跨模型 capture 累计 4 例（psm、participle、dasel、
   onedump）。
2. **修坏 11 例中 0 例发生在验证过的 reviewer 强格子**（精确化表述,2026-08-14）:
   9 例在验证过的 reviewer 弱格子（flash 2、sol 3、codex 0、opus 2——scc ×2）,
   2 例（happy-dom ×2,candidates 第二轮）发生在**方向未证实/已失效**的任务上——
   该题的"opus 强"标签本就因家族不佐证被拒收,内部 sol initial 3/4 进一步否定,
   reviewer 在无真实优势的任务上强行 revise 导致破坏,机制与规则本义一致。
   格子归属自此以验证过的方向为准,方向失效任务（bandit、happy-dom、abs-module）
   不参与格子读数。
3. **capture 与 harm 正相关于审查强度**：激进 reviewer（sol,85% revise）两头最高,
   克制 reviewer（opus,50–60% revise）两头最低;不存在"高 capture + 低 harm"的
   免费午餐配置。

## 结论与建议

1. **对主问题的回答**：最强配对确实把 capture 上限推到 43%（sol reviewer）,但 A 方向
   净 0、B 方向合并后净 +5pp（p≈0.625）——review-loop 的收益-损害耦合是机制性的,
   不随模型能力解耦。两方向最好的 final（60%）仍只及内部 oracle（90%）的三分之二,
   **headroom 捕获率 ≤22%**。
2. **routing 论证达到最强形态**：双强配对下互补结构近乎完整保存（9/10 题、oracle 90%）,
   同样的 initial patch,任务级选择器的理论上限比最好的 review-loop 高 30pp。
   下一个实验应直接做 routing/多候选选择（最小设计见 luna 总结文档建议 2）,
   opus/sol 是首选配对（成本论证见子集文档）。routing 底料现状：sol initial n=4 已齐,
   opus initial 尚为 n=2（A 方向扩样轮可按"底料采集"定位补齐,预期无机制惊喜）。
3. **"安全 review-loop"假设经扩样降级**：opus 式克制审查是 harm 最低配置
   （1/17 ≈ 6%,对比 sol 33%）但非零,净收益不显著。残值配方维持——克制审查 +
   仅在 initial 未全绿时触发 + 预期缺口为补齐式——但其验证实验的优先级应排在
   routing 之后。
4. **子集维护**：bandit-interprocedural-taint-checks 从机制池移除（三次跨 harness 反转）;
   koota-pair、httpx-streaming、scc 的"弱化复现"在扩样时优先复核。
5. 机制研究阶段就此收档：195 对、七个方向-配置、三条零反例规律。后续新增配对数据
   （如 A 方向扩样）只更新总账,不再重开机制结论。
