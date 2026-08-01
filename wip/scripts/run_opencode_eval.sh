#!/usr/bin/env bash

# Run a task list with Pier's containerized OpenCode agent and DeepSWE verifier.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

TASK_LIST="$REPO_ROOT/wip/data/selection/05_sample_dev.txt"
TASKS_DIR="${PIER_TASKS_DIR:-$REPO_ROOT/tasks}"
JOBS_DIR="${PIER_JOBS_DIR:-$REPO_ROOT/jobs}"
PIER_BIN="${PIER_BIN:-pier}"
OPENCODE_MODEL="${OPENCODE_MODEL:-deepseek/deepseek-v4-pro}"
OPENCODE_VERSION="${OPENCODE_VERSION:-1.18.10}"
OPENCODE_VARIANT="${OPENCODE_VARIANT:-}"
PIER_N_ATTEMPTS="${PIER_N_ATTEMPTS:-1}"
PIER_N_CONCURRENT="${PIER_N_CONCURRENT:-2}"
PIER_JOB_NAME="${PIER_JOB_NAME:-}"
ENV_FILE="${OPENCODE_ENV_FILE:-$SCRIPT_DIR/.env}"
OPENCODE_AUTH_JSON="${OPENCODE_AUTH_JSON:-$HOME/.local/share/opencode/auth.json}"

usage() {
  cat <<'EOF'
用 Pier 的容器内 OpenCode 执行任务列表，并运行 DeepSWE verifier 评测。

用法：
  wip/scripts/run_opencode_eval.sh [选项] [-- 额外的 pier run 参数...]

选项：
  -t, --task-list PATH           任务 ID 列表；默认：05_sample_dev.txt
  -m, --model PROVIDER/MODEL     模型；默认：deepseek/deepseek-v4-pro
      --opencode-version VERSION 容器内 opencode-ai 版本；默认：1.18.10
      --variant VARIANT          透传 opencode 的 --variant（可选）
  -k, --n-attempts N             每个任务的重复次数；默认：1
  -n, --n-concurrent N           并发 trial 数；默认：2
  -o, --jobs-dir PATH            结果目录；默认：仓库根目录下的 jobs
      --job-name NAME            Job 名称；默认自动包含模型、样本名和时间
      --dry-run                  校验输入并打印命令，不启动评测
  -h, --help                     显示帮助

认证：
  模型必须是 provider/model 格式，脚本按 provider 前缀确定所需的
  API Key（如 deepseek → DEEPSEEK_API_KEY），查找顺序：
    1. 当前环境变量
    2. wip/scripts/.env（可用 OPENCODE_ENV_FILE 指定其他文件）
    3. 本机 opencode 的 auth.json（默认 ~/.local/share/opencode/auth.json，
       可用 OPENCODE_AUTH_JSON 指定；即 opencode auth login 保存的 key）
  openai provider 额外支持 OPENAI_BASE_URL 指向自定义网关。

可选环境变量：
  OPENCODE_MODEL、OPENCODE_VERSION、OPENCODE_VARIANT
  OPENCODE_ENV_FILE、OPENCODE_AUTH_JSON
  PIER_TASKS_DIR、PIER_JOBS_DIR、PIER_JOB_NAME
  PIER_N_ATTEMPTS、PIER_N_CONCURRENT、PIER_BIN

示例：
  wip/scripts/run_opencode_eval.sh --dry-run

  wip/scripts/run_opencode_eval.sh \
    --task-list wip/data/selection/05_sample_confirm.txt \
    --job-name opencode-confirm-k4

  OPENAI_BASE_URL=https://gateway.example.com/v1 \
    wip/scripts/run_opencode_eval.sh -m openai/gpt-5.6-sol -- --debug
EOF
}

die() {
  echo "错误：$*" >&2
  exit 1
}

is_positive_integer() {
  [[ "$1" =~ ^[1-9][0-9]*$ ]]
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
      OPENCODE_MODEL="$2"
      shift 2
      ;;
    --model=*)
      OPENCODE_MODEL="${1#*=}"
      [[ -n "$OPENCODE_MODEL" ]] || die "--model 需要一个模型名称"
      shift
      ;;
    --opencode-version)
      [[ "$#" -ge 2 && -n "$2" ]] || die "$1 需要一个版本号"
      OPENCODE_VERSION="$2"
      shift 2
      ;;
    --opencode-version=*)
      OPENCODE_VERSION="${1#*=}"
      [[ -n "$OPENCODE_VERSION" ]] || die "--opencode-version 需要一个版本号"
      shift
      ;;
    --variant)
      [[ "$#" -ge 2 && -n "$2" ]] || die "$1 需要一个 variant 名称"
      OPENCODE_VARIANT="$2"
      shift 2
      ;;
    --variant=*)
      OPENCODE_VARIANT="${1#*=}"
      [[ -n "$OPENCODE_VARIANT" ]] || die "--variant 不能为空"
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
[[ "$OPENCODE_VERSION" =~ ^[0-9A-Za-z][0-9A-Za-z._+-]*$ ]] || \
  die "OPENCODE_VERSION 格式不合法：$OPENCODE_VERSION"
[[ "$OPENCODE_VARIANT" != *[[:space:]]* ]] || \
  die "OPENCODE_VARIANT 不能包含空白字符"
[[ "$OPENCODE_MODEL" == */* ]] || \
  die "模型必须是 provider/model 格式，例如 deepseek/deepseek-v4-pro：$OPENCODE_MODEL"

provider="${OPENCODE_MODEL%%/*}"

# 从 .env 文件读取指定的 key，找到则输出其值
read_key_from_dotenv() {
  local want="$1" line key value
  [[ -f "$ENV_FILE" ]] || return 1

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
    printf '%s' "$value"
    return 0
  done < "$ENV_FILE"
  return 1
}

# 从本机 opencode 的 auth.json 读取指定 provider 的 API Key
read_key_from_opencode_auth() {
  local provider_name="$1"
  [[ -f "$OPENCODE_AUTH_JSON" ]] || return 1
  python3 - "$OPENCODE_AUTH_JSON" "$provider_name" <<'PY'
import json
import sys

path, provider = sys.argv[1], sys.argv[2]
try:
    with open(path) as f:
        data = json.load(f)
except (OSError, ValueError):
    sys.exit(1)
entry = data.get(provider)
if not isinstance(entry, dict) or entry.get("type") != "api":
    sys.exit(1)
key = entry.get("key")
if not key:
    sys.exit(1)
sys.stdout.write(key)
PY
}

api_key_var=""
case "$provider" in
  anthropic) api_key_var="ANTHROPIC_API_KEY" ;;
  deepseek) api_key_var="DEEPSEEK_API_KEY" ;;
  github-copilot) api_key_var="GITHUB_TOKEN" ;;
  groq) api_key_var="GROQ_API_KEY" ;;
  huggingface) api_key_var="HF_TOKEN" ;;
  llama) api_key_var="LLAMA_API_KEY" ;;
  mistral) api_key_var="MISTRAL_API_KEY" ;;
  openai) api_key_var="OPENAI_API_KEY" ;;
  opencode) api_key_var="OPENCODE_API_KEY" ;;
  openrouter) api_key_var="OPENROUTER_API_KEY" ;;
  xai) api_key_var="XAI_API_KEY" ;;
esac

auth_description=""
if [[ -n "$api_key_var" ]]; then
  if [[ -n "${!api_key_var:-}" ]]; then
    auth_description="${api_key_var}（环境变量）"
  elif value="$(read_key_from_dotenv "$api_key_var")"; then
    export "$api_key_var=$value"
    auth_description="${api_key_var}（${ENV_FILE}）"
  elif value="$(read_key_from_opencode_auth "$provider")"; then
    export "$api_key_var=$value"
    auth_description="${api_key_var}（${OPENCODE_AUTH_JSON}）"
  else
    die "未找到 $provider 所需的 ${api_key_var}；请设置环境变量、写入 ${ENV_FILE}，或先运行 opencode auth login"
  fi
else
  auth_description="未知 provider（${provider}），跳过 API Key 检查；如需认证请自行 export 对应环境变量"
  echo "警告：$auth_description" >&2
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
  model_name="${OPENCODE_MODEL##*/}"
  safe_model_name="${model_name//[^[:alnum:]._-]/-}"
  PIER_JOB_NAME="opencode-${safe_model_name}-${sample_name}-$(date +%Y%m%d-%H%M%S)"
fi

command=(
  "$PIER_BIN" run
  --path "$TASKS_DIR"
  "${include_args[@]}"
  --agent opencode
  --model "$OPENCODE_MODEL"
  --agent-kwarg "version=$OPENCODE_VERSION"
)

if [[ -n "$OPENCODE_VARIANT" ]]; then
  command+=(--agent-kwarg "variant=$OPENCODE_VARIANT")
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

echo "即将使用容器内 OpenCode 运行 $task_count 个任务："
echo "  任务列表：$TASK_LIST"
echo "  Job 名称：$PIER_JOB_NAME"
echo "  结果目录：$JOBS_DIR/$PIER_JOB_NAME"
echo "  模型：$OPENCODE_MODEL"
echo "  OpenCode CLI：$OPENCODE_VERSION"
if [[ -n "$OPENCODE_VARIANT" ]]; then
  echo "  Variant：$OPENCODE_VARIANT"
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
