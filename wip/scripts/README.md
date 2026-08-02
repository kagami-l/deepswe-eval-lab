# WIP 脚本

## 用共享 mini-swe-agent runtime 运行评测

`wip/scripts/run_mini_swe_eval.sh` 默认使用只读共享 runtime 镜像。第一次运行
构建一次固定版本的 runtime，之后不同任务、attempt 和 job 都直接复用，不再
重复构建 Python 依赖层。设计、兼容回退模式和 Docker 要求见
`wip/docs/mini-swe-shared-runtime.md`。

## 用 Codex 运行筛选样本

`wip/scripts/run_codex_eval.sh` 会读取任务 ID 列表，将其转换为 Pier 的任务过滤参数，并在 Docker 中运行 Codex 和独立 verifier。默认运行 `05_sample_dev.txt`，每题 1 次、并发 2：

```bash
wip/scripts/run_codex_eval.sh
```

先校验输入并查看最终命令：

```bash
wip/scripts/run_codex_eval.sh --dry-run
```

指定其他任务列表或运行配置：

```bash
wip/scripts/run_codex_eval.sh \
  --task-list wip/data/selection/05_sample_confirm.txt \
  --codex-version 0.146.0 \
  --model openai/gpt-5.6-sol \
  --job-name codex-confirm-k4
```

脚本默认使用宿主机 `codex login` 生成的 `~/.codex/auth.json`。同一任务和同一 Codex 安装配置会复用 Docker 构建缓存；不要为常规评测追加 `--force-build`。
