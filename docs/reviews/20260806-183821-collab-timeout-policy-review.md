# Collab Timeout 策略实现 Review

- 评审时间：2026-08-06 18:38:21（Asia/Shanghai）
- 评审范围：`eval-lab` 分支上的 staged changes（基线 `d74e61f`，尚未提交）
- 主题：collab turn 超时改为共享整体软 deadline，新增 `total_deadline` /
  `stage_timeout` / `event_silence` 三类超时分类

涉及文件（16 个，+663/−81）：

- `docs/collab-timeout-policy.md`（新增）、`docs/collab-agent-design.md`、
  `docs/unified-agent-evaluation-design.md`
- `wip/agent_eval/`：`cli.py`、`models.py`、`planning.py` 及对应测试
- `wip/agents/deep_swe_agent/runtime/src/`：`agent-runner.ts`、
  `direct-engine.ts`、`single-engine.ts`、`collaboration-engine.ts`、
  `main.ts` 及对应测试

## 结论

方向正确，文档、代码、测试三者对齐良好，可以提交。

有 1 个真实缺陷（P2，仅影响诊断可读性）和 1 个观测性缺口（P3），另有 3 个可选小项。
不阻塞合入，但建议在批量评测前修掉 Finding 1，否则真实 adapter 下落盘的
`error` 字段会误导超时排查——而这正是本次改动想解决的场景。

## Findings

### [P2] 墙钟超时写入的 `errorMessage` 会被 abort 之后到达的 adapter 事件覆盖

位置：

- `wip/agents/deep_swe_agent/runtime/src/agent-runner.ts:279`
- `wip/agents/deep_swe_agent/runtime/src/agent-runner.ts:416`

timer 触发时同步写入：

```ts
errorMessage = `Turn exceeded its ${request.wallClockTimeoutKind} budget`;
beginAbortCleanup();
```

但 `controller.abort()` 之后 for-await 循环并不 `break`，仍会继续消费 generator
剩余事件，而 `error` 分支是无条件赋值：

```ts
} else if (type === 'error') {
  errorMessage = payload?.message ?? 'unknown adapter error';
}
```

catch 里新加的 `if (errorMessage === null)` 守卫只保护了抛异常路径，没有保护事件
路径。codex/claude 在收到 abort signal 后通常先发一个 `error` 再发 `done`，因此
真实运行中 round metadata 的 `error` 会变成 "aborted" 之类，而不是超时原因。

新增测试 `wall-clock timeout classification does not depend on adapter done
status` 用的 fake 只 yield `done`，覆盖不到这条路径。

影响有限：`timeoutKind` 现在是权威分类，`timedOut`/`ok` 都不依赖 `errorMessage`。
所以定为 P2。

建议：给 `error` 分支加守卫（例如仅在 `timeoutKind === null` 时覆盖），或单独保存
一个 `abortMessage` 在返回时优先使用；同时补一个"abort 后 adapter 先发 error 再发
done"的测试。

对照：event-silence 路径没有这个问题，因为它的 `errorMessage` 是在诊断采集完成后
才写入的（`agent-runner.ts:323`），时间上晚于 adapter 的收尾事件。

### [P3] single-engine 的 min-turn 跳过路径没有任何记录

位置：

- `wip/agents/deep_swe_agent/runtime/src/single-engine.ts:110`
- `wip/agents/deep_swe_agent/runtime/src/single-engine.ts:175`

direct-engine 这次专门补齐了两处观测点：`modifier_turn_skipped` /
`review_turn_skipped` trace（`direct-engine.ts:200`、`direct-engine.ts:307`）和
metadata 顶层 `timeoutKind`（`direct-engine.ts:276`、`direct-engine.ts:405`）。

single-engine 对应位置只有一句裸 `break`：

```ts
if (this.remainingSec() < this.config.minTurnSec) {
  failure = 'timeout';
  break;
}
```

既没有 trace 也没有 attempt 条目，`metadata.json` 也只写 `{ role, attempts }`，
没有顶层 `timeoutKind`。策略文档要求 timeoutKind 保留在 "round metadata" 中，
single 这边只做了一半（attempt 级有，round 级没有）。

建议：与 direct-engine 对齐，补 `modifier_turn_skipped` trace 和 metadata 顶层
`timeoutKind`。

## 可选小项

| 项 | 位置 | 说明 |
| --- | --- | --- |
| phase cap 无上界校验 | `wip/agent_eval/planning.py:112`、`wip/agents/deep_swe_agent/runtime/src/main.ts:180` | `--reviewer-timeout-seconds 100000` 能通过校验，之后被 `min(stage, remaining)` 静默截断并重新分类成 `total_deadline`。既然这两个选项定位是"有意控制成本"，加一条不超过 `soft_deadline_seconds` 的检查可以挡住手滑多打一个零 |
| 死分支 | `wip/agents/deep_swe_agent/runtime/src/agent-runner.ts:230` | `beginAbortCleanup` 里的 `abortReason === null` 不可达——三个调用点都先 `claimAbort` 成功才会进来 |
| cleanup reason 字符串变更 | `wip/agents/deep_swe_agent/runtime/src/agent-runner.ts:241` | `turn_timeout` → `total_deadline`/`stage_timeout`，`event_silence_timeout` → `event_silence`。已 grep 确认无消费方依赖旧值，仅历史 job 产物里的字符串对不上；策略文档已声明不迁移，可接受 |

## 正面结论

- **文档分层清晰**：新增 `docs/collab-timeout-policy.md` 明确区分"确认后的默认
  行为"与"容量规划参考"；`collab-agent-design.md` 里那段容易被误读成硬阶段配额的
  分配表也相应改写为"只作为容量规划参考"。
- **超时分类逻辑正确**：`direct-engine.ts:153-167` 的 `turnTimeout()` 只在 stage
  cap 真正是紧约束（`stageTimeoutSec <= remainingSec`）时才标记 `stage_timeout`，
  边界情况（cap 恰好等于剩余）归入 `stage_timeout` 也说得通。
- **abort 裁决点收敛**：`agent-runner.ts:222-227` 的 `claimAbort` 用单一裁决点取代
  原来 `timerFired` / `inactivityTriggered` 两个独立布尔量，并去掉了
  `timerFired && status === 'interrupted'` 这种依赖 adapter 终态的判断。
  `ok: status === 'success' && abortReason === null` 是本次最有价值的修正，
  两个新增测试（adapter 报 `error` / adapter 报 `success`）覆盖到位。
- **Python 与 runtime 对称**：`float | None` 贯通，`to_dict()` 省略 None 键，
  single 拒绝 collab-only 选项——planning.py 与 main.ts 两侧都有校验且错误信息一致。
- **legacy 未误伤**：`wip/agents/deep_swe_collab/`（旧默认值 2400/600/900）未改动，
  符合策略文档的非目标声明。

## 验证结果

| 检查项 | 结果 |
| --- | --- |
| runtime `npm test`（含 `tsc` 构建） | 52/52 通过 |
| `agent_eval` unittest | 32/32 通过 |
| TypeScript 类型检查 | 通过（无未使用导入，`positiveNumber` 仍被 3 处使用） |
| 全仓 grep `modifierTimeoutSec` 残留 | 仅 legacy `deep_swe_collab` 命中，符合预期 |
| 真实任务 collab 长时 review 验证 | 未执行 |

策略文档的验收标准中，以下几条仅由单元测试覆盖，尚未在真实任务上验证：

- 默认 review 能超过原 600 秒上限继续运行；
- 默认 revision 能超过原 900 秒上限继续运行；
- adapter 在 abort 后报 `done.status = "error"` 时分类仍准确（有 fake 覆盖，
  未经真实 adapter 验证）。

## 建议实施顺序

1. 修复 Finding 1（`error` 分支覆盖超时消息），并补 abort 后 error 事件的测试。
2. 补齐 single-engine 的 skip trace 与 metadata 顶层 `timeoutKind`。
3.（可选）phase cap 上界校验、清理死分支。
4. 批量评测前，用一个真实任务验证默认 review/revision 确实能跑满剩余预算，
   且 event-silence 看门狗仍在 600 秒生效。

## 处理情况（2026-08-06）

- Finding 1 已处理：本地 abort 确定后，adapter 随后的 `error` 事件不再覆盖
  runtime 生成的 timeout 消息；回归测试覆盖了 abort 后依次收到 `error` 和 `done`
  的场景。
- Finding 2 已处理：single-engine 的 min-turn 跳过会写入
  `modifier_turn_skipped` trace，并在 round metadata 顶层记录
  `timeoutKind = "total_deadline"`；新增了对应测试。
- runtime `npm test` 更新为 53/53 通过。可选小项保持原样，真实长时 smoke
  仍留待批量评测前执行。
