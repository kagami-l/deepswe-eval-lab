#!/usr/bin/env bash

# Run every task listed in 05_sample_dev.txt with the Pier KimiCodeAgent.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

TASK_LIST="${KIMI_TASK_LIST:-$REPO_ROOT/wip/data/selection/05_sample_dev.txt}"
TASKS_DIR="${PIER_TASKS_DIR:-$REPO_ROOT/tasks}"
PIER_BIN="${PIER_BIN:-pier}"
PIER_JOB_NAME="${PIER_JOB_NAME:-kimi-code-sample-dev}"
PIER_N_CONCURRENT="${PIER_N_CONCURRENT:-2}"
KIMI_CODE_VERSION="${KIMI_CODE_VERSION:-0.30.0}"

usage() {
  cat <<'EOF'
用 Pier 和 KimiCodeAgent 运行 05_sample_dev.txt 中的全部任务。

用法：
  wip/scripts/run_kimi_sample_dev.sh [--dry-run] [额外的 pier run 参数...]

必需环境变量：
  KIMI_MODEL_NAME              Kimi Code 使用的模型名称，例如 k3
  KIMI_MODEL_API_KEY           Kimi Code API Key

可选环境变量：
  KIMI_MODEL_BASE_URL          默认：https://api.kimi.com/coding/v1
  KIMI_MODEL_MAX_CONTEXT_SIZE  默认：1048576
  KIMI_CODE_VERSION            默认：0.30.0
  KIMI_TASK_LIST               默认：wip/data/selection/05_sample_dev.txt
  PIER_TASKS_DIR               默认：tasks
  PIER_JOB_NAME                默认：kimi-code-sample-dev
  PIER_N_CONCURRENT            默认：2
  PIER_MODEL_LABEL             默认：kimi-code/$KIMI_MODEL_NAME
  PIER_BIN                     默认：pier

示例：
  export KIMI_MODEL_NAME=k3
  export KIMI_MODEL_API_KEY='你的 API Key'
  wip/scripts/run_kimi_sample_dev.sh

传给脚本的其他参数会原样追加到 pier run 命令末尾，例如：
  wip/scripts/run_kimi_sample_dev.sh --n-attempts 2 --debug
EOF
}

DRY_RUN=0
case "${1:-}" in
  -h|--help)
    usage
    exit 0
    ;;
  --dry-run)
    DRY_RUN=1
    shift
    ;;
esac

if ! command -v "$PIER_BIN" >/dev/null 2>&1; then
  echo "错误：找不到 Pier 命令：$PIER_BIN" >&2
  exit 1
fi

if [[ -z "${KIMI_MODEL_NAME:-}" ]]; then
  echo "错误：必须设置 KIMI_MODEL_NAME，例如：export KIMI_MODEL_NAME=k3" >&2
  exit 1
fi

if [[ -z "${KIMI_MODEL_API_KEY:-}" ]]; then
  echo "错误：必须设置 KIMI_MODEL_API_KEY。" >&2
  exit 1
fi

if [[ ! "$PIER_N_CONCURRENT" =~ ^[1-9][0-9]*$ ]]; then
  echo "错误：PIER_N_CONCURRENT 必须是正整数，当前值：$PIER_N_CONCURRENT" >&2
  exit 1
fi

if [[ ! "$KIMI_CODE_VERSION" =~ ^[0-9A-Za-z][0-9A-Za-z._+-]*$ ]]; then
  echo "错误：KIMI_CODE_VERSION 格式不合法：$KIMI_CODE_VERSION" >&2
  exit 1
fi

if [[ ! -f "$TASK_LIST" ]]; then
  echo "错误：任务列表不存在：$TASK_LIST" >&2
  exit 1
fi

if [[ ! -d "$TASKS_DIR" ]]; then
  echo "错误：任务目录不存在：$TASKS_DIR" >&2
  exit 1
fi

export KIMI_MODEL_NAME
export KIMI_MODEL_API_KEY
export KIMI_MODEL_BASE_URL="${KIMI_MODEL_BASE_URL:-https://api.kimi.com/coding/v1}"
export KIMI_MODEL_MAX_CONTEXT_SIZE="${KIMI_MODEL_MAX_CONTEXT_SIZE:-1048576}"

PIER_MODEL_LABEL="${PIER_MODEL_LABEL:-kimi-code/$KIMI_MODEL_NAME}"
include_args=()
task_count=0

while IFS= read -r task || [[ -n "$task" ]]; do
  task="${task%$'\r'}"
  if [[ -z "${task//[[:space:]]/}" || "$task" =~ ^[[:space:]]*# ]]; then
    continue
  fi
  if [[ "$task" =~ [[:space:]] ]]; then
    echo "错误：任务名称不能包含空白字符：$task" >&2
    exit 1
  fi
  if [[ ! -d "$TASKS_DIR/$task" ]]; then
    echo "错误：任务列表中的目录不存在：$TASKS_DIR/$task" >&2
    exit 1
  fi
  include_args+=(--include-task-name "$task")
  task_count=$((task_count + 1))
done < "$TASK_LIST"

if [[ "$task_count" -eq 0 ]]; then
  echo "错误：任务列表为空：$TASK_LIST" >&2
  exit 1
fi

command=(
  "$PIER_BIN" run
  -p "$TASKS_DIR"
  "${include_args[@]}"
  --job-name "$PIER_JOB_NAME"
  --n-concurrent "$PIER_N_CONCURRENT"
  --agent-import-path wip.agents.kimi_code_agent:KimiCodeAgent
  --model "$PIER_MODEL_LABEL"
  --agent-kwarg "version=$KIMI_CODE_VERSION"
  --agent-env 'KIMI_MODEL_NAME=${KIMI_MODEL_NAME}'
  --agent-env 'KIMI_MODEL_API_KEY=${KIMI_MODEL_API_KEY}'
  --agent-env 'KIMI_MODEL_BASE_URL=${KIMI_MODEL_BASE_URL}'
  --agent-env 'KIMI_MODEL_MAX_CONTEXT_SIZE=${KIMI_MODEL_MAX_CONTEXT_SIZE}'
  "$@"
)

echo "即将运行 $task_count 个任务："
echo "  任务列表：$TASK_LIST"
echo "  Job 名称：$PIER_JOB_NAME"
echo "  并发数：$PIER_N_CONCURRENT"
echo "  模型：$KIMI_MODEL_NAME"
echo "  Kimi Code：$KIMI_CODE_VERSION"

cd "$REPO_ROOT"

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf '命令：'
  printf ' %q' "${command[@]}"
  printf '\n'
  exit 0
fi

exec "${command[@]}"
