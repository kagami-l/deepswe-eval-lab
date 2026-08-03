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
