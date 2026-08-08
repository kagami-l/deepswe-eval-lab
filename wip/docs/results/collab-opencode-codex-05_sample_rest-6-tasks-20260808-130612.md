# collab-opencode-codex-05_sample_rest-6-tasks-20260808-130612 结果分析（含配对重打分）

分析日期：2026-08-09。

本文记录 opencode/DeepSeek modifier + Codex reviewer 方向在 `05_sample_rest` 上的 eval 与
`score-patches` 配对结果，与同任务集的反向 job
[collab-codex-opencode-…-130605](collab-codex-opencode-05_sample_rest-6-tasks-20260808-130605.md)
构成两方向对照。方法见[设计文档](../collab-paired-checkpoint-verification-design.md)。

原始工件：

- [job result](../../../jobs/collab-opencode-codex-05_sample_rest-6-tasks-20260808-130612/result.json)
- [job config](../../../jobs/collab-opencode-codex-05_sample_rest-6-tasks-20260808-130612/config.json)
- [run manifest](../../../jobs/.agent-eval-manifests/collab-opencode-codex-05_sample_rest-6-tasks-20260808-130612.json)
- [patch-scores 汇总](../../../jobs/collab-opencode-codex-05_sample_rest-6-tasks-20260808-130612/patch-scores/summary.json)
- [配对表 pairs.csv](../../../jobs/collab-opencode-codex-05_sample_rest-6-tasks-20260808-130612/patch-scores/pairs.csv)
- [阶段表 stages.csv](../../../jobs/collab-opencode-codex-05_sample_rest-6-tasks-20260808-130612/patch-scores/stages.csv)

## 结论

1. 正式 reward `8/18 = 44.4%`，task-level pass@3 `5/6`（dateutil 0/3）。2 个 trial 因
   modifier 首轮实现超时无任何 patch（`NonZeroAgentExitCodeError`，计 0 分），7 个 trial
   degraded（全部 timeout）。**workflow 预算是本方向的主约束**：trial 中位耗时 78 分钟，
   逼近 90 分钟硬上限；18 个 trial 里 9 个以某种形式撞到超时。
2. **配对主结果：net delta 仍为 0，但首次出现实质性的双向翻转。** initial 直接提交
   `8/16 = 50%`，review-loop 终稿同为 `8/16`；1 修好、1 修坏，McNemar p = 1.0，
   bootstrap 95% CI `[-0.176, +0.176]`。
3. **与 c→o 方向的关键差异在节点层**：flash reviewer 审 codex 时零节点移动，而
   codex reviewer 审 flash 时 4/16 对有 F2P 移动，其中 bandit `UvV5LgS` 的首轮 review
   一次推动 **+48 个 F2P**（18/66 → 66/66）并翻转 reward——这是全部 58 个配对中最大的
   单轮 review 收益。**codex reviewer 的 findings 具有实质修复推动力**，只是收益与损害
   （dateutil `7UEaCKm` 满分被 revision-2 改坏）在小样本里相互抵消。
4. 评分管线继续保真：40 个 unique patch 全部评分成功，conformance `16/16 matched`，
   约 17 分钟（并发 4）。三个"revision 轮进行中被 deadline 打断"的 trial 触发了 discovery
   的 layout fail-closed，按设计意图扩展了受支持 profile（完成的 revision 数仍须严格匹配
   `revisionCount`，仅容忍一个处于末位、全 attempt 中断的 revision 轮）后正常纳入。
5. **官方到内部的迁移偏移可以非常大**：flash 在 `bandit-interprocedural-taint-checks` 上
   官方 4/4，内部 initial 0/3；opa 方向相反（官方 1/4，内部 2/2）。这直接佐证互补实验
   "内部确认不可省略"与 effort 对齐到 max 的必要性（本 job 的 modifier 仍是 effort high，
   早于默认值切换）。

## 运行配置

| 项目 | 值 |
|---|---|
| 开始 / 结束时间 | 2026-08-08 13:06:18 / 23:28:28 CST |
| 总 wall-clock | 约 10 小时 22 分（前 5 小时 52 分与反向 job 并行，总 4 slot） |
| 任务数 / trials | 6（`05_sample_rest`）/ 18（每题 3 次） |
| 并发 | 2 |
| Modifier | OpenCode `deepseek/deepseek-v4-flash`，effort `high`，permissions `auto` |
| Reviewer | Codex `gpt-5.6-luna`，effort `xhigh`，permissions `bypass` |
| Runtime | `deep-swe/agent-runtime:bd704fc758b47046` |
| Task hard / soft deadline | 5400 / 5100 秒 |
| Event-silence watchdog | 600 秒 |
| `maxReviews` / `maxAgentAttempts` / `minTurnSeconds` | 3 / 2 / 120 秒 |
| Pier / git commit | `0.3.0` / `7fd0cebdb70d8596d0c696547ddf32d61f3384f3`，dirty=false |

注意：本 job 在 opencode 默认 effort 改为 `max`、watchdog 默认改为 900 秒**之前**启动，
用的是 `high` / 600 秒。与官方 `v4_flash_max` 口径存在 effort 差异，解读单体代理成绩时必须注明。

## 汇总指标

| 指标 | 值 |
|---|---:|
| Reward | 8 / 18（44.4%） |
| Task-level pass@3 | 5 / 6（dateutil 0/3） |
| Outcome 分布 | 6 approved / 3 max_reviews_reached / 7 degraded（全部 timeout）/ 2 modifier 首轮超时 |
| 平均 / 中位 trial 时间 | 69 分 / 78 分 24 秒（最短 32:18，最长 87:47） |
| 有效 review 轮次 | 33（37 attempts，4 个失败后轮内重试恢复） |
| Pier 记录 input / output tokens | 76,514,995 / 1,434,869 |
| Pier 记录 cost | `$1.7719`（仅 OpenCode modifier；Codex reviewer cost 为 null） |

## Task 级结果

每格为 `reward（F2P，review/revision）`；`†` = degraded/timeout，`✗` = modifier 首轮超时无 patch。

| Task | Trial 1 | Trial 2 | Trial 3 | pass@3 |
|---|---|---|---|---:|
| `bandit-interprocedural-taint-checks` | `YsfDL4h`: 0（65/66，2/2）† | `UvV5LgS`: 1（66/66，3/2）† | `xX4egLS`: 0（63/66，2/2）† | 1 |
| `dateutil-rfc5545-timezone-interop` | `6LQids4`: 0（66/67，3/3） | `7UEaCKm`: 0（66/67，2/2）† | `D5r29VR`: 0（66/67，3/3） | 0 |
| `fd-deterministic-multi-key-sorting` | `dahndd5`: 1（43/43，2/1） | `FBstmLu`: 1（43/43，1/0） | `J3RV9mN`: 1（43/43，2/1） | 1 |
| `httpx-multipart-response-parsing` | `p52KZ2N`: 0（121/122，2/1） | `stSWKEa`: 0（121/122，3/2） | `Wqub97e`: 1（122/122，3/3） | 1 |
| `opa-rego-rule-profiling` | `UuRCBLP`: 1（25/25，2/1） | `inXofPo`: 0 ✗ | `zmefden`: 1（25/25，2/1）† | 1 |
| `yaegi-go-embed-directives` | `VnjHhjb`: 1（38/38，0/0）† | `3yfQmPx`: 0 ✗ | `wNhzKho`: 0（0/38，0/58，1/0）† | 1 |

`wNhzKho` 的 initial patch 连 P2P 都全挂（0/58），应为构建被破坏；`VnjHhjb` modifier 完成后
首轮 review 未能完成即超时 degraded，终稿即初稿而 reward=1。

## 超时形态与 discovery 修复

9 个撞超时的 trial 分为三类：

1. **modifier 首轮超时**（2）：opa `inXofPo`、yaegi `3yfQmPx`，无 patch，ineligible。
2. **review/revision 过程中总预算耗尽**（7 个 degraded）：其中 3 个（bandit `UvV5LgS` 的
   `06-final-revision`、opa `zmefden` 的 `04-revise`、yaegi `wNhzKho` 的 `02-revise`）在
   **revision turn 进行中**被截断——轮目录存在但全部 attempt 为 `interrupted/total_deadline`，
   summary 只计完成的 revision。这一形态在历史 fixture job（224833，degraded 发生在 review 轮）
   中未出现，首次触发 `score-patches` 的 layout fail-closed。
3. 修复（[patch_discovery.py](../../agent_eval/patch_discovery.py)）：完成的 revision 轮数
   仍须严格等于 `revisionCount`；额外容忍**至多一个**处于末位、无任何 success attempt 的
   revision 轮。非末位中断、多个中断轮继续 fail closed。配套 3 个新测试与历史 job 布局回归。

## score-patches 配对结果

| 项目 | 值 |
|---|---|
| 命令 | `score-patches --job-path jobs/collab-opencode-codex-…-130612 --concurrency 4` |
| Stage 实例 | 56（16 initial + 24 revision + 16 final） |
| Unique patch | 40，0 cached，全部评分成功，0 retry 耗尽 |
| Verifier 总耗时 | 约 17 分钟（并发 4） |
| Final conformance | matched 16 / mismatched 0 / unavailable 0 |
| Coverage / exit | 16/16 完整对，2 ineligible（no_initial_patch），exit 0 |

### 配对汇总

| 口径 | 对数 | initial 通过 | final 通过 | 修好 | 修坏 | 不变 | McNemar p | 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Intention-to-treat | 16 | 8 (50.0%) | 8 (50.0%) | 1 | 1 | 14 | 1.0 | [-0.176, +0.176] |
| Completed-protocol | 9 | 5 (55.6%) | 5 (55.6%) | 0 | 0 | 9 | — | — |

2×2：passedBoth 7、failedBoth 7、improved 1、harmed 1。两个不一致对都在 degraded 子集里，
所以 completed-protocol 恰好全不变。

### 不一致对与节点级轨迹

4/16 对存在 F2P 节点移动（对比：反向 job 为 0/18）：

| Trial | F2P 轨迹（initial → … → final） | reward |
|---|---|---|
| bandit `UvV5LgS` | 18/66 → **66/66**（revision-1）→ 66/66 | **0→1** |
| bandit `xX4egLS` | 18/66 → 56/66（rev-1）→ 63/66（rev-2） | 0→0 |
| httpx `p52KZ2N` | 118/122 → 121/122（rev-1） | 0→0 |
| dateutil `7UEaCKm` | 67/67 → 67/67（rev-1）→ **66/67**（rev-2） | **1→0** |

- **修好**（`UvV5LgS`）：codex reviewer 首轮 findings 推动 flash 一次修复 48 个 F2P 节点,
  是全部三个配对 job（58 对）中最大的单轮 review 收益。
- **修坏**（`7UEaCKm`）：initial 已满分，revision-2 在有 review 把关的情况下仍打破 1 个
  F2P（confirm 集的 harmed 案例发生在无把关的 final revision——两种路径都已观测到）。
- **方向正确但精度不足**（`xX4egLS` +45、`p52KZ2N` +3）：与 confirm 集 clack/cliffy 同型,
  大幅逼近但没补上 verifier 的最后缺口。

## 失败用例分析

- **bandit**（0/3，全部近失或大缺口）：剩余失败集中在
  `test_non_spec_sanitizers_do_not_break_taint`、`test_b623_detects_vulnerable_ssrf`、
  walrus 算子相关的两个 taint 传播测试。
- **dateutil**（0/3）：三个 trial 全部只失败 `testToStrTZIDFromTzicalZone`（66/67）,
  连续 3–8 轮 review/revision 都没能修复同一个测试；`7UEaCKm` 反而是从满分回归到这个测试。
- **httpx**（近失 ×2）：`test_iter_multipart_part_headers_parsing` 的 header 折行
  （continuation line）边界用例。
- **yaegi `wNhzKho`**：initial 即破坏构建（0/38 F2P、0/58 P2P），review 轮未及修复即超时。

## 与官方公开数据对照

官方为 mini-swe harness、flash **max**、每格 4 次；本 job initial 为 flash **high**（差一档
effort），可视为单体代理但口径不完全对齐：

| Task | 官方 flash max | 本 job initial（flash high） |
|---|---:|---:|
| `fd-deterministic-multi-key-sorting` | 3/4 | 3/3 |
| `dateutil-rfc5545-timezone-interop` | 2/4 | 1/3 |
| `yaegi-go-embed-directives` | 2/4 | 1/2 |
| `httpx-multipart-response-parsing` | 2/4 | 0/3 |
| `opa-rego-rule-profiling` | 1/4 | 2/2 |
| `bandit-interprocedural-taint-checks` | 4/4 | **0/3** |
| **合计** | **14/24（58.3%）** | **8/16（50.0%）** |

层均值接近，但逐题偏移剧烈且双向：bandit 官方全过、内部全败；opa 官方最弱、内部全过。
可能来源包括 effort 差（high vs max）、harness 差异与每格小样本噪声，无法在本数据内区分。
对互补实验的直接含义：**官方筛出的"某侧强"在内部复现前只能当假设**——bandit 恰好是官方
口径下 spread=1.00 的极端题（opus-5 0/4 vs flash 4/4），内部却完全反转了 flash 侧的表现。

## 与反向 job 及合并证据

| | c→o（codex 改，flash 审） | o→c（flash 改，codex 审） |
|---|---:|---:|
| Reward | 15/18（83.3%） | 8/18（44.4%） |
| initial = 单体代理 | 15/18 | 8/16 |
| 配对 delta | 0（0↑ 0↓） | 0（1↑ 1↓） |
| F2P 节点有移动的对 | 0/18 | 4/16 |
| 超时相关 trial | 0 | 9/18 |
| Wall-clock | 5h52m | 10h22m |

三个配对 job 合计 **58 对：2 修好、2 修坏，净效应 0**。但两方向的机制画像不同：flash
reviewer 对 codex patch 无任何可见推动；codex reviewer 对 flash patch 有实质推动力
（+48/+45/+3），只是被对称的破坏抵消且受预算截尾。互补实验里"codex reviewer 审 flash
modifier 做不出的题"是有先验支持的格子。

## 建议

1. 本 job 正式计为 `8/18`，coverage 16/16 + 2 ineligible；flash（high）单体基线记为
   initial 的 `8/16`。
2. **预算是 o→c 方向的第一约束**：中位 trial 78 分钟、9/18 撞超时,flash 换到 max 后只会
   更慢。互补实验若沿用 5400 秒预算，review-loop 的效果会被系统性截尾；考虑对两方向对称
   使用 `--agent-timeout-multiplier`（如 1.5）并在报告中注明与历史 job 的口径差异,或明确
   接受截尾并在 ITT 里单列 timeout 子集。
3. bandit 的官方/内部反转是"复现确认不可省略"的活例：互补子集 10 题在 collab 运行前的
   任何强弱假设都以 initial patch 的实测为准（effort 已对齐 max,消除一个混杂）。
4. dateutil `testToStrTZIDFromTzicalZone` 与 httpx header 折行用例加入 reviewer 定向探针
   清单；bandit 的 walrus/taint 系列适合作为"reviewer 有推动力但补不到边界"的案例研究。
5. `score-patches` 并发 4 下 17 分钟完成 40 个 patch,继续作为每个 collab job 的常规后处理；
   本次新增的进度日志将在下一次运行生效。
