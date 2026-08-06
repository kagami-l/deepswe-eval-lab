# unified-collab-05_sample_confirm-12-tasks-20260804-200817 结果分析

分析日期：2026-08-05。

原始工件：

- [job result](../../../jobs/unified-collab-05_sample_confirm-12-tasks-20260804-200817/result.json)
- [job config](../../../jobs/unified-collab-05_sample_confirm-12-tasks-20260804-200817/config.json)
- [run manifest](../../../jobs/.agent-eval-manifests/unified-collab-05_sample_confirm-12-tasks-20260804-200817.json)

## 结论

本次 job 完成了 `05_sample_confirm.txt` 中 12 个任务的两次独立 trial，共 24 个 trial。11 个 trial reward 为 1，12 个 reward 为 0，另有 1 个 Prometheus trial 因 Agent/watchdog 异常以及后续 verifier 网络错误而没有 verifier 结果。

- Pier 原始 aggregate reward：`11 / 24 = 45.83%`。
- 排除唯一无 verifier 结果的基础设施异常 trial：`11 / 23 = 47.83%`。
- 12 个任务中有 9 个至少一次通过，手工计算 task-level pass@2：`9 / 12 = 75.00%`。
- 两次均未通过的任务是 `anko-default-function-arguments`、`textual-richlog-follow-state` 和 `go-critic-doc-link-checker`。
- 24 个 trial 共启动/完成 modify `24/21` 轮、review `45/39` 轮、revision `33/29` 轮；这里的轮数不把同一轮内的 `a1/a2` 重试重复计数。

Pier 的 eval 条目记录 `n_trials=23`，但 metrics 中的 `reward=0.458333...` 等于 `11/24`，表明无 verifier 的 Prometheus trial 仍实际进入了 reward 分母。正式比较时不应只引用这个聚合值，应同时报告基础设施异常及有效分母。按 [DeepSWE 计分口径核查](../deepswe-pass-rate-and-leaderboard-scoring.md)，provider、verifier、network 类错误应排除，而 Agent timeout 应作为计分失败。

## 运行配置

| 项目 | 值 |
|---|---|
| 开始时间 | 2026-08-04 20:08:25 CST |
| 结束时间 | 2026-08-05 10:03:23 CST |
| 总 wall-clock | 约 13 小时 55 分钟 |
| Pier | `0.3.0` |
| 任务数 | 12 |
| 每任务 trials | 2 |
| 总 trials | 24 |
| 并发 | 2 |
| Workflow | `collab / review-loop / direct` |
| Modifier | OpenCode, `deepseek/deepseek-v4-flash`, effort `high` |
| Reviewer | Codex, `gpt-5.6-luna`, effort `xhigh` |
| Runtime | `deep-swe/agent-runtime:e87ec83987608685` |
| Runtime digest | `e87ec839876086859f99ca3ad2d81f72c39f40121e013a715244a93f7a37133e` |
| Task hard timeout | 5400 秒 |
| Workflow soft deadline | 5100 秒 |
| Event-silence watchdog | 600 秒 |
| 每个 turn 内 Agent 尝试 | 最多 2 次 |
| Review 上限 | 3 轮 |
| Git commit | `97db4d96f1f4f9ab6c1c6dc06b7bf9dbb1648cb6`，dirty worktree |

Run manifest 记录的 token/cost 汇总为 84,758,953 input tokens、1,701,535 output tokens、`$2.5724320496`。由于 OpenCode/Codex 事件转换和 usage 记录仍有已知缺失或重复问题，这组数值只适合作诊断参考，不应直接用于正式成本比较。

## Task 级结果

下表的“通过”只依据 verifier reward，不依据 review-loop 的 `approved`、`degraded` 或 `max_reviews_reached` outcome。

| Task | Trial 1 | Trial 2 | pass@2 |
|---|---|---|---:|
| `arcane-drift-detection-baselines` | `ZSavgNL`: 0 | `Lv3VNFm`: 1 | 1 |
| `tengo-callable-instance-isolation` | `KWcfETr`: 0 | `jnWHYJW`: 1 | 1 |
| `mobly-grouped-test-barriers` | `HPG7hyj`: 1 | `VMXYg93`: 1 | 1 |
| `fastapi-deprecation-response-headers` | `hJCjTdp`: 1 | `wTj24wc`: 0 | 1 |
| `anko-default-function-arguments` | `XSViwH5`: 0 | `SvgJuDM`: 0 | 0 |
| `prometheus-typed-label-sorting` | `tUjP82r`: 无 verifier | `kM7gVSE`: 1 | 1 |
| `kombu-single-active-consumer-priority` | `UK5tiWd`: 1 | `8jetM78`: 0 | 1 |
| `textual-richlog-follow-state` | `TYuW6wM`: 异常、0 | `TaRaiuc`: 0 | 0 |
| `tomlkit-toml-table-converters` | `b8DBQ5j`: 异常、0 | `Kz4G7NU`: 1 | 1 |
| `cliffy-config-file-parsing` | `kVWVMGR`: 1 | `Yjd9BFS`: 1 | 1 |
| `go-critic-doc-link-checker` | `i8JM6tz`: 0 | `yqCiTFe`: 0 | 0 |
| `clack-async-autocomplete-options` | `AmR2FGf`: 0 | `uDLDjVf`: 1 | 1 |

共有 11 个通过 trial、12 个有效失败 trial、1 个无评分 trial。两个 Mobly 和两个 Cliffy trial 均通过；其余通过任务各有一次通过。

## Modify、Review 与 Revision 轮数

下表按 `启动轮数/完成轮数` 统计工作流阶段：

- “启动”依据 `agent/system/rounds` 中的阶段目录；同一阶段内的 `a1/a2` 是 Agent attempt 重试，不另算新一轮。
- Modify 只指初始实现阶段；Revision 同时包含普通 `revise` 和达到 review 上限后的 `final-revision`。
- “完成”依据 runtime summary：初始 modify 成功并产生 checkpoint、review 成功解析并被编排接受、revision turn 成功结束；无改动的成功 revision 也计入完成，但不会新增 checkpoint。因 timeout、进程失败或无有效 review 输出而中止的已启动轮只计入启动数。

| Task | Trial | Reward | Outcome | Modify | Review | Revision |
|---|---|---:|---|---:|---:|---:|
| `arcane-drift-detection-baselines` | `ZSavgNL` | 0 | `degraded` | 1/1 | 2/2 | 2/1 |
| `arcane-drift-detection-baselines` | `Lv3VNFm` | 1 | `degraded` | 1/1 | 1/1 | 1/0 |
| `tengo-callable-instance-isolation` | `KWcfETr` | 0 | `approved` | 1/1 | 3/3 | 2/2 |
| `tengo-callable-instance-isolation` | `jnWHYJW` | 1 | `max_reviews_reached` | 1/1 | 3/3 | 3/3 |
| `mobly-grouped-test-barriers` | `HPG7hyj` | 1 | `max_reviews_reached` | 1/1 | 3/3 | 3/3 |
| `mobly-grouped-test-barriers` | `VMXYg93` | 1 | `max_reviews_reached` | 1/1 | 3/3 | 3/3 |
| `fastapi-deprecation-response-headers` | `hJCjTdp` | 1 | `max_reviews_reached` | 1/1 | 3/3 | 3/3 |
| `fastapi-deprecation-response-headers` | `wTj24wc` | 0 | `approved` | 1/1 | 2/2 | 1/1 |
| `anko-default-function-arguments` | `XSViwH5` | 0 | `degraded` | 1/1 | 3/3 | 3/2 |
| `anko-default-function-arguments` | `SvgJuDM` | 0 | `approved` | 1/1 | 1/1 | 0/0 |
| `prometheus-typed-label-sorting` | `tUjP82r` | 无 verifier | `timeout` | 1/0 | 0/0 | 0/0 |
| `prometheus-typed-label-sorting` | `kM7gVSE` | 1 | `max_reviews_reached` | 1/1 | 1/1 | 1/1 |
| `kombu-single-active-consumer-priority` | `UK5tiWd` | 1 | `degraded` | 1/1 | 2/1 | 1/1 |
| `kombu-single-active-consumer-priority` | `8jetM78` | 0 | `approved` | 1/1 | 2/2 | 1/1 |
| `textual-richlog-follow-state` | `TYuW6wM` | 0 | `timeout` | 1/0 | 0/0 | 0/0 |
| `textual-richlog-follow-state` | `TaRaiuc` | 0 | `degraded` | 1/1 | 2/1 | 1/1 |
| `tomlkit-toml-table-converters` | `b8DBQ5j` | 0 | `timeout` | 1/0 | 0/0 | 0/0 |
| `tomlkit-toml-table-converters` | `Kz4G7NU` | 1 | `degraded` | 1/1 | 2/1 | 1/1 |
| `cliffy-config-file-parsing` | `kVWVMGR` | 1 | `approved` | 1/1 | 2/2 | 1/1 |
| `cliffy-config-file-parsing` | `Yjd9BFS` | 1 | `degraded` | 1/1 | 3/3 | 3/2 |
| `go-critic-doc-link-checker` | `i8JM6tz` | 0 | `degraded` | 1/1 | 2/1 | 1/1 |
| `go-critic-doc-link-checker` | `yqCiTFe` | 0 | `degraded` | 1/1 | 1/0 | 0/0 |
| `clack-async-autocomplete-options` | `AmR2FGf` | 0 | `degraded` | 1/1 | 2/1 | 1/1 |
| `clack-async-autocomplete-options` | `uDLDjVf` | 1 | `approved` | 1/1 | 2/2 | 1/1 |
| **合计** | **24 trials** | **11 / 24** | — | **24/21** | **45/39** | **33/29** |

阶段内部实际发生 67 次 modifier attempt 和 57 次 reviewer attempt：前者分布在 24 个初始 modify 轮与 33 个 revision 轮中，后者分布在 45 个 review 轮中。轮数与 attempt 数的差异来自配置允许每轮最多两次 Agent 尝试。

## 三个异常 trial

### 1. prometheus-typed-label-sorting__tUjP82r

该 trial 没有生成有效 verifier 结果，不能简单解释为模型解题失败。

初始 modifier 的两次内部尝试均由 600 秒 event-silence watchdog 中止：

- 第一次尝试在执行 PromQL `go test` 时长期无事件。诊断快照显示 Go 进程仍存在，但测试二进制尚未出现，更符合冷编译、vet、链接或 Go 缓存等待，而不是测试函数本身死循环。
- 第一次 turn 中止后，`go test` 没有随 turn 一起终止，成为 PPID 1 的孤儿进程。
- 第二次尝试重新生成修改后卡在 `go vet`；第二个 watchdog 快照同时看到遗留的第一次 `go test` 和本次 `go vet`。
- 两次尝试耗尽后 workflow 返回 `outcome=timeout`、`deliverable=false`，Agent 以 exit 2 退出。

之后 verifier 构建又因访问 Public ECR 时 TLS handshake timeout 而失败，所以 `verifier_result=null`。同一任务的第二个独立 trial `kM7gVSE` reward 为 1，进一步说明第一个 trial 包含显著的基础设施/编排因素。

此案例验证了 watchdog 的事件检测、快照和 turn 重试能够工作，同时暴露两个限制：

1. 600 秒可能误判长时间、无事件的编译或测试工具调用。
2. Abort cligent/OpenCode turn 没有可靠清理该 turn 创建的整个工具进程组，内部重试可能被上一尝试污染。

### 2. tomlkit-toml-table-converters__b8DBQ5j

初始 modifier 持续运行约 5100 秒，直到 workflow soft deadline。它没有进入 reviewer 阶段，也没有剩余预算进行第二次 modifier 尝试，最终以 `outcome=timeout`、`deliverable=false`、exit 2 结束。

该 trial 的 verifier 正常运行：F2P `0/60`、P2P `964/964`、reward 0。它更接近预算内未完成解题的真实 Agent timeout，应作为计分失败保留。第二个独立 trial `Kz4G7NU` 通过。

### 3. textual-richlog-follow-state__TYuW6wM

初始 modifier 两次尝试均由 watchdog 中止：

- 第一次尝试在运行约 51 分钟后连续 600 秒没有事件。诊断快照中没有仍在运行的工具子进程，只看到 OpenCode 服务和已产生的大量代码修改。
- 第二次尝试卡在 `timeout 700 pip install mypy`。600 秒时 `pip` 进程仍存在且 CPU 很低，watchdog 保存快照并中止 turn。

第一次 attempt metadata 中出现 `No opencode event for 73ms`，但对应诊断 JSON 明确记录 `silenceMs=600068`。这是诊断过程中 `lastEventAt` 被后续事件更新造成的错误消息竞态，不表示 watchdog 在 73ms 时误触发。

Verifier 正常运行：F2P `0/20`、P2P `6/6`、reward 0。第二个独立 trial `TaRaiuc` 也为 reward 0，因此该任务的 pass@2 为 0。

## Outcome 与 verifier 的关系

Review-loop outcome 不是最终得分。此次结果包含以下正常组合：

- `approved` 但 reward 0，例如 Anko、Kombu、FastAPI 的部分 trial。
- `degraded` 但 reward 1，例如 Arcane、Kombu、Tomlkit、Cliffy 的部分 trial。
- `max_reviews_reached` 但 reward 1，例如 Mobly、FastAPI、Prometheus、Tengo。

这些组合不表示 Pier 或 verifier 异常，只说明 reviewer 判断与隐藏测试结果并不等价。正式通过率必须以 verifier reward 为准。

## Resume 与后续处理

Pier 技术上可以按异常类型原地 resume：

```bash
pier job resume \
  --job-path /Users/kgm/Projects/merico/deep-swe/jobs/unified-collab-05_sample_confirm-12-tasks-20260804-200817 \
  --filter-error-type NonZeroAgentExitCodeError
```

但不建议直接对本 job 执行：

- Pier 会先删除三个异常 trial 的原目录，现有诊断证据会丢失。
- 三者都是 `NonZeroAgentExitCodeError`，命令会一起重跑，不能只选择无 verifier 的 Prometheus trial。
- 选择性重跑失败 trial 会改变预先固定的两次采样，抬高统计结果；除非明确标注为 infrastructure retry，否则不能继续视为原始 pass@2 基线。
- 原 job config 已保存 `eventSilenceTimeoutSeconds=600`，resume 会自动继续使用，无需也无法在 `pier job resume` 命令后追加该参数。
- Resume 仍使用 `e87ec83987608685` runtime，其中工具进程组清理尚未修复，粗粒度 watchdog 仍可能在长工具调用期间触发，Prometheus/Textual 类问题可能复现。

建议保留该 job 作为原始基线，报告时将 Prometheus `tUjP82r` 标记为基础设施异常并从有效 trial 分母排除。完成工具进程组清理和 watchdog 时间戳修复后，如需复核，再以独立补充 job 重跑相关案例，不覆盖本 job。

## 后续处理决策与基础设计

后续不将 WIP runtime 扩张为 cligent 或 Pier 的替代实现。统一基线采用以下职责边界：

1. cligent 负责 Agent adapter 的语义事件和 session 生命周期，包括完整的 tool-use、tool-result 和 terminal event。
2. runtime 负责 single/collab workflow、总预算、粗粒度 event-silence watchdog 和 trial 内进程隔离。
3. Pier 继续负责 task/trial 生命周期、artifact、独立 verifier 和原始结果汇总。
4. 独立分析层基于不可变的 job 原始数据处理异常分类、有效分母和 pass@k，不修改 Pier 原始结果。

### Watchdog 与进程清理

Watchdog 是 cligent 上游问题尚未完全修复时的调用方保护，只保留为参数固定、写入 manifest
的粗粒度熔断器，暂不识别“Provider 静默”“Agent 思考”或“长工具调用”等细分类别。正式
比较的不同 Agent/job 必须使用相同参数，并单独记录 watchdog 触发的 trial。

该 job 完成后，runtime 已增加 turn 级进程树清理。它在 turn 开始时记录进程基线，异常触发
时冻结新增后代进程，诊断结束、真正 abort 前再次采集并合并；给予 adapter 一个短暂 grace
period 后，从叶到根发送 SIGTERM，仍未退出者再发送 SIGKILL。清理结果记录为
`runtime:turn_process_cleanup`。实现不使用可能误伤其他 trial 的全局进程匹配，也不直接
杀死可能与 runtime 共享的 PGID；已停止执行的 zombie 和仍在运行的 survivor 分开记录。

### 最小诊断快照

cligent 事件完善后，可以从事件流获得工具命令、输入、结果和 session 结束原因，但事件流
无法完全替代异常时的操作系统与工作区快照。例如工具没有返回时，仍需判断进程是否存在、
是否成为 PPID 1 的孤儿进程，以及中止前有哪些未 checkpoint 修改。

因此只在 watchdog/异常中止时保留 best-effort 最小快照：

- 触发瞬间冻结的最后事件、`lastEventAt` 和静默时长；
- 包含 PID、PPID、PGID、状态、运行时间、CPU 和命令的进程树；
- Git HEAD、status、diff stat 和 tracked binary patch；
- 如后续确有需要，只增加有大小上限的 untracked 文件名、大小和 hash 清单。

暂不默认采集完整 `/proc` 或完整 untracked 文件内容，避免诊断系统继续膨胀，以及大文件或
凭证进入 artifact。该 job 暴露的时间戳竞态也已修复：timer callback 会冻结触发时间、
`lastEventAt` 和最后事件字段，诊断异步执行期间到达的 terminal event 不会再改变错误消息和
timeout 事件中的静默时长。

### Pier 汇总

暂不修改或覆盖 Pier 的聚合行为。job 中的逐 trial 原始结果和 verifier artifact 是权威输入；
需要正式统计时，由独立、版本化的结果分析脚本计算 raw reward、有效 trial 分母、排除原因和
task-level pass@k，并同时保留 Pier 原始指标以便核对。

### Task 与 verifier 镜像

当前流程涉及三类镜像：

| 镜像 | 用途 | 当前准备方式 |
|---|---|---|
| Agent runtime image | 提供 cligent、OpenCode、Codex、Kimi 等统一工具层 | `runtime prepare` 构建并以只读 image mount 复用 |
| Task base image | 提供仓库、依赖和基础开发环境，Agent 在其中解题 | 由 task 的 `[environment].docker_image` 指定 |
| Verifier derived image | 从干净 task base 开始，加入隐藏测试和 grader | Pier 在 separate-verifier 阶段以 `tests/Dockerfile` 构建 |

Verifier derived image 通常只是 task base image 上的一层很小的隐藏测试层，但当前并不是已经
发布、可以直接拉取的独立镜像。本次 Prometheus trial 的 verifier 在 BuildKit 处理
`tests/Dockerfile` 的远程 `FROM public.ecr.aws/...` 时请求 registry 元数据和匿名 token，因
TLS handshake timeout 构建失败。即使对应 task base image 已存在于本地，BuildKit 仍可能在
构建时访问 registry。

预构建 verifier image 不改变 Agent 解题过程、最终 patch 或 verifier 测试语义；主要收益是
缩短 verify 阶段，并降低 trial 结束时受 registry 短暂故障影响的概率。当前先接受这类故障由
原始 artifact 识别并在统计中排除，暂不实现完整的 verifier image prepare/reuse。若之后批量
运行中 verifier build/network error 频繁出现，再增加按 `base image ID + tests 目录 hash`
寻址的预构建镜像，以及 `--require-prepared-images` 一类的运行前校验。

### 后续实现状态

以下修改已在该 job 结束后完成，原 job 使用的 runtime image 不包含这些修复。修复后的
content-addressed image 已构建为 `deep-swe/agent-runtime:12129eb84c44eb9d`，完整 manifest
digest 为 `12129eb84c44eb9d0f90ae8ae9c999c439b132e37c5ed92c0be5c946bd58b708`，并已在
`linux/amd64` task 容器中通过进程清理和诊断快照测试。

1. Abort 后的 turn 进程树清理已实现，并覆盖 adapter grace、SIGTERM、SIGKILL 和 survivor 记录。
2. Watchdog 的触发时间与 `lastEventAt` 已冻结，错误消息、事件和诊断快照使用同一静默区间。
3. 最小诊断快照已通过结构测试，覆盖进程字段、Git HEAD/status/diff stat 和 tracked binary patch；不增加完整 `/proc` 或 untracked 内容。
4. Tool-aware watchdog、Pier 聚合修改和 verifier image 预构建继续暂缓。
