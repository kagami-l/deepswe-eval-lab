#!/usr/bin/env bash

# Run a task list with Pier's containerized Codex agent and DeepSWE verifier.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

TASK_LIST="$REPO_ROOT/wip/data/selection/05_sample_dev.txt"
TASKS_DIR="${PIER_TASKS_DIR:-$REPO_ROOT/tasks}"
JOBS_DIR="${PIER_JOBS_DIR:-$REPO_ROOT/jobs}"
PIER_BIN="${PIER_BIN:-pier}"
CODEX_MODEL="${CODEX_MODEL:-openai/gpt-5.6-sol}"
CODEX_VERSION="${CODEX_VERSION:-0.146.0}"
CODEX_REASONING_EFFORT="${CODEX_REASONING_EFFORT:-high}"
PIER_N_ATTEMPTS="${PIER_N_ATTEMPTS:-4}"
PIER_N_CONCURRENT="${PIER_N_CONCURRENT:-2}"
PIER_JOB_NAME="${PIER_JOB_NAME:-}"
CODEX_FORCE_AUTH_JSON="${CODEX_FORCE_AUTH_JSON:-1}"

usage() {
  cat <<'EOF'
用 Pier 的容器内 Codex 执行任务列表，并运行 DeepSWE verifier 评测。

用法：
  wip/scripts/run_codex_eval.sh [选项] [-- 额外的 pier run 参数...]

选项：
  -t, --task-list PATH         任务 ID 列表；默认：05_sample_dev.txt
  -m, --model MODEL            Pier 模型标签；默认：openai/gpt-5.6-sol
      --codex-version VERSION  容器内 Codex CLI 版本；默认：0.146.0
      --reasoning-effort LEVEL Codex reasoning effort；默认：high
  -k, --n-attempts N           每个任务的重复次数；默认：4
  -n, --n-concurrent N         并发 trial 数；默认：2
  -o, --jobs-dir PATH          结果目录；默认：仓库根目录下的 jobs
      --job-name NAME          Job 名称；默认自动包含模型、样本名和时间
      --dry-run                校验输入并打印命令，不启动评测
  -h, --help                   显示帮助

认证：
  默认读取宿主机 ~/.codex/auth.json（先运行 codex login）。
  可用 CODEX_AUTH_JSON_PATH 指定其他 auth.json。
  若要使用 API Key，设置 CODEX_FORCE_AUTH_JSON=0 和 OPENAI_API_KEY。

可选环境变量：
  CODEX_MODEL、CODEX_VERSION、CODEX_REASONING_EFFORT
  CODEX_FORCE_AUTH_JSON、CODEX_AUTH_JSON_PATH、OPENAI_API_KEY
  PIER_TASKS_DIR、PIER_JOBS_DIR、PIER_JOB_NAME
  PIER_N_ATTEMPTS、PIER_N_CONCURRENT、PIER_BIN

示例：
  wip/scripts/run_codex_eval.sh --dry-run

  wip/scripts/run_codex_eval.sh \
    --task-list wip/data/selection/05_sample_confirm.txt \
    --job-name codex-confirm-k4

  CODEX_VERSION=0.146.0 wip/scripts/run_codex_eval.sh -- \
    --max-retries 1 --debug
EOF
}

die() {
  echo "错误：$*" >&2
  exit 1
}

is_positive_integer() {
  [[ "$1" =~ ^[1-9][0-9]*$ ]]
}

is_truthy() {
  case "$1" in
    1|true|TRUE|True|yes|YES|Yes|on|ON|On) return 0 ;;
    *) return 1 ;;
  esac
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
      CODEX_MODEL="$2"
      shift 2
      ;;
    --model=*)
      CODEX_MODEL="${1#*=}"
      [[ -n "$CODEX_MODEL" ]] || die "--model 需要一个模型名称"
      shift
      ;;
    --codex-version)
      [[ "$#" -ge 2 && -n "$2" ]] || die "$1 需要一个版本号"
      CODEX_VERSION="$2"
      shift 2
      ;;
    --codex-version=*)
      CODEX_VERSION="${1#*=}"
      [[ -n "$CODEX_VERSION" ]] || die "--codex-version 需要一个版本号"
      shift
      ;;
    --reasoning-effort)
      [[ "$#" -ge 2 && -n "$2" ]] || die "$1 需要一个 reasoning effort"
      CODEX_REASONING_EFFORT="$2"
      shift 2
      ;;
    --reasoning-effort=*)
      CODEX_REASONING_EFFORT="${1#*=}"
      [[ -n "$CODEX_REASONING_EFFORT" ]] || die "--reasoning-effort 不能为空"
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
[[ "$CODEX_VERSION" =~ ^[0-9A-Za-z][0-9A-Za-z._+-]*$ ]] || \
  die "CODEX_VERSION 格式不合法：$CODEX_VERSION"
[[ "$CODEX_REASONING_EFFORT" != *[[:space:]]* ]] || \
  die "CODEX_REASONING_EFFORT 不能包含空白字符"

auth_description=""
if [[ -n "${CODEX_AUTH_JSON_PATH:-}" ]]; then
  [[ -f "$CODEX_AUTH_JSON_PATH" ]] || \
    die "CODEX_AUTH_JSON_PATH 指向的文件不存在：$CODEX_AUTH_JSON_PATH"
  auth_description="auth.json: $CODEX_AUTH_JSON_PATH"
elif is_truthy "$CODEX_FORCE_AUTH_JSON"; then
  [[ -f "$HOME/.codex/auth.json" ]] || \
    die "找不到 $HOME/.codex/auth.json；请先运行 codex login，或改用 OPENAI_API_KEY"
  export CODEX_FORCE_AUTH_JSON=1
  auth_description="auth.json: $HOME/.codex/auth.json"
else
  [[ -n "${OPENAI_API_KEY:-}" ]] || \
    die "CODEX_FORCE_AUTH_JSON 已关闭，但未设置 OPENAI_API_KEY"
  export CODEX_FORCE_AUTH_JSON=0
  auth_description="OPENAI_API_KEY"
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
  model_name="${CODEX_MODEL##*/}"
  safe_model_name="${model_name//[^[:alnum:]._-]/-}"
  PIER_JOB_NAME="codex-${safe_model_name}-${sample_name}-$(date +%Y%m%d-%H%M%S)"
fi

command=(
  "$PIER_BIN" run
  --path "$TASKS_DIR"
  "${include_args[@]}"
  --agent codex
  --model "$CODEX_MODEL"
  --agent-kwarg "version=$CODEX_VERSION"
  --agent-kwarg "reasoning_effort=$CODEX_REASONING_EFFORT"
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

echo "即将使用容器内 Codex 运行 $task_count 个任务："
echo "  任务列表：$TASK_LIST"
echo "  Job 名称：$PIER_JOB_NAME"
echo "  结果目录：$JOBS_DIR/$PIER_JOB_NAME"
echo "  模型：$CODEX_MODEL"
echo "  Codex CLI：$CODEX_VERSION"
echo "  Reasoning effort：$CODEX_REASONING_EFFORT"
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
