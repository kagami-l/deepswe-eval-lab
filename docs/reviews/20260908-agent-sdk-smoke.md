# SDK 升级后的 one_task 真实 smoke

日期：2026-09-08。任务清单：`wip/one_task.txt`，唯一任务
`abs-module-cache-flags`。两组依次运行，各 1 个 trial，并发 1，开启独立 verifier。
使用同一原始任务基线；single 的 patch 没有带入 collab。

## 结果

| 配置 | Agent 结果 | 正式评分 | 总耗时 |
| --- | --- | --- | --- |
| single：Codex / gpt-5.6-luna / xhigh | completed，1 turn | **23/23，reward 1**；20/20 F2P、3/3 P2P | 16 分 35 秒 |
| collab：同上 modifier；Claude / claude-sonnet-5 / high reviewer | approved，2 轮 review、1 次修订 | **12/23，reward 0**；9/20 F2P、3/3 P2P | 34 分 14 秒 |

两组进程均正常退出，trial 无 exception。collab 的正常退出和 reviewer approve
表示工作流完成，不能代替 verifier 的任务通过结论。本次执行链路 smoke 通过，
但 collab 的最终任务评分失败。只有一个任务、每组一次，不足以推断两种模式的总体优劣。

运行基线为 [SDK 升级记录](./20260908-agent-sdk-upgrade.md)中的 runtime 0.6.0：
cligent 0.26.0、Codex SDK/CLI 0.151.0、Claude Agent SDK 0.3.251。
镜像 `deep-swe/agent-runtime:810a05e3fb3ee42c`；digest
`810a05e3fb3ee42c83b5097821914ff0924360c5dea1e67d4d97786b90a40cfc`。
模型与 effort 为本次 CLI 覆盖，未修改默认 profiles。

## 协作过程及评分失败

1. Codex 初始实现：14 分 45 秒，50 次工具调用。
2. Claude 第一轮审查：约 6 分 40 秒，61 次工具调用。最终 verdict 为 revise，
   包含 1 项 major（入口脚本参与循环加载时副作用重复执行）和 1 项 minor（缺少自动化测试）。
3. Codex 恢复同一 session 修订：约 4 分 34 秒，6 次工具调用，修复入口循环并补充测试。
4. Claude 第二轮审查：约 6 分 20 秒，45 次工具调用，verdict 为 approve。
   保留 1 项非阻断 suggestion：脚本入口占用 load stack，使 inflight 计数基线与 REPL 不同。

verifier 的 11 项失败分为两组：

- **8 项 evaluator 用例**在加载绝对路径模块时直接报 `cannot resolve module`，涉及
  canonical cache、cache keys、循环检测、debug 输出及缓存重置。
- **3 项 repl 用例**没有最终测试结果：ModuleDebugFlag 开始后该测试包失败退出，
  DoubleDashScriptPath 和 UnknownFlagBeforeScript 未产生结果。这里不能写成 3 个普通断言失败。

最终 patch 的 `resolveModule` 对请求无条件执行
`filepath.Join(directory, filepath.FromSlash(request))`，没有绝对路径分支，
与绝对路径模块加载失败一致。这是对冻结 patch 与评分日志的静态核对；没有修改产物
或额外重跑来推翻正式分数。reviewer 的手工验证和新增测试漏掉了该路径。
首次 smoke 报告时尚未单独评分初始 checkpoint；后续配对评分结果见下节。

## 后续：首轮 Codex patch 配对评分

2026-09-08 16:22–16:25，按用户要求运行现有入口：

```bash
wip/.venv/bin/python wip/scripts/run_agent_eval.py score-patches \
  --job-path jobs/sdk-upgrade-smoke-collab-one_task-20260908-140305 \
  --trial abs-module-cache-flags__GEbUkbb \
  --concurrency 1
```

该入口将首个 review 的 `01-review/patch.diff` 识别为 initial；
`03-review/patch.diff` 为 revision-1，与 final 内容相同，按指纹去重。
本次从任务基线分别重放两个不同的冻结 patch，使用正式 separate verifier，
未重新调用模型。未使用 `--reuse-final-score`，因此最终版也实际重新评分。

| 阶段 | F2P | P2P | 合计 | Reward |
| --- | --- | --- | --- | --- |
| 首轮 Codex，reviewer 介入前 | 9/20 | 3/3 | **12/23** | **0** |
| 修订一次后的最终版 | 9/20 | 3/3 | **12/23** | **0** |

首轮、重评最终版和原始 eval 最终版的 **23 项逐项测试状态完全一致**；
脚本报告 `classification=unchanged`、`delta=0`、`final_conformance=matched`，
无 verifier error 或不完整配对。正式评分中的失败在首轮就已存在，
此次 review/revision 没有改善或恶化这些测试结果；不能据此推断对所有代码行为没有影响。

独立 single run 的 23/23 是另一次模型生成的实现，不是此 collab 的首轮 patch。

产物：[阶段评分表](../../jobs/sdk-upgrade-smoke-collab-one_task-20260908-140305/patch-scores/stages.csv)、
[配对结果](../../jobs/sdk-upgrade-smoke-collab-one_task-20260908-140305/patch-scores/pairs.csv)、
[评分汇总](../../jobs/sdk-upgrade-smoke-collab-one_task-20260908-140305/patch-scores/summary.json)。

## SDK 和统计链路验收

- single 1 个 turn、collab 4 个 turn 均成功终止；**每个 turn 恰好 1 次 init 和 1 次 done**，
  无 error、协议违例、降级或重试。
- 实际 init 模型为 `gpt-5.6-luna` / `claude-sonnet-5`，与请求一致。
- collab modifier 的 modify/revise session ID 相同，真实会话恢复成功；两轮 reviewer
  使用独立新会话。尚未覆盖 Claude resume，不能据此宣称 Claude fresh/resume 全面验收完成。
- 原始 terminal usage 与 summary 中每轮 `usageReports` 逐项相等，统计脚本成功消费两组真实产物。
- Claude 两轮均报告 complete，保留 Sonnet 和 SDK 辅助 Haiku 模型 records、缓存读写及
  `agent-estimate` 费用来源。本次总计约 **$2.16917** 是上游 SDK 的估算，不是实际账单。

| 用量范围 | 已观测 input | 已观测 output | 覆盖与限制 |
| --- | ---: | ---: | --- |
| single Codex | 4,514,087 | 32,860 | partial；其中 cacheRead 4,388,096，reasoning 22,218；费用未知 |
| collab Codex 首轮 | 4,024,945 | 39,565 | partial；只代表有报告的首轮，费用未知 |
| collab Codex 修订轮 | 未知 | 未知 | terminal 仅有 toolUses=6，无 tokens/cost |
| collab Claude 两轮 | 5,604,701 | 53,164 | complete；cacheRead 5,452,289、cacheWrite 131,529 |

**待跟进的统计限制：Codex resume 修订轮缺少 token 报告。** 本地 adapter/Cligent
实例在两轮间复用，实际 session 也一致，但修订 terminal 仍未暴露 tokens。
cligent 的 codex-15 会在基线缺失、计数下降、形状变化或无有效快照时省略数据；
当前保存的是统一事件，缺少原生累计 usage 快照，无法确定本次具体触发哪一项，
也不能直接归因为供应商完全没发 usage。后续诊断需要记录原生快照。
本项目将 modifier 两轮合计的顶层 input/output 保留为 null，已观测首轮小计留在
nested tokens，coverage 为 partial。Pier 完整总量保持未知，没有把缺失轮次当作零。

## 产物

| 组别 | Job / Trial |
| --- | --- |
| single | `sdk-upgrade-smoke-single-one_task-20260908-140305` / `abs-module-cache-flags__vtU9bwB` |
| collab | `sdk-upgrade-smoke-collab-one_task-20260908-140305` / `abs-module-cache-flags__GEbUkbb` |

- [single job 结果](../../jobs/sdk-upgrade-smoke-single-one_task-20260908-140305/result.json)
- [single summary](../../jobs/sdk-upgrade-smoke-single-one_task-20260908-140305/abs-module-cache-flags__vtU9bwB/agent/system/summary.json)
- [collab job 结果](../../jobs/sdk-upgrade-smoke-collab-one_task-20260908-140305/result.json)
- [collab summary](../../jobs/sdk-upgrade-smoke-collab-one_task-20260908-140305/abs-module-cache-flags__GEbUkbb/agent/system/summary.json)
- [collab verifier 明细](../../jobs/sdk-upgrade-smoke-collab-one_task-20260908-140305/abs-module-cache-flags__GEbUkbb/verifier/ctrf.json)
- [collab 冻结 patch](../../jobs/sdk-upgrade-smoke-collab-one_task-20260908-140305/abs-module-cache-flags__GEbUkbb/artifacts/model.patch)

本次真实评测只产生 job 产物和此验收记录，未更改任务基线、历史评分、runtime 代码或默认 profile，
未提交 Git commit。
