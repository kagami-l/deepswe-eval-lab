# Pier 的 Kimi Code Agent 适配器

`KimiCodeAgent` 用于在 Pier 中运行 Moonshot AI 官方的
[`MoonshotAI/kimi-code`](https://github.com/MoonshotAI/kimi-code)。它使用的是
Node.js/TypeScript 版 npm 包 `@moonshot-ai/kimi-code`，不是旧版 Python
`kimi-cli`。

适配器默认将 Kimi Code 固定为 `0.30.0`，并安装到 Pier 为任务生成的派生
Docker 镜像中。API Key、模型名称和服务地址只在容器运行时注入，不会被写入
镜像。

## 实现方式

Kimi Code 本身是 Node.js 程序，提示词处理、工具调用和代码修改均由容器内的
官方 `kimi` 命令完成。

Pier 0.3.0 通过 Python import path 加载自定义 Agent，因此本目录中的
`kimi_code_agent.py` 是必要的生命周期适配层，负责：

- 定义容器内 Kimi Code 的安装流程；
- 向运行中的容器传递模型配置；
- 以非交互模式启动 `kimi`；
- 保存标准输出和标准错误；
- 将 `stream-json` 输出转换为 ATIF-v1.7 轨迹；
- 将 token、成本和步骤数等可用指标回填到 Pier 的 `AgentContext`。

## 环境要求

- Pier 0.3.0；
- 可用的 Docker 环境；
- Kimi Code API Key；
- 任务目录位于仓库的 `tasks/` 下。

容器内需要 Node.js 22.19.0 或更高版本。如果任务基础镜像中的 Node.js 不满足
要求，适配器会通过 NVM 安装 Node.js 22.19.0，然后安装指定版本的 Kimi Code。

## 配置模型

在启动 Pier 前设置 Kimi Code 环境变量：

```bash
export KIMI_MODEL_API_KEY='你的 API Key'
export KIMI_MODEL_BASE_URL=https://api.kimi.com/coding/v1
export KIMI_MODEL_MAX_CONTEXT_SIZE=1048576
```

`KIMI_MODEL_NAME` 默认是 `k3`，只有使用其他模型时才需要显式设置。

批量运行脚本也可以从 `wip/scripts/.env` 中读取 API Key：

```dotenv
KIMI_MODEL_API_KEY='你的 API Key'
```

宿主环境中已经存在的 `KIMI_MODEL_API_KEY` 优先于 `.env`。仓库的
`.gitignore` 已忽略 `.env`，不要强制提交密钥文件。

不要把真实 API Key 写进源码、任务配置或 Dockerfile。以下命令使用
`${KIMI_MODEL_API_KEY}`，由 Pier 在运行时从宿主机环境中读取。

## 运行单个任务

在仓库根目录执行：

```bash
cd /Users/kgm/Projects/merico/deep-swe

pier run \
  -p tasks/tengo-destructuring-bindings \
  --agent-import-path wip.agents.kimi_code_agent:KimiCodeAgent \
  --model kimi-code/k3 \
  --agent-kwarg version=0.30.0 \
  --agent-env 'KIMI_MODEL_NAME=${KIMI_MODEL_NAME}' \
  --agent-env 'KIMI_MODEL_API_KEY=${KIMI_MODEL_API_KEY}' \
  --agent-env 'KIMI_MODEL_BASE_URL=${KIMI_MODEL_BASE_URL}' \
  --agent-env 'KIMI_MODEL_MAX_CONTEXT_SIZE=${KIMI_MODEL_MAX_CONTEXT_SIZE}'
```

`--model kimi-code/k3` 是写入 Pier 结果和轨迹的模型标识；真正传给 Kimi Code
的模型名称由 `KIMI_MODEL_NAME` 决定。建议两者保持对应，方便后续分析评测结果。

## 运行 `05_sample_dev.txt` 中的全部任务

推荐使用已经封装好的启动脚本。它会读取
`wip/data/selection/05_sample_dev.txt`、校验任务目录和必需环境变量，并组装
Pier 的全部参数：

```bash
cd /Users/kgm/Projects/merico/deep-swe

wip/scripts/run_kimi_sample_dev.sh
```

指定其他任务列表：

```bash
wip/scripts/run_kimi_sample_dev.sh \
  --task-list wip/data/selection/05_sample_confirm.txt
```

先检查最终命令但不运行评测：

```bash
wip/scripts/run_kimi_sample_dev.sh --dry-run
```

通过参数调整并发数和每个 trial 的尝试次数：

```bash
wip/scripts/run_kimi_sample_dev.sh \
  --n-concurrent 4 \
  --n-attempts 2
```

脚本默认生成包含 agent、模型、样本名和时间的 Job 名称，例如：

```text
kimi-code-k3-05_sample_dev-20260729-183000
```

也可以显式指定：

```bash
wip/scripts/run_kimi_sample_dev.sh \
  --job-name kimi-code-k3-dev-baseline
```

额外参数会原样传给 `pier run`：

```bash
wip/scripts/run_kimi_sample_dev.sh --debug
```

`--n-concurrent` 默认是 2，`--n-attempts` 默认是 1。可以根据 API 限流、
Docker 资源和预算调整。首次运行时需要为各任务构建派生镜像，建议先用单个
任务验证配置，再启动完整任务集。使用 `--help` 可以查看脚本支持的全部参数。

## 安装与缓存机制

Pier 中的每个 benchmark 任务都可能使用不同的基础镜像，因此适配器不会在
每次容器启动后临时执行安装，而是在任务基础镜像之上构建一个包含 Kimi Code
的派生镜像。

缓存行为如下：

- 某个任务首次运行时，需要构建派生镜像并安装 Kimi Code；
- 同一任务的后续 attempt 和重复评测会复用 Docker 缓存；
- 不同任务的基础镜像不同时，通常仍需分别完成首次构建；
- 修改 Kimi Code 版本或安装步骤后，相关安装层会重新构建；
- 使用 Pier 的 `--force-build` 会绕过正常构建缓存。

API Key 不参与安装指纹，也不会进入镜像层，因此更换 API Key 不会触发重新
安装。

## 运行方式与权限

适配器使用以下官方非交互接口：

```bash
kimi --prompt '<任务说明>' --output-format stream-json
```

Kimi Code 的 prompt 模式本身已经是非交互模式，因此适配器不会同时传入
`--auto` 或 `--yolo`。这两个选项不能与 `--prompt` 组合使用。

## 输出文件

每次 trial 的 Agent 日志目录中会生成：

- `kimi-code.jsonl`：Kimi Code 的原始 `stream-json` 标准输出；
- `kimi-code.stderr.log`：进度信息、警告和错误输出；
- `trajectory.json`：转换后的 ATIF-v1.7 轨迹；
- `kimi-code-home/`：该次运行使用的 Kimi Code 配置与运行数据目录。

`trajectory.json` 会尽可能保留：

- assistant 消息；
- tool call 名称、参数和调用 ID；
- tool result；
- session ID；
- Kimi Code 输出中提供的 token 和成本指标。

如果当前版本的 Kimi Code 没有在 `stream-json` 中输出 token 或成本信息，对应
字段会留空，不影响代码修改和 verifier 评测。

## 网络白名单

适配器根据以下环境变量自动生成 Pier 网络白名单：

- `KIMI_MODEL_BASE_URL`；
- `KIMI_CODE_BASE_URL`；
- `KIMI_WEB_SEARCH_BASE_URL`；
- `KIMI_WEB_FETCH_BASE_URL`。

未显式配置模型服务地址时，默认允许访问 `api.moonshot.ai`。使用 Kimi Coding
服务时，通常应配置：

```bash
export KIMI_MODEL_BASE_URL=https://api.kimi.com/coding/v1
```

## 使用其他 Kimi Code 版本

通过 `--agent-kwarg` 指定版本：

```bash
--agent-kwarg version=0.30.0
```

版本值会经过安全校验，并被用于 npm 安装命令和 Pier 安装指纹。升级版本后，
建议先运行本目录的测试，再选择一个任务进行 smoke test。

## 运行测试

```bash
cd /Users/kgm/Projects/merico/deep-swe

PYTHONDONTWRITEBYTECODE=1 \
  /Users/kgm/.local/share/uv/tools/datacurve-pier/bin/python \
  -m unittest -v wip.agents.test_kimi_code_agent
```

运行 Ruff 检查：

```bash
PYENV_VERSION=dc ruff check wip/agents
PYENV_VERSION=dc ruff format --check wip/agents
```

这些测试不会调用真实模型，也不会消耗 Kimi API 额度。

## 常见问题

### 为什么不能只写一个 Node.js 适配器？

Kimi Code 的执行部分已经是 Node.js。当前 Pier 的自定义 Agent 扩展点要求传入
Python 类，例如：

```text
wip.agents.kimi_code_agent:KimiCodeAgent
```

因此仍需要 Python 适配层。如果未来 Pier 支持以外部进程或 JavaScript 模块作为
Agent 插件，可以再把生命周期适配部分迁移到 Node.js。

### 是否会为每次 attempt 重新安装 Kimi Code？

不会。安装发生在 Docker 镜像构建阶段。同一任务只要基础镜像、Kimi Code 版本
和安装步骤没有变化，后续 attempt 会命中缓存。

### 为什么没有生成 token 或成本数据？

适配器只能记录 Kimi Code `stream-json` 实际提供的数据。Kimi Code 0.30.0 的
部分执行路径不会输出 usage 事件，此时 Pier 仍可正常保存轨迹并运行 verifier。

### 如何先验证配置而不运行完整样本集？

先运行 `tengo-destructuring-bindings` 单任务，确认：

1. 派生镜像构建成功；
2. Kimi Code API 鉴权成功；
3. Agent 能修改任务仓库；
4. verifier 能正常给出结果；
5. trial 日志中存在 `kimi-code.jsonl` 和 `trajectory.json`。

确认单任务工作正常后，再运行 `05_sample_dev.txt` 中的全部任务。
