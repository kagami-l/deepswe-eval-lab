# luna/v4-flash 互补子集 collab 实验总结（两方向合并）

分析日期：2026-08-10。

本文合并 [c→o](collab-codex-opencode-complementary-luna-v4flash-10-tasks-20260809-003646.md)
与 [o→c](collab-opencode-codex-complementary-luna-v4flash-10-tasks-20260809-122655.md)
两个方向在[互补机制探测池](../deepswe-luna-v4flash-complementary-subset.md)上的结果，回答
该子集设计的核心问题：**review-loop 协作能捕获多少已知的模型互补收益**。并给出全部五个
配对 job（135 对）的机制总账与后续方向建议。

## 实验设置回顾

- 子集：10 题（5 luna 强 + 5 flash 强），由官方 mini-swe 数据按"一侧 ≥0.75、另一侧 ≤0.25"
  构造，oracle 路由的官方口径上限 ~95%、单配置 ~50%。
- 两方向 collab：modifier 与 reviewer 互换（luna xhigh ↔ v4-flash max），每题 4 次,
  `--agent-timeout-multiplier 1.5`；`score-patches` 事后配对评分（initial = modifier 单体
  代理，final = review-loop 终稿）。
- 预注册读数：reviewer 强格子的 capture rate、modifier 强格子的 harm rate。

## 总结果

| | c→o（luna 改，flash 审） | o→c（flash 改，luna 审） |
|---|---:|---:|
| 正式 reward | 15/40（37.5%） | 17/40（42.5%） |
| initial（modifier 单体代理） | 35.9%（ITT 39 对） | 42.1%（ITT 38 对） |
| final | 38.5% | 44.7% |
| 修好 / 修坏 | 3 / 2 | 1 / 0 |
| capture rate（reviewer 强格子） | 3/18 = 16.7%（全部 eicrud） | **0/14 = 0%** |
| harm rate（initial 通过被改坏） | 2/13 = 15.4% | 0/16 = 0% |
| conformance | 39 matched + 1 flaky（eval 侧,已复跑归因） | 38 matched |
| wall-clock / 成本焦点 | 9.5h | 17.7h,flash-max 成本 $5.26 |

## 读数一：oracle headroom 在内部大幅缩水,collab 捕获 <15%

用两方向 initial（direct 口径）构成内部单体矩阵：

| Task | 官方构造方向 | 内部 luna | 内部 flash | 内部判定 |
|---|---|---:|---:|---|
| `meriyah` | luna 强 | 2/4 | 0/3 | 弱化的 luna 强 |
| `superjson` | luna 强 | 0/4 | 0/4 | **双弱（结构失效）** |
| `numba` | luna 强 | 4/4 | 4/4 | **双强（结构失效）** |
| `valibot` | luna 强 | 4/4 | 1/4 | ✓ luna 强 |
| `sqlfmt` | luna 强 | 3/4 | 0/4 | ✓ luna 强 |
| `eicrud` | flash 强 | 1/4 | 4/4 | ✓ flash 强 |
| `onedump` | flash 强 | 0/4 | 1/4 | **双弱倾向（flash 强未复现）** |
| `python-statemachine` | flash 强 | 1/4 | 3/3 | ✓ flash 强 |
| `prometheus-transactional` | flash 强 | 0/4 | 1/4 | **双弱倾向（flash 强未复现）** |
| `anko` | flash 强 | 0/4 | 2/4 | ✓ flash 强（弱） |

- 官方口径的 headroom（单配置 ~50% → oracle ~95%）经内部迁移后收缩为:
  **单 luna 37.5% / 单 flash 42.1% → 内部 oracle ≈ 62.5%**，即 20–25pp。
  winner's curse 与 harness 迁移吃掉了一半以上的构造互补性;10 题中仅 6 题
  （valibot、sqlfmt、meriyah、eicrud、python-statemachine、anko）的互补方向存活。
- 两个 collab 配置的 final 各自只比自己 modifier 的单体高 ~2.6pp,
  **对内部 headroom 的捕获率约 10–13%**。同样的 headroom,任务级路由(按题选模型)
  的理论捕获率是 100%。

## 读数二：capture 只取决于缺口类型,不取决于 reviewer 能力

全部 135 个配对中共 6 次真实翻正（0→1），全部同型：**initial 已有部分 F2P 骨架,
review findings 指出剩余缺口,一轮 revision 补齐**：

| 案例 | Job | initial F2P → final |
|---|---|---|
| tomlkit `Yoaiwcp` | confirm c→o | 57/60 → 60/60 |
| bandit `UvV5LgS` | rest o→c | 18/66 → 66/66 |
| eicrud ×3 | 互补 c→o | 8/14 → 14/14（三次独立复现） |
| anko `uKc9Di6` | 互补 o→c | 5/9 → 9/9 |

反面证据同样一致：**当 initial 是路线级失败（接近 0 F2P）时,capture 为零**——即使
reviewer 恰好是会做这道题的模型（o→c 的 luna 强格子 0/14,codex reviewer 在 superjson
投入 10 轮 revision、sqlfmt 6 轮,全部无法跨过阈值）。findings 通道能传"改哪里",
传不了"怎么做"。

## 读数三：harm 与 reviewer 强度反相关

| Reviewer | initial 通过被改坏 | 案例 |
|---|---:|---|
| v4-flash（弱侧审强侧） | 4/49（confirm 1 + rest 1* + 互补 2） | go-critic、dateutil、meriyah、sqlfmt |
| codex/luna（强侧审弱侧） | 0/16 | — |

（* rest o→c 的 dateutil 属 codex 审 flash,归入下行？——该例中 reviewer 为 codex,
但被改坏的是 flash 的满分 patch,是弱 modifier 执行 revision 引入回归；两类破坏路径
——"弱 reviewer 提错误要求"与"弱 modifier 执行走样"——都已观测到。）

## 五个配对 job 总账（135 对）

| Job | 对数 | 修好 | 修坏 |
|---|---:|---:|---:|
| confirm c→o（20260806-224833） | 24 | 1 | 1 |
| rest c→o（-130605） | 18 | 0 | 0 |
| rest o→c（-130612） | 16 | 1 | 1 |
| 互补 c→o（-003646） | 39 | 3 | 2 |
| 互补 o→c（-122655） | 38 | 1 | 0 |
| **合计** | **135** | **6** | **4** |

净效应 +2/135 ≈ +1.5pp。review-loop 的机制画像至此完整：

> **能迁移"补齐式"能力（与 reviewer 强弱无关），不能迁移"路线式"能力（与 reviewer
> 强弱也无关）；弱侧参与 revision 时有 ~8–15% 的破坏率;整体净收益在任何已测配置下
> 都不超过噪声水平,而 wall-clock 成本增加 1.7–2.4 倍。**

## 建议

1. **停止 review-loop 配置扫描**。两方向、三个任务集、135 对的证据一致指向机制天花板,
   继续换模型/effort 组合的预期收益低于任何一个新机制实验。
2. **下一个实验测路由/多候选**：互补收益的正确形态是任务级选择。最小实验：两模型各出
   initial patch（复用单体 eval 即可）,按可见测试/自建 probe 选优提交,与 oracle 62.5%
   对比测"可实现路由"的捕获率。所需新基建极少（patch 选择器 + 现成 score-patches）。
3. **review-loop 的残值**在"补齐式"场景：若保留,应限定为"initial 已通过部分可见测试"
   时才触发 review,并禁止弱侧 reviewer 对全绿 patch 强制 revision（direct 数据显示这
   只带来破坏）。
4. **子集修订**（按替补规则，运行前冻结）：superjson（双弱）、numba（双强）出列;
   onedump、prometheus-transactional 的 flash 强前提未复现,降级或替换；eicrud 的
   flaky P2P 节点（167/168 一次性失败,复跑 3 次满分归因 eval 侧）报修。
5. 官方 → 内部迁移偏移已积累 5 例（bandit、superjson、numba、onedump、
   prometheus-transactional,方向不一）,后续任何用官方逐题数据做的设计都必须内置
   内部确认步骤——initial-as-single 的配对框架使这一步免费,应成为默认实践。
