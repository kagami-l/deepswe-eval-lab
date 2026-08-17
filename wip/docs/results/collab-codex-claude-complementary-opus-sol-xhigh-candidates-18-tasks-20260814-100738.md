# collab-codex-claude candidates 扫描第二轮结果分析（18 题,含配对重打分）

分析日期：2026-08-14。

[candidates 扫描第一轮](collab-codex-claude-complementary-opus-sol-xhigh-candidates-18-tasks-20260813-215326.md)
的**同配置扩样轮**（B 方向:sol 改,opus 审;18 题 × 2）,把 sol 侧内部确认合并到
n=4。合并读数与子集修订修订见文末;机制总账更新见
[实验总结](complementary-opus-sol-xhigh-collab-summary.md)。

原始工件：

- [job result](../../../jobs/collab-codex-claude-complementary-opus-sol-xhigh-candidates-18-tasks-20260814-100738/result.json)
- [patch-scores 汇总](../../../jobs/collab-codex-claude-complementary-opus-sol-xhigh-candidates-18-tasks-20260814-100738/patch-scores/summary.json)
- [配对表](../../../jobs/collab-codex-claude-complementary-opus-sol-xhigh-candidates-18-tasks-20260814-100738/patch-scores/pairs.csv)、[阶段表](../../../jobs/collab-codex-claude-complementary-opus-sol-xhigh-candidates-18-tasks-20260814-100738/patch-scores/stages.csv)

## 结论

1. 正式 reward `18/36 = 50%`（第一轮 30.6%）。**涨幅几乎全部是 n=2 小样本摆动**:
   两轮合并后逐题与官方比率高度吻合（dasel 合并 initial 2/4 vs 官方 1/4、ink 2/4 vs
   3/4、httpx-streaming 与 arktype 均 3/4 vs 3/4）,合并口径官方 29/72（40.3%）、
   initial 27/72（37.5%）才是该方向的稳定估计。
2. 配对：initial 44.4% → final 50.0%，**+4/−2**。4 例修好中 2 例是 opus reviewer 在
   **验证过的强格子**的真跨模型 capture（dasel `t3yqPLe` 144/146→146/146、onedump
   `KRUxX5y` 76/82→82/82,均补齐式）;另 2 例（abs、bandit）发生在方向已失效的任务上,
   不计入格子读数。
3. **happy-dom 双重 harm 是规则 2 的边界案例而非反例**：两个 trial 的 sol initial 均
   满分（14/14 + 9/9）,opus reviewer 要求 revision 后同样打破 3 个 F2P（11/14）→ 0。
   happy-dom 的"opus 强"标签正是当初以家族不佐证拒收、且被内部数据否定的
   （sol initial 合并 3/4）——reviewer 在**无真实优势**的任务上强行 revise 导致破坏,
   机制与规则本义吻合。规则表述精确化为："修坏 0 例发生在**验证过的** reviewer 强
   格子"（见总结文档）。
4. **第一轮的 ink 结论撤销修订**：本轮两个 initial 均满分,合并 2/4——ink 是高波动
   任务而非"做不出",从"预警兑现,不转正"改判为"维持替补,标注高波动"。
5. python-statemachine 出现 sol 单体满分（`estzSZt`,官方 0/4）——弱侧偶发做出,
   合并 1/4,方向未失效但列入观察。
6. 评分一次干净：conformance 36/36 matched、0 problems、exit 0（第一轮的两类抖动
   未复现）。

## 运行配置与汇总

| 项目 | 值 |
|---|---|
| 时间 | 2026-08-14 10:07 → 18:41（8h34m,无中断） |
| 配置 | 与第一轮完全一致（含并发 4、multiplier 1.5、watchdog 1200、cligent 0.20.0 runtime） |
| Reward | 18 / 36（50%） |
| Outcome | 32 approved / 2 max_reviews / 2 degraded（bandit reviewer_failed、pest timeout） |
| Review / revision | 65 轮有效 / 33 次；verdict 32 approve / 33 revise（51% revise） |
| Findings | 231（21% blocking） |
| Reviewer attempts | 69（4 失败,含 bandit 一轮 reviewer_failed degraded） |
| 平均 / 中位 / 最长 trial | 53 / 48 / 131 分钟 |
| sol modifier tokens in/out | 559,039,726 / 3,226,104 |
| opus-5 reviewer tokens in/out | 141,300,818 / 1,891,930 |

## Trial 级明细（仅列有信息量的行,全量见 pairs.csv）

| Trial | 能力倾向 | initial | final | Rev | 说明 |
|---|---|---:|---|---:|---|
| dasel `QfPdfHq` | opus 强 | 1 | 1 | 0 | sol 单体直接做出（官方 1/4 内) |
| dasel `t3yqPLe` | opus 强 | 0 | **1 ▲** | 1 | 144/146 → 146/146,强格子 capture |
| onedump `KRUxX5y` | opus 强 | 0 | **1 ▲** | 1 | 76/82 → 82/82,强格子 capture |
| onedump `8bgCgKe` | opus 强 | 0 | 0 | 0 | 71/82 缺口,首轮 approve 未拦 |
| psm `estzSZt` | opus 强 | 1 | 1 | 1 | **sol 单体满分**（官方 0/4） |
| psm `QEGB6tq` | opus 强 | 0 | 0 | 1 | 69/72,revision 未补上（与 B1 capture 同缺口） |
| happy-dom `AVWhQ28` | 方向失效 | 1 | **0 ▼** | 2 | 满分 → 11/14 |
| happy-dom `UU7r426` | 方向失效 | 1 | **0 ▼** | 1 | 满分 → 11/14,两 trial 同型 |
| abs `LbhZ5Ku` | 方向失效 | 0 | **1 ▲** | 1 | 19/20 → 20/20 |
| bandit `tBhoqV8` | 方向失效 | 0 | **1 ▲** | 1 | 64/66 → 66/66 |
| ink `PS3vsfh` / `rCGmeR3` | sol 强 | 1 / 1 | 1 / 1 | 1 / 1 | 两个 initial 均满分（第一轮为 0/2） |

## 两轮 candidates 合并（B 方向 n=4 × 18 题）

| 口径 | 第一轮 | 第二轮 | **合并** |
|---|---:|---:|---:|
| 官方 reward | 11/36 | 18/36 | **29/72（40.3%）** |
| initial（sol 单体） | 11/36 | 16/36 | **27/72（37.5%）** |
| 修好 / 修坏 | 1 / 1 | 4 / 2 | **5 / 3** |

逐题合并 initial 与官方对照（仅列有变化解读的）：

| Task | 官方 sol-xhigh | 内部合并 initial | 判定更新 |
|---|---:|---:|---|
| `ink-grid-box-layout` | 3/4 | 2/4 | **改判**:高波动,维持替补并标注（撤销第一轮"预警兑现"） |
| `dasel-html-document-format` | 1/4 | 2/4 | 与官方一致,维持替补 |
| `python-statemachine` | 0/4 | 1/4 | 弱侧偶发,列入观察 |
| `abs-module` / `happy-dom` | 1/4 / 1/4 | 2/4 / 3/4 | **拒收判定强化**（sol 侧比官方更强,方向进一步失效） |
| 其余 13 题 | — | — | 第一轮判定维持 |

## 建议

1. 合并口径写入子集修订：ink 改判、happy-dom 拒收强化并与 bandit 同列"方向失效"
   （其 harm/capture 不再按格子解读）;
2. opus reviewer 验证强格子 capture 升至 4 例（psm、participle、dasel、onedump）,
   全部补齐式——"克制 reviewer 的 capture 依赖缺口恰好是补齐型"的画像更扎实;
3. B 方向数据至此充分（18 题 n=4 + 10 题 n=4）;剩余缺口仍是 **A 方向（opus 改）的
   candidates 轮**,补齐后 routing 底料矩阵闭环。
