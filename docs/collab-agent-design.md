# DeepSWE 多 Agent 协作评测方案

> **文档定位（2026-08-03）**：本文描述现有 `deep_swe_collab` direct
> review-loop 原型及其历史设计。后续 single/collab 统一新基线、通用 shared
> runtime、版本化 Agent profiles 和正式实施计划见
> [DeepSWE 统一 Agent 评测基线：正式设计与实施计划](./unified-agent-evaluation-design.md)。
> 新基线不会在开发阶段改写本文对应的旧脚本和旧 runtime。

## 1. 目标

在 DeepSWE 评测集上运行自定义的“修改 → 审查 → 修订”协作流程，比较单 Agent、自审和异构 Agent 协作的效果。协作 treatment 只包含 Modifier 和 Reviewer 两个 LLM Agent；状态流转和结构化输出判定由本地确定性控制逻辑完成，不引入 Captain/Judge 模型调用。

设计优先级如下：

1. 以方便、可靠地在 DeepSWE/Pier 上运行为第一目标。
2. 使用 Pier/Harbor 原生的任务隔离、工件提取和 verifier，不依赖 SWE-bench Pro runner。
3. 分阶段 dogfood：首阶段使用 `@sublang/cligent`，待关注的评测任务稳定运行后再引入 `@sublang/playbook`，避免同时调试两层新基础设施。
4. 隐藏测试和 verifier 不进入协作循环，只评价最终提交。

依赖包与本地仓库：

- `cligent`：npm `@sublang/cligent`（当前 0.18.0，与本地 checkout `/Users/kgm/Projects/merico/cligent` 的 v0.18.0 tag 一致）
- `playbook`（第二阶段）：npm `@sublang/playbook`（当前 3.1.0，与本地 checkout `/Users/kgm/Projects/merico/playbook` 一致）

默认从 npm 锁定精确版本安装；本地 tarball 仅作为修复迭代期的 override 通道（见第 11 节）。

## 2. 推荐架构

```mermaid
flowchart LR
    P["Pier / Harbor"] --> A["DeepSweCollabAgent"]
    A --> R["容器内协作 Runtime"]
    R --> CE["CollaborationEngine 接口"]
    CE --> D["首阶段：Direct engine"]
    D --> C["cligent Modifier LLM"]
    D --> V["cligent Reviewer LLM"]
    D --> J["本地 Reviewer JSON parser"]
    C --> APP["/app 主工作区"]
    V --> WT["隔离 Review 拷贝工作区"]
    APP --> G["Git checkpoint commits"]
    G --> PA["pre_artifacts.sh"]
    PA --> E["独立 verifier 环境"]
    PB["第二阶段：Playbook engine"] -.实现同一接口.-> CE
```

各组件职责：

- Pier/Harbor：准备任务环境、执行自定义 Agent、管理网络策略、提取 patch、运行 verifier 和汇总 reward。
- `DeepSweCollabAgent`：Pier 自定义 Agent 适配层，负责安装和启动容器内协作 Runtime，并回填 AgentContext。
- 手写 deterministic orchestrator：首阶段直接控制修改、审查、修订、重试、轮数和最终交付，并解析 Reviewer 的严格 JSON。
- `cligent`：统一驱动 Codex、Claude Code、OpenCode 等 coding-agent SDK/CLI，提供事件流、session、usage、permissions 和 abort。
- `playbook`：第二阶段实现同一 `CollaborationEngine` 接口的可替换控制后端；在首阶段评测稳定前不进入关键路径。
- Git：保存每轮可信修改。DeepSWE 的 `pre_artifacts.sh` 从最终 HEAD 提取相对 base commit 的 patch。

## 3. 为什么在任务容器内运行 cligent

`cligent` 的内置 adapter 驱动本地 SDK/CLI，并通过 `cwd` 访问代码工作区。Pier 的 `/app` 位于任务容器中，宿主机进程不能直接把本地 adapter 的 `cwd` 指向容器内部路径。

因此推荐：

1. Pier 自定义 Agent 是宿主侧的薄 Python 适配层。
2. `cligent`、Node runtime 和 coding-agent SDK/CLI 安装在任务容器中。
3. Python 适配层通过 Pier `environment.exec()` 启动容器内 runtime。

不建议为了宿主侧运行 cligent 而实现一套跨 Python/TypeScript 的远程执行 adapter；这会显著增加复杂度，也不利于 DeepSWE 原生运行。

## 4. Pier 自定义 Agent

建议目录（沿用仓库现有的 `wip/agents/` 约定，实现方式参考 `wip/agents/kimi_code_agent.py`）：

```text
wip/agents/deep_swe_collab/
├── __init__.py
├── pier_agent.py          # Pier BaseInstalledAgent 适配层
├── test_pier_agent.py     # unittest（含 install_spec 与 package.json 防漂移测试）
├── README.md
└── runtime/               # 容器内 TypeScript orchestrator
    ├── package.json       # npm 锁定 @sublang/cligent + SDK 版本
    ├── package-lock.json
    ├── tsconfig.json
    └── src/
        ├── main.ts                  # 入口：读 config、写 summary.json、exit code
        ├── collaboration-engine.ts  # CollaborationEngine 接口与 outcome 类型
        ├── direct-engine.ts         # 首阶段确定性状态机
        ├── agent-runner.ts          # AgentRunner 接口 + CligentRunner（6.4 的 adapter 配置）
        ├── git-workspace.ts         # 基线 untracked、checkpoint、拷贝隔离、apply --check
        ├── prompts.ts               # Modifier/Reviewer prompt 构造
        ├── review-schema.ts         # 严格 JSON review 解析与仲裁
        └── *.test.ts                # node:test 单测（fake runner 驱动状态机）
```

`npm run build` 产出 `runtime/dist/`（不入库），`setup()` 上传到容器
`/opt/collab-runtime/dist`；npm 依赖由 `install_spec()` 在派生镜像中安装。

`pier_agent.py` 实现 `pier.agents.base.BaseAgent`（如需 `install_spec()` 派生镜像和 `populate_context_post_run()` 则继承 `BaseInstalledAgent`；pier 是 Harbor 的 fork 但运行时不使用 harbor 包，不要 import harbor）：

- `setup(environment)`：
  - 上传 runtime bundle；
  - 安装 cligent（npm 锁定版本）和所需 coding-agent SDK/CLI——任务镜像是 Debian 12 且预装 Node v24.12.0，无需自装 Node；
  - 记录实际安装版本。
  - 注意 agent setup 有独立的默认 360 秒超时（`--agent-setup-timeout-multiplier` 可放大），不占 agent 运行预算；批量运行时应改用 `install_spec()` 把安装步骤烘进派生镜像，避免每个 trial 重复在线安装。
- `run(instruction, environment, context)`：
  - 将 DeepSWE instruction 安全写入容器；
  - 在 `/app` 上运行协作 workflow；
  - 收集 summary、token usage、耗时和 outcome；
  - 将最终数据写入 `/logs/agent/`；
  - 回填 `AgentContext`（`n_input_tokens`、`n_output_tokens`、`cost_usd`、`n_agent_steps` 等；Modifier/Reviewer 分角色明细放入 `metadata`）。

Pier 通过 `--agent-import-path` 加载自定义 Agent（`--agent` 是内置 agent 的固定枚举，不能用于自定义类）。预期调用形式：

```bash
pier run \
  -p tasks/fastapi-implicit-head-options \
  --agent-import-path wip.agents.deep_swe_collab.pier_agent:DeepSweCollabAgent \
  --ak modifier_adapter=codex \
  --ak reviewer_adapter=claude \
  --ak max_reviews=3
```

正式实验推荐使用 Pier job config 固化完整配置，而不是依赖较长的命令行。

## 5. 分阶段协作控制层

### 5.1 首阶段：手写 deterministic orchestrator

首阶段不安装、不导入 `playbook`。用普通 TypeScript 编写小型控制循环，直接根据 Reviewer 严格 JSON 中是否存在 blocking finding 决定交付或修订（`verdict` 字段仅作交叉校验，见第 8 节），不经过 Captain、Judge 或 LLM 控制面。

控制层实现统一接口，避免以后引入 playbook 时改动 Pier 和 cligent 集成：

```ts
interface CollaborationEngine {
  run(input: TaskInput): Promise<CollaborationResult>;
}
```

`DirectCollaborationEngine` 执行以下流程：

```text
prepare
  → initial_modify
  → checkpoint_0
  → review_1
      ├── approve → deliver
      └── revise → revision_1
                       → checkpoint_1
                       → review_2
                           ├── approve → deliver
                           └── revise → revision_2
                                            → checkpoint_2
                                            → review_3
                                                ├── approve → deliver
                                                └── revise → final_revision
                                                                 → checkpoint_3
                                                                 → max_reviews_reached
```

控制代码仍需显式记录上述状态和 transition event，以便测试、恢复和分析。这样有以下优点：

- 状态和 artifacts 容易检查；
- 每个阶段可独立设置 timeout；
- 异常和降级语义明确；
- 便于可视化和测试；
- Reviewer 结构化输出可以直接驱动分支，不需要额外 adjudication。

后续验证稳定后，再把它泛化为可配置的 `max_reviews=N` 循环。

该流程是非交互式的：Pier 只提交一次当前 task 的 `instruction.md`。后续 Modifier prompt、Reviewer prompt 和修订反馈都由 orchestrator 根据既有 instruction、patch 和 findings 自动生成，不再请求新的用户输入。遇到信息不足时，Agent 应基于仓库和 instruction 作合理假设，无法继续则返回结构化失败。

### 5.2 第二阶段：playbook backend

待 3 题 smoke、12 题 dev 以及关注的正式评测任务稳定运行后，再增加 `PlaybookCollaborationEngine`。它与 direct engine 共用 prompts、Reviewer schema、cligent player、Git/拷贝工作区、outcome 和 artifact schema，只替换状态流转实现。

第二阶段不直接使用 `@sublang/playbook` 自带的 CODE workflow，因为它包含 spex/spec、IR 和 Committer 等与 DeepSWE 无关的语义。应编写专用 workflow，并先通过 fake player 测试证明它与 direct engine 在相同输入序列下产生相同 transition 和 outcome，再运行真实任务。

## 6. cligent Agent 配置

创建两个主要 `Cligent` 对象：

### 6.1 Modifier

- 工作目录：`/app`。
- 允许修改文件和运行公开测试。
- 初始修改和所有修订复用同一个 session（cligent 的 resume token 机制）；resume 失败时降级为 fresh session，并在 prompt 中重建完整上下文。
- 初始 prompt 只接收公开 instruction、代码仓库和普通工程指令。
- 修订 prompt 额外接收结构化 findings 和历史处理情况。
- 每轮（初始或修订）失败、超时或产出无效 patch 时，harness 先 `git reset --hard` 回到上一个 checkpoint 并按基线清单清理新增 untracked 文件，再重试；每轮最多 `max_modifier_attempts`（默认 2）次，全部失败按第 13 节处理。
- prompt 要求 Modifier 不自行 commit；若其仍然 commit（DeepSWE 原生 instruction 鼓励 commit，agent 可能习惯性执行），harness 容忍 HEAD 移动，把这些 commit 视为该轮修改的一部分并记录 protocol violation。

### 6.2 Reviewer

- 工作目录：每轮从当前 checkpoint 制作的独立完整拷贝（`cp -a`），不是 git worktree。
- 每轮使用 fresh session，降低对上一轮结论的锚定；但第 N（N>1）轮 prompt 必须附带上一轮 findings 和 Modifier 的 accepted/rebutted/unresolved 处理记录，避免重提已被有据反驳的问题和 finding churn。
- 可以读取完整代码、当前 patch、原始 instruction，并运行公开测试。
- 只输出 findings，不对 `/app` 贡献代码。
- 即使 Reviewer 修改或 commit，它也只影响临时拷贝。

Reviewer 隔离不能只依赖 adapter permissions。不同 adapter 对“允许执行 shell，但禁止写文件”的表达能力并不一致（Kimi adapter 甚至直接拒绝 capability 策略），尤其 Bash 命令本身可能写入文件。独立拷贝是跨 adapter 更可靠的事务边界。

不使用 `git worktree` 的原因：任务镜像的 `/app` 里通常带有 git 不追踪的环境文件（node_modules、venv、构建产物等），worktree 会全部丢失，导致 Reviewer 无法运行公开测试；SWE-bench Pro runner 的 workspace 实现正是因此弃用 worktree、改用完整目录拷贝。残余风险是项目配置对 `/app` 绝对路径的耦合可能使测试在拷贝目录中失败，须在 smoke run 中按语言逐一验证；确不可行的任务可降级为“Reviewer 只读审查、不跑测试”。

### 6.3 非 LLM 控制逻辑

首阶段由 direct engine 本地完成：

- 接收 Pier 提交的唯一 DeepSWE instruction，并启动固定流程；
- 使用 JSON Schema 校验 Reviewer 输出；
- 把 `approve` 和 `revise` 直接映射为控制分支；
- 维护轮数、deadline、checkpoint 和 outcome；
- 输出结构化 transition trace。

这些操作都是本地确定性代码，不创建 `Cligent`，也不产生模型 token 或费用。因此实际模型调用严格限定为 Modifier 和 Reviewer。

### 6.4 adapter 配置注意事项（容器内 headless）

- Codex：必须以 `mode: 'bypass'` 运行（映射为 `:danger-full-access` + approval never）。Codex 自带的 OS 级沙箱在普通 Docker 容器内无法初始化，任何映射到 `:read-only`/`:workspace` profile 的 capability 策略都会失败；pier 内置 Codex agent 同样以 `--dangerously-bypass-approvals-and-sandbox` 运行，容器本身就是隔离边界。
- cligent 的 `PermissionPolicy` 一旦提供，未显式设置的字段默认为 `ask`，而 headless 下 `ask` 等价于拒绝——各 adapter 的策略必须逐字段显式写全。
- OpenCode：`websearch` 不在 capability 映射内，落到 `ask` 会让 headless run 无限挂起，必须在 opencode 配置中显式处理。
- Kimi：拒绝一切 capability 策略（仅接受 `mode: 'auto'` 或不传 permissions），且不产出 cost 数据。必须使用新版 Kimi Code CLI（npm `@moonshot-ai/kimi-code`，cligent 通过其 `kimi acp` 子命令驱动），不是旧版 Python `kimi-cli`；两代二进制同名 `kimi` 且 cligent 从 PATH 解析，容器 setup 应复用 `wip/agents/kimi_code_agent.py` 的安装与版本校验逻辑，并在安装后探针确认 `acp` 子命令存在。
- cligent 的 usage 是 per-run 粒度，跨轮/跨角色汇总由 orchestrator 自行累加。
- cligent 无结构化输出能力，`DonePayload.result` 是自由文本——6.3 的本地 JSON parser 是必要设计而非可选项。

## 7. Git 与 DeepSWE patch 提取

DeepSWE v1.1 的 `pre_artifacts.sh` 是严格的 commit-to-commit diff（`git diff --binary <base> HEAD`），工作区未提交修改和 untracked 文件都不会进入 patch。因此所有可信 Modifier 状态都应机械 checkpoint：

0. Harness 启动时记录基线 untracked 清单（镜像在 base commit 时 `/app` 里已存在的未追踪文件）。
1. Modifier 完成一轮修改。
2. Harness 检查当前状态和 patch 是否有效；若 Modifier 自行 commit 过，容忍 HEAD 移动并记录。
3. Harness 暂存全部修改，但排除基线 untracked 清单中的文件（等价于 `git add -u` + 仅添加新增的 untracked）。不能直接 `git add -A`：那会把镜像自带的基线文件提交进历史、污染最终 patch，甚至导致 verifier apply 失败。
4. Harness 创建固定格式 checkpoint commit。
5. Reviewer 从该 checkpoint 制作独立完整拷贝（见 6.2）。
6. 修订成功后创建新的 checkpoint commit。
7. 交付前对干净基线做一次 `git apply --check` 终验，确保最终 patch 可应用。

建议 commit message：

```text
collab: initial implementation
collab: revision 1
collab: final revision
```

DeepSWE verifier 只消费最终 diff，不要求中间 commit 历史整洁。机械 commit 可以避免引入第三个 Committer LLM，也保证最终修改不会被 `pre_artifacts.sh` 丢失。

创建 review workspace 的概念流程：

```text
/app HEAD at checkpoint-N
  └── cp -a /app /tmp/deepswe-review-N
          └── Reviewer 在这里审查和运行公开测试
```

review 结束后删除临时拷贝；无论 Reviewer 做了什么，都不能污染 `/app`。

## 8. Reviewer 输出协议

Reviewer 输出严格 JSON。

通过示例：

```json
{
  "verdict": "approve",
  "summary": "Implementation covers the requested behavior.",
  "findings": []
}
```

要求修订示例：

```json
{
  "verdict": "revise",
  "summary": "Two blocking correctness issues remain.",
  "findings": [
    {
      "id": "R2-F1",
      "severity": "major",
      "file": "src/foo.ts",
      "line": 84,
      "issue": "Repeated registration loses the previous handler.",
      "evidence": "register() overwrites the map entry unconditionally.",
      "required_change": "Preserve and compose existing handlers."
    }
  ]
}
```

协议规则：

- `critical`、`major` 为 blocking findings。
- `minor`、`suggestion` 仅记录，不阻止交付。
- 仲裁以 findings 为准：是否进入修订由是否存在 blocking finding 决定；`verdict` 只作交叉校验，与 findings 矛盾时（如 `approve` 却带 critical finding）记录 `verdict_mismatch` 并按 findings 执行。
- 非法 JSON 重试 Reviewer 一次，并明确要求修正格式。
- 修订轮产出与上一 checkpoint 完全相同的 patch（no-change revision）时记录标记，不再消耗下一次 review，直接按当前 patch 交付并标记 `max_reviews_reached`。
- Reviewer 进程或 API 失败、重试后仍非法的输出，按第 13 节的降级语义处理，不伪装成正常评分结果。
- 第 `N` 次 review 仍有 blocking findings 时，Modifier 获得一次最终修订机会，但不执行第 `N+1` 次 review。
- 此时正常交付最终 patch，但 outcome 标记为 `max_reviews_reached`，不能标记为 approved。

Modifier 应逐条记录：

- accepted：接受并修改；
- rebutted：有证据地反驳；
- unresolved：未完成或不确定。

## 9. 第二阶段的 playbook Captain/Judge 边界

本节只约束后续 `PlaybookCollaborationEngine`，不属于首阶段 direct engine 的运行路径。

playbook 术语在参考 workflow 的自然语言和 runtime 中容易混淆，本方案按以下含义使用：

| 概念 | 在通用 playbook 中 | 在第二阶段 backend 中 |
|---|---|---|
| Boss | 发起请求并可能继续回复的人或外部系统 | Pier/harness；只提交一次 `instruction.md` |
| Boss input | Boss 发给 workflow 的输入 | task 的 `instruction.md`，即唯一初始指令 |
| Captain | workflow 的协调视角；只有编译出 `src: 'captain'` 时才是实际 Agent actor | 不实例化，也不调用 |
| Player | 执行具体工作的 Agent | Modifier 和 Reviewer |
| Judge | 把 player 输出判定为 FSM guard/payload 的端口 | 本地确定性 JSON parser，不是 LLM |

因此，`instruction.md` 相当于“用户给系统的唯一任务输入”，但它不是 Captain。更准确的对应关系是：Pier/harness 代表 Boss，`instruction.md` 是 Boss input；playbook runtime 负责编排，Modifier 和 Reviewer 执行工作。

参考 CODE workflow 中诸如 “Captain shall relay to Coder” 的表述，不等于必须先调用一个 Captain LLM 再调用 Coder。这里的 Captain 可以只是流程描述中的协调主体；如果编译结果直接进入 player actor，runtime 只调用相应 Player。只有 FSM 中实际存在 `src: 'captain'` 状态时才会调用 `callCaptain`。

本方案的完整输入与执行序列是：

```text
Pier/harness (Boss) -- instruction.md, exactly once --> playbook runtime
playbook runtime -- initial prompt --> Modifier
playbook runtime -- patch + instruction --> Reviewer
playbook runtime -- findings --> Modifier
...直到 approved、max_reviews_reached 或结构化失败
```

初次调用 `handleBossInput()` 并产生 `START` 后，workflow 在终态前不再等待 Boss。后续所谓“指令”都是 runtime 依据初始 instruction 和中间 artifacts 构造的内部 Agent prompt，不是新的用户输入。任何进入 `awaitBossReply` 的执行都属于此评测方案的建模错误。注意这无法在 artifact 编译层面禁止：GEARS 编译约定强制给每个 agent-invoking state 附带 `needsBossReply` 结果且无源头开关，实际执行点只能是（a）确定性 Judge 永不选择该 guard，（b）用 `resumableStateIds` 收紧可恢复状态集合，或（c）手写/后编辑 FSM artifact；smoke test 应对“落入 awaitBossReply”直接判失败。

Captain 和 Judge 的 runtime 行为也不同：

- Captain 是一种 agent actor。只有 FSM 中存在 `src: 'captain'` 状态时才会调用 `callCaptain`。
- Judge 是 player 输出到 FSM guard 之间的 adjudication port。当前共享 player bridge 会在每次 `callPlayer` 完成后调用 `callJudge`。

第二阶段的专用 workflow 不定义任何 Captain 状态，因此不会产生 Captain Agent 调用。`callCaptain` 只保留为公共 runtime contract 要求的 fail-fast stub。

当前 playbook 包还不能仅通过重新编写自然语言 workflow 完全跳过 `callJudge` port，但 port 不必由 LLM 实现。第二阶段若不修改上游包，可使用 deterministic Judge：

1. 自定义 artifact 的 `buildJudgePrompt` 把 `stateId`、合法 guards 和 player `finalText` 编码为确定性 JSON envelope。
2. 嵌入式 host 的 `callJudge` 解析 envelope。
3. Modifier 状态机械选择唯一的成功 guard。
4. Reviewer 状态解析严格 JSON 中的 `verdict`，将 `approve` 映射为 `approved`，将 `revise` 映射为 `needsRevision`。
5. Findings 原文通过 verbatim payload 或 JSON 字符串进入 FSM context，不让另一个模型重述。

这能使 playbook backend 仍保持严格的两个 LLM Agent。Judge trace 应标记 `implementation: deterministic`，其 token 和 cost 为“不适用”，而不是伪造为 0 token 的模型调用。

另一个已知语义偏差：playbook runtime 的 player session 策略是固定的——每个 playerId 首次调用 fresh、之后必带存储的 resume token，FSM 层没有 per-call 开关。而本方案要求 Reviewer 每轮 fresh session（见 6.2）。第二阶段需要通过 `resolvePlayerId` 给每轮 review 派生不同的 playerId，或让 host 在 reviewer 调用上忽略 resume token；无论哪种方式，都必须纳入与 direct engine 的等价性测试。另外 playbook 的 fake player 测试设施是各测试文件内的本地函数、包不导出，等价性测试需要照抄该模式自建。

如果希望连 `callJudge` port 和相应 trace 都消失，并让结构化 `PlayerResult` 直接成为 XState actor output，则需要修改 playbook 包的正式 runtime/compiler contract。可能的上游能力包括 `playerOutput.mode: 'structured-json'` 或可配置的 deterministic adjudicator，并需要同步修改 runtime 类型、player bridge、linker/compiler spec 和测试。这是有价值的 dogfooding 改进，但不是首版评测的前置条件。

## 10. Timeout 与成本控制

DeepSWE 单任务 Agent timeout 为 5400 秒（来自各 task.toml 的 `[agent] timeout_sec`，113/113 一致；verifier 独立为 1800 秒）。agent setup 阶段有单独的默认 360 秒超时，不占这一预算。多轮协作很容易耗尽 5400 秒。

首版建议：

- `max_reviews=3`（与 SWE-bench Pro collab runner 的默认值一致，便于跨 benchmark 对比；这是上限而非保证，5400 秒预算内第三轮常常放不下，由 deadline 管理决定是否执行）；
- 整体 deadline 由 runtime 统一管理；
- Modifier 初始实现获得最大预算；
- Reviewer 使用较短预算；
- 修订轮使用剩余预算动态分配；
- 每次 cligent 调用使用 AbortController；
- 不在 timeout 前启动没有足够完成时间的新 review/revision。

一种初始分配参考：

```text
initial modifier          30–40 min
review 1                   8–10 min
revision 1                10–12 min
review 2                   8–10 min
revision 2                10–12 min
review 3 / final revision  使用剩余预算，不足则跳过并提前交付
```

实际分配应在 smoke run 后根据不同语言和仓库大小调整。

## 11. 依赖安装与可复现性

默认从 npm 安装并锁定精确版本（当前 `@sublang/cligent@0.18.0` 与本地 checkout 一致）：

1. 容器内 `npm install @sublang/cligent@<pin>`，npm 自动解析 linux-x64/glibc 平台二进制（任务镜像是 Debian 12，无 musl 问题）。
2. 固定 Codex SDK、Claude Agent SDK 等依赖版本；注意 cligent 的 codex adapter 一旦传 permissions 就需要完整的 `@openai/codex` 包（不只 `codex-sdk`），gemini/kimi 走 PATH 二进制而非 npm 依赖。
3. 每个 trial 记录实际 package version（版本号可映射到 release tag 与 Git SHA）。
4. 修复迭代期（发现 cligent bug、修复尚未发版时）用 override（如 `--ak cligent_tarball=...`）切换到本地 `npm pack` 产物；tarball 必须在联网侧打好（prepack 需要 devDeps 构建）。

第二阶段同样以 npm `@sublang/playbook@<pin>` 为默认（当前 3.1.0 与本地一致），并固定 XState 版本（playbook 锁定 5.x）。首阶段锁文件中不应出现 playbook，以确保评测关键路径没有隐式依赖它。

初期可以在 Agent setup 阶段在线安装依赖（注意 360 秒 setup 超时）。正式批量运行前，改用 `install_spec()` 把安装步骤烘进派生镜像，减少 113 个 trial 重复下载 SDK/CLI 所带来的延迟及失败率。

网络与凭据的实际情况（以 pier 0.3.0 为准）：

- task.toml 里的 `[agent] network_mode = "no-network"` 是 harbor 语义；pier 的 task 模型没有该字段、会静默忽略，真正的开关 `[environment] allow_internet` 默认为 True 且任务未设置。因此 **agent 容器实际有全网**，模型调用和在线安装都不需要网络豁免配置（`--allow-agent-host` 只存在于 harbor，pier 没有这个 flag）。
- 代价是 benchmark 卫生（禁 git fetch 找答案等）只靠 prompt 约束和镜像的 git 手术（已删 origin 与未来 refs），没有网络层强制。如需收紧，pier 的机制是任务环境 `allow_internet=False` + 在 agent 代码中实现 `network_allowlist()`（egress proxy 仅在两者同时满足时启用），这是代码级配置而非 CLI flag。
- API key 通过 Pier 的 `--ae/--agent-env` 注入（支持 `${VAR}` 引用宿主环境变量，job config 序列化时自动脱敏），不写入 prompt、日志和 artifacts。
- 除 API key 外，支持复用宿主机登录态：Codex 走 `CODEX_FORCE_AUTH_JSON=1` / `CODEX_AUTH_JSON_PATH`（与 pier 内置 Codex agent 同机制，上传 `~/.codex/auth.json` 并落到容器 `$CODEX_HOME/auth.json`）；Kimi ACP 要求 `kimi login` 凭据。本文对应的旧原型曾复制整个 Kimi 配置，但统一新基线只通过 `KIMI_AUTH_HOME_PATH` 复制 `credentials/`、`oauth/` 和 `device_id` 登录材料，不复制宿主 `config.toml`，而由版本化 profile 在 trial 内生成最小 provider/OAuth 文件引用/model 注册；Claude 无文件注入路径（macOS 凭据在 Keychain），标准做法是 `claude setup-token` → `CLAUDE_CODE_OAUTH_TOKEN`，具体见 [`claude-code-oauth-token.md`](./claude-code-oauth-token.md)。凭据文件一律放容器 `/tmp`，不进会同步回宿主的 `/logs`。

## 12. Artifacts 与观测性

建议 `/logs/agent/` 结构：

```text
collab/
├── summary.json
├── orchestrator-trace.jsonl
├── cligent-events.jsonl
├── rounds/
│   ├── 00-modify/
│   │   ├── prompt.md
│   │   ├── events.jsonl
│   │   ├── patch.diff
│   │   └── metadata.json
│   ├── 01-review/
│   │   ├── prompt.md
│   │   ├── events.jsonl
│   │   └── review.json
│   └── 02-revise/
└── final/
    ├── patch.diff
    └── git-status.txt
```

`summary.json` 至少记录：

- Modifier、Reviewer 的 adapter、model、effort；
- `engine=direct` 和控制端实现版本；第二阶段增加 `engine=playbook`；
- cligent、coding-agent SDK 版本；仅在第二阶段记录 playbook 版本；
- cligent 安装来源（npm pin 版本，或迭代期 tarball 对应的 checkout SHA）；仅在第二阶段记录 playbook 的同类信息；
- review count 和 workflow outcome；
- Modifier、Reviewer 各自的 input/output tokens、tool uses、duration 和 cost；
- 本地 JSON 解析和 transition 次数、duration，不将其计入模型 token/cost；
- findings 数量及严重级别；
- findings 的 accepted/rebutted/unresolved 状态；
- checkpoint commit hashes；
- final patch hash；
- setup、agent、verifier 错误分类；
- 卫生审计结果（record-only）：扫描日志和 artifacts 是否引用 harness 数据或上游 fix commit（移植 SWE-bench Pro runner 的 audit 思路），三个实验组统一执行。

首版可以直接保存 cligent event stream；后续建议实现 cligent events 到 Harbor ATIF trajectory 的转换，使 Pier viewer、analyze 和 critique 能直接处理协作轨迹。

## 13. Outcome 与失败语义

建议 outcome：

```text
approved
max_reviews_reached
degraded            # 附 degraded_reason: reviewer_failed | invalid_review_output | revision_failed | timeout | infrastructure
modifier_failed
timeout             # 初始实现阶段即超时、无可信 patch
empty_patch
checkpoint_failed
```

其中：

- `approved`、`max_reviews_reached` 和 `degraded` 都正常送入 verifier；`degraded` 在统计中单独分层，绝不与 approved 混合。
- 判定原则：**一旦存在可信 checkpoint，后续 Reviewer/修订/超时故障默认降级交付该 checkpoint**（outcome=degraded 并记录 degraded_reason），而不是丢弃成果、整个 trial 重跑。否则协作组会因纯基础设施抖动损失已有的有效 patch，而 Single 组永远交付工作区现状——这种不对称本身就会污染协作效果统计；降级交付 + 分层统计才能把基础设施噪声和协作质量分开。
- 提供 `strict` 开关恢复 fail-hard 语义（degraded 不交付、trial 失败），供需要“纯净协作路径”的分析口径使用。
- 初始 Modifier 没有产生可信 patch 时（modifier_failed / timeout / empty_patch / checkpoint_failed），trial 失败，标记为基础设施/Agent 错误并允许 Pier job retry。

## 14. 实验设计

建议至少比较：

| 组别 | Modifier | Reviewer | 目标 |
|---|---|---|---|
| Single | A | 无 | 单 Agent 基准 |
| Self-review | A | A | 测量协作流程本身 |
| Cross-review | A | B | 测量异构审查价值 |

如果要声称“协作机制本身带来提升”，Single 必须尽量保持：

- 相同 Modifier model/effort；
- 相同初始 prompt；
- 相同 task；
- 相同 timeout；
- 相同重复次数。

同时报告两种口径：

1. 实际系统效果：允许协作使用额外 token、时间和费用。
2. Matched budget：给 Single 相同的总 token 或 wall-clock 预算，减少“只是多投入算力”的混淆。

主要指标：

- binary reward；
- verifier 分项 pass fraction；
- 同任务 paired delta；
- token、费用和 wall-clock；
- review 轮数；
- Reviewer blocking finding 数量；
- finding 修复率；
- approved、max_reviews_reached 与 degraded 分层通过率；
- setup、Agent、verifier 基础设施错误率；
- patch churn 和每轮新增/删除行数。

冻结配置前先在 12 题 dev 上估算单 trial 成本（token 与 wall-clock）：三组 × 每题 ≥4 次 × 30 题 core 就是 ≥360 个 trial、单个上限 90 分钟双 Agent 调用，总预算需要在扩大规模前确认。

## 15. 任务抽样与推进顺序

仓库已有稳定性和区分度筛选结果（`wip/data/selection/`，清单文件 `05_sample_dev.txt` / `05_sample_confirm.txt`；另有与 03 同集合重排序的 `04_core_ranked`）：

```text
00_all：113 题
└── 01_stable：99 题
    └── 02_broad_discriminative：51 题
        └── 03_core_discriminative：30 题
            ├── 05_sample_dev：12 题
            └── 05_sample_confirm：12 题
```

推荐实验阶段：

1. 现有 3 题 smoke（`wip/smoke_tasks.txt`）：验证 harness、网络、认证、提交和 verifier。
2. `05_sample_dev` 12 题：调整 prompt、轮数、timeout 和失败语义。
3. 冻结配置。
4. `05_sample_confirm` 12 题：确认效果，避免继续针对 dev 调参。
5. `03_core_discriminative` 30 题：获得更稳定的 paired comparison。
6. 最后再考虑完整 113 题。

每种 Agent system 每题建议至少运行 4 次，并将基础设施错误从模型失败中单独统计。

## 16. 实施顺序

### Phase 1：Pier 边界验证

- 实现最小 `BaseAgent`。
- 在 `/app` 创建一次机械 commit。
- 验证 `pre_artifacts.sh` 能提取 patch。
- 验证 separate verifier 能正常评分。

### Phase 2：单 cligent Modifier

- 在容器安装 cligent（npm 锁定版本）。
- 跑单个 Modifier。
- 验证 API 认证、adapter permissions 配置（含 Codex bypass，见 6.4）、event stream、usage 和 timeout。
- 建立 Single baseline 所需产物。

### Phase 3：单轮审查

- 增加 Reviewer 独立拷贝工作区，并验证公开测试在拷贝目录中可运行。
- 实现严格 JSON review 和一次格式重试。
- 实现 revision、基线 untracked 排除和 checkpoint。
- 验证 Reviewer 修改不会污染 `/app`。

### Phase 4：完整 direct workflow

- 增加第二次 review 和最终 revision。
- 实现 deadline、降级交付语义（第 13 节）、summary 和完整 artifacts。
- 增加 direct engine、fake adapter 和工作区隔离测试。

### Phase 5：首阶段实验

- 3 题 smoke。
- 12 题 dev。
- 整理 cligent dogfooding 反馈。
- 冻结配置后运行 confirm/core。

只有在关注的评测任务能够稳定完成、基础设施错误率达到可接受水平后，才进入下一阶段。

### Phase 6：引入 playbook backend

- 保留 `DirectCollaborationEngine` 作为参考实现。
- 编写 DeepSWE 专用自然语言 playbook，编译 GEARS/FSM/runtime artifact。
- 实现 `PlaybookCollaborationEngine`，通过嵌入式六端口 host 将 player call 绑定到相同 cligent 实例。
- 用 fake player 对 direct/playbook backend 做 transition、outcome 和失败语义的等价性测试。
- 在少量已跑通任务上 smoke，并记录运行开销和集成摩擦。

### Phase 7：playbook dogfooding 决策

- 整理 playbook dogfooding 反馈。
- 比较两种 backend 的可靠性、可观测性、代码复杂度和维护成本。
- 只有 playbook backend 达到语义等价且没有显著降低稳定性时，才考虑用于后续正式实验；否则保留为可选实验 backend。

## 17. 预期 dogfooding 反馈点

### cligent

- 容器环境和 headless 权限配置是否足够稳定。
- 不同 adapter 的只读/可执行权限是否具有可比较语义。
- session resume 在多轮长任务中的可靠性。
- event stream 是否足够生成统一协作轨迹。
- usage/cost 是否能跨 adapter 一致汇总。
- SDK/CLI 安装和版本探测是否适合短生命周期 benchmark 容器。
- 是否值得新增结构化输出（JSON schema）能力，避免调用方自行解析最终文本。
- `PermissionPolicy` 未设字段默认 `ask`（headless 下等于拒绝）是否应有更安全的默认值或显式校验。

### playbook

以下反馈在第二阶段收集，不阻塞首阶段评测：

- 专用 benchmark workflow 的编译体验。
- 有限次数循环、deadline 和异常路径的表达能力。
- 现有 `buildJudgePrompt` + deterministic `callJudge` 方案是否足够稳定和自然。
- 是否应新增 structured-output player mode，让合法结构化结果直接驱动 guard 并省略 `callJudge` port。
- headless embedding 下 trace 和 artifact 是否足够完整。
- Player role alias、fresh/resume session 选择是否易于控制。
- 是否方便向 Pier/ATIF 等外部观测系统输出结构化轨迹。

## 18. 结论

推荐先把整个协作系统实现为 Pier 的一个自定义复合 Agent：Pier 是 benchmark harness，手写 deterministic orchestrator 是首阶段控制面，cligent 只执行 Modifier 和 Reviewer 两个 LLM Agent，本地 parser 直接处理 Reviewer JSON，Git checkpoint 是协作系统与 DeepSWE verifier 之间唯一的提交接口。

待关注的评测任务稳定运行后，再以相同 `CollaborationEngine` 接口引入 playbook backend，并以 direct engine 作为语义和稳定性基线。这样能先获得可靠的 DeepSWE 结果和 cligent 使用反馈，再单独判断 playbook 是否真正降低了协作编排成本，而不会让两层 dogfooding 风险互相干扰。
