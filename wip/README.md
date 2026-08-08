# WIP 开发环境

`wip` 下的 Python 实验代码使用独立的 uv 项目环境。该环境负责固定 Python 版本和
项目自身的第三方依赖。评测 CLI（`eval`）通过子进程调用全局 `uv tool` 安装的
`pier` 运行 job。

本地环境同时固定 `datacurve-pier==0.3.0`，因为 `score-patches` 的事后评分需要在
进程内导入 Pier，复用其 separate-verifier 评分路径给已冻结的 patch 打分（见
[事后配对评分设计](docs/collab-paired-checkpoint-verification-design.md)）。
版本被钉死并在启动时校验：Python package 版本、外部 `pier --version` 与所依赖的
私有接口签名任一不符即 fail closed。升级 Pier 时必须同步更新该固定版本。

首次准备或依赖变更后执行：

```bash
cd wip
uv sync
```

Python 脚本、测试和工具统一通过项目环境运行：

```bash
uv run python scripts/run_agent_eval.py --help
uv run python -m unittest discover -s agent_eval -t .. -p 'test_*.py'
uv run ruff check .
```

这些命令应在 `wip` 目录执行，因此不需要重复传 `--project wip`。如果从仓库根目录
直接执行，仍需使用 `--project wip`，因为 uv 不会向子目录搜索项目。

项目虚拟环境位于 `wip/.venv`，uv 下载缓存位于 `wip/.uv-cache`；两者都不会提交。
本地单元测试包含 Pier adapter 的契约测试（版本固定、私有接口签名守卫），它们只导入
Pier、不启动容器；真正启动 verifier 环境的评分仍属集成行为，由 `score-patches`
在真实 job 上执行，不在单元测试中运行。

统一 Agent runtime 的 Node 依赖由
`wip/agents/deep_swe_agent/runtime/package.json` 和 `package-lock.json` 管理，安装在同目录的
`node_modules`：

```bash
npm --prefix agents/deep_swe_agent/runtime ci
npm --prefix agents/deep_swe_agent/runtime test
```
