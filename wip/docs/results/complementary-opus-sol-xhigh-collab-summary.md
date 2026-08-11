# opus/sol 互补子集 collab 实验总结（两方向合并）

分析日期：2026-08-11。

本文合并 [A: opus 改,sol 审](collab-claude-codex-complementary-opus-sol-xhigh-10-tasks-20260810-154536.md)
与 [B: sol 改,opus 审](collab-codex-claude-complementary-opus-sol-xhigh-10-tasks-20260810-154601.md)
在 [opus/sol 互补子集（配对一）](../deepswe-opus-sol-complementary-subsets.md)上的结果,
回答本实验的核心问题：**表现最强的模型配对能否让 review-loop 协助得更好**。并更新全部
七个方向-配置、175 对的机制总账。前序实验见
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

## 读数三：175 对机制总账

| Job | 对数 | 修好 | 修坏 |
|---|---:|---:|---:|
| confirm c→o（224833） | 24 | 1 | 1 |
| rest c→o / o→c | 18 / 16 | 0 / 1 | 0 / 1 |
| luna 互补 c→o / o→c | 39 / 38 | 3 / 1 | 2 / 0 |
| **opus-sol A / B** | **20 / 20** | **3 / 2** | **3 / 0** |
| **合计** | **175** | **11** | **7** |

三条规律至今零反例：

1. **修好 11 例全部是补齐式**（本实验 5 例 initial F2P：107/108 ×3、28/31、69/72）,
   路线级失败（≈0 F2P 或大缺口）在任何 reviewer 下零捕获。
2. **修坏 7 例全部发生在 reviewer 弱格子**,且集中于高 revise 率 reviewer
   （flash 2、sol 3、codex 0、opus 0）。
3. **capture 与 harm 正相关于审查强度**：激进 reviewer（sol）两头都高,克制 reviewer
   （opus）两头都低;不存在"高 capture + 低 harm"的免费午餐配置。

## 结论与建议

1. **对主问题的回答**：最强配对确实把 capture 上限推到 43%,并首次出现净正零害的方向
   （B）,但 A 方向净 0 再次证明 review-loop 的收益-损害耦合是机制性的,不随模型能力
   解耦。两方向最好的 final（60%）仍只及内部 oracle（90%）的三分之二,
   **headroom 捕获率 ≤22%**。
2. **routing 论证达到最强形态**：双强配对下互补结构近乎完整保存（9/10 题、oracle 90%）,
   同样 40 个 initial patch,任务级选择器的理论上限比最好的 review-loop 高 30pp。
   下一个实验应直接做 routing/多候选选择（最小设计见 luna 总结文档建议 2）,
   opus/sol 是首选配对（成本论证见子集文档）。
3. **review-loop 的残值配方已收敛**：opus 式克制审查 + 仅在 initial 未全绿时触发 +
   预期缺口为补齐式。若要验证,以 B 方向为基线加触发条件做一个小型对照即可,
   不必再扫配置。
4. **子集维护**：bandit-interprocedural-taint-checks 从机制池移除（三次跨 harness 反转）;
   koota-pair、httpx-streaming、scc 的"弱化复现"在扩样时优先复核。
5. n=2 是初筛规模,两方向 CI 都宽（±0.25–0.30）。若要确认 B 方向的净正,按预注册路径
   扩样到 n=4 合并,而不是重跑替换。
