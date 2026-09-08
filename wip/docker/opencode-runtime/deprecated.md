# 已弃用

本目录的 shared runtime 镜像只服务旧的 OpenCode watchdog adapter
（`wip/agents/opencode_watchdog_agent.py`），其启动脚本 `wip/scripts/run_opencode_eval.sh`
已于 2026-09-08 移除。Dockerfile 保留作记录，不再维护。统一 Agent runtime 镜像由
`wip/docker/agent-runtime/` 和 `run_agent_eval.py runtime prepare` 提供。
详情见 [`../../agents/deprecated.md`](../../agents/deprecated.md)。
