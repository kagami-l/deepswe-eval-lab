# DeepSWE Collab（review-loop）协作机制详解

状态：与统一 runtime 当前实现（`wip/agents/deep_swe_agent/runtime/src/`）一致

日期：2026-08-07

本文详细描述 `collab/review-loop/direct` 工作方式下 Modifier 与 Reviewer 的协作流程：
各步骤之间传递哪些信息、采用什么格式，以及隔离、容错与落盘契约。总体架构、CLI、
profile 与实施计划见
[DeepSWE 统一 Agent 评测基线](./unified-agent-evaluation-design.md)；时间预算策略见
[collab-timeout-policy.md](./collab-timeout-policy.md)。

代码索引：

| 主题 | 实现位置 |
|---|---|
| 控制循环（状态机） | `runtime/src/direct-engine.ts` |
| 接口与 outcome 类型 | `runtime/src/collaboration-engine.ts` |
| Prompt 构造（信息传递格式） | `runtime/src/prompts.ts` |
| Reviewer JSON 协议解析与仲裁 | `runtime/src/review-schema.ts` |
| Git checkpoint / 拷贝隔离 / 终验 | `runtime/src/git-workspace.ts` |

## 1. 总体结构

```text
initial_modify → checkpoint → ┌ review ─ approve ──────────────→ deliver
                              │        └ revise → revision → checkpoint ┐
                              └──────────── (最多 maxReviews 轮) ←──────┘
```

两个角色由编排器（`DirectCollaborationEngine`）串联，**彼此从不直接对话**：所有信息
都由编排器收集、格式化后注入对方的 prompt。Pier 只提交一次任务 instruction，后续全部
prompt 都由编排器从 instruction 和中间产物派生，不引入新的用户输入。

关键的不对称设计：

- **Modifier**：始终在主仓库 checkout（`/app`）里工作，初始实现与所有修订**复用同一个
  session**（`resumeSession: true`），因此它天然记得自己之前做过什么，revision prompt
  不需要重述改动内容。
- **Reviewer**：每轮在**隔离的完整拷贝**中以**全新 session** 运行
  （`resumeSession: false`），编辑随拷贝丢弃。历史上下文完全靠编排器在 prompt 中重建。

信息传递一句话总结：**Modifier→Reviewer 传的是 git diff（事实）+ resolutions JSON
（观点）；Reviewer→Modifier 传的是结构化 findings（经编排器格式化为可读文本）；两者
之间唯一的持久状态载体是 git checkpoint 链**。

## 2. 逐步信息流

### 2.1 初始实现（modify）

**编排器 → Modifier**：纯文本 prompt（`buildModifierInitialPrompt`），包含：

- 任务原文（从 `instructionPath` 读入）；
- Modifier ground rules：只在工作目录内改、**不许 commit**（checkpoint 由 harness
  创建）、不建分支/不 fetch/不查看 HEAD 不可达的 commit、改动最小化、可以运行仓库
  自带测试。

**Modifier → 编排器**：不通过文本传递结果，编排器直接检查**工作树**：

1. 用 `stageAllExcept(baseline)` 暂存改动（`git add -u` + 仅新增的 untracked 文件，
   排除启动时记录的基线 untracked 清单，避免把镜像自带文件卷入 patch）；
2. 判断是否有实际变更：无变更视为失败（最终映射为 `empty_patch`）；
3. 失败/超时/空改动会 `git reset --hard` 回滚到本轮基准 commit 并清理新增 untracked
   文件后重试，最多 `maxAgentAttempts` 次；
4. Modifier 若违规自行 commit，容忍 HEAD 移动并记录 protocol violation。

成功后编排器执行 `git commit --no-verify` 创建 checkpoint
（message 形如 `collab: initial implementation`）。

### 2.2 Review 轮次（第 round 轮）

**工作区准备**：review 开始前，Modifier 的改动已 checkpoint 到主仓库 HEAD。编排器用
`cp -a` 把**整个主仓库目录**（含 `.git`、untracked、ignored 文件）完整拷贝到
`workDir/review-<round>-a<attempt>/`。Reviewer 在该拷贝中工作，看到的是**修改后的
最终状态**，git 历史完整保留——它可以直接跑测试、读改动周边代码，也可以通过
`git show <baseCommit>:path` 查看任务初始状态。每次 attempt 都重新拷贝一份，review
结束即删除（除非 `keepWorkspaces`），任何编辑都不会回流主仓库。

**编排器 → Reviewer**：prompt 由 `buildReviewerPrompt` 组装，包含五块信息：

1. **任务原文**（`<original-task>` 标签包裹）——评审标准是"改动是否正确完整地实现了
   任务且不破坏已有行为"，风格问题至多标 `suggestion`；
2. **补丁**：`git diff --binary <baseCommit> HEAD` 的输出，内联在 `<patch>` 标签中；
   超过 200 KB 截断，并附上可在拷贝中自行运行的 `git diff <baseCommit> HEAD` 命令；
3. **轮次信息**：`review round {round} of {maxReviews}`；
4. **上一轮历史**（第 2 轮起）：上一轮 findings 的格式化文本 + Modifier 自报的
   resolutions（见 2.3），并附指令"不要重提已被有效反驳的 finding，去验证反驳；关注
   blocking findings 是否真被解决，以及 revision 引入的新问题"；
5. **格式重试提示**（仅当上一 attempt 输出解析失败）：要求只输出 JSON，并附具体
   解析错误信息。

**Reviewer → 编排器**：要求最终回复是**纯 JSON 对象**（cligent 无结构化输出能力，
由本地 parser 解析）：

```json
{
  "verdict": "approve" | "revise",
  "summary": "<one or two sentences>",
  "findings": [
    {
      "id": "R<round>-F<n>",
      "severity": "critical" | "major" | "minor" | "suggestion",
      "file": "<repo-relative path or null>",
      "line": "<number or null>",
      "issue": "<what is wrong>",
      "evidence": "<why you believe it is wrong>",
      "required_change": "<what must change>"
    }
  ]
}
```

**解析与仲裁规则**（`parseReview`）：

- 解析对不守规矩的输出健壮：扫描全文所有平衡的 `{...}` 区域（含引号/转义追踪，避免
  prose 中的引号或引用代码里的花括号干扰），从后往前取**最后一个声明了 `verdict`
  的候选**——verdict 是 reviewer "签署"决定的方式；
- **Fail closed**：末尾声明了 verdict 但 JSON 损坏（如截断）时抛
  `ReviewParseError` 触发带错误信息的格式重试，而不是回退到更早的旧对象；无 verdict
  时仅当全文恰好只有一个候选对象才接受，多个候选一律判无效；
- **裁决依据是 findings 而非 verdict**：存在 `critical`/`major`（blocking）即进入
  revision；`minor`/`suggestion` 仅记录、不阻塞交付；verdict 与 findings 矛盾时记录
  `verdictMismatch` 并按 findings 执行。

### 2.3 Revision（revise / final-revision）

无 blocking findings → outcome `approved`，交付。否则：

**编排器 → Modifier**（同一 session 续接，`buildRevisionPrompt`）：

- 任务原文（`<original-task>`）+ "独立 reviewer 要求 revision（第 round/maxReviews
  轮）"；
- Reviewer summary + findings 的格式化文本，每条形如：

  ```text
  - [major] R1-F2 src/foo.py:42
    issue: ...
    evidence: ...
    required change: ...
  ```

- 处理要求：每个 blocking finding 要么修复、要么**给出具体证据反驳**；非 blocking
  可选处理；
- 最后一轮附 final note：不会再有 review，优先处理你认同的 blocking findings，把
  代码留在可交付状态；
- 要求回复末尾附 **resolutions JSON**：

  ```json
  {
    "resolutions": [
      { "id": "<finding id>", "status": "accepted" | "rebutted" | "unresolved", "note": "<short reason>" }
    ]
  }
  ```

**Modifier → 编排器**：两个通道——

- (a) 工作树中的实际改动：同样 stage 后 checkpoint（`collab: revision N` 或
  `collab: final revision`）；
- (b) 最终文本中的 resolutions 报告：`parseResolutions` **尽力解析**（取最后一个声明
  `resolutions` 的候选；解析失败不判本轮失败，下一轮 reviewer 会看到
  "(no resolution report provided)"）。这份 resolutions 是 reviewer 唯一能看到的
  Modifier 观点，构成两个角色之间的"对话"回路。

特殊规则：

- **No-change revision**：revision 允许零改动（例如全部反驳）。此时不再消耗下一轮
  review，直接以 `max_reviews_reached` 结束并记录 `noChangeRevision`；
- 最后一轮 revision 完成后同样不再启动新 review，outcome 为 `max_reviews_reached`
  （正常可交付结果，不是失败或降级）。

## 3. 交付与终验（finalize）

最终产物为 `final/patch.diff`（`git diff --binary <baseCommit> HEAD`）与
`final/git-status.txt`。可交付 outcome（`approved` / `max_reviews_reached` /
`degraded`；single 为 `completed`）还须通过两道终验：

1. patch 非空，否则降级为 `empty_patch`；
2. 在以 base commit 检出的干净临时 worktree 上 `git apply --check` 通过，否则
   `checkpoint_failed`。

## 4. 容错与降级

核心原则：**一旦存在可信 checkpoint，后续失败不丢弃已有工作**。

- Reviewer 进程失败/超时/输出无法解析（重试耗尽）、revision 失败、总预算耗尽、
  checkpoint 之后的基础设施异常——都降级为交付最后一个 checkpoint：outcome
  `degraded`，`degradedReason` 取
  `reviewer_failed | invalid_review_output | revision_failed | timeout | infrastructure`；
- `strict` 模式恢复 fail-hard：`degraded` 不算可交付；
- 初始实现失败则整个 trial 失败（`modifier_failed` / `timeout` / `empty_patch` /
  `checkpoint_failed`），不接受半成品工作区；
- 每个 turn 受总 wall-clock deadline、可选阶段 timeout 与事件静默 watchdog 共同约束，
  剩余时间不足 `minTurnSec` 时不再启动新 turn（详见
  [collab-timeout-policy.md](./collab-timeout-policy.md)）。

## 5. 落盘的中间产物（可观测性）

每个回合一个目录 `rounds/NN-<kind>/`（kind ∈ `modify` / `review` / `revise` /
`final-revision`）：

```text
rounds/NN-<kind>/
├── prompt.md 或 prompt-aN.md   # 发给 agent 的完整 prompt（review 每 attempt 一份）
├── events.jsonl                # cligent 事件流（同时汇总到全局 events.jsonl）
├── patch.diff                  # review 轮：送审的 base→HEAD diff
├── review-raw-aN.txt           # review 轮：reviewer 原始最终文本
├── review.json                 # review 轮：解析后的 verdict/summary/findings
├── diagnostics/                # watchdog 触发时的诊断快照
└── metadata.json               # 每次 attempt 的状态、超时类型、token 用量
```

全局 `orchestrator-trace.jsonl` 记录编排器状态机事件（`review_done`、`checkpoint`、
`no_change_revision`、`engine_exception` 等），不混入 LLM 消息。汇总结果
（outcome、degradedReason、双角色 usage、实际模型、findings 计数、checkpoint 列表、
protocol violations）进入 `summary.json`，字段定义见
`collaboration-engine.ts` 的 `CollaborationResult`。
