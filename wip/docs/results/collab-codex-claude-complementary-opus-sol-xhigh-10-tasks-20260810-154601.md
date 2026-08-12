# collab-codex-claude-complementary-opus-sol-xhigh 结果分析（含配对重打分）

分析日期：2026-08-11。

[opus/sol 互补子集](../deepswe-opus-sol-complementary-subsets.md)（配对一）的方向 B：
Codex/sol（xhigh）modifier + Claude/opus-5（high）reviewer。反方向见
[A 方向结果](collab-claude-codex-complementary-opus-sol-xhigh-10-tasks-20260810-154536.md),
合并结论见[实验总结](complementary-opus-sol-xhigh-collab-summary.md)。

> 后续：本方向的[第二轮扩样](collab-codex-claude-complementary-opus-sol-xhigh-10-tasks-20260811-190656.md)
> （2026-08-12）未能延续本轮的"净正零破坏"——合并 40 对为 3↑/1↓（净 +5pp,p≈0.625）,
> 本文单轮结论的引用应以合并口径为准。

原始工件：

- [job result](../../../jobs/collab-codex-claude-complementary-opus-sol-xhigh-10-tasks-20260810-154601/result.json)
- [patch-scores 汇总](../../../jobs/collab-codex-claude-complementary-opus-sol-xhigh-10-tasks-20260810-154601/patch-scores/summary.json)
- [配对表](../../../jobs/collab-codex-claude-complementary-opus-sol-xhigh-10-tasks-20260810-154601/patch-scores/pairs.csv)、[阶段表](../../../jobs/collab-codex-claude-complementary-opus-sol-xhigh-10-tasks-20260810-154601/patch-scores/stages.csv)

## 结论

1. 正式 reward `11/20 = 55%`。配对结果：initial `45%` → final `55%`，**2 修好 / 0 修坏,
   净 +10pp**——**全部 7 个已测方向-配置中第一个净正且零破坏的**。CI `[0, +0.25]`,
   n=2 初筛样本，方向性信号而非定论。
2. **opus reviewer 是四种 reviewer 中唯一"克制"的**：50% revise 率（17/17），findings
   133 个中仅 23% blocking（sol/codex 家族为 89–92%）；17/20 trial 以 approved 结束,
   0 degraded、0 超时——审查克制直接换来零破坏（9 个通过 initial 全部保住）。
3. 2 个修好中,`python-statemachine __eEfCcr3`（69/72 → 72/72）是**真正的跨模型
   capture**——opus 教会了 sol 官方 0/4、内部 initial 0/2 的题；另一例 httpx-streaming
   （107/108 → 108/108）为 sol 自身强侧的补齐。两例仍均为补齐式。
4. sol 单体（initial）对官方结构的复现非常干净：sol 强侧 9/10、opus 强侧 0/10,
   零反转——与 A 方向合并后本子集互补结构 9/10 题存活（详见总结文档,oracle 90%）。
5. 评分管线 20/20 conformance matched，exit 0，无任何 layout 问题。

## 运行配置

| 项目 | 值 |
|---|---|
| 时间跨度 | 2026-08-10 15:46 → 08-11 11:31（含额度中断与 resume） |
| 任务 / trials | 10 / 20（每题 2 次），并发 2（与 A 方向并行启动） |
| Modifier | Codex `gpt-5.6-sol`，effort `xhigh`，permissions `bypass` |
| Reviewer | Claude `claude-opus-5`，effort `high`，permissions `bypass` |
| Budget / watchdog | multiplier 1.5（hard 8100 秒）/ 1200 秒 |
| Runtime | `deep-swe/agent-runtime:bd704fc758b47046` |
| Pier | `0.3.0` |

运行史：08-10 晚额度 Ctrl-C 中断（当时 7 完成），孤儿容器手工清理；额度恢复后一次
resume 顺利补齐全部剩余 trial，无 errored、无重跑。

## 汇总指标

| 指标 | 值 |
|---|---:|
| Reward | 11 / 20（55%） |
| Outcome | 17 approved / 3 max_reviews_reached / 0 degraded |
| Review / revision | 34 轮 / 17 次（34 attempts 零失败） |
| Findings | 133（**仅 23% blocking**） |
| Verdict | 17 approve / 17 revise（50% revise 率） |
| Tokens in/out | 429,367,549 / 2,901,809（cost 双侧均为 null） |

## Task 级配对结果

| Task | 方向 | initial | final | 备注 |
|---|---|---:|---:|---|
| `koota-pair-relation-tracking` | opus 强 | 0/2 | 0/2 | 6 次 revision 未跨过阈值 |
| `participle-grammar-conflict-analysis` | opus 强 | 0/2 | 0/2 | |
| `pest-character-class-coalescing` | opus 强 | 0/2 | 0/2 | |
| `python-statemachine-state-data-scoping` | opus 强 | 0/2 | **1/2 ▲** | 69/72 → 72/72,跨模型 capture |
| `testem-bail-on-test-failure` | opus 强 | 0/2 | 0/2 | 0 revision（opus 首轮 approve 了失败 patch） |
| `bandit-interprocedural-taint-checks` | sol 强 | 2/2 | 2/2 | |
| `csstree-shorthand-expansion-compression` | sol 强 | 2/2 | 2/2 | |
| `httpx-streaming-json-iteration` | sol 强 | 1/2 | **2/2 ▲** | 107/108 → 108/108 |
| `koota-deferred-mutation-buffer` | sol 强 | 2/2 | 2/2 | |
| `scc-bounded-memory-spilling` | sol 强 | 2/2 | 2/2 | |
| **opus 强合计** | | **0/10** | 1/10 | |
| **sol 强合计** | | **9/10** | 10/10 | |

### 配对汇总

| 口径 | 对数 | initial | final | 修好 | 修坏 | 95% CI |
|---|---:|---:|---:|---:|---:|---|
| ITT | 20 | 45% | 55% | 2 | 0 | [0, +0.25] |
| Completed-protocol | 20 | 45% | 55% | 2 | 0 | — |

## 读数解释

- **capture（opus 强格子）= 1/10**。低于 sol reviewer 的 43%,但两个零捕获的原因不同:
  testem 上 opus 首轮 approve 了失败 patch（"没拦"型,与其克制风格一致）;koota-pair 上
  投入 6 次 revision 未能跨过阈值（"教不会"型,路线级缺口）。克制审查减少了破坏,
  也减少了强推修复的机会——capture 与 harm 的正相关在 reviewer 风格层面同样成立。
- **harm = 0/9**。连同 luna 实验的 codex reviewer（0/16）,克制/对等及以上强度的
  reviewer 至今零破坏,与 flash（15%）、sol（33%）形成两个清晰的族群。

## 建议

见[实验总结](complementary-opus-sol-xhigh-collab-summary.md)。本方向单独要点：这是目前
唯一值得作为 review-loop 默认形态保留的配置画像——克制审查 + 补齐式触发；若后续做
"安全 review-loop"实验,以本方向为基线,叠加"initial 未全绿才触发 review"的条件。
