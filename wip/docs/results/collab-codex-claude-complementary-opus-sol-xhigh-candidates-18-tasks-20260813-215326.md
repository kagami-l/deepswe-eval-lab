# collab-codex-claude candidates 扫描轮结果分析（18 题候选池,含配对重打分）

分析日期：2026-08-14。

B 方向（sol 改,opus 审）在 [opus/sol 互补候选池](../deepswe-opus-sol-complementary-subsets.md)
**全部 18 题**（正选 + 替补 + 被拒候选 + confirm 题 clack）上的扫描轮。三重用途：

1. **子集修订复核**：用内部 initial（sol 单体）检验候选扫描表的逐题判定,含被拒题的
   "翻车验证"；
2. **routing 底料**：sol 侧 initial 矩阵扩展到 18 题；
3. **opus reviewer 追加观测**：并入机制总账（结论按约定不重开）。

本轮起机制线不再回避 confirm 任务（决策注记见子集文档 2026-08-13 更新）。
前两轮 B 方向见[第一轮](collab-codex-claude-complementary-opus-sol-xhigh-10-tasks-20260810-154601.md)、
[第二轮](collab-codex-claude-complementary-opus-sol-xhigh-10-tasks-20260811-190656.md),
合并语境见[实验总结](complementary-opus-sol-xhigh-collab-summary.md)。

> 后续：[candidates 扫描第二轮](collab-codex-claude-complementary-opus-sol-xhigh-candidates-18-tasks-20260814-100738.md)
> （2026-08-14,同配置扩样至 n=4）修订了本文的两项逐题结论——**ink 改判为高波动**
> （合并 initial 2/4,撤销"预警兑现"）,happy-dom 拒收强化并列为"方向失效"。
> 逐题引用以合并口径为准。

原始工件：

- [job result](../../../jobs/collab-codex-claude-complementary-opus-sol-xhigh-candidates-18-tasks-20260813-215326/result.json)
- [patch-scores 汇总](../../../jobs/collab-codex-claude-complementary-opus-sol-xhigh-candidates-18-tasks-20260813-215326/patch-scores/summary.json)
- [配对表](../../../jobs/collab-codex-claude-complementary-opus-sol-xhigh-candidates-18-tasks-20260813-215326/patch-scores/pairs.csv)、[阶段表](../../../jobs/collab-codex-claude-complementary-opus-sol-xhigh-candidates-18-tasks-20260813-215326/patch-scores/stages.csv)
- arktype 抖动记录归档：`<trial>/patch-scores/results-run1-backup/`

## 结论

1. 正式 reward `11/36 = 30.6%`。36/36 完成、0 errored；配对 initial `30.6%` = final
   `30.6%`，+1/−1,净 0。
2. **筛选方法论获得系统性预测验证**：18 题中互补方向干净复现 15 题；3 个"翻车"题
   （abs-module 1/2、happy-dom 1/2、ink 0/2）**全部是子集文档预先以"家族不佐证 /
   档位依赖"标记过的**——规则先于数据给出了正确判定。
3. `clack`（confirm 题,opus 强 A 档）sol initial 0/2 干净复现,可转正为可用替补;
   `koota-query`、`dasel`、`onedump` 等替补的 sol 侧同样确认。
4. **capture 出现新形态**：bandit `mcvgbyY` 的 initial F2P 全过但 **P2P 19/293**
   （initial 破坏了存量行为）,opus reviewer 首轮 findings 推动一次 revision 把 P2P 修回
   293/293 → reward 翻正。此前 12 例修好全是"补 F2P 缺口",这是第一例"修 P2P 破坏",
   仍属"小缺口 + findings 可指出"的广义补齐式。
5. **scc 第二次被 opus reviewer 改坏**（`atEszX4`：满分 → revision-1 打破 1 个 P2P）,
   与第二轮 `FDKdUkJ` 同任务、同格子（reviewer 弱格子）,conformance matched 排除
   verifier 抖动。opus reviewer 合并 harm 上升至 2/28 ≈ 7%。
6. 评分管线经历两次**瞬时基础设施抖动**并按设计流程处理干净（见"score-patches 运行
   记录"）,最终 36/36 conformance matched、exit 0。

## 运行配置

| 项目 | 值 |
|---|---|
| 时间 | 2026-08-13 21:53 → 08-14 06:01（8h08m,无中断） |
| 任务 / trials | 18（candidates 池）/ 36（每题 2 次）,并发 4 |
| Modifier / Reviewer | Codex `gpt-5.6-sol` xhigh / Claude `claude-opus-5` high |
| Budget / watchdog | multiplier 1.5（hard 8100 秒）/ 1200 秒 |
| Runtime | manifest digest `e991c576…`（**cligent 0.20.0**,区别于前两轮的 0.18.0） |
| Pier | `0.3.0` |

## 运行事件与修复

1. **凭证清理竞态告警 ×1**（pest `P8eo5ZZ`）：runtime 退出后残留子进程仍向
   `/tmp/deep-swe-agent-home` 写入,`rm -rf` 报 "Directory not empty"。凭证目录
   （`REMOTE_SECRETS`,列在命令首位）已成功删除,工件扫描无泄漏,结果零影响。
   已修复：[pier_agent.py](../../agents/deep_swe_agent/pier_agent.py) 的
   `_cleanup_credentials` 改为失败后 2 秒重试一次,配 2 个单测。
2. **score-patches 两次瞬时抖动**。背景：score-patches 是事后补丁重打分工序——为
   trial 留存的每份补丁（初稿、各轮修订稿）新建全新测试容器重跑完整测试套件,并把
   "最终提交补丁"的重跑得分与正式评测当时的得分做一致性核对。本轮遇到两次容器侧
   的一次性故障：
   - bandit `eoChrUK` 的一份补丁重跑连续失败两次（一次容器操作报错,一次测试跑完
     却没有产出记分文件）→ 按提示做幂等重跑,一次补验成功（42 秒）;
   - arktype `VoWNjeD`：正式评测满分（新功能 25/25、存量 1679/1679）,事后重跑却
     出现反常结果——新功能测试全过、1679 个存量测试只过 2 个,且第一次尝试连记分
     文件都没产出。补丁字节未变而存量测试近乎全挂,判定为**重跑新建容器的依赖安装
     一次性故障**（存量套件根本没能运行起来）,不是补丁问题。备份异常记录后强制
     重跑：两份补丁均满分,与正式评测一致。与 eicrud 案例方向相反——那次是正式评测
     侧挂了 1 个测试、事后重跑三次都满分;两个方向的抖动,现有流程（备份 → 强制
     重跑 → 归因）都已验证可处理。

## 汇总指标

| 指标 | 值 |
|---|---:|
| Reward | 11 / 36（30.6%） |
| Outcome | 31 approved / 4 max_reviews / 1 degraded（psm,timeout） |
| Review / revision | 63 轮有效 / 31 次；verdict 31 approve / 32 revise（51% revise） |
| Findings | 235（19% blocking,克制画像与前两轮一致） |
| Reviewer attempts | 64（0 失败,0 watchdog 触发） |
| 平均 / 中位 / 最长 trial | 49 / 39 / 131 分钟 |
| sol modifier tokens in/out | 604,137,098 / 3,374,077 |
| opus-5 reviewer tokens in/out | 151,338,644 / 1,970,260 |

Token 口径同前（codex/claude 含缓存累计,cost null;详见 token_usage.py caveats）。

## Task 级结果（initial = sol 单体确认）

`官方` 两列取自子集文档的配对一候选扫描表（mini-swe harness,每格 4 次）；`initial` 为
本 job 的内部 sol 单体口径,与`官方 sol-xhigh` 列直接对比即是逐题复核。

| Task | 扫描表判定 | 官方 opus-high | 官方 sol-xhigh | initial（内部 sol） | final | 复核结论 |
|---|---|---:|---:|---:|---:|---|
| `clack-async-autocomplete-options` | opus 强 A（confirm 隔离） | 4/4 | 0/4 | 0/2 | 0/2 | ✓ 复现,可转正替补 |
| `koota-pair-relation-tracking` | opus 强 A（正选） | 4/4 | 0/4 | 0/2 | 0/2 | ✓ |
| `koota-query-predicates` | opus 强 A⁻（替补） | 3/3 | 0/4 | 0/2 | 0/2 | ✓ |
| `participle-grammar-conflict-analysis` | opus 强 A（正选） | 4/4 | 0/4 | 0/2 | 0/2 | ✓ |
| `python-statemachine-state-data-scoping` | opus 强 A（正选） | 4/4 | 0/4 | 0/2 | 0/2 | ✓ |
| `testem-bail-on-test-failure` | opus 强 A（正选） | 4/4 | 0/4 | 0/2 | 0/2 | ✓ |
| `abs-module-cache-flags` | **家族不佐证,拒收** | 4/4 | 1/4 | **1/2** | 1/2 | **翻车如预测** |
| `dasel-html-document-format` | opus 强 B（替补） | 4/4 | 1/4 | 0/2 | 0/2 | ✓ |
| `onedump-dump-encryption-pipeline` | opus 强 B（替补） | 3/4 | 0/4 | 0/2 | 0/2 | ✓ |
| `pest-character-class-coalescing` | opus 强 B（正选） | 3/4 | 0/4 | 0/2 | 0/2 | ✓ |
| `happy-dom-deterministic-intersectionobserver` | **C 档且家族不佐证,拒收** | 3/4 | 1/4 | **1/2** | 1/2 | **翻车如预测** |
| `bandit-interprocedural-taint-checks` | sol 强 A（已标记移出机制池） | 0/4 | 4/4 | 1/2 | **2/2 ▲** | 摇摆依旧,维持移出 |
| `koota-deferred-mutation-buffer` | sol 强 A（正选） | 0/4 | 4/4 | 2/2 | 2/2 | ✓ |
| `csstree-shorthand-expansion-compression` | sol 强 B（正选） | 1/4 | 4/4 | 2/2 | 2/2 | ✓ |
| `httpx-streaming-json-iteration` | sol 强 B（正选） | 0/4 | 3/4 | 1/2 | 1/2 | ✓（弱） |
| `ink-grid-box-layout` | **sol 家族仅 9/20,仅替补** | 0/4 | 3/4 | **0/2** | 0/2 | **预警兑现,不转正** |
| `scc-bounded-memory-spilling` | sol 强 B（正选,评分敏感） | 1/4 | 4/4 | 2/2 | **1/2 ▼** | ✓;harm 见下 |
| `arktype-json-schema-refs-dependencies` | sol 强 C（替补） | 1/4 | 3/4 | 1/2 | 1/2 | ✓（弱） |
| **opus 强合计** | | **40/43** | **3/44** | **2/22** | 2/22 | |
| **sol 强合计** | | **3/28** | **25/28** | **9/14** | 10/14 | |

## Trial 级明细

`initial` / `final` 为该补丁的重打分 reward；`▲` = 修好，`▼` = 修坏。

| Trial | 能力倾向 | initial | final | Review | Revision | 最终状态 |
|---|---|---:|---|---:|---:|---|
| abs-module `Py9cieT` | opus 强 | 0 | 0 | 3 | 2 | approved |
| abs-module `xB7q9E6` | opus 强 | 1 | 1 | 1 | 0 | approved |
| clack `QzoxVGT` | opus 强 | 0 | 0 | 1 | 0 | approved |
| clack `RYkNTJd` | opus 强 | 0 | 0 | 1 | 0 | approved |
| dasel `4HXb3TV` | opus 强 | 0 | 0 | 1 | 0 | approved |
| dasel `LqLHNM8` | opus 强 | 0 | 0 | 1 | 0 | approved |
| happy-dom `YKNeDyn` | opus 强 | 1 | 1 | 2 | 1 | approved |
| happy-dom `jv8xj2v` | opus 强 | 0 | 0 | 2 | 1 | approved |
| koota-pair `u9UkPMC` | opus 强 | 0 | 0 | 1 | 0 | approved |
| koota-pair `xV6VyNX` | opus 强 | 0 | 0 | 2 | 1 | approved |
| koota-query `WzhHg9X` | opus 强 | 0 | 0 | 2 | 1 | approved |
| koota-query `joAJ4hu` | opus 强 | 0 | 0 | 3 | 3 | max_reviews |
| onedump `68KS8Ce` | opus 强 | 0 | 0 | 1 | 0 | approved |
| onedump `UvnZvvC` | opus 强 | 0 | 0 | 2 | 1 | approved |
| participle `LVgxitb` | opus 强 | 0 | 0 | 1 | 0 | approved |
| participle `ajij7EX` | opus 强 | 0 | 0 | 1 | 0 | approved |
| pest `P8eo5ZZ` | opus 强 | 0 | 0 | 1 | 0 | approved |
| pest `shVKSgB` | opus 强 | 0 | 0 | 1 | 0 | approved |
| python-statemachine `B9XnWvo` | opus 强 | 0 | 0 | 1 | 0 | degraded/timeout |
| python-statemachine `Fm7oLs2` | opus 强 | 0 | 0 | 3 | 2 | approved |
| testem `pCG27Xr` | opus 强 | 0 | 0 | 1 | 0 | approved |
| testem `zNns236` | opus 强 | 0 | 0 | 1 | 0 | approved |
| arktype `VoWNjeD` | sol 强 | 1 | 1 | 2 | 1 | approved |
| arktype `cRuHmYb` | sol 强 | 0 | 0 | 1 | 0 | approved |
| bandit `eoChrUK` | sol 强 | 1 | 1 | 2 | 1 | approved |
| bandit `mcvgbyY` | sol 强 | 0 | **1 ▲** | 2 | 1 | approved |
| csstree `gv2VEQf` | sol 强 | 1 | 1 | 1 | 0 | approved |
| csstree `vnivT9L` | sol 强 | 1 | 1 | 1 | 0 | approved |
| httpx-streaming `EDpGuxr` | sol 强 | 0 | 0 | 1 | 0 | approved |
| httpx-streaming `U6W9KgN` | sol 强 | 1 | 1 | 3 | 2 | approved |
| ink `Fp3teSD` | sol 强 | 0 | 0 | 3 | 2 | approved |
| ink `PuzAivc` | sol 强 | 0 | 0 | 3 | 3 | max_reviews |
| koota-deferred `FPPW3Sh` | sol 强 | 1 | 1 | 3 | 3 | max_reviews |
| koota-deferred `nTUSTFD` | sol 强 | 1 | 1 | 3 | 3 | max_reviews |
| scc `atEszX4` | sol 强 | 1 | **0 ▼** | 3 | 2 | approved |
| scc `zEkfmu3` | sol 强 | 1 | 1 | 2 | 1 | approved |

## 配对结果与不一致对

| 口径 | 对数 | initial | final | 修好 | 修坏 | CI |
|---|---:|---:|---:|---:|---:|---|
| ITT | 36 | 30.6% | 30.6% | 1 | 1 | [−0.083, +0.083] |

| Trial | 轨迹 | 说明 |
|---|---|---|
| bandit `mcvgbyY` ▲ | F2P 66/66 恒定;**P2P 19/293 → 293/293**（revision-1） | capture 新形态：修复 initial 的存量行为破坏 |
| scc `atEszX4` ▼ | 31/31 + 286/286 满分 → revision-1 打破 1 个 P2P（285/286） | opus reviewer 对 scc 的第二次破坏,同为 reviewer 弱格子 |

## 机制总账更新（231 对）

| 新增 | 对数 | 修好 | 修坏 |
|---|---:|---:|---:|
| candidates 扫描轮（本文） | 36 | 1 | 1 |
| **累计** | **231** | **13** | **9** |

opus reviewer 合并读数更新：强格子 capture `2/40 = 5%`（本轮 opus 强格子 0/20）,
harm `2/28 ≈ 7%`（两次都在 scc）。三条机制规律（广义补齐式 capture、弱格子 harm、
capture-harm 与审查强度正相关）在 231 对上仍零反例。

## 子集修订建议（可执行清单）

1. abs-module、happy-dom：维持拒收（家族准则获预测性验证）;
2. ink：维持替补不转正（档位依赖预警兑现）;
3. bandit：维持移出机制池（第四次摇摆）。"移出"是分析层面的决策：任务清单文件保持
   冻结不改（保证与前几轮可合并）、trial 照常运行并计入配对总账;但逐题方向性读数
   （内部确认、oracle、capture/harm 格子归属）不再解读它,未来生成正式
   `complementary-core` 清单时不纳入;
4. clack：转正为可用替补（配对一 opus 强方向首位替补）;
5. koota-query、dasel、onedump、arktype 的 sol 侧已确认;**候选/替补题的 opus 侧
   initial 仍缺**——A 方向 candidates 轮（opus 改,18 题 × 2）可一次补齐 routing
   底料全矩阵,预期无机制惊喜。
