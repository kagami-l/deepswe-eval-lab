#!/usr/bin/env bash

# Run every task listed in 05_sample_dev.txt with the Pier KimiCodeAgent.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

TASK_LIST="$REPO_ROOT/wip/data/selection/05_sample_dev.txt"
TASKS_DIR="${PIER_TASKS_DIR:-$REPO_ROOT/tasks}"
ENV_FILE="${KIMI_ENV_FILE:-$SCRIPT_DIR/.env}"
PIER_BIN="${PIER_BIN:-pier}"
PIER_JOB_NAME="${PIER_JOB_NAME:-}"
KIMI_CODE_VERSION="${KIMI_CODE_VERSION:-0.30.0}"
N_CONCURRENT=2
N_ATTEMPTS=1

usage() {
  cat <<'EOF'
用 Pier 和 KimiCodeAgent 运行 05_sample_dev.txt 中的全部任务。

用法：
  wip/scripts/run_kimi_sample_dev.sh [选项] [额外的 pier run 参数...]

选项：
  -t, --task-list PATH         指定任务列表文件
  -n, --n-concurrent N         并发运行的 trial 数量，默认：2
  -k, --n-attempts N           每个 trial 的尝试次数，默认：1
      --job-name NAME          Job 名称；默认包含 agent、模型、样本名和时间
      --dry-run               只打印最终命令，不启动评测
  -h, --help                  显示帮助

必需环境变量：
  KIMI_MODEL_API_KEY           Kimi Code API Key；也可写入 wip/scripts/.env

可选环境变量：
  KIMI_MODEL_NAME              默认：k3
  KIMI_MODEL_BASE_URL          默认：https://api.kimi.com/coding/v1
  KIMI_MODEL_MAX_CONTEXT_SIZE  默认：1048576
  KIMI_CODE_VERSION            默认：0.30.0
  KIMI_ENV_FILE                默认：wip/scripts/.env
  PIER_TASKS_DIR               默认：tasks
  PIER_JOB_NAME                设置 Job 名称；默认自动生成
  PIER_MODEL_LABEL             默认：kimi-code/$KIMI_MODEL_NAME
  PIER_BIN                     默认：pier

示例：
  export KIMI_MODEL_API_KEY='你的 API Key'
  wip/scripts/run_kimi_sample_dev.sh

  wip/scripts/run_kimi_sample_dev.sh \
    --task-list wip/data/selection/05_sample_confirm.txt \
    --n-concurrent 4 \
    --n-attempts 2 \
    --job-name kimi-code-k3-confirm

传给脚本的其他参数会原样追加到 pier run 命令末尾，例如：
  wip/scripts/run_kimi_sample_dev.sh --debug
EOF
}

DRY_RUN=0
PIER_ARGS=()
HAS_PIER_ARGS=0
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -t|--task-list)
      if [[ "$#" -lt 2 || -z "$2" ]]; then
        echo "错误：$1 需要一个任务列表路径。" >&2
        exit 1
      fi
      TASK_LIST="$2"
      shift 2
      ;;
    --task-list=*)
      TASK_LIST="${1#*=}"
      if [[ -z "$TASK_LIST" ]]; then
        echo "错误：--task-list 需要一个任务列表路径。" >&2
        exit 1
      fi
      shift
      ;;
    -n|--n-concurrent)
      if [[ "$#" -lt 2 || -z "$2" ]]; then
        echo "错误：$1 需要一个正整数。" >&2
        exit 1
      fi
      N_CONCURRENT="$2"
      shift 2
      ;;
    --n-concurrent=*)
      N_CONCURRENT="${1#*=}"
      shift
      ;;
    -k|--n-attempts)
      if [[ "$#" -lt 2 || -z "$2" ]]; then
        echo "错误：$1 需要一个正整数。" >&2
        exit 1
      fi
      N_ATTEMPTS="$2"
      shift 2
      ;;
    --n-attempts=*)
      N_ATTEMPTS="${1#*=}"
      shift
      ;;
    --job-name)
      if [[ "$#" -lt 2 || -z "$2" ]]; then
        echo "错误：$1 需要一个名称。" >&2
        exit 1
      fi
      PIER_JOB_NAME="$2"
      shift 2
      ;;
    --job-name=*)
      PIER_JOB_NAME="${1#*=}"
      if [[ -z "$PIER_JOB_NAME" ]]; then
        echo "错误：--job-name 需要一个名称。" >&2
        exit 1
      fi
      shift
      ;;
    --)
      shift
      if [[ "$#" -gt 0 ]]; then
        PIER_ARGS+=("$@")
        HAS_PIER_ARGS=1
      fi
      break
      ;;
    *)
      PIER_ARGS+=("$1")
      HAS_PIER_ARGS=1
      shift
      ;;
  esac
done

load_api_key_from_dotenv() {
  local line key value
  [[ -n "${KIMI_MODEL_API_KEY:-}" || ! -f "$ENV_FILE" ]] && return

  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    line="${line#"${line%%[![:space:]]*}"}"
    [[ -z "$line" || "$line" == \#* ]] && continue

    if [[ "$line" == export[[:space:]]* ]]; then
      line="${line#export}"
      line="${line#"${line%%[![:space:]]*}"}"
    fi
    [[ "$line" == *=* ]] || continue

    key="${line%%=*}"
    key="${key%"${key##*[![:space:]]}"}"
    [[ "$key" == "KIMI_MODEL_API_KEY" ]] || continue

    value="${line#*=}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    if [[ ${#value} -ge 2 ]]; then
      if [[ "${value:0:1}" == '"' && "${value: -1}" == '"' ]]; then
        value="${value:1:${#value}-2}"
      elif [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
        value="${value:1:${#value}-2}"
      fi
    fi
    KIMI_MODEL_API_KEY="$value"
    export KIMI_MODEL_API_KEY
    return
  done < "$ENV_FILE"
}

load_api_key_from_dotenv

if ! command -v "$PIER_BIN" >/dev/null 2>&1; then
  echo "错误：找不到 Pier 命令：$PIER_BIN" >&2
  exit 1
fi

if [[ -z "${KIMI_MODEL_API_KEY:-}" ]]; then
  echo "错误：必须设置 KIMI_MODEL_API_KEY，或将其写入 $ENV_FILE。" >&2
  exit 1
fi

if [[ ! "$N_CONCURRENT" =~ ^[1-9][0-9]*$ ]]; then
  echo "错误：--n-concurrent 必须是正整数，当前值：$N_CONCURRENT" >&2
  exit 1
fi

if [[ ! "$N_ATTEMPTS" =~ ^[1-9][0-9]*$ ]]; then
  echo "错误：--n-attempts 必须是正整数，当前值：$N_ATTEMPTS" >&2
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

export KIMI_MODEL_NAME="${KIMI_MODEL_NAME:-k3}"
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

if [[ -z "$PIER_JOB_NAME" ]]; then
  sample_name="$(basename "$TASK_LIST")"
  sample_name="${sample_name%.*}"
  model_name="${KIMI_MODEL_NAME##*/}"
  safe_model_name="${model_name//[^[:alnum:]._-]/-}"
  safe_sample_name="${sample_name//[^[:alnum:]._-]/-}"
  PIER_JOB_NAME="kimi-code-${safe_model_name}-${safe_sample_name}-$(date +%Y%m%d-%H%M%S)"
fi

command=(
  "$PIER_BIN" run
  -p "$TASKS_DIR"
  "${include_args[@]}"
  --job-name "$PIER_JOB_NAME"
  --n-concurrent "$N_CONCURRENT"
  --n-attempts "$N_ATTEMPTS"
  --agent-import-path wip.agents.kimi_code_agent:KimiCodeAgent
  --model "$PIER_MODEL_LABEL"
  --agent-kwarg "version=$KIMI_CODE_VERSION"
  --agent-env 'KIMI_MODEL_NAME=${KIMI_MODEL_NAME}'
  --agent-env 'KIMI_MODEL_API_KEY=${KIMI_MODEL_API_KEY}'
  --agent-env 'KIMI_MODEL_BASE_URL=${KIMI_MODEL_BASE_URL}'
  --agent-env 'KIMI_MODEL_MAX_CONTEXT_SIZE=${KIMI_MODEL_MAX_CONTEXT_SIZE}'
)

if [[ "$HAS_PIER_ARGS" -eq 1 ]]; then
  command+=("${PIER_ARGS[@]}")
fi

echo "即将运行 $task_count 个任务："
echo "  任务列表：$TASK_LIST"
echo "  Job 名称：$PIER_JOB_NAME"
echo "  并发数：$N_CONCURRENT"
echo "  每个 trial 的尝试次数：$N_ATTEMPTS"
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
