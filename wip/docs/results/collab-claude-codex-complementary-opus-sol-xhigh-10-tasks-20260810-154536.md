# collab-claude-codex-complementary-opus-sol-xhigh 结果分析（含配对重打分）

分析日期：2026-08-11。

[opus/sol 互补子集](../deepswe-opus-sol-complementary-subsets.md)（配对一：opus-high vs
sol-xhigh）的方向 A：Claude/opus-5（high）modifier + Codex/sol（xhigh）reviewer。反方向见
[B 方向结果](collab-codex-claude-complementary-opus-sol-xhigh-10-tasks-20260810-154601.md),
两方向合并结论见[实验总结](complementary-opus-sol-xhigh-collab-summary.md)。

原始工件：

- [job result](../../../jobs/collab-claude-codex-complementary-opus-sol-xhigh-10-tasks-20260810-154536/result.json)
- [patch-scores 汇总](../../../jobs/collab-claude-codex-complementary-opus-sol-xhigh-10-tasks-20260810-154536/patch-scores/summary.json)
- [配对表](../../../jobs/collab-claude-codex-complementary-opus-sol-xhigh-10-tasks-20260810-154536/patch-scores/pairs.csv)、[阶段表](../../../jobs/collab-claude-codex-complementary-opus-sol-xhigh-10-tasks-20260810-154536/patch-scores/stages.csv)
- 被替换 trial 的归档：`jobs/.removed-trials/collab-claude-codex-…-154536/pest-…__9Q3gD53/`

## 结论

1. 正式 reward `12/20 = 60%`。配对结果：initial `60%` = final `60%`，**3 修好 / 3 修坏,
   净效应精确为 0**——capture 与 harm 完全抵消，与 luna/v4-flash c→o 方向同构。
2. **sol reviewer 的 capture 是四种 reviewer 中最高的**：sol 强格子 7 个 initial 失败翻正
   3 个（43%；httpx-streaming ×2、scc ×1），全部补齐式（initial F2P 107/108、107/108、
   28/31），全部一轮 revision 完成。
3. **sol reviewer 的 harm 也是最高的**：opus 强格子 9 个满分 initial 被改坏 3 个（33%;
   pest ×2、python-statemachine ×1）。**pest 是整个研究最干净的自然实验**：opus 三次
   initial 全部 104/104 满分，review loop 运行的两次全被改坏（→103/104、→100/104）,
   唯一存活的是 review 因基础设施故障未运行的那次（见"运行史"，后被删除重跑，替补
   trial 再次被改坏）。
4. sol reviewer 审查风格与同族 codex/luna 一致：85% revise 率（7 approve / 41 revise）,
   findings 142 个中 92% blocking，12/20 trial 打满 max_reviews。
5. 评分管线 20/20 conformance matched；本 job 触发并修复了 discovery 的第三种中断形态
   （"快照后 reviewer 未启动"，详见下文）。

## 运行配置

| 项目 | 值 |
|---|---|
| 时间跨度 | 2026-08-10 15:45 → 08-11 18:12（含额度中断与两次 resume，见运行史） |
| 任务 / trials | 10（`complementary-opus-sol-xhigh`）/ 20（每题 2 次），并发 2 |
| Modifier | Claude `claude-opus-5`，effort `high`，permissions `bypass` |
| Reviewer | Codex `gpt-5.6-sol`，effort `xhigh`，permissions `bypass` |
| Budget / watchdog | multiplier 1.5（hard 8100 秒）/ 1200 秒 |
| Runtime | `deep-swe/agent-runtime:bd704fc758b47046` |
| Pier | `0.3.0` |

与 B 方向同时启动（claude+codex 各 ~2 并发），这是 claude adapter 首个正式 job（此前
经 5 个单体 + 1 个 collab 冒烟验证）。

## 运行史（透明记录）

1. **额度中断**：08-10 晚因模型额度将尽 Ctrl-C 中断（当时 5 完成），孤儿容器手工清理。
2. **resume 失误一次**：额度恢复后在 `wip/` 目录直接 `pier job resume` 触发
   `No module named 'wip'`，7 个 trial 启动即失败（零模型消耗），改为仓库根目录执行后恢复。
3. **koota `PXCJBfC` verifier 网络故障**：agent 阶段完成后 verifier 构建时 ECR 短暂不可达
   （RuntimeError），`resume -f RuntimeError` 重跑成功。
4. **pest `9Q3gD53` 删除重跑**：原 trial 为 degraded/infrastructure（review 未启动,
   initial 直接提交，reward=1）。经讨论后按用户决定删除重跑（原目录归档于
   `jobs/.removed-trials/`）；替补 trial `EijeAzS` 的 initial 同为满分,被 review 改坏,
   reward=0，**官方口径由 13/20 变为 12/20**。此替换是 result-relevant 操作,在此如实
   记录；它同时把 pest 的"无 review = 过,有 review = 挂"自然实验补充完整。

## 汇总指标

| 指标 | 值 |
|---|---:|
| Reward | 12 / 20（60%） |
| Outcome | 7 approved / 12 max_reviews_reached / 1 degraded（timeout） |
| Review / revision | 48 轮 / 40 次（48 attempts 零失败,zero watchdog 触发） |
| Findings | 142（**92% blocking**） |
| Verdict | 7 approve / 41 revise（85% revise 率） |
| opus-5 modifier tokens in/out | 441,996,879 / 2,446,776 |
| sol reviewer tokens in/out | 67,512,669 / 735,835 |
| Pier job 级 tokens in/out | 415,752,244 / 2,757,959（混合口径,≠ 角色求和） |

Token 口径：分角色数字来自各 trial `summary.json` 的 `result.usage`（20/20 齐全）;
input tokens 跨 adapter 语义不同（codex 含缓存重复计数,claude 口径另异）,只宜同模型
纵向对比,output 相对可比；cost 双侧均为 null（登录订阅制）;claude adapter 未上报
toolUses（计 0）。

## Task 级配对结果

| Task | 方向 | initial | final | 备注 |
|---|---|---:|---:|---|
| `koota-pair-relation-tracking` | opus 强 | 1/2 | 1/2 | |
| `participle-grammar-conflict-analysis` | opus 强 | 2/2 | 2/2 | |
| `pest-character-class-coalescing` | opus 强 | 2/2 | **0/2 ▼▼** | 两次均被 revision 改坏 |
| `python-statemachine-state-data-scoping` | opus 强 | 2/2 | **1/2 ▼** | 72/72 → 70/72 |
| `testem-bail-on-test-failure` | opus 强 | 2/2 | 2/2 | |
| `bandit-interprocedural-taint-checks` | sol 强 | 2/2 | 2/2 | opus 官方 0/4 → 内部 2/2（反转） |
| `csstree-shorthand-expansion-compression` | sol 强 | 0/2 | 0/2 | |
| `httpx-streaming-json-iteration` | sol 强 | 0/2 | **2/2 ▲▲** | 107/108 → 108/108 ×2 |
| `koota-deferred-mutation-buffer` | sol 强 | 0/2 | 0/2 | |
| `scc-bounded-memory-spilling` | sol 强 | 1/2 | **2/2 ▲** | 28/31 → 31/31 |
| **opus 强合计** | | **9/10** | 6/10 | |
| **sol 强合计** | | **3/10** | 6/10 | |

### 配对汇总

| 口径 | 对数 | initial | final | 修好 | 修坏 | 95% CI |
|---|---:|---:|---:|---:|---:|---|
| ITT | 20 | 60% | 60% | 3 | 3 | [−0.30, +0.30] |
| Completed-protocol | 19 | 63% | 63% | 3 | 3 | — |

## discovery 修复记录

pest `9Q3gD53`（删除前）触发第三种中断形态：runtime 写入 pre-review 快照后、reviewer
启动前遭遇基础设施故障，`01-review/` 只有 patch.diff 而无 metadata.json。
[patch_discovery.py](../../agent_eval/patch_discovery.py) 已扩展：metadata 完全缺失的
review 轮仅在"degraded trial + 末轮 + patch 非空"时作为不计数轮接受（快照写于 reviewer
启动前,内容可信）；metadata 存在但 role 错误仍 fail closed。配套 2 个 fixture 测试。

## 建议

见[实验总结](complementary-opus-sol-xhigh-collab-summary.md)；本方向单独的要点：sol
reviewer 高强度审查在自己弱的格子里是净风险源（pest/psm 共 3 例改坏均为满分 patch）,
任何后续使用都应引入"initial 全绿则限制 revision 范围"的保护。
