# cligent Dogfooding 问题记录

本文持续记录 dogfooding `@sublang/cligent` 时发现的跨 Agent 抽象、adapter 兼容性、
事件语义、可观测性和运行稳定性问题，供 cligent 开发和回归验证使用。

每个问题尽量包含可复核证据、上游协议或 SDK 结构、定位结论、建议修复方式和验收标准。
调用方特有的编排、存储或结果处理不作为本文重点。

## 问题索引

| ID | 标题 | 组件 | 严重程度 | 状态 | 首次发现 |
|---|---|---|---|---|---|
| CLI-001 | OpenCode 工具事件丢失参数和结果，并重复计数 | OpenCode adapter | High | Open | 2026-08-03 |
| CLI-002 | Codex 命令执行和 MCP 调用未转换成工具事件 | Codex adapter | High | Open | 2026-08-03 |
| CLI-003 | Kimi 未提供 token usage 时被报告为真实零值 | Kimi adapter / usage schema | Medium | Open | 2026-08-03 |
| CLI-004 | OpenCode auto 权限遗漏 external_directory，导致 headless run 无限等待 | OpenCode adapter / permissions | Critical | Open | 2026-08-04 |
| CLI-005 | OpenCode 工具事件后不再产生 terminal event，adapter 无限等待 SSE | OpenCode adapter / lifecycle | Critical | Open | 2026-08-04 |

## 状态约定

- `Open`：问题已确认，尚未修复。
- `In progress`：已有修复工作。
- `Released`：修复已发布，等待 dogfooding 验收。
- `Verified`：修复版本已通过回归测试和真实运行验收。
- `Won't fix`：确认不在 cligent 的职责范围，已记录替代处理方式。

---

## CLI-001：OpenCode 工具事件丢失参数和结果，并重复计数

### 基本信息

- 组件：`@sublang/cligent` OpenCode adapter
- dogfooding 环境：
  - cligent `0.16.0`
  - OpenCode CLI `1.18.10`
  - `@opencode-ai/sdk` `1.18.10`
- 严重程度：`High`
- 状态：`Open`
- 证据目录：[`CLI-001-opencode-tool-events/`](./CLI-001-opencode-tool-events/)

### 背景

cligent 的 `OpenCodeAdapter` 启动或连接 `opencode serve`，消费 OpenCode SDK/SSE
事件，并将 OpenCode 的 `ToolPart` 生命周期转换成统一的 `tool_use` 和
`tool_result` 事件。

期望的转换边界为：

```text
OpenCode message.part.updated / ToolPart
        ↓
cligent OpenCodeAdapter 解析、关联并去重
        ↓
统一的 tool_use / tool_result 事件流
```

### 现象

真实运行中，OpenCode 可以正常执行工具，但 cligent 输出的统一事件存在以下异常：

1. 253 条 `tool_use` 的 `payload.input` 全部是空对象 `{}`。
2. 正常完成或失败的工具调用没有产生 `tool_result`。
3. 253 条 `tool_use` 只有 56 个唯一 ID，存在 197 条重复事件。
4. 同一个 ID 最多重复 25 次。
5. `done.payload.usage.toolUses` 按状态更新次数而非唯一调用数累计为 253。
6. 重复事件显著放大日志体积，并破坏“调用 → 结果”的可观测语义。

真实事件片段：

```json
{"type":"tool_use","agent":"opencode","payload":{"toolName":"bash","toolUseId":"prt_fc6b1f1cd001ceXiB2H75BOb4P","input":{}}}
{"type":"tool_use","agent":"opencode","payload":{"toolName":"bash","toolUseId":"prt_fc6b1f1cd001ceXiB2H75BOb4P","input":{}}}
```

完整统计和脱敏后的最小样本见：

- [`event-stats.json`](./CLI-001-opencode-tool-events/event-stats.json)
- [`duplicate-tool-use-excerpt.jsonl`](./CLI-001-opencode-tool-events/duplicate-tool-use-excerpt.jsonl)
- [`trajectory-summary.json`](./CLI-001-opencode-tool-events/trajectory-summary.json)

### 定位结论

问题发生在 cligent 的 OpenCode SSE 事件转换逻辑。

OpenCode SDK 的 `ToolPart` 结构为：

```ts
type ToolPart = {
  id: string
  callID: string
  tool: string
  state: ToolState
}

type ToolState =
  | { status: "pending"; input: Record<string, unknown>; raw: string }
  | { status: "running"; input: Record<string, unknown>; time: { start: number } }
  | {
      status: "completed"
      input: Record<string, unknown>
      output: string
      time: { start: number; end: number }
    }
  | {
      status: "error"
      input: Record<string, unknown>
      error: string
      time: { start: number; end: number }
    }
```

cligent `0.16.0` adapter 的行为与该结构不一致：

- 从 `part.input`、`part.arguments`、`part.args` 读取参数，没有读取
  `part.state.input`，因此参数被归一化为空对象。
- 选择工具调用 ID 时优先使用 `part.id`，而 OpenCode 的调用关联字段是
  `part.callID`；`part.id` 是消息 part ID。
- 每收到一次 `message.part.updated` 就生成一条 `tool_use` 并增加
  `accumulatedToolUses`，没有按调用 ID 或状态去重。
- 没有把 `state.status=completed/error` 转换成 `tool_result`。
- 只有 `permission.replied` 且决定为拒绝时才生成 `tool_result`，不能覆盖正常的工具
  生命周期。

由于 `state.input/output/error` 在 adapter 转换时没有进入统一事件，任何只消费 cligent
事件的调用方都无法在下游可靠恢复这些字段。

### 建议处理方式

#### 1. 按 OpenCode ToolPart 结构解析

- 工具名读取 `part.tool`。
- 关联 ID 优先且正常情况下必须使用 `part.callID`。
- 参数读取 `part.state.input`。
- 完成结果读取 `part.state.output`。
- 失败结果读取 `part.state.error`。
- 若存在 `state.time.start/end`，计算并填写 `durationMs`。

如需兼容旧版 OpenCode，可以保留旧字段回退，但 SDK 当前结构应具有最高优先级，并由
类型或 fixture 固定。

#### 2. 建立每次 run 内的工具调用状态表

建议按 `callID` 维护轻量状态：

```ts
type SeenToolCall = {
  toolUseEmitted: boolean
  terminalResultEmitted: boolean
}
```

转换语义建议为：

| OpenCode 状态 | cligent 事件 |
|---|---|
| 首次 `pending` 或 `running` | 生成一次 `tool_use` |
| 后续 `pending` 或 `running` 更新 | 不重复生成 |
| `completed` | 必要时先补 `tool_use`，再生成一次成功 `tool_result` |
| `error` | 必要时先补 `tool_use`，再生成一次失败 `tool_result` |

“必要时先补”用于处理 SSE 订阅较晚、只观察到 terminal 状态的情况，保证统一事件始终
可以配对。

#### 3. 修正工具调用计数

`toolUses` 应按唯一实际调用计数。建议仅在首次记录 `callID` 时加一，而不是在每次
`message.part.updated` 时加一。

#### 4. 保留权限事件的独立语义

`permission_request` 继续表示授权请求。权限拒绝可以生成 `status=denied` 的
`tool_result`，但应与 ToolPart 的 `completed/error` 生命周期使用同一 `callID`
关联，并保证每个调用最多一个 terminal result。

### 建议的回归测试

至少覆盖以下 OpenCode SSE fixtures：

1. `pending → running → completed`：只产生一个 `tool_use` 和一个成功
   `tool_result`。
2. `pending → running → error`：只产生一个 `tool_use` 和一个失败
   `tool_result`。
3. 多次相同 `running` 更新：不重复产生事件或增加计数。
4. 只收到 `completed`：自动补齐可配对的 `tool_use/tool_result`。
5. `state.input` 为对象以及 JSON 字符串兼容场景。
6. `part.id` 与 `part.callID` 不同：统一事件必须使用 `callID`。
7. 权限拒绝后又收到 ToolPart 状态更新：只产生一个 terminal result。
8. 并行工具调用：不同 `callID` 的状态互不干扰。

本次 dogfooding 没有保存转换前的原始 OpenCode SSE。修复时建议用 SDK 类型构造上述 raw
event fixtures，并断言完整的 normalized event 序列。

### 验收标准

- 同一个 `callID` 最多一个 `tool_use` 和一个 terminal `tool_result`。
- `tool_use.input` 与 OpenCode `state.input` 一致。
- completed/error/denied 都产生可关联的 `tool_result`。
- `tool_result.output` 和 `durationMs` 在上游提供时得到保留。
- `done.usage.toolUses` 等于唯一实际工具调用数。
- 重复 `message.part.updated` 不再放大统一事件数量。
- 真实运行中不再出现连续多条相同的空参数 `tool_use`。

### 相关源码

- cligent OpenCode adapter：`packages/cligent/src/adapters/opencode.ts`（以 cligent
  仓库实际路径为准）
- OpenCode SDK ToolPart 类型：`@opencode-ai/sdk/dist/gen/types.gen.d.ts`

---

## CLI-002：Codex 命令执行和 MCP 调用未转换成工具事件

### 基本信息

- 组件：`@sublang/cligent` Codex adapter
- dogfooding 环境：
  - cligent `0.16.0`
  - Codex CLI `0.144.5`
  - `@openai/codex-sdk` `0.144.5`
- 严重程度：`High`
- 状态：`Open`
- 证据目录：[`CLI-002-codex-command-events/`](./CLI-002-codex-command-events/)

### 现象

一次成功完成并通过 verifier 的真实运行只产生了以下 cligent 事件：

```text
init                 1
text                 7
codex:file_change   11
done                 1
tool_use             0
tool_result          0
```

最终 `done.payload.usage.toolUses` 为 0，下游 trajectory 也没有任何 tool call 或
observation。运行期间实际完成了代码修改和命令验证，因此统一事件流无法表达 Codex 的
shell/MCP 工具执行过程。

统计和最小样本见：

- [`event-stats.json`](./CLI-002-codex-command-events/event-stats.json)
- [`representative-events.jsonl`](./CLI-002-codex-command-events/representative-events.jsonl)
- [`trajectory-summary.json`](./CLI-002-codex-command-events/trajectory-summary.json)

### 定位结论

Codex SDK `0.144.5` 的 ThreadItem 使用以下实际类型：

```ts
type CommandExecutionItem = {
  id: string
  type: "command_execution"
  command: string
  aggregated_output: string
  exit_code?: number
  status: "in_progress" | "completed" | "failed"
}

type McpToolCallItem = {
  id: string
  type: "mcp_tool_call"
  server: string
  tool: string
  arguments: unknown
  result?: unknown
  error?: { message: string }
  status: "in_progress" | "completed" | "failed"
}
```

cligent `0.16.0` 的 `parseItemCompleted()` 只把 `tool_call`、`function_call`、
`tool_use` 识别为调用，并把 `tool_result`、`function_call_result`、`tool_output`
识别为结果。它没有处理 SDK 实际输出的 `command_execution` 和 `mcp_tool_call`。

同时，adapter 只重点处理 `item.completed`，没有利用 `item.started` 和 `item.updated`
维护工具生命周期。Codex SDK usage 本身不提供 cligent 的 `toolUses` 字段，adapter 又没有
独立计数，因此最终固定退化为 0。

### 建议处理方式

#### 1. 映射 command_execution 生命周期

按 `item.id` 维护状态：

- 首次 `item.started` 或 `in_progress`：生成一次 `tool_use`。
- `toolName` 使用稳定名称，例如 `shell` 或 `command_execution`。
- `input` 至少保留 `{ "command": item.command }`。
- `completed/failed`：生成一次对应的 `tool_result`。
- result 建议保留 `aggregated_output` 和 `exit_code`，避免丢失退出状态。

#### 2. 映射 mcp_tool_call 生命周期

- `toolUseId` 使用 `item.id`。
- `toolName` 应稳定表达 server/tool，例如 `${server}:${tool}`，或将 server 放入扩展字段。
- `input` 使用 `item.arguments`。
- completed 使用 `item.result`，failed 使用 `item.error`。
- 同一 ID 最多一个 `tool_use` 和一个 terminal `tool_result`。

#### 3. 由 adapter 统计唯一工具调用

维护已见 item ID 集合，在首次生成 `tool_use` 时增加计数，并将该值写入
`done.payload.usage.toolUses`。不能依赖 Codex SDK token usage 提供工具计数。

### 建议的回归测试

1. `command_execution` 的 started → updated → completed 只生成一对事件。
2. command failed 保留非零 exit code 和输出。
3. `mcp_tool_call` completed/failed 分别映射正确结果。
4. 重复的 updated/completed 不重复生成 terminal result。
5. 并行 command/MCP item 按各自 ID 正确关联。
6. `toolUses` 等于唯一 command/MCP 调用数。
7. 现有 `codex:file_change` 事件保持兼容。

本次 dogfooding 没有保存转换前的 Codex SDK raw event stream。修复时应根据 SDK
ThreadItem 类型补齐 fixture，并增加一次真实运行验收。

### 验收标准

- shell 和 MCP 调用均形成可关联的 `tool_use/tool_result`。
- command、arguments、output/error、exit code 不丢失。
- 每个 item ID 最多一个调用事件和一个 terminal result。
- `done.usage.toolUses` 等于唯一工具调用数。
- 成功执行命令的真实运行不再出现 `toolUses=0`。

### 相关源码

- cligent Codex adapter：`packages/cligent/src/adapters/codex.ts`（以 cligent 仓库实际
  路径为准）
- Codex SDK ThreadItem 类型：`@openai/codex-sdk/dist/index.d.ts`

---

## CLI-003：Kimi 未提供 token usage 时被报告为真实零值

### 基本信息

- 组件：`@sublang/cligent` Kimi adapter / `DonePayload.usage`
- dogfooding 环境：
  - cligent `0.16.0`
  - Kimi Code CLI `0.30.0`
  - 模型 `kimi-code/k3`
- 严重程度：`Medium`
- 状态：`Open`
- 证据目录：[`CLI-003-kimi-unknown-token-usage/`](./CLI-003-kimi-unknown-token-usage/)

### 现象

一次真实成功运行具有明确的非零模型活动：

```text
duration                 1,234,525 ms
text_delta               1,003 条 / 4,310 字符
tool_use / tool_result   56 / 56
patch                    22,963 bytes
status                   success
```

但最终事件仍报告：

```json
{"usage":{"inputTokens":0,"outputTokens":0,"toolUses":56}}
```

下游 trajectory 因而把 prompt/completion token 同样记录为 0。对一次包含长 prompt、持续
20 分钟并输出大量文本的成功模型运行，这里的 0 只能表示 usage 不可用，不能解释为真实
零消耗。

### 定位结论

Kimi adapter 的 `mapUsage()` 在 ACP `session/prompt` response 没有 `usage` 时执行：

```ts
if (!usage) return { inputTokens: 0, outputTokens: 0, toolUses }
```

与此同时，`DonePayload.usage.inputTokens/outputTokens` 是必填 `number`，没有表达
`unknown/unavailable` 的能力。这使上游缺失信息被静默改写成了有效数值 0。

本次未保存 raw ACP response，因此不能仅凭运行产物断言 usage 是由 Kimi Code CLI 未提供
还是在更早的协议层丢失；但 cligent 将 missing 映射为 zero 的语义问题是确定的。

### 建议处理方式

优先让统一 usage schema 能表达可用性，例如以下任一方案：

1. `usage` 在上游未提供时省略，并保持 `DonePayload.usage` 可选。
2. token 字段允许 `null`，例如 `inputTokens: number | null`。
3. 保留数值字段但增加明确的 `usageAvailable: false` 或 token 级 provenance；调用方必须
   忽略占位零值。

`toolUses` 是 adapter 根据工具生命周期独立计数得到的真实值，不应因 token usage 缺失而
丢弃。若 schema 必须保持向后兼容，建议至少增加 availability/provenance，再在下一个主
版本移除“missing → zero”的歧义。

### 建议的回归测试

1. ACP prompt response 含完整 usage：准确映射 input/cache/output token。
2. ACP prompt response 不含 usage：输出明确的 unavailable，而不是可解释为真实值的 0。
3. usage 缺失但有工具调用：保留准确 `toolUses`。
4. 成功、失败、取消三种 terminal 状态都保留相同的 usage 可用性语义。
5. 下游汇总不会把 unavailable token 加入真实 token 总量。

### 验收标准

- 调用方可以无歧义地区分 token usage 为 0 与 token usage 不可用。
- Kimi 成功运行不再被统计成“消耗 0 token”。
- `toolUses` 继续等于唯一实际工具调用数。
- schema 变更包含兼容策略和 adapter fixture 回归测试。

### 相关源码

- cligent Kimi adapter：`packages/cligent/src/adapters/kimi.ts`（以 cligent 仓库实际路径为准）
- cligent usage schema：`packages/cligent/src/types.ts`

---

## CLI-004：OpenCode auto 权限遗漏 external_directory，导致 headless run 无限等待

### 基本信息

- 组件：`@sublang/cligent` OpenCode adapter / permission policy mapping
- dogfooding 环境：
  - cligent `0.16.0`
  - OpenCode CLI `1.18.10`
  - `@opencode-ai/sdk` `1.18.10`
- 严重程度：`Critical`
- 状态：`Open`
- 证据目录：[`CLI-004-opencode-auto-permission-hang/`](./CLI-004-opencode-auto-permission-hang/)

### 背景与期望

cligent 文档将 `permissions: { mode: "auto" }` 定义为 OpenCode 的无人值守自动执行
模式，并描述为 SDK 侧等价于全局 `permission: "allow"`。在 headless run 中，这一模式
应覆盖完成正常工具调用所需的权限；即使上游仍意外发出权限请求，adapter 也不能在没有
交互方的情况下无限等待。

OpenCode SDK `1.18.10` 的 `PermissionConfig` 除了 `edit`、`bash`、`webfetch`，还包含：

```text
read, glob, grep, list, task, external_directory, todowrite, question,
websearch, lsp, doom_loop, skill, ...
```

其中，shell 命令读写工作目录之外的路径时可能触发 `external_directory`。真实运行中，
Agent 使用 `/tmp` 保存临时测试文件或测试输出即触发了该权限。

### 现象

同一批任务中的两个并发、相互独立的 OpenCode run 都出现了相同阻塞：

| Trial | 最后事件 | 最后更新时间 | 取证时静默时间 | 进程状态 |
|---|---|---|---:|---|
| `anko-typed-variable-bindings` | `permission_request(external_directory)` | 12:02:26 | 约 24 分钟 | Node/OpenCode server 存活 |
| `skrub-duration-encoding` | `permission_request(external_directory)` | 12:08:31 | 约 18 分钟 | Node/OpenCode server 存活 |

两个事件请求的目录和 pattern 都是 `/tmp`：

```json
{"type":"permission_request","agent":"opencode","payload":{"toolName":"external_directory","input":{"directories":["/tmp"],"patterns":["/tmp/*"]}}}
```

权限请求后没有 `permission.replied`、`tool_result`、后续模型事件或 terminal `done`。
容器、cligent runtime 和 `opencode serve` 均继续存活，所以调用方只能看到 run 长时间保持
running，直至外层 turn/job timeout。

两条投影后的终止事件和取证快照见：

- [`permission-requests.jsonl`](./CLI-004-opencode-auto-permission-hang/permission-requests.jsonl)
- [`run-state.json`](./CLI-004-opencode-auto-permission-hang/run-state.json)
- [`permission-mapping.json`](./CLI-004-opencode-auto-permission-hang/permission-mapping.json)

### 定位结论

cligent `0.16.0` 的 `mapPermissionsToOpenCodeOptions()` 在 `mode === "auto"` 时生成：

```ts
permission: { edit: "allow", bash: "allow", webfetch: "allow" }
```

这不是 OpenCode 的全局 allow，只允许了三个权限名。`external_directory` 未包含其中，
因此 OpenCode 按默认规则发出请求。

OpenCode adapter 观察到 `permission.updated` / `permission.asked` 后只将其转换为统一的
`permission_request` 事件。该路径没有调用 SDK 的 permission reply/respond API；统一
Cligent run 接口也没有提供一个正在等待本次请求的交互回调。因此 OpenCode session 等待
授权，adapter 等待后续 SSE，形成稳定的 headless deadlock。

这是权限映射和无人值守请求处理问题，不是 CLI-001 的工具事件转换问题。CLI-001 会造成
日志与计数失真；CLI-004 会直接阻塞 Agent 执行并消耗完整 timeout。

严重程度定为 `Critical`：该问题不是可观测性降级，而是会稳定阻塞真实 Agent 执行；批量
并发时，每个命中的 trial 都可能占用一个并发槽直到外层 timeout，使整批评测失去进展。

### 建议处理方式

#### 1. 让 OpenCode auto 真正表达全局 allow

根据使用的 OpenCode API 版本传递真正的全局规则，而不是枚举三个工具权限：

- v1 配置优先使用 SDK 支持的全局 `permission: "allow"`；
- v2 `PermissionRuleset` 使用 OpenCode 支持的 wildcard allow rule；
- 若当前 API 不支持 wildcard，则完整覆盖 SDK 声明的权限名，至少包括
  `external_directory`，并用 SDK 类型/fixture 防止新权限默认回退为 ask。

具体 wire shape 应以对应 OpenCode SDK 版本的类型和真实 server 行为验证，避免仅更新注释
或只修 v1/v2 其中一条路径。

#### 2. 为意外权限请求提供确定性终止语义

即使 auto policy 配置正确，headless adapter 也应防御上游新增权限类型：

- `mode=auto` 下收到未预期请求时，使用 SDK reply/respond API 自动批准，并继续保留
  `permission_request` / reply 事件用于审计；或
- 将未覆盖权限立即报告为 terminal adapter error，指出 permission 名和 request ID。

不能只 emit 事件后无限等待。若未来支持 `ask`，应要求调用方显式提供 approval callback；
没有 callback 时必须快速失败或采用文档明确的默认拒绝语义。

#### 3. 保留 abort 和 timeout 可取消性

等待 permission reply 的路径必须响应 `AbortSignal`，关闭 SSE/session/server，并产出可诊断
的 terminal 状态，避免只能依赖更外层的进程超时清理。

### 建议的回归测试

1. OpenCode `mode=auto` 下执行写入 workspace 外临时目录的命令，不产生悬而未决的
   `external_directory` 请求。
2. 分别覆盖 adapter 的 v1 prompt permission 和 v2 session `PermissionRuleset`。
3. OpenCode 新增或返回未知 permission 名时，run 自动处理或快速失败，不无限等待。
4. `permission.asked → reply → tool completed` 形成完整、可关联的事件序列。
5. 明确的 `ask` policy 在无 callback 时快速失败，在有 callback 时按决定回复。
6. permission pending 期间触发 AbortSignal，run 在限定时间内退出并清理 server。
7. 两个并发 session 的 request/reply 使用各自 ID，不相互串扰。

### 验收标准

- `permissions: { mode: "auto" }` 的 OpenCode run 可无人值守访问任务容器内的 `/tmp`。
- auto 模式覆盖 `external_directory`，并与 cligent 文档中的“permission allow”语义一致。
- 任意未处理的权限请求都不会让 run 无限保持 running。
- 权限 request/reply 可观测且与正确 session/request ID 关联。
- 真实并发运行不再停在 `permission_request` 直到外层 timeout。

### 调用方临时缓解

在 cligent 发布正式修复前，dogfooding 调用方可以对 `0.16.0` 使用严格版本限定的 runtime
兼容补丁：为 OpenCode auto policy 和 v2 ruleset 增加 `external_directory=allow`。同时，
OpenCode headless runner 收到任何残留 `permission_request` 时应中止当前 turn 并快速失败，
不能继续等待交互；其他 adapter 保留各自原生的 request/reply 或自动拒绝语义。

该措施只用于恢复评测可运行性，不改变本 issue 的 `Open` 状态，也不能替代 cligent 对
全局 auto 权限语义、未知权限和 request/reply 生命周期的正式修复。升级 cligent 后应先
移除兼容补丁，再按本节验收标准回归。

### 相关源码

- cligent OpenCode adapter：`packages/cligent/src/adapters/opencode.ts`（以 cligent 仓库实际路径为准）
- cligent permission policy：`packages/cligent/src/permissions.ts`
- OpenCode SDK permission 类型：`@opencode-ai/sdk/dist/v2/gen/types.gen.d.ts`

---

## CLI-005：OpenCode 工具事件后不再产生 terminal event，adapter 无限等待 SSE

### 基本信息

- 组件：`@sublang/cligent` OpenCode adapter / session lifecycle
- dogfooding 环境：
  - cligent `0.16.0`
  - OpenCode CLI `1.18.10`
  - `@opencode-ai/sdk` `1.18.10`
- 严重程度：`Critical`
- 状态：`Open`
- 证据目录：[`CLI-005-opencode-session-silence/`](./CLI-005-opencode-session-silence/)

### 背景与期望

OpenCode adapter 在 managed 模式启动 `opencode serve`，订阅 SDK/SSE，并以
`session.idle` 或 `session.status(type=idle)` 作为正常 terminal event。工具执行结束、
session 出错、SSE 中断或 server 异常时，headless run 都应产生 terminal `done/error`，
或在可配置的 inactivity deadline 后返回可诊断错误，不能无限等待下一条 SSE。

### 现象

两个独立 session 均在正常输出模型内容和工具事件后进入永久静默：

| Case | 最后事件 | 唯一工具调用 | 静默时间 | 终止方式 |
|---|---|---:|---:|---|
| `anko-typed-variable-bindings` | `tool_use(edit)` | 60 | 约 77 分钟 | 外层 5100 秒 deadline abort |
| `adaptix-name-mapping-aliases` | `tool_use(bash)` | 2 | 约 48 分钟 | 人工 SIGTERM |

两个 session 均满足：

- 没有 `permission_request`，因此不是 CLI-004；
- 没有 `tool_result`、`error` 或自然产生的 terminal `done`；
- 静默期间只剩调用方 Node 进程和 `opencode serve`，没有仍在执行的 shell/test 子进程；
- OpenCode server 继续存活且 CPU 接近空闲；
- adapter 只能依赖外层 abort 才退出。

其中第一个 case 在 abort 后由 adapter 产生 `done(status=interrupted)`；第二个 case 因整个
Agent 进程组被 SIGTERM，未产生 adapter terminal event。精简时间线和计数见证据目录。

### 定位结论

cligent OpenCode adapter 在取得 event stream 后循环等待 `iterator.next()`。当前只有以下路径
可以结束 run：

1. 收到 `session.idle` / idle `session.status`；
2. stream 结束或抛错；
3. managed server 退出；
4. 调用方触发 `AbortSignal`。

当 SSE 连接保持打开、server 仍存活、但 session 不再产生事件时，adapter 没有 inactivity
deadline，也不会主动查询 session 状态，因此会永久等待。现有统一事件又受 CLI-001 影响，
缺少 tool input/result 和 raw SSE，暂时无法进一步区分以下底层原因：

- OpenCode session 没有从 tool phase 推进到 idle；
- provider 后续请求挂起；
- SDK/SSE 漏掉 terminal event；
- terminal event 被 session 关联逻辑过滤。

严重程度定为 `Critical`：每个命中的 headless run 都会占用并发槽直到最外层 timeout，且
调用方无法通过现有统一事件判断 session 是否仍有有效工作。

### 建议处理方式

1. adapter 提供可配置的 event inactivity timeout；每个有效事件重置计时。
2. timeout 前记录最后 raw event 类型、session ID、server/process 状态和当前 session 状态。
3. timeout 时优先调用 OpenCode session status API：
   - session 已 idle：补发/合成 terminal done，并报告缺失的 idle event；
   - session busy 但无活动：abort session 并返回明确的 inactivity error；
   - 查询失败：关闭 SSE/server 并返回 adapter error。
4. 修复 CLI-001，完整记录去重后的 tool use/result，使调用方能够区分工具仍在执行与
   session lifecycle 卡住。
5. 保证 inactivity abort 可取消 `iterator.next()`、关闭 SSE 和 managed server，且不会留下
   orphan process。

### 建议的回归测试

1. 模拟工具事件后永不结束的 SSE，adapter 在 inactivity deadline 内退出。
2. timeout 诊断包含最后事件、session ID 和 server 状态。
3. 正常的长工具调用持续产生 heartbeat/progress 时不会误终止。
4. session 已 idle 但 idle event 丢失时能够恢复或返回明确协议错误。
5. inactivity abort 后 SSE、server 和工具子进程全部清理。
6. inactivity timeout 与调用方总 timeout 竞争时只产生一次 terminal event。

### 调用方临时缓解

在 cligent 发布正式修复前，调用方可在统一事件流外增加 watchdog：连续 600 秒没有任何
Agent event 时，先保存进程、Git working tree 和最后事件快照，再触发 `AbortSignal`。该措施
能限制并发槽损失并保留诊断材料，但不能确定或修复 OpenCode 内部 session 停滞的根因，
因此本 issue 保持 `Open`。
