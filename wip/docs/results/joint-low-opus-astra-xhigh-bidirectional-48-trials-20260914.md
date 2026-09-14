# Astra xhigh 与 Opus high：共同低分集双向协作结果

分析日期：2026-09-14。12 个 task × 每题 2 次 × 两个方向，共 48 个 trial。本报告分析 9 月 13 日启动的共同低分 xhigh 实验，不包含互补集实验。

**全部直接补评分显示：Codex 修改 → Claude Code 审查为 initial 2/24 → final 2/24；Claude Code 修改 → Codex 审查为 3/24 → 1/24。两边均没有把初始失败的 trial 改到通过；反向损失了 Arktype 与 Ink 各一次初始通过。最终两方向各只有 Arktype 一个 task 至少通过一次。**

此前原始 eval 的 4 次评分环境故障均已通过 score-patches 补出分数，其中 Codex → Claude 的 Arktype 新补出一次通过。它是此前缺分的已存在补丁通过，并非此次重跑模型后新增成功。

## 实验范围与统计口径

- [12 题清单](../../data/selection/joint-low-opus-astra-xhigh.txt)与[筛选依据](../deepswe-opus-astra-joint-low-subsets.md)：历史 mini-swe-agent 两侧各至多 1/4 通过，且各有 4 次有效重复。“共同低分”指二元总通过率低，不表示所有功能测试都难以通过。
- Codex 使用 `gpt-6-astra / xhigh`，Claude Code 使用 `claude-opus-5 / high`，互换 modifier/reviewer。每方向 attempts=2，12 题各两次齐全。当前保存配置中的并发分别为 **1、2**；不把此前讨论过的“将 Codex → Claude 改为 2”当作已执行事实。
- Runtime 均为 `deep-swe/agent-runtime:86d93103f53a80a1`；maxReviews=3、maxAgentAttempts=2；每 task hard timeout 5400 秒、清理预留 300 秒、工作预算 5100 秒、事件静默超时 900 秒。两方向及与 medium 共有 task 的 checksum 均一致。
- Initial 是 modifier 首次实现完成、reviewer 尚未审查时的冻结补丁；final 是本次 collab 最终交付。Reward=1 要求 F2P 和 P2P 全部通过。
- 主表按每方向 **全部 24 对直接评分**统计，包含原始 eval 缺分但已补评分的 4 个 trial，也包含超时降级交付。task 通过数按两次中至少一次通过去重。
- 原始 job 结果未改写，原始缺分与直接补评分分别记录。CSV 的 repeat_by_start 是同方向同 task 按启动时间排序的 R1/R2，不代表跨方向共享随机种子。
- 附件：[48 行 trial 明细 CSV](joint-low-opus-astra-xhigh-bidirectional-48-trials-20260914.csv)、[机器可读汇总 JSON](joint-low-opus-astra-xhigh-bidirectional-48-trials-20260914.json)，包含配置、来源哈希、原始异常、阶段分项、直接最终分数及 medium 的同题对照。

## 初始与最终结果

| 指标 | Codex → Claude Code | Claude Code → Codex |
|---|---:|---:|
| 全部运行 / 完整配对 | 24 / 24 | 24 / 24 |
| Initial 通过 | 2/24（8.33%） | 3/24（12.50%） |
| Final 通过 | **2/24（8.33%）** | **1/24（4.17%）** |
| 净变化 | 0 | −2（−8.33 个百分点） |
| 0→1 新增通过 | 0 | 0 |
| 1→0 失去通过 | 0 | 2 |
| 1→1 保持通过 | 2 | 1 |
| 0→0 仍未通过 | 22 | 21 |
| Initial → final 通过 task | 1/12 → 1/12 | 2/12 → 1/12 |

合计为 5/48 → 3/48。两方向共享相同的 12 题，同题又有两次重复，不能把 48 个 trial 当作 48 道独立题目。

## 逐 task 结果

每格为初始通过次数 → 最终通过次数，分母均为两次执行。

| Task | Codex → Claude Code | Claude Code → Codex |
|---|---:|---:|
| `bandit-structured-nosec-directives` | 0/2 → 0/2 | 0/2 → 0/2 |
| `gql-incremental-graphql-delivery` | 0/2 → 0/2 | 0/2 → 0/2 |
| `ink-grid-box-layout` | 0/2 → 0/2 | 1/2 → 0/2 |
| `meriyah-explicit-resource-declarations` | 0/2 → 0/2 | 0/2 → 0/2 |
| `obsidian-linter-auto-table-of-contents` | 0/2 → 0/2 | 0/2 → 0/2 |
| `obsidian-linter-link-format-conversion` | 0/2 → 0/2 | 0/2 → 0/2 |
| `sqlfmt-create-table-ddl-formatting` | 0/2 → 0/2 | 0/2 → 0/2 |
| `termenv-preserve-ansi-resets` | 0/2 → 0/2 | 0/2 → 0/2 |
| `vulture-persistent-analysis-cache` | 0/2 → 0/2 | 0/2 → 0/2 |
| `arktype-json-schema-refs-dependencies` | 2/2 → 2/2 | 2/2 → 1/2 |
| `igel-persist-feature-schema` | 0/2 → 0/2 | 0/2 → 0/2 |
| `prometheus-transactional-reload-status` | 0/2 → 0/2 | 0/2 → 0/2 |

两方向最终通过都集中在 Arktype：Codex modifier 两次均过，Claude modifier 仅一次通过；后者的通过 trial `DMKWUkW` 以 timeout 降级结束，但保留补丁仍全部通过。其余 11 题本批最终均未通过。

## 阶段变化与部分测试分数

阶段记录中没有 initial=0、任意后续已评分阶段 reward=1 的 trial。按 pairs.jsonl 的 revision_deltas，Codex → Claude 有 14 次 revision 转移，二元分数全部不变；反向有 54 次，52 次不变、2 次下降，没有下降后重新恢复全部通过的记录。

宏平均是每个 trial 的通过率等权平均；微平均是全部通过测试数 / 全部测试数。下面均覆盖全部 24 个直接配对。

| 指标 | Codex → Claude Code，initial → final | Claude Code → Codex，initial → final |
|---|---:|---:|
| F2P 汇总/微平均 | 717/832 → 712/832（86.18% → 85.58%） | 719/832 → 703/832（86.42% → 84.50%） |
| F2P 宏平均 | 86.06% → 85.63% | 83.96% → 80.40% |
| P2P 汇总/微平均 | 116562/116582 → 116562/116582（99.98% → 99.98%） | 116554/116582 → 116471/116582（99.98% → 99.90%） |
| P2P 宏平均 | 99.80% → 99.80% | 99.79% → 95.61% |

- Codex → Claude 的 F2P 净少 5 个通过，全来自 Meriyah 两次：48/49 → 45/49、48/49 → 46/49；P2P 不变。二元分数虽然保持 0→0，部分完成度仍下降。
- Claude → Codex 的 F2P 净少 16：Arktype −2、Bandit −2、Ink −2、Prometheus −10；P2P 净少 83：Bandit −1、Prometheus −82。其余 trial 的 initial/final 测试通过数不变。
- P2P 微平均接近满分不能掩盖局部回归：Meriyah 两次合计 102,938 个 P2P，占每方向总分母 116,582 的约 88.3%。
- 许多 0→0 并不等于完全没有功能；例如补评分的两次 Vulture 均为 F2P 24/24、P2P 291/295，仍因回归测试未全过而 reward=0。

## 关键退步案例

### Arktype：第二次 revision 后丢失通过

Claude → Codex 的 `arktype-json-schema-refs-depende__9d3M8EV`：initial 与 revision-1 均 F2P 25/25、P2P 1679/1679；revision-2 降为 F2P 23/25，final 未恢复。

第二轮 reviewer 提出两个递归引用问题：失败的 anyOf 分支污染后续分支的验证状态；未解析递归 alias 在交集中被当作 object，拒绝可满足的 primitive 约束。随后发生分数下降。此处只确认时间顺序与测评分数变化，尚未逐项裁定审查意见和隐藏测试的语义冲突。[第二轮审查](../../../jobs/collab-claude-codex-joint-low-opus-astra-xhigh-12-tasks-20260913-111243/arktype-json-schema-refs-depende__9d3M8EV/agent/system/rounds/03-review/review.json)。
 
### Ink：第一次 revision 后丢失通过，后续审查超时

Claude → Codex 的 `ink-grid-box-layout__kUepWZ2`：initial F2P 25/25、P2P 49/49；revision-1 和 final 均为 F2P 23/25、P2P 49/49。第二轮审查触及 total_deadline，该 trial 最终因 timeout 降级。

首次审查提出 minmax 内容测量、指定行的放置冲突、嵌套 grid 换行高度、最终 flex 宽度变化、百分比尺寸参考区域五项问题。补丁随后丢失两项 F2P 通过；不能仅凭二元分数宣称所有审查意见都不合理。[首次审查](../../../jobs/collab-claude-codex-joint-low-opus-astra-xhigh-12-tasks-20260913-111243/ink-grid-box-layout__kUepWZ2/agent/system/rounds/01-review/review.json)。

### Prometheus：二元仍为 0，但第一次修改后整套测试未能运行

Claude → Codex 的 `prometheus-transactional-reload__FiSaxqu`：initial F2P 10/15、P2P 82/82；从 revision-1 起两项均为 0，最终保持 0。

最终 verifier 原始输出标记 `cmd/prometheus [build failed]`，base/new 测试报告缺失或为空，97 个白名单测试按未产生结果计失败。这是构建失败后形成的全零评分，不是 97 个独立运行时断言都失败。补评分与原始 final 一致；具体编译错误及其与修改的关系仍需专项定位。[最终验证日志](../../../jobs/collab-claude-codex-joint-low-opus-astra-xhigh-12-tasks-20260913-111243/prometheus-transactional-reload__FiSaxqu/verifier/test-stdout.txt)。

## 运行与审查行为

| 指标 | Codex → Claude Code | Claude Code → Codex |
|---|---:|---:|
| 保存的评测并发 | 1 | 2 |
| 完成 review | 36 | 65 |
| 完成 revision | 14 | 54 |
| approve / revise | 21 / 15 | 5 / 60 |
| findings / blocking | 118 / 19 | 240 / 222 |
| approved / max_reviews_reached / degraded | 21 / 1 / 2 | 5 / 12 / 7 |
| 开始（北京时间） | 09-13 11:12:40 | 09-13 11:12:48 |
| 结束（北京时间） | 09-14 04:36:57 | 09-14 00:23:49 |
| job 总耗时 | 17小时24分17秒 | 13小时11分1秒 |

Codex 作 reviewer 的完成 review 中，60/65（92.3%）要求 revise，blocking findings 为 222/240（92.5%）；Claude 作 reviewer 时为 15/36（41.7%）、19/118（16.1%）。前者本批要求更多修改，但未新增全部通过，且有 7/24 次超时降级。由于初始实现不同，这不是纯 reviewer 能力的受控比较。

总耗时包含环境、Agent、原始验证和等待，不含 score-patches。反向并发是 2，不能根据其墙钟更短就认定单个 task 更快。job 级 token/cost 为空，本报告不以缺失值估算模型费用。

## 四次原始缺分已补齐

四次均是 Agent 已完成、有 final 补丁，但原始 verifier 拉取镜像时失败。此次没有重跑模型或替换这些 trial。

| 方向 | Task / trial 后缀 | 原始异常 | 补评分 initial → final | Final F2P / P2P |
|---|---|---|---:|---|
| Codex → Claude | Arktype `jyzumxB` | DNS 解析失败 | **1 → 1** | 25/25，1679/1679 |
| Codex → Claude | Vulture `vRKrhHz` | DNS 解析失败 | 0 → 0 | 24/24，291/295 |
| Codex → Claude | Vulture `QDFnyNX` | DNS 解析失败 | 0 → 0 | 24/24，291/295 |
| Claude → Codex | Obsidian link `3hKFact` | TLS 握手超时 | 0 → 0 | 59/60，1131/1131 |

Codex → Claude 的原始结果只有 1 次通过，直接评分新增确认了 Arktype `jyzumxB` 的通过，所以本报告 final 为 2/24。原始 result.json 仍只有 21 次有效评分，不能将原始汇总与补评分后的汇总混写。

## 补评分完整性和脚本统计口径

| 指标 | Codex → Claude Code | Claude Code → Codex |
|---|---:|---:|
| 原始有效评分 / RuntimeError | 21 / 3 | 23 / 1 |
| 直接补评分完整配对 | 24/24 | 24/24 |
| 不同补丁评分 | 38 | 78 |
| 阶段记录 / success | 61 / 61 | 90 / 90 |
| 原始 final 对照 matched | 21 | 23 |
| mismatch / incompletePair | 0 / 0 | 0 / 0 |
| unavailable 原始对照 | 3 | 1 |
| verifierErrors | 空 | 空 |
| score-patches exitCode | 1 | 1 |

两个评分命令均 concurrency=2、force=false、reuseFinalScore=false。116 个不同补丁、151 条阶段记录均评分成功；44 条已有原始 final 的完整 reward 对照全部一致。

两个 exitCode=1 都仅因缺少原始 eval final 对照（problems 分别为 3、1 对），并非当前评分失败。补评分结果已齐全，但未回填原始 job result。脚本名为 intentionToTreat 的汇总只纳入有可用原始对照的配对，故需要和本报告全 24 对口径区分：

| 方向 / 口径 | 配对数 | Initial → final | 新增 / 失去通过 | 净变化 |
|---|---:|---:|---:|---:|
| Codex → Claude，全部直接评分 | 24 | 2 → 2 | 0 / 0 | 0 pp |
| Codex → Claude，脚本 ITT | 21 | 1 → 1 | 0 / 0 | 0 pp |
| Codex → Claude，completed-protocol | 21 | 1 → 1 | 0 / 0 | 0 pp |
| Claude → Codex，全部直接评分 | 24 | 3 → 1 | 0 / 2 | −8.33 pp |
| Claude → Codex，脚本 ITT | 23 | 3 → 1 | 0 / 2 | −8.70 pp |
| Claude → Codex，completed-protocol | 16 | 1 → 0 | 0 / 1 | −6.25 pp |

Codex → Claude 的两次降级恰好也属于原始缺分的 trial，所以 ITT 与 completed-protocol 都是 21 对。Claude → Codex 唯一最终通过来自降级 trial，因此 completed-protocol 的 final 为 0。该过滤结果不能解释为模型完全没有成功。

脚本 ITT 按 task 聚类 bootstrap 95% 区间：正向 [0, 0]，反向 [−20.83, 0] 个百分点；反向 McNemar exact p=0.5，正向无不一致配对，p=null。正向区间退化为零仅反映样本中二元变化全为零，不是“协作效果精确为零”的总体保证。上述区间仅对应脚本 ITT，并非全 24 对重算；同题重复和 12 题小样本限制了推广。

## 与 medium 在相同 12 题上的比较

[medium 报告](joint-low-opus-astra-medium-bidirectional-52-trials-20260913.md)原为 13 题；此处移除 effect，统一按每方向 12 题 × 两次、全部直接补评分比较。task checksum 一致。

| 方向 | Astra effort | Initial → final trial | 净变化 | Final 通过 task | 新增 / 失去通过 | 超时降级 | 评测并发 |
|---|---|---:|---:|---:|---:|---:|---:|
| Codex → Claude | medium | 2/24 → 0/24 | −2 | 0/12 | 0 / 2 | 3 | 1 |
| Codex → Claude | xhigh | 2/24 → 2/24 | 0 | 1/12 | 0 / 0 | 2 | 1 |
| Claude → Codex | medium | 5/24 → 4/24 | −1 | 3/12 | 0 / 1 | 2 | 1 |
| Claude → Codex | xhigh | 3/24 → 1/24 | −2 | 1/12 | 0 / 2 | 7 | 2 |

- Codex → Claude：final 从 0 增至 2，但初始通过的任务已变。medium 的两个 initial 通过来自 Meriyah，随后丢失；xhigh 的两个 initial 通过来自 Arktype，并保持到 final。两批均没有 0→1，不能把 final 差异归为 reviewer 修复能力增强。xhigh 的 Meriyah initial 本就 48/49，修改后仍退步到 45/49、46/49，二元指标没有显示这部分损失。
- Claude → Codex：final 从 4 降至 1，初始通过从 5 降至 3，且修改后损失从 1 次增至 2 次。medium 的初始通过任务是 Arktype、Bandit、Ink、Prometheus；xhigh 是 Arktype 与 Ink。两次实验的 modifier 都是 Opus high，初始表现已经不同；反向并发又从 1 改为 2，不能将全部变化归因于 Astra reviewer effort。
- 反向 timeout 从 2/24 增到 7/24，值得结合单轮时长和修改负担进一步复盘，但当前数据不足以区分思考强度、初始实现差异、并发资源争用和运行时网络情况的贡献。
- 本批只能说：xhigh 未展示把共同低分集上的初始失败修到全部通过的收益；不能凭两次采样断言提高 effort 普遍无效。

## 后续分析建议

1. 优先复盘 Arktype 第二次 revision、Ink 第一次 revision，逐项映射 review、修改响应和失败测试；单独区分 benchmark 分数下降与真实需求语义冲突。
2. 对 Prometheus `FiSaxqu` 查明编译失败原因；其二元分数一直为 0，但部分测试完成度损失很大，不能在只看 reward 的分析中忽略。
3. 后续比较保持共同任务集、并发和预算一致，增加重复次数，并设置等预算的独立单体对照。当前 initial 是 collab 内部检查点，无法分离额外修改时间与 reviewer 的因果作用。
4. 如探索保留 initial 的保护策略，应基于公开测试和可见需求；不能在线使用本次隐藏测试得分挑选 checkpoint，否则改变了评测信息边界。

## 原始证据

- **Codex → Claude Code**：`collab-codex-claude-joint-low-opus-astra-xhigh-12-tasks-20260913-111233`。
  [原始结果](../../../jobs/collab-codex-claude-joint-low-opus-astra-xhigh-12-tasks-20260913-111233/result.json) · [配置](../../../jobs/collab-codex-claude-joint-low-opus-astra-xhigh-12-tasks-20260913-111233/config.json) · [补评分汇总](../../../jobs/collab-codex-claude-joint-low-opus-astra-xhigh-12-tasks-20260913-111233/patch-scores/summary.json) · [配对明细](../../../jobs/collab-codex-claude-joint-low-opus-astra-xhigh-12-tasks-20260913-111233/patch-scores/pairs.csv) · [阶段明细](../../../jobs/collab-codex-claude-joint-low-opus-astra-xhigh-12-tasks-20260913-111233/patch-scores/stages.csv)。
- **Claude Code → Codex**：`collab-claude-codex-joint-low-opus-astra-xhigh-12-tasks-20260913-111243`。
  [原始结果](../../../jobs/collab-claude-codex-joint-low-opus-astra-xhigh-12-tasks-20260913-111243/result.json) · [配置](../../../jobs/collab-claude-codex-joint-low-opus-astra-xhigh-12-tasks-20260913-111243/config.json) · [补评分汇总](../../../jobs/collab-claude-codex-joint-low-opus-astra-xhigh-12-tasks-20260913-111243/patch-scores/summary.json) · [配对明细](../../../jobs/collab-claude-codex-joint-low-opus-astra-xhigh-12-tasks-20260913-111243/patch-scores/pairs.csv) · [阶段明细](../../../jobs/collab-claude-codex-joint-low-opus-astra-xhigh-12-tasks-20260913-111243/patch-scores/stages.csv)。
