# mini-swe-agent 共享 runtime 方案

## 背景

Pier 的 installed-agent 默认流程会把 agent 安装步骤写入每个任务的派生
Dockerfile。mini-swe-agent 2.4.6 的 Python 依赖包含 LiteLLM、datasets、
PyArrow、NumPy、Pandas 等，因此首次构建较大；不同任务的基础镜像不同，安装层
也无法像同一任务的多次 attempt 那样稳定复用。

共享 runtime 模式把“任务环境”和“agent 可执行环境”拆开：

1. 一次性构建 `deep-swe/mini-swe-runtime:<version>`；
2. 最终 runtime 镜像是 scratch 文件镜像，包含独立 Python、mini-swe-agent
   及全部 Python 依赖；
3. 每个 trial 直接启动任务声明的预构建镜像；
4. Docker Compose 用 `type: image` 把 runtime 镜像根目录只读挂载到
   `/opt/mini-swe-runtime`；
5. agent setup 只写一个很小的 `$HOME/.local/bin/env` PATH 兼容文件，不安装包。

API key 仍由 Pier 在 agent 执行时注入，不进入 runtime 镜像或构建日志。

## 实现边界

- `SharedRuntimeMiniSweAgent` 负责 agent 启动、模型配置、日志和 trajectory；
  `install_spec()` 返回 `None`，使 Pier 不生成 agent 安装镜像。
- `SharedRuntimeDockerEnvironment` 负责保留 Pier 日志挂载、追加只读 runtime
  镜像挂载，并在启动前确认 runtime 镜像已存在于本机。
- environment cleanup 不使用 `--rmi all`，避免删除需要跨 attempt/job 复用的
  任务基础镜像和 runtime 镜像。
- `OptimizedMiniSweAgent` 继续作为 `per-task` 兼容回退模式。

对应文件：

- `wip/agents/mini_swe_agent.py`
- `wip/environments/mini_swe_runtime.py`
- `wip/docker/mini-swe-runtime/Dockerfile`
- `wip/scripts/run_mini_swe_eval.sh`

## 使用

共享模式现在是脚本默认值：

```bash
wip/scripts/run_mini_swe_eval.sh \
  -t wip/data/selection/05_sample_dev.txt \
  -k 2 -n 2
```

第一次运行若本地没有 runtime 镜像，脚本会先构建一次。构建时仍需下载约
73 个 Python 包；BuildKit cache mount 会保留 uv 下载缓存，使中断后的重试可
复用已下载内容。构建成功后，其他 task、attempt 和后续 job 都直接使用同一
runtime 镜像。

常用控制项：

```bash
# 只打印 Pier 命令；不触发 runtime 构建
wip/scripts/run_mini_swe_eval.sh --dry-run

# 强制重新构建 runtime（升级版本或排查镜像时）
wip/scripts/run_mini_swe_eval.sh --rebuild-runtime --dry-run

# 使用自定义本地 runtime 标签
wip/scripts/run_mini_swe_eval.sh \
  --runtime-image registry.example/mini-swe-runtime:2.4.6

# 回退到原先的逐任务 agent 安装层
wip/scripts/run_mini_swe_eval.sh --runtime-mode per-task

# 同时要求所有任务基础镜像已经在本机，彻底避免 job 期间访问 ECR
wip/scripts/run_mini_swe_eval.sh --require-local-images
```

runtime 默认按 `linux/amd64` 构建，与当前 DeepSWE 任务镜像一致。可通过
`MINI_SWE_RUNTIME_PLATFORM` 覆盖，但 runtime 与任务镜像必须使用同一架构。

## 与基础镜像策略的关系

共享模式下 Pier 直接使用任务的 `docker_image`，不再生成包含 agent 安装层的
任务派生镜像，因此已缓存任务不会触发 BuildKit 的 `FROM ... load metadata`
步骤。`--base-image-mode remote` 仍允许 Docker Compose 在任务镜像缺失时拉取；
`--require-local-images` 会在启动 job 前逐个检查并失败退出。

`classic` / `BuildKit` 的选择只影响 `per-task` 模式中的任务派生镜像构建，以及
一次性的 runtime 构建。runtime 构建固定使用 BuildKit，因为它需要持久的 uv
cache mount。

## 约束和故障定位

- 需要支持 Compose `type: image` mount 的 Docker Desktop/Engine；该能力目前
  会显示 experimental 提示。当前验证环境为 Engine 29.6.1、API 1.55、
  Compose 5.2.0。
- runtime 使用 glibc 版 Python，适用于当前 Linux DeepSWE 镜像，不适用于
  Windows 或 Alpine/musl 任务。
- shared 模式必须固定 mini-swe-agent 版本；版本变化会生成新的默认镜像标签。
- `extra_python_packages` 不能在 trial 内临时安装。需要这些包时应扩展 runtime
  Dockerfile，或使用 `--runtime-mode per-task`。
- runtime 构建阶段长时间无输出通常是 uv 解析索引；最终会出现
  `Resolved ... packages`。下载阶段会逐项显示大包。中断后重跑会复用 BuildKit
  下载缓存，但未完成的最终镜像不会被标记为可用。
- 若 job 报 runtime 镜像不存在，先用下面的命令确认本地标签，再重跑脚本或
  使用 `--rebuild-runtime`：

  ```bash
  docker image inspect deep-swe/mini-swe-runtime:2.4.6
  ```
