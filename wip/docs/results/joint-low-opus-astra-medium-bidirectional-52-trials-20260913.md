# Astra medium 与 Opus high：共同低分集双向协作结果

分析日期：2026-09-13。13 个 task × 每题 2 次 × 两个方向，共 52 个 trial。仅分析 9 月 11 日启动的 medium/high 实验；不包含正在执行的共同低分 xhigh 实验。

**核心结果：Codex 修改、Claude Code 审查为 initial 2/26 → final 0/26；反向为 6/26 → 5/26。两个方向均未出现初始失败、最终通过的 trial，共 3 次初始通过在修改后失去通过。Claude Code 担任 modifier 的方向最终通过 4/13 个 task，但这 5 次通过的 trial 在首次审查前就已通过。**

## 范围、配置与统计口径

- 任务清单：[joint-low-opus-astra-medium.txt](../../data/selection/joint-low-opus-astra-medium.txt)。[筛选依据](../deepswe-opus-astra-joint-low-subsets.md)是历史 mini-swe-agent 两侧各至多 1/4 通过；“共同低分”是二元通过率低，不表示 F2P/P2P 都低。历史 harness 与当前 CLI 不同，历史分数不能充当本次协作的对照组。
- Codex 使用 `gpt-6-astra / medium`，Claude Code 使用 `claude-opus-5 / high`；互换 modifier/reviewer。两边均 attempts=2、并发=1；各 13 题恰好 2 次，任务 checksum 跨方向一致。
- 两边 runtime 均为 `deep-swe/agent-runtime:86d93103f53a80a1`；最多 3 轮 review，每 Agent turn 最多 2 次尝试；hard timeout 5400 秒、清理预留 300 秒，工作预算 5100 秒，事件静默超时 900 秒。每 turn 的重试上限与每题重复次数是不同参数。
- 初始补丁指 modifier 首次实现完成、reviewer 尚未审查时的冻结补丁；最终补丁指该次 collab 最终交付。通过定义为 Reward=1，即 F2P 和 P2P 全部通过。
- 主表采用 **全部 26 次直接补评分**，包括原 eval 缺分、此次已补出直接评分的 Meriyah。超时降级但有有效补丁的 trial 也保留。原始 job 结果未被此报告改写。
- task 通过数按两次中至少一次通过去重；这是当前样本的观察值。CSV 的 R1/R2 按同一方向、同一 task 的启动时间排序，不代表跨方向共享随机种子。
- 附件：[52 行 trial 明细 CSV](joint-low-opus-astra-medium-bidirectional-52-trials-20260913.csv)、[完整统计与配置 JSON](joint-low-opus-astra-medium-bidirectional-52-trials-20260913.json)。

## 初始与最终成绩

| 指标 | Codex → Claude Code | Claude Code → Codex |
|---|---:|---:|
| 完整直接评分配对 | 26/26 | 26/26 |
| 初始通过 trial | 2/26（7.69%） | 6/26（23.08%） |
| 最终通过 trial | 0/26（0%） | 5/26（19.23%） |
| 净变化 | −2（−7.69 个百分点） | −1（−3.85 个百分点） |
| 初始→最终通过 task | 1/13 → 0/13 | 5/13 → 4/13 |
| 0→1 新增通过 | 0 | 0 |
| 1→0 失去通过 | 2 | 1 |
| 1→1 保持通过 | 0 | 5 |
| 0→0 仍未通过 | 24 | 20 |

两方向合并描述为 8/52 → 5/52，净减 3 次通过；两边共享相同 task，这 52 次不能视为 52 个独立题目。两边初始失败的 24、20 次均未在任何已评分中间阶段获得 Reward=1，并非只在最终提交时丢失了中间通过。

## 逐 task 结果

每格为初始通过次数 → 最终通过次数，分母均为该方向的两次执行。

| Task | Codex → Claude Code | Claude Code → Codex |
|---|---:|---:|
| `bandit-structured-nosec-directives` | 0/2 → 0/2 | 1/2 → 0/2 |
| `gql-incremental-graphql-delivery` | 0/2 → 0/2 | 0/2 → 0/2 |
| `ink-grid-box-layout` | 0/2 → 0/2 | 1/2 → 1/2 |
| `obsidian-linter-auto-table-of-contents` | 0/2 → 0/2 | 0/2 → 0/2 |
| `obsidian-linter-link-format-conversion` | 0/2 → 0/2 | 0/2 → 0/2 |
| `sqlfmt-create-table-ddl-formatting` | 0/2 → 0/2 | 0/2 → 0/2 |
| `termenv-preserve-ansi-resets` | 0/2 → 0/2 | 0/2 → 0/2 |
| `vulture-persistent-analysis-cache` | 0/2 → 0/2 | 0/2 → 0/2 |
| `arktype-json-schema-refs-dependencies` | 0/2 → 0/2 | 2/2 → 2/2 |
| `effect-sse-httpapi-streaming` | 0/2 → 0/2 | 1/2 → 1/2 |
| `igel-persist-feature-schema` | 0/2 → 0/2 | 0/2 → 0/2 |
| `meriyah-explicit-resource-declarations` | 2/2 → 0/2 | 0/2 → 0/2 |
| `prometheus-transactional-reload-status` | 0/2 → 0/2 | 1/2 → 1/2 |

最终通过的 task 全在 Claude Code → Codex：arktype 两次、effect 一次、ink 一次、prometheus 一次；其中 ink 的通过来自一次超时降级交付。

## F2P/P2P：二元分数未提高，不代表所有修改均无变化

宏平均按每个 trial 的通过率等权；微平均为全部通过测试数/总测试数。两边均按 26 次直接评分比较，分母一致。

| 指标 | Codex → Claude Code，initial → final | Claude Code → Codex，initial → final |
|---|---:|---:|
| F2P 汇总/微平均 | 805/926 → 798/926（86.93% → 86.18%） | 828/926 → 825/926（89.42% → 89.09%） |
| F2P 宏平均 | 86.34% → 85.79% | 87.00% → 86.90% |
| P2P 汇总/微平均 | 116698/116722 → 116700/116722（99.98% → 99.98%） | 116581/116722 → 116585/116722（99.88% → 99.88%） |
| P2P 宏平均 | 99.71% → 99.82% | 99.38% → 99.39% |

- Codex → Claude Code：F2P 净少 7 个通过，全部来自 Meriyah 的两次退步；P2P 净多 2 个通过。Claude Code → Codex：F2P 净少 3 个通过，P2P 净多 4 个通过。
- 反向仍有局部改善：effect 的未通过 trial 增加 2 个 F2P 通过，ink 的未通过 trial 增加 1 个，但均不足以达到全部通过。
- 不能只看 P2P 微平均：Meriyah 每次有 51,469 个 P2P，两次占本方向 116,722 个 P2P 中的约 88.2%，会掩盖其他任务的回归。
- 多个 trial 卡在少数测试：例如 GQL 的 F2P 全过但 P2P 未全过；Vulture 也出现 F2P 全过、P2P 291/295。0 分不等价于没有实现功能。

## 三次失去通过发生在哪里

| 方向 / trial 后缀 | 阶段 | F2P | P2P |
|---|---|---|---|
| Codex → Claude / Meriyah `bqmBaPd` | initial → revision-1 → final | 49/49 → 46/49 → 45/49 | 均 51469/51469 |
| Codex → Claude / Meriyah `Mw9q9D4` | initial → revision-1 → final | 49/49 → 46/49 → 46/49 | 均 51469/51469 |
| Claude → Codex / Bandit `w6TnoqF` | initial → revision-1 → final | 69/69 → 67/69 → 67/69 | 282/282 → 281/282 → 281/282 |

三次首次退步都发生在第一次 revision 后。Meriyah 的两次同题复现值得优先复盘，但不能算两个独立任务证据。

- Meriyah：首次审查要求调整 `using` 声明 lookahead、`using[...]` 表达式及 `for (using of ...)` 的解析兼容性；一条审查还涉及静态块内 `await using`。这是审查记录提出的语义问题。本报告确认其后分数下降，未逐一裁定审查意见、任务需求及隐藏测试谁更符合规范。[bqmBaPd 首次审查](../../../jobs/collab-codex-claude-joint-low-opus-astra-medium-13-tasks-20260911-095901/meriyah-explicit-resource-declar__bqmBaPd/agent/system/rounds/01-review/review.json)、[Mw9q9D4 首次审查](../../../jobs/collab-codex-claude-joint-low-opus-astra-medium-13-tasks-20260911-095901/meriyah-explicit-resource-declar__Mw9q9D4/agent/system/rounds/01-review/review.json)。
- Bandit：首次审查要求 statement 范围内区域抑制、malformed selector fallback 和按 resolved set 分类统计；之后 F2P 和 P2P 都下降。[首次审查](../../../jobs/collab-claude-codex-joint-low-opus-astra-medium-13-tasks-20260911-095927/bandit-structured-nosec-directiv__w6TnoqF/agent/system/rounds/01-review/review.json)。

因此这里的“退步”严格指 benchmark 分数退步，不能由此直接推断所有审查建议都错误；仍需把具体失败测试与对应修改逐项对照。

## 审查行为与耗时

以下为运行记录统计，review 数只计完成并产生结果的轮次。

| 指标 | Codex → Claude Code | Claude Code → Codex |
|---|---:|---:|
| 完成 review 轮数 | 48 | 76 |
| 完成 revision 次数 | 26 | 61 |
| approve / revise | 22 / 26 | 13 / 63 |
| findings / blocking | 154 / 36 | 153 / 147 |
| approved / max_reviews_reached / degraded | 22 / 1 / 3 | 13 / 11 / 2 |
| job 开始（北京时间） | 09-11 09:59:12 | 09-11 09:59:37 |
| job 结束（北京时间） | 09-12 02:10:08 | 09-12 07:17:16 |
| job 总耗时 | 16小时10分56秒 | 21小时17分39秒 |
| 总耗时 / 26（非纯模型耗时） | 37分21秒 | 49分08秒 |

Codex 作 reviewer 时，完成审查中的 revise 比例为 63/76（82.9%），blocking findings 占 147/153（96.1%）；Claude Code 作 reviewer 时分别为 26/48（54.2%）、36/154（23.4%）。本批中前者要求更多修改、打满审查轮数的 trial 更多，但未增加二元通过。两边被审查的初始实现不同，这些差异不能单独归因于 reviewer。

Claude Code 担任 modifier 的方向总耗时多 5小时6分42秒，约多 31.6%。总耗时包含任务环境、Agent 执行、原始测试验证及等待，不含后续 score-patches；它不是模型算力或费用的直接比较。job 级 token/cost 字段为空，本报告不将缺失值当成零，也不据此估算费用。

## 执行异常与补评分完整性

| 项目 | Codex → Claude Code | Claude Code → Codex |
|---|---:|---:|
| 原始 job 结束 trial | 26 | 26 |
| 原始有效最终评分 | 26 | 25 |
| 原始基础设施异常 | 0 | 1 |
| 超时降级、有补丁 | 3 | 2 |
| 本次不同补丁评分数 | 52 | 87 |
| 阶段记录 / 成功 | 77 / 77 | 102 / 102 |
| initial/final 完整对 | 26/26 | 26/26 |
| 原始 final 对照 | 26 matched | 25 matched，1 unavailable |
| 补评分 verifierErrors | 空 | 空 |
| 补评分 exitCode | 0 | 1（缺少原始对照） |

- Codex → Claude Code 的降级：ink `VnKgrxn`、Meriyah `Mw9q9D4`、Prometheus `LdQpEnr`，均触及 total_deadline 后提交已有补丁。另在 ink `VnKgrxn` 和 Vulture `rkqEfv9` 记录到网络重连/请求超时，运行随后继续；不能把它们称为完全无执行异常。
- Claude Code → Codex 的降级：ink `Tz2q3dJ` 与 `rMAaqPh` 两次均触及 total_deadline；前者 final Reward=1，后者为 0。降级仍可能提交可评分、甚至全部通过的补丁。
- 原始 Meriyah `RBj2uq7` 的 Agent 已完成，但 verifier 镜像拉取 TLS 握手超时导致缺分。本次直接评分补齐为 initial F2P 47/49、final 46/49，P2P 均 51469/51469，二元结果为 0→0。
- 该次补评分成功不等于原始 eval 结果被修改：原始对照仍 unavailable，所以反向 summary 的 exitCode=1、problems 只有“1 pair(s) lack an eval final reward to compare”。这是原始对照缺失，非本次 verifier 失败。其余 51 个 final 的完整 reward 对照均 matched，无 mismatch、无 incompletePair。

## 脚本统计口径与不确定性

`summary.json` 中名为 `intentionToTreat` 的集合要求存在符合条件的原始 final 对照，因此反向排除了已补评分的 Meriyah；它不是全部运行的 26 次口径。`completedProtocol` 在此集合基础上继续排除超时降级。

| 方向 / 口径 | 对数 | Initial → final | 新增 / 失去通过 | 净变化 |
|---|---:|---:|---:|---:|
| Codex → Claude，全部直接配对 | 26 | 2 → 0 | 0 / 2 | −7.69 pp |
| Codex → Claude，脚本 ITT | 26 | 2 → 0 | 0 / 2 | −7.69 pp |
| Codex → Claude，completed-protocol | 23 | 1 → 0 | 0 / 1 | −4.35 pp |
| Claude → Codex，全部直接配对 | 26 | 6 → 5 | 0 / 1 | −3.85 pp |
| Claude → Codex，脚本 ITT | 25 | 6 → 5 | 0 / 1 | −4.00 pp |
| Claude → Codex，completed-protocol | 23 | 5 → 4 | 0 / 1 | −4.35 pp |

脚本 ITT 的按 task 聚类 bootstrap 95% 区间分别为 [−23.08, 0]、[−12.5, 0] 个百分点；McNemar exact p 分别为 0.5、1.0。后者不处理同题重复相关性，仅作为脚本附带统计。样本仅 13 题、每题两次，区间和检验不支持推广为“审查普遍有害”或模型总体优劣结论。

## 对后续实验的含义

1. 本批没有观察到 review loop 新增全部通过；分数上的主要问题是已有通过被修改丢失。下一步可优先复盘 Meriyah 和 Bandit 的第一次 revision，对照隐藏测试失败、review 要求和修改响应，区分需求解释冲突、实现回归和测试覆盖差异。
2. 初始补丁是同次协作运行中的检查点，不是等预算、独立运行的 single-agent 对照。当前数据只能描述本批 initial→final 变化，无法隔离 reviewer 相对额外修改时间的因果贡献。
3. 不应把隐藏测试评分用于在线选择 initial/final，否则改变了 benchmark 信息边界。可探索基于公开测试与需求检查的回归保护，并作为新实验单独评估。
4. 正在运行的 xhigh 共同低分集为 12 题，少了 medium 中的 effect。后续先在共同 12 题上比较，且要披露反向并发从 1 提到 2。作为对齐基线，medium 在这 12 题上：Codex → Claude initial 2/24 → final 0/24；Claude → Codex 5/24 → 4/24，最终通过 task 分别 0/12、3/12。不能直接拿 13 题与 12 题的总通过率解释 effort 收益。

## 原始证据

- **Codex → Claude Code**：`collab-codex-claude-joint-low-opus-astra-medium-13-tasks-20260911-095901`。
  [原始结果](../../../jobs/collab-codex-claude-joint-low-opus-astra-medium-13-tasks-20260911-095901/result.json) · [配置](../../../jobs/collab-codex-claude-joint-low-opus-astra-medium-13-tasks-20260911-095901/config.json) · [补评分汇总](../../../jobs/collab-codex-claude-joint-low-opus-astra-medium-13-tasks-20260911-095901/patch-scores/summary.json) · [配对明细](../../../jobs/collab-codex-claude-joint-low-opus-astra-medium-13-tasks-20260911-095901/patch-scores/pairs.csv) · [阶段明细](../../../jobs/collab-codex-claude-joint-low-opus-astra-medium-13-tasks-20260911-095901/patch-scores/stages.csv)。
- **Claude Code → Codex**：`collab-claude-codex-joint-low-opus-astra-medium-13-tasks-20260911-095927`。
  [原始结果](../../../jobs/collab-claude-codex-joint-low-opus-astra-medium-13-tasks-20260911-095927/result.json) · [配置](../../../jobs/collab-claude-codex-joint-low-opus-astra-medium-13-tasks-20260911-095927/config.json) · [补评分汇总](../../../jobs/collab-claude-codex-joint-low-opus-astra-medium-13-tasks-20260911-095927/patch-scores/summary.json) · [配对明细](../../../jobs/collab-claude-codex-joint-low-opus-astra-medium-13-tasks-20260911-095927/patch-scores/pairs.csv) · [阶段明细](../../../jobs/collab-claude-codex-joint-low-opus-astra-medium-13-tasks-20260911-095927/patch-scores/stages.csv)。
