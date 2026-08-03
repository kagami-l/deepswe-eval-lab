# harbor 共享 agent runtime 方案调研

> 调研时间：2026-08-03
> 对应 harbor 版本：`main @ 72bc40b1`（2026-07-31）
> 本文中的 `src/...` 路径均相对 harbor 仓库根目录

## 1. 需求

我们把 harbor 当评测执行器用，使用模式有两个固定特征：

1. **task 镜像由数据集发布者准备**，不会绑定任何 agent；
2. **同一批评测使用同一个 agent**，不同批次之间才换 agent（就像换模型一样）。

因此期望：**一批评测只安装一次 agent CLI**，而不是每个 trial 装一遍。

这与 `wip/docs/mini-swe-shared-runtime.md` 里对 Pier 做的改造是同一个诉求，区
别在于 harbor 的安装时机不同（见 §2），改造点也不同。

## 2. harbor 现状：agent 安装是 per-trial 的

以下均已对照代码确认。

- **trial 展开**：`n_attempts × tasks × agents` 的笛卡尔积，每个组合一个独立
  Trial —— `src/harbor/job_plan.py:149-152`
- **每个 Trial 自建 environment（容器）**，随后 `_setup_agent()` →
  `agent.setup()` —— `src/harbor/trial/trial.py:1199-1216`
- **`BaseInstalledAgent.setup()` 在容器内执行 `install()`** ——
  `src/harbor/agents/installed/base.py:929-944`
- **claude-code 的 `install()` 是运行时联网安装**：`curl .../bootstrap.sh | bash`
  （Alpine 走 `npm install -g`）—— `src/harbor/agents/installed/claude_code.py:188-213`

所以 100 个 task 就是 100 个容器各下载安装一次，耗时计入 trial 结果的
`agent_setup` 字段。

### 2.1 已有的两层短路

- **install 探测**：安装前先跑 `command -v claude`；未指定 `version` 时命中即
  跳过安装，指定了 `version` 则要求版本精确相等 ——
  `src/harbor/agents/installed/claude_code.py:173-186`
- **系统依赖**：`curl/bash/nodejs/npm/procps` 先 `command -v` 全命中就跳过 ——
  `src/harbor/agents/installed/base.py:612-625`

### 2.2 缓存边界

镜像层缓存**只覆盖 task 镜像构建**：同名镜像并发 build 会加锁串行，只 build
一次，后续 trial 复用 docker 层缓存 ——
`src/harbor/environments/docker/docker.py:884-891`。

**容器内的 agent 安装不在这个缓存范围内**，没有任何跨容器复用。

## 3. harbor 已具备的零件

主干其实已经能拼出共享 runtime，只是没有产品化成 feature：

| 能力 | 位置 | 说明 |
|---|---|---|
| `type: "image"` 挂载 | `src/harbor/models/trial/config.py:43-50` | `ServiceVolumeConfig` 的 type 已含 `bind`/`volume`/`image`，并支持 `image.subpath`、`read_only` |
| `--mounts` 透传 | `src/harbor/cli/jobs.py:761-772` | 写 compose override 时原样透传，不做校验 —— `src/harbor/environments/docker/__init__.py:28-33` |
| agent 阶段 env 覆盖 | `src/harbor/trial/trial.py:1209-1216` | `--ae` 的值经 `scoped_exec_env` 覆盖 agent setup+run，**不污染 verifier** —— `src/harbor/environments/base.py:435-457` |
| 内容寻址构建 | `src/harbor/environments/docker/utils.py:169-184` | `ensure_docker_image_built` 的镜像名是内容哈希，天然跨 job 去重 |

### 3.1 不改 harbor 即可用的 workaround

```bash
harbor run -t <dataset> --agent claude-code --model ... \
  --mounts '[{"type":"image","source":"claude-code-runtime:2.0.30","target":"/opt/cc-runtime","read_only":true}]' \
  --ae PATH=/opt/cc-runtime/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

`command -v claude` 在注入的 PATH 下命中 → `install()` 整段跳过。

注意事项：

- `--ae` 的值**不做 shell 展开**，`$PATH` 写不了，必须列全绝对路径；
- compose 的 image volume 需要较新的 Docker（本机 Compose v5.2.0 /
  Engine 29.6.1 可用）；
- 这条路径的失败语义很差，见 §6.2。

## 4. 上游相关 issue / PR

| 编号 | 状态 | 内容 |
|---|---|---|
| [#25](https://github.com/harbor-framework/harbor/issues/25) | OPEN | 最早的需求帖。列了三条路：运行时安装（现状）/ 烘进 task 镜像（M×N 爆炸）/ **单独构建 agent 再挂载**；作者倾向挂载，提到用 nix 做 POC |
| [#641](https://github.com/harbor-framework/harbor/issues/641) [#654](https://github.com/harbor-framework/harbor/issues/654) | OPEN | 同一件事：运行时安装给每次 eval 加 30s+ 并烧带宽。#654 下面指向 PR #222 |
| [PR #222](https://github.com/harbor-framework/harbor/pull/222) | **DRAFT（2025-12 至今）** | "Mounted agents"。`BaseAgent.prepare()` 钩子 → `ensure_docker_image_built` 构建含 `/nix/store` 的镜像 → 生成 `{"type":"image","source":...,"image":{"subpath":"./nix"},"target":"/nix"}` 挂进容器。**机制与我们的方案同构，只是用 nix 装 agent** |
| [#571](https://github.com/harbor-framework/harbor/issues/571) | OPEN | 更激进：容器级复用（build queue + 快照 + trial 间 reset）。PR #572 draft |
| [#1962](https://github.com/harbor-framework/harbor/issues/1962) | CLOSED | "skip install for pre-built images"。**已落地**，就是现在的 `_INSTALL_CHECK_COMMAND` 自动探测 |
| [#1839](https://github.com/harbor-framework/harbor/issues/1839) + [PR #2126](https://github.com/harbor-framework/harbor/pull/2126) | OPEN | codex 的显式 `skip_install` 开关，maintainer 已表态接受，PR 未合 |
| [#2045](https://github.com/harbor-framework/harbor/issues/2045) | OPEN | 限网场景设计文档。结论一致：inline `RUN` 安装在 N 个 task 镜像上会跑 N 次，**只有 `COPY --from=<prebuilt-tools-image>` 才 scale**；提出 `PreinstalledBinaryAgentMixin`（install 退化为 `command -v` + `--version` 校验，缺失就 fail loudly） |
| [#1427](https://github.com/harbor-framework/harbor/issues/1427) | OPEN | AGS 的 envd 挂载 + 按 Dockerfile 内容哈希去重镜像 |
| [#2472](https://github.com/harbor-framework/harbor/issues/2472) [#2435](https://github.com/harbor-framework/harbor/issues/2435) | OPEN | claude-code 安装相关：固定版本产物、bootstrap 下载需有界且可重试 |

**判断**：需求已被上游确认，方案方向也确认是挂载，卡点在实现——#222 draft 了
八个月，很可能是因为把 nix 引入 harbor 依赖链太重（agent 得先有 flake），而
不是挂载机制本身有问题。

## 5. 我们的方案

在自适配的本地流程中已落地：在 Docker environment 中运行原始任务镜像，另外
构建 shared runtime 镜像并只读挂载进去。

- `wip/docker/opencode-runtime/Dockerfile` —— `FROM scratch`，内含
  opencode-ai + 拷入的 node 二进制
- `wip/docker/mini-swe-runtime/Dockerfile` —— `FROM scratch`，内含独立
  Python（拷 `/usr/local`）+ uv tool 安装的 mini-swe-agent

布局上比 #222 更干净：镜像根目录即 runtime，挂载时连 `subpath` 都不需要。

与 PR #222 的关键差异：**不依赖 nix**，runtime 由用户按评测集自备。这既是优势
（无额外依赖、任何人都能构建）也是风险来源（见 §6.1）。

## 6. 已识别的风险与细节

### 6.1 ABI 兼容：责任在用户，但"按评测集准备"没那么容易

框架侧只负责挂载，兼容性由 runtime 镜像的准备者保证——这个边界是清晰的。但
**一个 dataset 不等于一个基础镜像**：

- adapters 模板里 `python:3.11-slim` ×8、`python:3.11-slim-bookworm` ×3，另有
  `ubuntu:22.04`、`rust:1.83-slim`、`t-bench/ubuntu-24-04` 等；
- 更关键的是 `FROM {docker_image}` / `{{dataset_base_image}}` / `${docker_base}`
  这类占位符——SWE-Bench 系是**每个 instance 一个上游镜像**，基础发行版由原仓
  库决定。

所以"按评测集准备 runtime"实操上等于"对该评测集全部镜像的 glibc 取下界"，换
数据集要重新确认。当前两个 runtime 都基于 bookworm（glibc 2.36），在 musl
（alpine）或更老的 glibc 镜像上会直接跑不起来。

**结论**：不影响 harbor 该不该做这个 feature，但意味着不匹配是常态，框架必须
提供明确的失败语义（§7）。

### 6.2 现有探测语义太弱 → fail late 且被误分类

`command -v claude`（`claude_code.py:39-40`）是纯 PATH 查找，**不执行二进制**。
ABI 不匹配的 `claude` 照样命中 → install 被跳过 → 错误推迟到 agent run 才爆 →
最终记成 agent 失败 / reward 0，而不是 setup 失败。参见上游
[#2317](https://github.com/harbor-framework/harbor/issues/2317)（infra fail 被
当成 honest fail）。

另外版本探测是 best-effort 吞异常（`agents/installed/base.py:946-954`），挂载
模式下二进制跑不起来时会**静默把 version 记成 None**，结果文件里看不出异常。

### 6.3 跳过 install 同时跳过了系统依赖

`ClaudeCode.install()` 第一件事就是短路 return（`claude_code.py:189-197`），后
面的 `ensure_system_dependencies(curl, bash, nodejs, npm, procps)` 一行都不执
行。需要自行确认：

- **ca-certificates** —— stripped 镜像没有 `/etc/ssl/certs` 时 agent 连不上模
  型 API，且报错长得像网络故障；
- **procps** —— 部分 agent 的进程管理依赖（[#2311](https://github.com/harbor-framework/harbor/issues/2311)）；
- tzdata / locale 等次要项。

当前两个 runtime 镜像都只装了 agent 本体。

### 6.4 platform 不是主机平台

多个 adapter 在 Dockerfile 里钉死 `--platform=linux/amd64`：medagentbench、
scienceagentbench、cybergym、deveval。而 harbor 的
`default_docker_platform()`（`environments/docker/utils.py:35-54`）取的是
**daemon 平台**。在 Apple Silicon 上默认构建出的 arm64 runtime 挂进 amd64 容器
= `exec format error`，且本地跑 hello-world 验证时完全不会暴露。

### 6.5 挂载是 trial 级的，覆盖验证阶段

`--ae PATH=...` 只作用于 agent setup/run（`trial.py:1209-1216` +
`environments/base.py:435-457` 明确不覆盖 verifier），但**挂载本身是容器级
的**，verifier 运行时 runtime 目录仍在容器里。

这是"挂载"相对"运行时安装"的可观测行为差异。[#25](https://github.com/harbor-framework/harbor/issues/25)
里提到 terminal-bench 的 extract-safely 这类任务对 installed agent 不公平，本
质就是 agent 在被测环境里留下的痕迹会影响评测。应写进文档而非当作对用户透明
的优化。

### 6.6 PATH 优先级导致版本静默漂移（claude-code 特有）

其 run 命令写死 `export PATH="$HOME/.local/bin:$PATH"`
（`claude_code.py:1554`），排在注入的 PATH 之前。只要有某个 trial 因版本探测不
过而真的执行了一次安装，之后该容器用的就是 `~/.local/bin` 那份——同一批评测出
现两个版本，而结果文件里的 version 字段是对的，不易察觉。

→ feature 化时 prefix 必须参与 agent 的命令构造，靠 `--ae PATH` 外挂只是权宜。

### 6.7 只读挂载 vs 自更新

claude-code 原生安装是 launcher + versions 目录结构，会尝试自更新；只读挂载下
每个 trial 都有一次失败的更新尝试。需显式 `DISABLE_AUTOUPDATER=1`（harbor 目前
不设置）。opencode 同理，需确认它不往安装目录写 plugin/cache。

### 6.8 云 environment 无本地镜像可挂

daytona / modal / gke 拿不到本机镜像。要么 runtime 推到 registry 且 provider
网络可达，要么在 capability 层显式声明不支持——不能静默降级。

## 7. 建议的 harbor feature 设计

把 ABI 责任留给用户，框架提供**快速失败 + 可诊断**，而不是兼容性保证。

1. `AgentConfig.runtime_image: str | None` + `runtime_prefix`（默认
   `/opt/harbor-agent-runtime`），CLI 暴露 `--agent-runtime-image`；
2. 复用 PR #222 已设计的 `BaseAgent.prepare(environment)` 钩子，在
   `_init_agent_environment` 之前执行，把 `{"type":"image", ...}` 追加进
   `_agent_env_mounts`（`trial.py:1249+`）；
3. 挂载后**执行** `<prefix>/bin/<agent> --version`，成功才跳过 install；
4. 失败按显式策略处理：`on_mismatch: fail`（默认，抛 setup 错误并原样带出
   stderr——`exec format error` / `GLIBC_2.36 not found` 本身就是诊断结论）或
   `install`（回退现有安装路径，但必须 log warning，否则用户以为省了时间其实
   每个 trial 都在装）；
5. runtime 镜像 platform 显式可配，并与任务容器 platform 做一次比对；
6. prefix 注入走 agent 命令构造，不用外挂 PATH；
7. 加 environment capability（如 `image_mounts`），不支持的 provider 明确报错。

如果用户自备 runtime 镜像，harbor 不需要构建它——但若要支持"harbor 帮你构建
runtime"，直接复用 `ensure_docker_image_built`，它已经是内容寻址的，一个 job
内只 build 一次、跨 job 自动命中。

## 8. 后续动作

- [ ] 在 [#654](https://github.com/harbor-framework/harbor/issues/654) 或
      [#25](https://github.com/harbor-framework/harbor/issues/25) 回帖：说明我
      们已有非 nix 的 image-mount 实践，贴省下的时间数据，询问 maintainer 是否
      接受把 #222 的 `prepare()` 钩子拆出来、runtime 镜像交给用户自备
      （#222 作者 @xiaoxiangmoe 与 @alexgshaw 都在这条线上，避免重复劳动）
- [ ] 用 §3.1 的 workaround 在真实数据集上量一组数据：per-trial 安装 vs 挂载
      的 `agent_setup` 耗时差、失败率、带宽
- [ ] 验证目标数据集的镜像分布：glibc 下界、是否有 musl、是否有钉 amd64 的任务
- [ ] 补全 runtime 镜像的自包含性：ca-certificates、procps、必要 locale
- [ ] 决定是否提最小 PR（`prepare()` 钩子 + `runtime_image` + 执行式准入检查）

## 9. 开放问题

- runtime 镜像该由 harbor 构建还是完全用户自备？前者能复用内容寻址缓存，后者
  边界更清晰。倾向：**自备为主，构建能力可选**。
- 准入检查失败的默认策略是 `fail` 还是 `install`？倾向 `fail`——静默回退会让
  "共享 runtime 没生效"变成无声的性能退化。
- 是否需要在 trial 结果里记录"本次 agent 来自挂载还是安装"？对复现和归因有价
  值，也能让 §6.6 的版本漂移可见。
- 挂载对评测公平性的影响（§6.5）要不要暴露成显式开关，比如验证阶段卸载 runtime？
