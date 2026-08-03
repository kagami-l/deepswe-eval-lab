# WIP 开发环境

`wip` 下的 Python 实验代码使用独立的 uv 项目环境。该环境负责固定 Python 版本和
项目自身的第三方依赖，不重复安装 Pier。评测 CLI 通过子进程调用全局 `uv tool`
安装的 `pier`。

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
由于本地环境不安装 `datacurve-pier`，直接导入 `pier` 的 adapter/environment 测试仍
属于 Pier 工具侧集成测试，不包含在上面的本地单元测试命令中。

统一 Agent runtime 的 Node 依赖由
`wip/agents/deep_swe_agent/runtime/package.json` 和 `package-lock.json` 管理，安装在同目录的
`node_modules`：

```bash
npm --prefix agents/deep_swe_agent/runtime ci
npm --prefix agents/deep_swe_agent/runtime test
```
