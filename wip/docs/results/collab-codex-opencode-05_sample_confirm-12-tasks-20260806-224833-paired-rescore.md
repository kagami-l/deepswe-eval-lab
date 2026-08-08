# collab-codex-opencode-…-224833 配对重打分(score-patches)结果分析

分析日期:2026-08-07。

本文是 [collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833](collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833.md)
建议第 7 条的落地:对同一 job 的每个 trial,离线重打分 reviewer 介入前的 initial patch
(no-review 反事实)与各轮 revision 后的 stage patch,与 review-loop 终稿构成配对。
方法与工具见[设计文档](../collab-paired-checkpoint-verification-design.md)。

数据来源是对既有历史 job 的 verifier-only 回放(设计实现顺序第 9–10 步的 Phase 0),
不调用任何模型、不产生新 trial。设计验收清单中的两方向 collab smoke 属于独立事项,
与本文结论无关。

原始工件:

- [patch-scores 汇总](../../../jobs/collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833/patch-scores/summary.json)
- [配对表 pairs.csv](../../../jobs/collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833/patch-scores/pairs.csv)
- [阶段表 stages.csv](../../../jobs/collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833/patch-scores/stages.csv)
- 各 trial `patch-scores/stages.json` 与 `patch-scores/results/<fingerprint>/`

## 结论

1. **保真度成立**:24/24 个 trial 的 direct final 重打分与 Pier eval 记录的 reward 完全一致
   (`finalConformance: matched 24`),零 mismatch、零 verifier 基础设施错误、零 retry。
   `score-patches` 的评分路径与正式 verifier 等价,且本 job 的 verifier 完全可复现。
2. **主结果:review-loop 的净 verifier 价值为零。** 同一批 initial patch 直接提交的
   pass rate 是 `14/24 = 58.33%`,与 review-loop 终稿完全相同(`14/24`)。配对 delta
   均值 0;不一致对 1:1(1 个修好,1 个修坏);McNemar 精确 p = 1.0;task-clustered
   bootstrap 95% CI `[-0.125, +0.125]`。Completed-protocol 子集(23 对,排除 1 个
   degraded)结论相同。
3. 此前只能观察到"standalone 14/24 vs collab 14/24 持平"。配对证据现在排除了
   "modifier 行为差异与 review 收益相互抵消"的解释:**collab 的 initial patch 本身就是
   14/24,review-loop 在其上净变化为 0**,而它使 wall-clock 从约 4 小时增加到约 10 小时。
4. 节点级同样几乎静止:24 对中仅 4 对的 F2P/P2P 通过节点在 initial→final 间有任何移动
   (2 正向未翻转、1 正向翻转、1 负向翻负)。

## 运行与方法摘要

| 项目 | 值 |
|---|---|
| 命令 | `score-patches --job-path jobs/collab-codex-opencode-…-224833 --concurrency 2` |
| Pier / adapter | `datacurve-pier==0.3.0`,adapter schema 1,契约检查通过 |
| Stage 实例 | 70(24 initial + 22 revision + 24 final) |
| Unique patch(按完整 fingerprint 去重) | 49(21 个 final 与既有 stage 内容相同) |
| Verifier 运行 | 49 成功 / 0 失败 / 0 retry;总计约 69 分钟,单个最长 431 秒(FastAPI) |
| Final conformance | matched 24 / mismatched 0 / unavailable 0 |
| Exit code | 0,coverage 完整(24/24 对) |

所有中间 verifier 结果均为事后离线产生,任何 agent 在运行期都不可见。

## 配对汇总

| 口径 | 对数 | initial 通过 | final 通过 | 修好 (0→1) | 修坏 (1→0) | 不变 | 均值 delta | McNemar p | 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Intention-to-treat | 24 | 14 (58.33%) | 14 (58.33%) | 1 | 1 | 22 | 0.0 | 1.0 | [-0.125, +0.125] |
| Completed-protocol | 23 | 13 (56.52%) | 13 (56.52%) | 1 | 1 | 21 | 0.0 | 1.0 | [-0.125, +0.130] |

Degraded 的 `prometheus-typed-label-sorting__afHT2KR`(reviewer 首轮失败,终稿即初稿,
reward 1)只进入 ITT,delta 恒 0。

## Trial 级配对明细

`rd` 为各轮 revision 的 parent→child reward delta(最后一项为 final revision,若有)。

| Trial | Outcome | Revs | initial→final | 分类 | rd |
|---|---|---:|---|---|---|
| `anko__4QdKMdb` | approved | 0 | 1→1 | unchanged | — |
| `anko__AYN5MhD` | approved | 1 | 1→1 | unchanged | [0] |
| `arcane__j5ZxGvX` | approved | 0 | 1→1 | unchanged | — |
| `arcane__tduG2uV` | approved | 1 | 1→1 | unchanged | [0] |
| `clack__ddnwt5p` | approved | 0 | 0→0 | unchanged | — |
| `clack__t7AW9LD` | approved | 2 | 0→0 | unchanged | [0, 0] |
| `cliffy__QG2fVMb` | approved | 1 | 0→0 | unchanged | [0] |
| `cliffy__cQ7tP9d` | approved | 2 | 0→0 | unchanged | [0, 0] |
| `fastapi__jbGvFZv` | approved | 0 | 0→0 | unchanged | — |
| `fastapi__xCcgJ2J` | approved | 0 | 0→0 | unchanged | — |
| `go-critic__RGFqwkq` | max_reviews | 3 | **1→0** | **harmed** | [0, 0, **-1**] |
| `go-critic__qG7JRk5` | approved | 0 | 0→0 | unchanged | — |
| `kombu__UYS9QJ3` | approved | 1 | 1→1 | unchanged | [0] |
| `kombu__ZXz6KYJ` | approved | 1 | 0→0 | unchanged | [0] |
| `mobly__3JC3N3W` | approved | 2 | 1→1 | unchanged | [0, 0] |
| `mobly__dHgC4b9` | approved | 0 | 1→1 | unchanged | — |
| `prometheus__WtSqCjs` | approved | 2 | 0→0 | unchanged | [0, 0] |
| `prometheus__afHT2KR` | degraded | 0 | 1→1 | unchanged | — |
| `tengo__ahKpCiN` | approved | 1 | 1→1 | unchanged | [0] |
| `tengo__kPyvB8r` | approved | 1 | 1→1 | unchanged | [0] |
| `textual__5SepKJv` | approved | 0 | 1→1 | unchanged | — |
| `textual__ABqw2iA` | approved | 1 | 1→1 | unchanged | [0] |
| `tomlkit__SQgJiwu` | max_reviews | 3 | 1→1 | unchanged | [0, 0, 0] |
| `tomlkit__Yoaiwcp` | max_reviews | 3 | **0→1** | **improved** | [**+1**, 0, 0] |

## 不一致对与节点级分析

initial→final 有节点移动的仅 4 对:

| Trial | F2P | P2P | reward |
|---|---|---|---|
| `tomlkit__Yoaiwcp` | 57/60 → 60/60 | 964/964 → 964/964 | **0→1** |
| `go-critic__RGFqwkq` | 3/3 → 2/3 | 16/16 → 15/16 | **1→0** |
| `clack__t7AW9LD` | 81/82 → 81/82 | 625/643 → 643/643 | 0→0 |
| `cliffy__QG2fVMb` | 35/37 → 36/37 | 451/451 → 451/451 | 0→0 |

- **唯一修好**(`tomlkit__Yoaiwcp`):首轮 review 的 findings 触发 revision-1,一次性修复
  3 个缺失 F2P 节点;之后两轮 revision 无净变化。这是 review-loop 的标准正收益路径。
- **唯一修坏**(`go-critic__RGFqwkq`):initial 已经满分(3/3 F2P、16/16 P2P)。前两轮
  revision 无变化,**破坏发生在 final revision——协议中唯一没有后续 review 把关的那次
  修改**(1 F2P、1 P2P 同时跌落)。同 task 的另一 trial `qG7JRk5` 被 reviewer 首轮
  approve 而 reward 为 0,说明该 reviewer 在 go-critic 上双向都不可靠。
- **方向正确但精度不足**(clack、cliffy):revision 确实修复了节点(+18 P2P、+1 F2P),
  但都没有补上决定 reward 的最后缺口。它们与上一份报告的
  `approved-but-verifier-failed` 类别一致:reviewer 能推动修复,但探测不到 verifier
  的精确边界。
- 9 个 `approved` 且 reward 0 的 trial,其 initial 全部也是 0:reviewer 没有引入这些
  失败,但除 tomlkit 外也从未修好任何一个。差距主要在**初始缺陷从未被发现**,而非
  revision 引入回归。

## 对上一份报告结论的修正与确认

- 确认:「当前结果不支持加入 reviewer 已提高总体通过率」——现在有配对层面的直接证据,
  且净效应精确为 0(1 修 1 坏)。
- 修正:持平不是"独立随机波动掩盖了收益",而是 review-loop 本身几乎不改变 verifier
  结果:22/24 对 reward 不变,20/24 对连节点都纹丝不动。
- 新发现:唯一的回归来自无 review 把关的 final revision。max_reviews 协议末轮的
  "最后一改"是已观测的风险点。

## 建议

1. 当前配置(Codex modifier + OpenCode/DeepSeek reviewer,maxReviews=3)在确认集上
   无净收益、成本翻倍,不应作为默认拓扑。后续实验应先改变 reviewer 的能力配置
   (更强模型、定向 smoke tests、剩余预算提示——见上一份报告建议 3/4),再用同一
   配对框架验证,而不是重复同配置扩样。
2. ±0.125 的 CI 意味着本框架在 24 对下只能排除 >12.5pp 的效应。按当前不一致率
   (2/24),把样本扩到 12×4 也难以对 ~5pp 的效应显著;先提高 reviewer 的单对修复率
   比扩样更有效。配对打分本身成本很低(全 job 约 40 分钟 verifier-only),任何新
   collab job 结束后顺手 `score-patches` 即可持续监控。
3. 针对 final revision 的回归风险:考虑禁止 final revision 做 findings 范围之外的
   改动,或在预算允许时对 final revision 增加一轮轻量 review;至少应在结果分析中
   把"final revision 是否改变 reward"单列(本工具的 `rd` 最后一项已提供)。
4. `score-patches` 在本次回放中表现出与正式 verifier 的一致性(24/24 matched)和幂等性
   (重入零 verifier 调用),可作为 collab eval 的常规后处理步骤。注意这是历史 job 的
   verifier-only 回放结果,不等同于设计验收清单里的两方向 collab smoke——后者尚未执行。
