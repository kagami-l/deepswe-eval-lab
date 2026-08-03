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

## 2. LiteLLM 远程 cost map 获取超时

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
