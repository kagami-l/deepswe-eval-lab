# DeepSWE 评测低优先级问题与踩坑记录

## 文档目的

本文记录使用 DeepSWE 评测集过程中遇到的各种小问题、环境差异、工具行为和容易踩到的坑，
不限于 OpenCode、Pier、某个 agent、某个模型或某一种运行方式。

这里收录的问题通常具有以下一个或多个特点：偶发、影响范围有限、有明确绕过方式、只影响
少量 trial、修复 ROI 暂时不高，或者尚不足以证明需要引入新的系统复杂度。记录的目的不是
为每个问题立即安排实现，而是保存现场证据、判断边界和处置经验，避免以后重复排查。

以下严重或系统性问题不应作为低优先级条目留在本文：

- 高频发生、严重阻塞批量评测或会系统性污染评测结果的问题；
- 无法通过局部绕过恢复，必须优先修复的问题；
- 涉及凭证泄露、错误 verifier 结果或数据破坏的问题；
- 已确认需要实施、已经进入实现阶段或已有独立设计文档的问题。

这类问题应单独记录并直接实施改进。例如 terminal event 后不退出的问题已有正式方案，见
`wip/docs/opencode-terminal-event-watchdog.md`。

## 1. OpenCode 初始化阶段偶发 hang

### 状态

- 优先级：低
- 当前决策：记录并人工处理，暂不实现 startup watchdog
- 影响范围：单个 trial；会临时占用一个并发槽
- 恢复方式：只终止对应 trial 的 OpenCode process group，释放槽位；后续 attempt 或补跑
  通常可以正常执行

### 观察记录

Job：`opencode-deepseek-v4-pro-05_sample_confirm-20260802-132803`

Trial：`kombu-single-active-consumer-pri__TZ2doEn`

异常时间线：

```text
13:28:20 watchdog 启动 OpenCode
13:28:22 OpenCode 创建 session
13:28:23 开始 title 小模型 stream
13:28:24 project copy refresh started
13:28:24 之后日志、数据库和事件文件不再更新
13:57:39 人工向 OpenCode process group 49 发送 SIGTERM
```

现场特征：

- `opencode.txt` 始终为 0 bytes；
- 尚未产生第一条 `step_start`，watchdog 没有主 session ID；
- 工作区没有修改；
- 没有 permission `ask`、provider error、429 或 retry 记录；
- OpenCode 主进程处于 `futex_wait_queue`，没有 git、测试或其他工具子进程；
- 最后的内部日志同时包含 title LLM stream 启动和 project snapshot refresh 启动，但两者都
  没有明确的完成记录。

同一 kombu 任务在之前 job
`opencode-deepseek-v4-pro-05_sample_confirm-20260802-130033` 中可以正常进入主 session、执行
subagent、修改代码并结束，说明它不是由任务内容稳定触发的确定性故障。

### 当前判断

这是 OpenCode 初始化阶段的偶发 hang，可能原因包括：

1. 单次 title API stream 永久 pending；
2. project snapshot refresh 内部等待或死锁；
3. 两个初始化异步任务之间的协调没有完成。

现有证据不足以唯一归因于网络。同期另一个 trial 的 DeepSeek 请求持续成功，因此不是全局
网络或 provider 故障；但单条连接偶发卡住仍不能排除。snapshot refresh 同时没有完成，使
OpenCode 内部初始化问题比“单纯 API 慢”更符合现象。

### 人工处置

先确认目标容器、OpenCode PID 和 PGID，再只终止目标进程组。不要停止整个 job，也不要操作
其他 trial 容器。

终止后的语义：

- 没有 terminal event，因此 watchdog 保留失败语义；
- Pier 将该 trial 记为 agent command failure；
- 当前 job 若配置 `max_retries=0`，不会原地自动重试；
- `-k 2` 等多 attempt 配置下，另一 attempt 仍会按队列执行；
- job 完成后也可用 `pier job resume --filter-error-type ...` 补跑失败项。

### 暂缓实现的方案

可增加 startup watchdog：OpenCode 启动后一定时间仍没有首条 `step_start`，则清理进程组并
返回专门的 `startup_stall` 失败。建议候选阈值为 180～300 秒，并配合一次自动 retry。

当前暂缓原因：

- 目前只有单次明确复现；
- 同任务重跑可以成功；
- 单 trial 可以安全终止，不影响其他并发任务；
- 新增 terminal 前超时语义、错误分类和 retry 策略会增加 runner/Pier 集成复杂度；
- 在发生率未知时，立即实现和维护的收益有限。

### 重新评估触发条件

满足任一条件时，应把 startup watchdog 提升为正式需求：

- 在多个 job 或多个任务上重复出现；
- 发生率达到足以明显降低并发利用率的程度；
- 经常需要人工值守和定向结束 trial；
- 单次 hang 的 API 成本、机器时间或总 job 延迟不可接受；
- 能从上游 OpenCode 日志或 issue 获得更确定的故障判据。

后续每次复现建议追加：job、trial、OpenCode 版本、模型、最后事件时间、最后内部日志、进程
等待状态、是否有工作区修改，以及重跑是否成功。

## 2. OpenCode 主会话中途长时间无事件，最终触发 agent timeout

### 状态

- 优先级：暂定低，待下一批次复现率确认
- 当前决策：保留 Pier 总超时，异常 trial 补跑；暂不默认启用 inter-step stall watchdog
- 影响范围：单个 trial 会占用并发槽直到 5400 秒上限；同一 job 中多次发生时会明显延长总
  运行时间并污染补跑前的聚合分数
- 恢复方式：job 结束后按 `AgentTimeoutError` resume；若发生率继续偏高，则升级为独立设计和
  实现任务

### 观察记录

Job：`opencode-deepseek-v4-flash-05_sample_dev-20260803-205511`

环境：OpenCode 1.18.10、`deepseek/deepseek-v4-flash`、shared runtime、并发数 2。

该 job 共 22 个 trial，最终有 6 个 `AgentTimeoutError`，均由 Pier 在约 5400 秒硬上限正确
终止。根据超时前的事件活跃度，可分为两类：

| Trial | 超时前无事件时间 | 判断 |
| --- | ---: | --- |
| `adaptix-name-mapping-aliases__nT5DFzS` | 22 秒 | 持续工作到上限，属于真实任务超时 |
| `obsidian-linter-scoped-ignore-ma__VF6tjh6` | 64 分 34 秒 | 主会话停滞 |
| `bandit-incremental-cache-control__knK8Bp9` | 82 分 56 秒 | 主会话停滞 |
| `pebble-durability-wait-apis__Rynywqb` | 71 分 43 秒 | 主会话停滞 |
| `scriggo-method-declarations__BnLVBMr` | 50 分 17 秒 | 主会话停滞 |
| `mnamer-daemon-watch-lifecycle__DfeZKNv` | 78 分 55 秒 | 主会话停滞 |

五个停滞 trial 的共同特征：

- 都已经产生 `step_start` 并被 watchdog 识别为主 session，不是初始化阶段 hang；
- 都没有 `step_finish(reason="stop")`，不是 terminal event 后的退出 hang；
- 日志中没有 401、429、provider error 或其他顶层 `error` 事件；
- obsidian、bandit、scriggo、mnamer 均停在已完成的工具调用和
  `step_finish(reason="tool-calls")` 之后；
- pebble 停在一轮 reasoning 中间；
- 最终都由 Pier 总 agent timeout 回收，verifier 随后仍能运行，但评测的是未完成修改，不能
  把对应零分当成正常模型结果。

这与 terminal-event watchdog 处理的问题不同。terminal watchdog 只在主 session 已明确输出
`stop` 后清理残留进程；本问题没有语义完成信号，因此 watchdog 按设计不介入。

### 当前判断

更可能的机制是单次 LLM 请求或流式响应长期 pending，或 OpenCode 内部一直等待 provider
stream/session 状态且没有有效 read timeout：

- 四个 trial 在完整 `step_finish` 后再无事件，符合下一轮请求一直没有首个响应的表现；
- pebble 在 reasoning 流中停止，符合响应流中途不再返回数据的表现；
- 停滞发生时 peak context 从约 100k 到 320k 不等，不能仅归因于上下文过大；
- 同期其他 trial 可以继续调用相同 provider，因此不像全局网络或认证故障，但不能排除单条
  HTTP/stream 连接偶发失活。

目前没有 OpenCode 内部 provider trace，无法在“上游连接未返回”和“OpenCode 内部 session
等待”之间唯一归因，不应把网络问题写成已确认根因。

adaptix 不符合上述停滞特征：它完成 201 steps，超时前 22 秒仍开始新 step，属于固定 90 分钟
预算下的有效超时。它不应仅因为异常类型相同就被解释成会话 hang。

### 人工处置

当前 Pier 只能按异常类型过滤，以下命令会重跑全部 6 个 timeout，包括真实超时的 adaptix：

```bash
set -a
source wip/scripts/.env
set +a

pier job resume \
  --job-path jobs/opencode-deepseek-v4-flash-05_sample_dev-20260803-205511 \
  --filter-error-type AgentTimeoutError
```

resume 会删除并替换匹配 trial 目录；需要保留诊断现场时应提前备份。为保持简单且一致，可以
整类补跑，但统计时要意识到这会给真实超时 attempt 一次额外机会。正常完成但测试未通过的
trial 不应补跑。

### 暂缓实现的方案

候选增强是 inter-step stall watchdog，与现有 terminal watchdog 并列：

1. 主 session 建立后记录最后事件时间和事件类型；
2. `step_finish(reason="tool-calls")` 后 5 分钟无事件，只记录 `stall_suspected`；
3. 10～15 分钟仍无事件，且 OpenCode 进程组内没有正在运行的工具子进程，记录
   `stall_confirmed` 并结束进程组；
4. 对 reasoning/`step_start` 后的静默使用更保守的 15～20 分钟阈值；
5. 使用独立的 `AgentStalledError`，与真实 `AgentTimeoutError` 分开统计，并只对前者自动 retry
   一次；
6. Pier 的 5400 秒总超时继续保留为最后兜底。

不能只按日志文件 N 分钟不更新就终止，因为编译、测试、下载等工具可能合法地长时间没有
OpenCode JSON 事件。进程组内是否存在工具子进程是降低误杀的重要辅助条件；CPU 使用率本身
不能证明模型仍有有效进展。

当前暂缓原因是尚只有一个批次的集中观察，且补跑可以恢复，还需要确认复现率和阈值误判率。
但本轮 5/22 的停滞比例以及约 10 小时总运行时间已经接近不应继续视为低优先级的边界。

### 重新评估触发条件

满足任一条件时，应将本条移出低优先级文档，建立独立设计并实现 stall watchdog：

- 后续 OpenCode 批次再次出现多个超过 15 分钟无事件的主 session；
- 停滞率达到 5% 或以上，明显降低并发利用率；
- 经常需要统一 resume timeout，导致真实超时和基础设施停滞无法区分；
- 能从 OpenCode/provider 日志获得稳定的 request/stream pending 判据；
- 上游仍没有单请求 read timeout，而人工值守成本持续增加。

后续复现建议记录：最后事件类型、最后工具是否完成、静默时长、主 session ID、进程组内工具
子进程、peak context、provider error、重跑结果，以及相同任务在其他 attempt 是否成功。

## 3. LiteLLM 远程 cost map 获取超时

### 状态

- 优先级：低
- 当前决策：忽略，无需干预

Pier 启动时偶尔出现：

```text
LiteLLM: Failed to fetch remote model cost map ... timed out.
Falling back to local backup.
```

该警告发生在宿主 Pier/LiteLLM 的模型价格元数据加载阶段，不是任务容器内的模型请求失败。
已有日志确认它会回退到本地 backup，且不阻止 shared runtime、OpenCode agent 或 verifier
运行。只有在 token/cost 统计明显错误或启动阶段因此失败时才需要进一步处理。

## 维护约定

新增条目时至少包含：状态、影响范围、复现证据、当前判断、人工处置、暂缓原因和重新评估
触发条件。条目标题应标明相关组件或阶段，例如 agent、模型 API、Pier、Docker、任务镜像、
verifier 或数据集本身。不要把推测写成已确认根因；无法区分的机制应并列记录。

如果后续证据表明某个条目已经成为严重阻塞或系统性问题，应将其移出本文，建立独立设计或
问题记录，并优先实施修复；本文只保留简短链接和历史背景。
