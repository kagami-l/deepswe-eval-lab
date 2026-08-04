# CLI-004 OpenCode auto 权限阻塞证据

本目录保存 CLI-004 的最小可复核证据集。样本来自同一批 cligent `0.16.0` +
OpenCode CLI/SDK `1.18.10` 真实运行中的两个并发 trial。

## 结论摘要

- 两个独立 OpenCode session 都配置了 `permissions.mode=auto`。
- 两者都在访问 `/tmp` 时产生 `external_directory` 权限请求。
- 权限请求是各自事件流的最后一条记录，此后没有 reply、tool result 或 terminal done。
- 取证时两个容器、Node runtime 和 `opencode serve` 均仍存活，但事件流已分别静默约
  24 分钟和 18 分钟。
- cligent 的 OpenCode auto 映射只允许 `edit`、`bash`、`webfetch`，没有包含
  OpenCode SDK 明确定义的 `external_directory`。

这组证据说明 run 不是因容器或进程退出而停止，而是停在无人响应的权限请求上。

## 文件说明

- [`permission-requests.jsonl`](./permission-requests.jsonl)：从两个完整事件流的最后一条
  记录投影出的权限事件。命令正文被缩短，只保留触发行为和权限范围。
- [`run-state.json`](./run-state.json)：2026-08-04 12:26:40 CST 的运行状态、事件文件
  大小、行数、校验值和静默时长。
- [`permission-mapping.json`](./permission-mapping.json)：从已安装 cligent adapter 和
  OpenCode SDK 类型提取的权限映射差异。

## 原始文件校验

取证时完整事件文件的 SHA-256：

```text
anko events.jsonl   8ddb082480696063bc0156d5920b671f0fa6cdb0a335ebaeb52c061dcee3904c
skrub events.jsonl  7a44cd333d1e68043538d2029520a1ce4d843410cfd4aa24d9855038c814e151
```

原始事件文件仍属于正在运行的 job，后续 timeout 或清理可能继续追加内容；以上 hash 对应
`run-state.json` 记录的取证时刻和字节数。

## 证据边界

本次保存的是 cligent 规范化事件，而不是转换前的 OpenCode SSE/HTTP 请求响应。结合
adapter 源码和 SDK 类型，可以确认 `external_directory` 没有进入 auto permission map；
但修复具体使用全局 permission config、wildcard v2 rule，还是 request reply API，应由
cligent 使用 raw SDK fixture 和真实 OpenCode server 集成测试确定。
