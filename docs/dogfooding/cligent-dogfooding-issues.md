# cligent Dogfooding 问题记录

本文持续记录 dogfooding `@sublang/cligent` 时发现的跨 Agent 抽象、adapter 兼容性、
事件语义、可观测性和运行稳定性问题，供 cligent 开发和回归验证使用。

每个问题尽量包含可复核证据、上游协议或 SDK 结构、定位结论、建议修复方式和验收标准。
调用方特有的编排、存储或结果处理不作为本文重点。

## 问题索引

| ID | 标题 | 组件 | 严重程度 | 状态 | 首次发现 |
|---|---|---|---|---|---|
| CLI-001 | OpenCode 工具事件丢失参数和结果，并重复计数 | OpenCode adapter | High | Open | 2026-08-03 |

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

