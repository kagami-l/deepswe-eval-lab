#!/usr/bin/env bash

# Run a task list with Pier's containerized mini-swe-agent and DeepSWE verifier.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

TASK_LIST="$REPO_ROOT/wip/data/selection/05_sample_dev.txt"
TASKS_DIR="${PIER_TASKS_DIR:-$REPO_ROOT/tasks}"
JOBS_DIR="${PIER_JOBS_DIR:-$REPO_ROOT/jobs}"
PIER_BIN="${PIER_BIN:-pier}"
MINI_SWE_MODEL="${MINI_SWE_MODEL:-deepseek/deepseek-v4-pro}"
MINI_SWE_AGENT_VERSION="${MINI_SWE_AGENT_VERSION:-2.4.6}"
MINI_SWE_COST_LIMIT="${MINI_SWE_COST_LIMIT:-0}"
MINI_SWE_REASONING_EFFORT="${MINI_SWE_REASONING_EFFORT:-}"
MINI_SWE_PYPI_INDEX="${MINI_SWE_PYPI_INDEX:-https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple}"
MINI_SWE_ENV_FILE="${MINI_SWE_ENV_FILE:-$SCRIPT_DIR/.env}"
PIER_N_ATTEMPTS="${PIER_N_ATTEMPTS:-1}"
PIER_N_CONCURRENT="${PIER_N_CONCURRENT:-2}"
PIER_JOB_NAME="${PIER_JOB_NAME:-}"

usage() {
  cat <<'EOF'
用 Pier 的容器内 mini-swe-agent 执行任务列表，并运行 DeepSWE verifier 评测。

用法：
  wip/scripts/run_mini_swe_eval.sh [选项] [-- 额外的 pier run 参数...]

选项：
  -t, --task-list PATH            任务 ID 列表；默认：05_sample_dev.txt
  -m, --model PROVIDER/MODEL      模型；默认：deepseek/deepseek-v4-pro
      --mini-swe-version VERSION  容器内 mini-swe-agent 版本；默认：2.4.6
      --pypi-index-url URL        安装依赖的 PyPI 源；默认：清华镜像
      --cost-limit USD            mini-swe-agent cost limit；默认：0（不限制）
      --reasoning-effort LEVEL    可选的模型 reasoning effort
  -k, --n-attempts N              每个任务的重复次数；默认：1
  -n, --n-concurrent N            并发 trial 数；默认：2
  -o, --jobs-dir PATH             结果目录；默认：仓库根目录下的 jobs
      --job-name NAME             Job 名称；默认自动包含模型、样本名和时间
      --dry-run                   校验输入并打印命令，不启动评测
  -h, --help                      显示帮助

DeepSeek 官方认证：
  默认模型的 provider 前缀是 deepseek，mini-swe-agent/LiteLLM 会直接访问
  api.deepseek.com，并读取 DEEPSEEK_API_KEY。脚本按以下顺序查找 key：
    1. 当前环境变量 DEEPSEEK_API_KEY
    2. wip/scripts/.env（可用 MINI_SWE_ENV_FILE 指定其他文件）

  .env 只按 KEY=VALUE 读取，不会被 source 或执行。建议 CI/批量环境直接注入
  DEEPSEEK_API_KEY，本机临时使用再放入已被 gitignore 的 .env。

可选环境变量：
  MINI_SWE_MODEL、MINI_SWE_AGENT_VERSION、MINI_SWE_COST_LIMIT
  MINI_SWE_REASONING_EFFORT、MINI_SWE_PYPI_INDEX、MINI_SWE_ENV_FILE
  PIER_TASKS_DIR、PIER_JOBS_DIR、PIER_JOB_NAME
  PIER_N_ATTEMPTS、PIER_N_CONCURRENT、PIER_BIN

示例：
  wip/scripts/run_mini_swe_eval.sh --dry-run

  wip/scripts/run_mini_swe_eval.sh \
    --task-list wip/one_task.txt \
    --n-attempts 1 --n-concurrent 1

  MINI_SWE_AGENT_VERSION="$TESTED_MINI_SWE_VERSION" \
    wip/scripts/run_mini_swe_eval.sh -- --debug
EOF
}

die() {
  echo "错误：$*" >&2
  exit 1
}

is_positive_integer() {
  [[ "$1" =~ ^[1-9][0-9]*$ ]]
}

is_nonnegative_number() {
  [[ "$1" =~ ^[0-9]+([.][0-9]+)?$ ]]
}

# Read one literal KEY=VALUE entry without executing the dotenv file.
read_key_from_dotenv() {
  local want="$1" line key value
  [[ -f "$MINI_SWE_ENV_FILE" ]] || return 1

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
    [[ "$key" == "$want" ]] || continue

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
    [[ -n "$value" ]] || return 1
    printf '%s' "$value"
    return 0
  done < "$MINI_SWE_ENV_FILE"
  return 1
}

DRY_RUN=0
PIER_ARGS=()

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
      [[ "$#" -ge 2 && -n "$2" ]] || die "$1 需要一个任务列表路径"
      TASK_LIST="$2"
      shift 2
      ;;
    --task-list=*)
      TASK_LIST="${1#*=}"
      [[ -n "$TASK_LIST" ]] || die "--task-list 需要一个任务列表路径"
      shift
      ;;
    -m|--model)
      [[ "$#" -ge 2 && -n "$2" ]] || die "$1 需要一个模型名称"
      MINI_SWE_MODEL="$2"
      shift 2
      ;;
    --model=*)
      MINI_SWE_MODEL="${1#*=}"
      [[ -n "$MINI_SWE_MODEL" ]] || die "--model 需要一个模型名称"
      shift
      ;;
    --mini-swe-version)
      [[ "$#" -ge 2 && -n "$2" ]] || die "$1 需要一个版本号"
      MINI_SWE_AGENT_VERSION="$2"
      shift 2
      ;;
    --mini-swe-version=*)
      MINI_SWE_AGENT_VERSION="${1#*=}"
      [[ -n "$MINI_SWE_AGENT_VERSION" ]] || die "--mini-swe-version 需要一个版本号"
      shift
      ;;
    --pypi-index-url)
      [[ "$#" -ge 2 && -n "$2" ]] || die "$1 需要一个 URL"
      MINI_SWE_PYPI_INDEX="$2"
      shift 2
      ;;
    --pypi-index-url=*)
      MINI_SWE_PYPI_INDEX="${1#*=}"
      [[ -n "$MINI_SWE_PYPI_INDEX" ]] || die "--pypi-index-url 需要一个 URL"
      shift
      ;;
    --cost-limit)
      [[ "$#" -ge 2 && -n "$2" ]] || die "$1 需要一个非负数字"
      MINI_SWE_COST_LIMIT="$2"
      shift 2
      ;;
    --cost-limit=*)
      MINI_SWE_COST_LIMIT="${1#*=}"
      shift
      ;;
    --reasoning-effort)
      [[ "$#" -ge 2 && -n "$2" ]] || die "$1 需要一个 reasoning effort"
      MINI_SWE_REASONING_EFFORT="$2"
      shift 2
      ;;
    --reasoning-effort=*)
      MINI_SWE_REASONING_EFFORT="${1#*=}"
      [[ -n "$MINI_SWE_REASONING_EFFORT" ]] || die "--reasoning-effort 不能为空"
      shift
      ;;
    -k|--n-attempts)
      [[ "$#" -ge 2 && -n "$2" ]] || die "$1 需要一个正整数"
      PIER_N_ATTEMPTS="$2"
      shift 2
      ;;
    --n-attempts=*)
      PIER_N_ATTEMPTS="${1#*=}"
      shift
      ;;
    -n|--n-concurrent)
      [[ "$#" -ge 2 && -n "$2" ]] || die "$1 需要一个正整数"
      PIER_N_CONCURRENT="$2"
      shift 2
      ;;
    --n-concurrent=*)
      PIER_N_CONCURRENT="${1#*=}"
      shift
      ;;
    -o|--jobs-dir)
      [[ "$#" -ge 2 && -n "$2" ]] || die "$1 需要一个目录路径"
      JOBS_DIR="$2"
      shift 2
      ;;
    --jobs-dir=*)
      JOBS_DIR="${1#*=}"
      [[ -n "$JOBS_DIR" ]] || die "--jobs-dir 需要一个目录路径"
      shift
      ;;
    --job-name)
      [[ "$#" -ge 2 && -n "$2" ]] || die "$1 需要一个名称"
      PIER_JOB_NAME="$2"
      shift 2
      ;;
    --job-name=*)
      PIER_JOB_NAME="${1#*=}"
      [[ -n "$PIER_JOB_NAME" ]] || die "--job-name 需要一个名称"
      shift
      ;;
    --)
      shift
      PIER_ARGS+=("$@")
      break
      ;;
    *)
      die "未知选项：$1（额外的 Pier 参数请放在 -- 之后）"
      ;;
  esac
done

command -v "$PIER_BIN" >/dev/null 2>&1 || die "找不到 Pier 命令：$PIER_BIN"
[[ -f "$TASK_LIST" ]] || die "任务列表不存在：$TASK_LIST"
[[ -d "$TASKS_DIR" ]] || die "任务目录不存在：$TASKS_DIR"
is_positive_integer "$PIER_N_ATTEMPTS" || die "PIER_N_ATTEMPTS 必须是正整数：$PIER_N_ATTEMPTS"
is_positive_integer "$PIER_N_CONCURRENT" || die "PIER_N_CONCURRENT 必须是正整数：$PIER_N_CONCURRENT"
is_nonnegative_number "$MINI_SWE_COST_LIMIT" || \
  die "MINI_SWE_COST_LIMIT 必须是非负数字：$MINI_SWE_COST_LIMIT"
[[ -z "$MINI_SWE_AGENT_VERSION" || "$MINI_SWE_AGENT_VERSION" =~ ^[0-9A-Za-z][0-9A-Za-z._+-]*$ ]] || \
  die "MINI_SWE_AGENT_VERSION 格式不合法：$MINI_SWE_AGENT_VERSION"
[[ "$MINI_SWE_REASONING_EFFORT" != *[[:space:]]* ]] || \
  die "MINI_SWE_REASONING_EFFORT 不能包含空白字符"
[[ "$MINI_SWE_MODEL" == */* ]] || \
  die "模型必须是 provider/model 格式，例如 deepseek/deepseek-v4-pro：$MINI_SWE_MODEL"
[[ "$MINI_SWE_PYPI_INDEX" =~ ^https?://[^[:space:]]+$ ]] || \
  die "MINI_SWE_PYPI_INDEX 必须是 HTTP(S) URL：$MINI_SWE_PYPI_INDEX"

provider="${MINI_SWE_MODEL%%/*}"
api_key_var=""
case "$provider" in
  anthropic) api_key_var="ANTHROPIC_API_KEY" ;;
  deepseek) api_key_var="DEEPSEEK_API_KEY" ;;
  gemini|google) api_key_var="GEMINI_API_KEY" ;;
  groq) api_key_var="GROQ_API_KEY" ;;
  mistral) api_key_var="MISTRAL_API_KEY" ;;
  openai) api_key_var="OPENAI_API_KEY" ;;
  openrouter) api_key_var="OPENROUTER_API_KEY" ;;
  xai) api_key_var="XAI_API_KEY" ;;
esac

if [[ -z "$api_key_var" ]]; then
  die "暂不认识 provider '$provider' 的认证变量；请扩展脚本映射或使用已支持的 provider"
fi

auth_description=""
if [[ -n "${!api_key_var:-}" ]]; then
  auth_description="${api_key_var}（环境变量）"
elif value="$(read_key_from_dotenv "$api_key_var")"; then
  export "$api_key_var=$value"
  auth_description="${api_key_var}（${MINI_SWE_ENV_FILE}）"
else
  die "未找到 $provider 所需的 ${api_key_var}；请设置环境变量或写入 ${MINI_SWE_ENV_FILE}"
fi

include_args=()
task_count=0
while IFS= read -r task || [[ -n "$task" ]]; do
  task="${task%$'\r'}"
  task="${task#"${task%%[![:space:]]*}"}"
  task="${task%"${task##*[![:space:]]}"}"
  [[ -z "$task" || "$task" == \#* ]] && continue
  [[ "$task" != *[[:space:]]* ]] || die "任务名称不能包含空白字符：$task"
  [[ -f "$TASKS_DIR/$task/task.toml" ]] || \
    die "任务不存在或缺少 task.toml：$TASKS_DIR/$task"
  include_args+=(--include-task-name "$task")
  task_count=$((task_count + 1))
done < "$TASK_LIST"

[[ "$task_count" -gt 0 ]] || die "任务列表为空：$TASK_LIST"

if [[ -z "$PIER_JOB_NAME" ]]; then
  sample_name="$(basename "$TASK_LIST")"
  sample_name="${sample_name%.*}"
  model_name="${MINI_SWE_MODEL##*/}"
  safe_model_name="${model_name//[^[:alnum:]._-]/-}"
  PIER_JOB_NAME="mini-swe-${safe_model_name}-${sample_name}-$(date +%Y%m%d-%H%M%S)"
fi

command=(
  "$PIER_BIN" run
  --path "$TASKS_DIR"
  "${include_args[@]}"
  --agent-import-path wip.agents.mini_swe_agent:OptimizedMiniSweAgent
  --model "$MINI_SWE_MODEL"
  --agent-kwarg "cost_limit=$MINI_SWE_COST_LIMIT"
  --agent-kwarg "pypi_index_url=$MINI_SWE_PYPI_INDEX"
)

if [[ -n "$MINI_SWE_AGENT_VERSION" ]]; then
  command+=(--agent-kwarg "version=$MINI_SWE_AGENT_VERSION")
fi

if [[ -n "$MINI_SWE_REASONING_EFFORT" ]]; then
  command+=(--agent-kwarg "reasoning_effort=$MINI_SWE_REASONING_EFFORT")
fi

command+=(
  --env docker
  --enable-verification
  --no-force-build
  --delete
  --n-attempts "$PIER_N_ATTEMPTS"
  --n-concurrent "$PIER_N_CONCURRENT"
  --job-name "$PIER_JOB_NAME"
  --jobs-dir "$JOBS_DIR"
)

if [[ "${#PIER_ARGS[@]}" -gt 0 ]]; then
  command+=("${PIER_ARGS[@]}")
fi

echo "即将使用容器内 mini-swe-agent 运行 $task_count 个任务："
echo "  任务列表：$TASK_LIST"
echo "  Job 名称：$PIER_JOB_NAME"
echo "  结果目录：$JOBS_DIR/$PIER_JOB_NAME"
echo "  模型：$MINI_SWE_MODEL"
echo "  Provider：${provider}（默认 endpoint 由 LiteLLM provider 决定）"
echo "  mini-swe-agent：${MINI_SWE_AGENT_VERSION}（优化安装 adapter）"
echo "  PyPI：$MINI_SWE_PYPI_INDEX"
echo "  Cost limit：$MINI_SWE_COST_LIMIT"
if [[ -n "$MINI_SWE_REASONING_EFFORT" ]]; then
  echo "  Reasoning effort：$MINI_SWE_REASONING_EFFORT"
fi
echo "  Attempts：$PIER_N_ATTEMPTS"
echo "  并发数：$PIER_N_CONCURRENT"
echo "  认证：$auth_description"
echo "  Docker 构建缓存：启用"

cd "$REPO_ROOT"

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf '命令：'
  printf ' %q' "${command[@]}"
  printf '\n'
  exit 0
fi

exec "${command[@]}"
