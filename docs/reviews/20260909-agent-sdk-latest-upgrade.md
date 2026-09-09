# Agent SDK / CLI 最新版本升级（2026-09-09）

本次针对容器内 Codex 0.151.0 无法启动 `gpt-6-astra` 的报错，升级评测运行时中的 Agent SDK / CLI。版本来自 npm 官方 registry 的最新稳定标签；cligent 继续通过 npm 包安装，不引用本地源码仓库。

| 依赖 | 升级前 | 升级后 |
| --- | --- | --- |
| Codex CLI | 0.151.0 | 0.153.4 |
| Codex SDK | 0.151.0 | 0.153.4 |
| Claude Agent SDK | 0.3.251 | 0.3.266 |
| OpenCode SDK / CLI | 1.18.25 | 1.18.30 |
| Gemini CLI | 0.57.0 | 0.59.0 |
| Kimi Code | 0.39.1 | 0.41.0 |
| cligent | 0.27.0 | 0.27.0（仍为最新） |

运行时版本从 0.7.0 更新为 0.8.0，同步 package.json、官方 registry 的 package-lock.json、运行时 manifest 和 Dockerfile 的 CLI 默认版本。Node 继续使用 22 系列；Kimi 0.41.0 要求 Node >=22.19.0。本次范围为 Agent 运行依赖，未迁移 TypeScript、Python 或 Pier。

## 问题与修复验证

用户报告的任务：`jobs/collab-codex-claude-complementary-opus-astra-medium-10-tasks-20260909-134550/python-statemachine-state-data-s__ier4RVC`。

以隔离的工作目录、相同登录凭证和同一个最小请求（gpt-6-astra / medium，要求只回复 OK）做升级前后对照：

- 升级前 Codex SDK / CLI 0.151.0：退出 1，复现 `The 'gpt-6-astra' model requires a newer version of Codex`。
- 升级后 Codex SDK / CLI 0.153.4：退出 0，回复 OK，并返回 token usage。
- 86 项 TypeScript 运行时测试通过，58 项 Python 测试通过，包含镜像配置一致性、评测规划、Agent 封装及 token/cost 统计。

官方 [Codex changelog](https://learn.chatgpt.com/docs/changelog) 也记录了 0.153.1 加入 Astra API 配置支持、0.153.4 修正 Astra 模型展示的问题。此次修复以实际请求的前后对照为依据。

## 构建产物

- Runtime：0.8.0，Node 22.23.2，linux/amd64。
- 镜像：`deep-swe/agent-runtime:86d93103f53a80a1`。
- Manifest digest：`86d93103f53a80a12d691cf0d3cd2b94c9c3e0ff1244384983d6dc8526c3a86b`。
- Image ID：`sha256:952d33d5d60caa28e54ecad18c591d9a687d72f5fcc60003beea702bfc4c3233`。
- 五种 Agent 的生产依赖可用性检查通过；各 SDK / CLI 版本与 manifest 一致。
- 实际容器以只读 image mount 加载上述 runtime，通过 cligent 调用 `gpt-6-astra / medium` 成功，回复 OK；done.status 为 success，toolUses 为 0，input 为 15,274，output 为 5，coverage 为 partial。
- 最小验证容器的 Node 基础镜像缺少 CA，首次请求因 UnknownIssuer 失败；挂载主机可信 CA bundle 并设置 SSL_CERT_FILE 后通过。始终保持 TLS 校验开启。这个验证环境问题不涉及评测项目代码调整。

后续按当前配置创建的评测会解析到这个新镜像。既有 job 的冻结计划和历史结果保持原样。

## verifier 为什么继续执行

运行时没有把 modifier 启动失败视为成功：该 trial 的 summary.json 是 `outcome: modifier_failed`、`deliverable: false`，没有生成修改；runtime/main.ts 对不可交付结果返回退出码 2。

Pier 0.3.0 的 Trial.run 会捕获 `NonZeroAgentExitCodeError` 和 `AgentTimeoutError`，记录 exception_info，随后继续收集产物并运行 verifier。因此这是当前框架的执行策略。此次依赖升级解决 Astra 的启动兼容性，不修改这个策略；其他原因引发的 Agent 非零退出仍可能进入 verifier。

## 用量数据的能力边界

cligent 的已验证版本表滞后于本次安装版本，readiness 的 `untested` 表示超出上游已验证组合，并不等于不可用。保留这一真实状态，不伪造兼容或完整性结论。

- Codex 的 token coverage 仍由 cligent 0.27.0 标为 partial；SDK 更新不等于 cligent 已补齐子线程统计。
- OpenCode 0.27.0 adapter 的完整性判断绑定其已验证的 server 1.18.25；升级到 1.18.30 后用量可能被标为 partial。沿用 cligent 返回的 coverage 和 cost，缺少直接 cost 时仍走现有 estimateCost() 逻辑。
- Gemini / Kimi / OpenCode 的可用性检查不等于所有模型和功能已经跑过完整评测。

原始验证输出保存于项目临时目录 `tmp/sdk-upgrade-20260909/`。
