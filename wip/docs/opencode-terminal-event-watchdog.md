# OpenCode terminal-event watchdog 方案

## 状态与结论

本文只保存修复设计，当前暂不修改 Pier 或 OpenCode adapter。短期内如果目标是评测
`deepseek/deepseek-v4-pro`，优先改用 Pier 内置的 `mini-swe-agent`，运行入口见
`wip/scripts/run_mini_swe_eval.sh`。

已观察到的问题不是普通的“模型响应慢”：OpenCode 已经输出表示任务完成的
`step_finish` 事件，进程却一直不退出，Pier 最终只能在 agent 总超时处将它记为
`AgentTimeoutError`。

证据包括：

- 批量 job `opencode-deepseek-v4-pro-05_sample_dev-20260731-220319` 中，16 个超时
  trial 全部精确运行到 5400 秒；其中 13 个在超时前很久已经输出
  `step_finish(reason="stop")`。
- 这 13 个 trial 从最后一个有效事件到超时平均静默约 65.2 分钟，说明大量时间耗在
  会话收尾而不是模型生成或工具执行。
- 单任务 job `opencode-deepseek-v4-pro-one_task-20260801-121525` 使用 OpenCode
  1.18.10，日志最后一行已经是主 session 的 `step_finish(reason="stop")`；代码已提交、
  工作区干净且 `go test ./...` 通过，但 OpenCode 主进程和 `tee` 仍然存活。
- 日志里没有与超时相对应的 provider error、429 或重试风暴。简单本机调用也能在数秒内
  正常完成。因此已有证据更符合 OpenCode 的进程/会话生命周期 hang，而不是 DeepSeek
  API 普遍响应慢。

相关上游线索：

- [OpenCode issue #17516：`opencode run` 在完成工具调用后不退出](https://github.com/anomalyco/opencode/issues/17516)
- [OpenCode v1.18.10 release](https://github.com/anomalyco/opencode/releases/tag/v1.18.10)

## 两种修复分别解决什么

### 去掉 `tee`，直接重定向

当前 Pier adapter 的核心命令是：

```bash
opencode ... 2>&1 </dev/null | stdbuf -oL tee /logs/agent/opencode.txt
```

可以改为：

```bash
opencode ... </dev/null > /logs/agent/opencode.txt 2>&1
```

它简化了进程拓扑，能解决这一类问题：OpenCode 主进程已经退出，但某个残留子进程仍继承
stdout pipe，导致 `tee` 永远等不到 EOF，shell 也就不返回。

但单任务复现中 OpenCode 主进程本身在 terminal event 后仍存活。直接重定向后 shell 仍然
会等待这个主进程，所以它不是当前问题的完整修复。

### terminal-event watchdog

watchdog 不把“OS 进程退出”作为唯一完成条件，而是同时理解 OpenCode NDJSON 协议。当主
session 明确输出 `step_finish(reason="stop")` 后，watchdog 给 OpenCode 一个短暂的正常退出
窗口；窗口结束后进程仍存活，就清理整个 OpenCode 进程组并把这次运行按语义完成处理。

两种方案并不冲突。推荐最终实现同时使用“直接写日志文件 + terminal-event watchdog”：
前者消除无意义的管道依赖，后者处理 OpenCode 自身不退出。

## 推荐实现架构

不要直接编辑本机 `site-packages/pier/.../opencode.py`。在仓库中新增自定义 Pier agent，继承
内置 `OpenCode`，复用它的安装、网络白名单、配置、trajectory 转换和 token/cost 统计，只
替换 `run()` 的进程执行部分；运行脚本通过 `--agent-import-path` 加载该类。

容器内放置一个很小的 Node runner。选择 Node 是因为 OpenCode 镜像必然已有 Node，避免再
引入 Python/系统工具版本假设。

runner 的职责：

1. 以新的 process group/session 启动 OpenCode。
2. stdin 使用 `/dev/null`，stdout 和 stderr 使用同一个已打开的日志文件描述符，直接写入
   `/logs/agent/opencode.txt`，不创建 `tee` 管道。
3. watchdog 自己轮询新增日志字节，按行解析 JSON；未完成的半行留到下一轮，不把非 JSON
   行视为 terminal event。
4. 第一条 `step_start` 的 `sessionID` 作为主 session ID。只接受该 session 的 terminal
   event，防止子 agent/session 的 `stop` 误杀主任务。
5. 识别到主 session 的 `type=step_finish` 且 `part.reason=stop` 后进入 grace 状态，默认等待
   10 秒。
6. grace 内 OpenCode 自行退出：保留原退出结果，不发送信号。
7. grace 到期仍存活：向整个进程组发送 `SIGTERM`；默认再等 5 秒，仍存活则发送
   `SIGKILL`。
8. watchdog 自己收到 `SIGTERM`/`SIGINT` 时，也先转发给整个子进程组，避免 Pier 中断后留下
   容器内孤儿进程。
9. 另写 `/logs/agent/opencode-watchdog.jsonl`，只记录状态、时间、PID、主 session ID、信号和
   退出码，不记录命令参数、prompt 或环境变量，避免泄露 API key。

## 状态机与退出语义

```text
STARTING
  -> RUNNING
       -> PROCESS_EXITED              # OpenCode 正常自行退出
       -> TERMINAL_GRACE               # 主 session: step_finish(reason=stop)
            -> PROCESS_EXITED          # grace 内正常退出
            -> TERMINATING             # SIGTERM(process group)
                 -> PROCESS_EXITED
                 -> KILLING             # SIGKILL(process group)
                      -> PROCESS_EXITED
```

退出规则建议如下：

- 已看到主 session 的 `stop`，之后因 watchdog 的 TERM/KILL 才退出：runner 返回 0；这是语义
  完成后的生命周期清理，不应再被 Pier 记为 agent timeout。
- OpenCode 在 terminal event 前自行退出：保留它原本的退出码，兼容现有 adapter 行为。
- 日志出现顶层 `error`：不要伪装成成功。可以立即进入较短的清理流程，最终由 adapter
  现有 `_error_messages()` 抛出失败。
- 没有 terminal event 且一直无输出：terminal watchdog 不做判断，继续由 Pier 的总
  `agent_timeout` 兜底。不能仅凭“静默 N 分钟”结束任务，因为编译、测试或其他工具可能
  合法地长时间不输出。

可选的第二阶段增强是 inter-step stall watchdog：看到
`step_finish(reason="tool-calls")` 后，若数分钟内既没有下一条 `step_start`，进程也没有退出，
则标记成单独的 `AgentStalledError`。这个条件比 terminal stop 更有误判风险，不应与第一版
一起默认启用。

## 参数建议

| 参数 | 默认值 | 说明 |
| --- | ---: | --- |
| `terminal_grace_seconds` | 10 | terminal event 后允许 OpenCode 自行收尾的时间 |
| `terminate_grace_seconds` | 5 | SIGTERM 后等待时间 |
| `poll_interval_ms` | 100 | 日志增量读取间隔 |
| `stall_timeout_seconds` | 禁用 | 可选的 inter-step stall 检测 |

这些参数应作为自定义 agent kwargs 暴露，方便在不改代码的情况下调整。Pier 的 5400 秒总
agent timeout 保留为最后一道兜底，不应为了掩盖 hang 而继续调大。

## 测试与上线顺序

实现时至少覆盖以下自动测试：

1. 子进程正常输出 stop 并退出，不发送信号，返回原退出码。
2. 子进程输出 stop 后永久存活，grace 后 TERM，必要时 KILL，runner 返回 0。
3. 子进程创建继承资源的后代进程，确认终止目标是进程组而不是单个 PID。
4. 子 session 先输出 stop，主 session 继续运行，确认不会提前结束。
5. terminal event 被拆成多次文件读取时仍能正确解析。
6. 非 JSON stderr、顶层 error、无 terminal 的非零退出均保持失败语义。
7. watchdog 状态日志不包含 prompt、命令参数或环境变量。

上线顺序：先跑本地 fake-process 测试，再跑一个短 DeepSWE task，然后复跑已经稳定复现 hang
的 `tengo-destructuring-bindings`，最后才恢复批量 job。成功标准不只是“不再超时”，还包括
patch、trajectory、token/cost、verifier 结果与未加 watchdog 时保持兼容。
