# collab-codex-claude-complementary-opus-sol-xhigh 第二轮结果分析（含配对重打分）

分析日期：2026-08-12。

B 方向（sol 改,opus 审）的**预注册扩样轮**：与
[第一轮](collab-codex-claude-complementary-opus-sol-xhigh-10-tasks-20260810-154601.md)
配置逐项相同（含保留 bandit 于任务清单）,唯一差异为并发 2 → 4。主分析口径是两轮合并
40 对（见[实验总结](complementary-opus-sol-xhigh-collab-summary.md)的合并章节）,本文记录
单轮事实。

原始工件：

- [job result](../../../jobs/collab-codex-claude-complementary-opus-sol-xhigh-10-tasks-20260811-190656/result.json)
- [patch-scores 汇总](../../../jobs/collab-codex-claude-complementary-opus-sol-xhigh-10-tasks-20260811-190656/patch-scores/summary.json)
- [配对表](../../../jobs/collab-codex-claude-complementary-opus-sol-xhigh-10-tasks-20260811-190656/patch-scores/pairs.csv)、[阶段表](../../../jobs/collab-codex-claude-complementary-opus-sol-xhigh-10-tasks-20260811-190656/patch-scores/stages.csv)

## 结论

1. 正式 reward `8/20 = 40%`。配对：initial `40%` = final `40%`，**+1/−1,净 0**。
   第一轮的"净正零破坏"未能延续——这正是扩样要检验的问题（见总结文档合并读数）。
2. **opus reviewer 出现第一次破坏**：scc `FDKdUkJ` 满分 initial（31/31）被 revision 改坏
   （28/31）。位置精确落在机制规则的预测处：scc 是 sol 强题,opus 是弱侧 reviewer。
   "opus 零破坏"修正为"低破坏但非零"（两轮合并 1/17 ≈ 6%）。
3. 修好一例仍为真跨模型 capture：participle `hhSBpvL`（opus 强题、sol initial 0/2）
   89/91 → 91/91,补齐式,opus reviewer 两轮各贡献一例同型 capture（psm、participle）。
4. 运行干净：20/20 完成、0 errored、conformance 20/20 matched；conc 3 下 **6 小时 58 分**
   完成,无限流、无 watchdog 触发。2 个 degraded（1 timeout、1 infrastructure,均不影响
   eligibility）。
5. opus reviewer 本轮审查略趋严格：revise 率 60%（上轮 50%）,findings 155 个中 25%
   blocking（与上轮 23% 持平,远低于 sol/codex 家族的 ~90%）。

## 运行配置与汇总

| 项目 | 值 |
|---|---|
| 时间 | 2026-08-11 19:07 → 08-12 02:05（6h58m,无中断） |
| 配置 | 与第一轮完全一致（sol xhigh 改 / opus-5 high 审,multiplier 1.5,watchdog 1200） |
| 并发 | **3**（第一轮为 2;B 方向对预算不敏感,判定不影响可合并性,如实记录） |
| Reward | 8 / 20（40%） |
| Outcome | 16 approved / 2 max_reviews / 2 degraded（timeout、infrastructure 各 1） |
| Review / revision | 40 轮 / 23 次；verdict 16 approve / 24 revise |
| sol modifier tokens in/out | 444,164,985 / 2,320,487 |
| opus-5 reviewer tokens in/out | 113,496,036 / 1,325,333 |
| Pier job 级 tokens in/out | 457,956,884 / 3,242,888（混合口径,≠ 角色求和） |

Token 口径：分角色数字来自各 trial `summary.json` 的 `result.usage`（20/20 齐全）;
input tokens 跨 adapter 语义不同（codex 含缓存重复计数,claude 口径另异）,只宜同模型
纵向对比,output 相对可比；cost 双侧均为 null（登录订阅制）;claude adapter 未上报
toolUses（计 0）。

## Task 级配对结果

| Task | 方向 | initial | final | 备注 |
|---|---|---:|---:|---|
| `koota-pair-relation-tracking` | opus 强 | 0/2 | 0/2 | 5 次 revision 未跨阈值 |
| `participle-grammar-conflict-analysis` | opus 强 | 0/2 | **1/2 ▲** | 89/91 → 91/91,跨模型 capture |
| `pest-character-class-coalescing` | opus 强 | 0/2 | 0/2 | |
| `python-statemachine-state-data-scoping` | opus 强 | 0/2 | 0/2 | |
| `testem-bail-on-test-failure` | opus 强 | 0/2 | 0/2 | |
| `bandit-interprocedural-taint-checks` | sol 强 | 1/2 | 1/2 | |
| `csstree-shorthand-expansion-compression` | sol 强 | 2/2 | 2/2 | |
| `httpx-streaming-json-iteration` | sol 强 | 1/2 | 1/2 | |
| `koota-deferred-mutation-buffer` | sol 强 | 2/2 | 2/2 | |
| `scc-bounded-memory-spilling` | sol 强 | 2/2 | **1/2 ▼** | 31/31 → 28/31,opus reviewer 首次破坏 |
| **opus 强合计** | | **0/10** | 1/10 | |
| **sol 强合计** | | **8/10** | 7/10 | |

sol initial 本轮 8/20（上轮 9/20）,opus 强侧连续两轮 0/10,sol 单体的官方结构复现继续
干净（波动在 bandit 1/2、httpx 1/2 两格,均在 n=2 噪声内）。

## 与第一轮的对照要点

| | 第一轮 | 第二轮 |
|---|---:|---:|
| initial → final | 45% → 55% | 40% → 40% |
| 修好 / 修坏 | 2 / 0 | 1 / 1 |
| revise 率 / blocking 率 | 50% / 23% | 60% / 25% |
| degraded | 0 | 2 |

合并读数、规则检验更新与决策含义见[实验总结](complementary-opus-sol-xhigh-collab-summary.md)。
