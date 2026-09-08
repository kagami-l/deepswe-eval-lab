# Agent SDK 升级实施记录

日期：2026-09-08。承接 [cligent 0.25.0 迁移](./20260908-cligent-0.25.0-upgrade-assessment.md)。
本次将供应商 SDK/CLI 更新到 cligent 最新正式版所验证的版本组合。

后续已完成用户指定的两次真实模型 smoke：single 23/23、collab 12/23；执行链路正常，
Codex resume 用量仍有缺失。详见 [one_task smoke 记录](./20260908-agent-sdk-smoke.md)。
下方“未调用真实模型”仅描述依赖升级实施阶段。

## 版本选择

| 组件 | 本次升级前 | 本次固定版本 | 查询时 npm latest |
| --- | --- | --- | --- |
| cligent | 0.25.0 | **0.26.0** | 0.26.0 |
| Claude Agent SDK | 0.3.220 | **0.3.251** | 0.3.263 |
| Codex SDK / CLI | 0.146.0 | **0.151.0** | 0.153.4 |
| Gemini CLI | 0.53.1 | **0.57.0** | 0.58.0 |
| Kimi Code | 0.31.1 | **0.39.1** | 0.41.0 |
| OpenCode SDK / CLI | 1.18.25 | **1.18.25** | 1.18.29 |
| ACP SDK（cligent 传递依赖） | 1.4.0 | **1.4.0** | 随 cligent 固定 |

更高的供应商版本被 cligent 标为 `untested`，不代表不兼容，也不是支持上限。
本次选择上游已验证的组合。OpenCode 另有具体约束：cligent 0.26.0 的完整用量
统计要求健康检查报告恰好为 1.18.25，更高版本会降为 partial，因此保留这一对版本。
ACP 使用 cligent 固定的版本，不单独覆盖。

调查期间 npm 新发布了 cligent 0.26.0；它增加可选模型发现 API。
正式 tarball 中的执行核心、五个 adapter JavaScript 和版本规则与 0.25.0 相同，
不需要再次迁移现有调用接口。该版本来自 npm，未引用本地 cligent checkout。
源码、正式包比较及兼容规则证据见[兼容性核验记录](./20260908-agent-sdk-compatibility-notes.md)。

## 实施范围

- 更新统一入口和旧协作入口的 package.json、官方 registry lockfile 及本地安装。
  Codex SDK 与其实际执行的 CLI 保持同版本；旧入口通过 SDK 的精确依赖安装 CLI。
- shared runtime manifest 更新为 **0.6.0**，Docker 的 Gemini/Kimi 默认版本与之同步；
  旧协作入口的按需安装默认值和相关测试同步更新。
- 镜像在移除开发依赖后调用 cligent 的公开 readiness API，检查全部五个 adapter
  能否加载及其实际版本。缺失、不支持、版本不可读会使构建失败；较新的 `untested`
  版本仍可通过并显示状态，不把 tested 版本误设成硬上限。
- 保留已迁移的 usageSchema=2、错误码透传、watchdog、进程清理及权限 fail-fast。
  本次供应商升级没有提供足以删除这些保护的证据。
- 修正旧入口 Kimi 文档和错误提示：OAuth 是本项目当前认证流程的要求。
  上游 0.39.1 已支持配置默认模型凭据或 model/key 对；本次不扩展认证流程。

## 验证

- 两套依赖均从官方 npm registry 完成全新安装，直接依赖、lockfile 与 manifest
  一致；无本地路径依赖。
- 统一 runtime **85/85**、旧协作 runtime **33/33**、受影响 Python 测试 **81/81**，
  共 **199 项**通过；TypeScript 编译、Python lint 和 diff whitespace 检查通过。
- Linux `amd64` 镜像已完成构建。删除开发依赖后，Claude、Codex、Gemini、Kimi、
  OpenCode 五个 adapter 全部可用，所有目标均报告 supported，实际版本与上表一致。
- 最终镜像文件中的八个直接 SDK/CLI 包版本、ACP 1.4.0、manifest 内容及 digest
  已核对；编译后的 usage 模块和 readiness 检查脚本存在。临时检查容器已移除。

| 镜像信息 | 值 |
| --- | --- |
| 镜像 | `deep-swe/agent-runtime:810a05e3fb3ee42c` |
| manifest digest | `810a05e3fb3ee42c83b5097821914ff0924360c5dea1e67d4d97786b90a40cfc` |
| image ID | `sha256:f7df59e88d271e4610e1e4d5104fff54fdfc6504e63eaa688cf975654a7d8312` |
| 平台 / 构建 Node | `linux/amd64` / `22.23.2` |

未调用真实模型或重跑 SWE 评测。安装、适配器可用性及合成事件回归不能替代真实
认证、模型会话或供应商行为验收；CLI-008 因此继续保持 Released。
未提交 Git commit；之前已暂存的修改保持原样，本次修改留在工作区。
历史执行计划不自动重写，新计划读取新的 runtime digest。
