"""Public CLI for the unified DeepSWE agent evaluation baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .credentials import require_kimi_auth_home
from .pier_command import build_pier_command
from .planning import (
    DEFAULT_CLEANUP_RESERVE_SECONDS,
    PlanRequest,
    build_execution_plan,
)
from .profiles import ProfileError, ProfileRegistry
from .runtime_image import RuntimeImageError, RuntimeImageManager, resolve_runtime_spec
from .tasks import TaskSelectionError, common_agent_timeout, resolve_tasks


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILES = REPO_ROOT / "wip/config/agent-profiles.json"
DEFAULT_TASKS_DIR = REPO_ROOT / "tasks"
DEFAULT_JOBS_DIR = REPO_ROOT / "jobs"
DEFAULT_RUNTIME_TARGET = "/opt/deep-swe-agent-runtime"
MAX_JOB_NAME_LENGTH = 200


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the unified DeepSWE single/collab evaluation baseline."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    runtime = subparsers.add_parser("runtime", help="Manage the shared runtime")
    runtime_subcommands = runtime.add_subparsers(dest="runtime_command", required=True)
    prepare = runtime_subcommands.add_parser(
        "prepare", help="Build or verify the runtime"
    )
    _add_runtime_args(prepare)
    prepare.add_argument("--dry-run", action="store_true")

    evaluate = subparsers.add_parser("eval", help="Run a DeepSWE evaluation")
    evaluate.add_argument("--task", action="append", default=[])
    evaluate.add_argument("--task-list", action="append", type=Path, default=[])
    evaluate.add_argument("--tasks-dir", type=Path, default=DEFAULT_TASKS_DIR)
    evaluate.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    evaluate.add_argument("--agent", required=True)
    evaluate.add_argument("--modifier")
    evaluate.add_argument("--reviewer")
    evaluate.add_argument("--model")
    evaluate.add_argument("--effort")
    evaluate.add_argument("--modifier-model")
    evaluate.add_argument("--modifier-effort")
    evaluate.add_argument("--reviewer-model")
    evaluate.add_argument("--reviewer-effort")
    evaluate.add_argument("--allow-unverified", action="store_true")
    evaluate.add_argument("--max-reviews", type=int)
    evaluate.add_argument("--max-agent-attempts", type=int, default=2)
    evaluate.add_argument("--reviewer-timeout-seconds", type=float, default=600.0)
    evaluate.add_argument("--revision-timeout-seconds", type=float, default=900.0)
    evaluate.add_argument("--min-turn-seconds", type=float, default=120.0)
    evaluate.add_argument("--strict", action="store_true")
    evaluate.add_argument("--keep-workspaces", action="store_true")
    evaluate.add_argument(
        "--cleanup-reserve-seconds", type=float, default=DEFAULT_CLEANUP_RESERVE_SECONDS
    )
    evaluate.add_argument("--agent-timeout-multiplier", type=float, default=1.0)
    evaluate.add_argument("--n-attempts", type=int, default=1)
    evaluate.add_argument("--n-concurrent", type=int, default=2)
    evaluate.add_argument("--jobs-dir", type=Path, default=DEFAULT_JOBS_DIR)
    evaluate.add_argument("--job-name")
    evaluate.add_argument("--pier-bin", default=os.environ.get("PIER_BIN", "pier"))
    _add_runtime_args(evaluate)
    evaluate.add_argument("--rebuild-runtime", action="store_true")
    evaluate.add_argument("--dry-run", action="store_true")
    evaluate.add_argument(
        "pier_args",
        nargs=argparse.REMAINDER,
        help="Additional pier run arguments after --",
    )
    return parser


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--runtime-image")
    parser.add_argument("--runtime-platform", choices=["linux/amd64", "linux/arm64"])
    parser.add_argument("--runtime-target", default=DEFAULT_RUNTIME_TARGET)
    parser.add_argument("--rebuild", action="store_true")


def _safe_job_component(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in "._-" else "-"
        for character in value
    )


def _task_list_label(path: Path) -> str:
    """Return a readable, path-safe label for a task-list filename."""
    filename = path.name
    stem = filename[: -len(path.suffix)] if path.suffix else filename
    label = _safe_job_component(stem).strip("._-")
    while "--" in label:
        label = label.replace("--", "-")
    return label or "task-list"


def _shorten_generated_job_name(base: str, timestamp: str) -> str:
    """Bound generated names while retaining a stable disambiguating suffix."""
    available = MAX_JOB_NAME_LENGTH - len(timestamp) - 1
    if len(base) <= available:
        return f"{base}-{timestamp}"
    digest = hashlib.sha256(base.encode()).hexdigest()[:8]
    prefix_length = available - len(digest) - 1
    shortened = base[:prefix_length].rstrip("._-")
    return f"{shortened}-{digest}-{timestamp}"


def _default_job_name(
    agent: str, tasks: list[str], task_lists: list[Path] | None = None
) -> str:
    task_scope = tasks[0] if len(tasks) == 1 else f"{len(tasks)}-tasks"
    list_labels = list(
        dict.fromkeys(_task_list_label(path) for path in (task_lists or []))
    )
    scope = (
        f"{'-and-'.join(list_labels)}-{task_scope}"
        if list_labels
        else task_scope
    )
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = _safe_job_component(f"unified-{agent}-{scope}").strip("._-")
    return _shorten_generated_job_name(base, timestamp)


def _validate_explicit_job_name(job_name: str) -> None:
    if not job_name or _safe_job_component(job_name) != job_name:
        raise ValueError(
            "--job-name may contain only letters, numbers, '.', '_' and '-'"
        )
    if job_name in {".", ".."}:
        raise ValueError("--job-name may not be '.' or '..'")
    if len(job_name) > MAX_JOB_NAME_LENGTH:
        raise ValueError(
            f"--job-name may not exceed {MAX_JOB_NAME_LENGTH} characters"
        )


_SECRET_ENV_FLAGS = {"--ae", "--agent-env", "--ve", "--verifier-env"}


def _redact_assignment(value: str) -> str:
    key, separator, _ = value.partition("=")
    return f"{key}=<redacted>" if separator else "<redacted>"


def _redact_args(values: list[str]) -> list[str]:
    redacted: list[str] = []
    redact_next = False
    for value in values:
        if redact_next:
            redacted.append(_redact_assignment(value))
            redact_next = False
            continue
        if value in _SECRET_ENV_FLAGS:
            redacted.append(value)
            redact_next = True
            continue
        matched = next(
            (flag for flag in _SECRET_ENV_FLAGS if value.startswith(f"{flag}=")),
            None,
        )
        if matched is not None:
            redacted.append(f"{matched}={_redact_assignment(value.split('=', 1)[1])}")
            continue
        redacted.append(value)
    return redacted


def _network_policy(plan: dict[str, Any]) -> dict[str, Any]:
    roles = plan.get("roles") or {}
    adapters = {
        role.get("adapter")
        for role in (roles.get("modifier"), roles.get("reviewer"))
        if isinstance(role, dict)
    }
    domains: set[str] = set()
    if "claude" in adapters:
        domains.add("api.anthropic.com")
    if "codex" in adapters:
        domains.update({"api.openai.com", "auth.openai.com", "chatgpt.com"})
    if "kimi" in adapters:
        domains.update({"api.kimi.com", "api.moonshot.ai"})
    if "opencode" in adapters:
        provider_domains = {
            "anthropic": "api.anthropic.com",
            "deepseek": "api.deepseek.com",
            "google": "generativelanguage.googleapis.com",
            "openai": "api.openai.com",
            "opencode": "opencode.ai",
            "openrouter": "openrouter.ai",
            "xai": "api.x.ai",
        }
        for role in (roles.get("modifier"), roles.get("reviewer")):
            if not isinstance(role, dict) or role.get("adapter") != "opencode":
                continue
            model = role.get("model")
            provider = model.split("/", 1)[0] if isinstance(model, str) else ""
            if domain := provider_domains.get(provider):
                domains.add(domain)
    if "gemini" in adapters:
        domains.update(
            {
                "accounts.google.com",
                "generativelanguage.googleapis.com",
                "oauth2.googleapis.com",
            }
        )
    return {"mode": "provider-only", "domains": sorted(domains)}


def _require_plan_credentials(plan: dict[str, Any]) -> None:
    roles = plan.get("roles") or {}
    if any(
        isinstance(role, dict) and role.get("adapter") == "kimi"
        for role in (roles.get("modifier"), roles.get("reviewer"))
    ):
        require_kimi_auth_home(os.environ.get("KIMI_AUTH_HOME_PATH"))


def _git_metadata() -> dict[str, Any]:
    def run(*args: str) -> str | None:
        result = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    status = run("status", "--short")
    return {
        "commit": run("rev-parse", "HEAD"),
        "dirty": bool(status),
        "status": status.splitlines() if status else [],
    }


def _pier_version(pier_bin: str) -> str | None:
    result = subprocess.run(
        [pier_bin, "--version"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return (
        result.stdout.strip().splitlines()[-1]
        if result.returncode == 0 and result.stdout.strip()
        else None
    )


def _write_run_manifest(
    *,
    path: Path,
    argv: list[str],
    tasks: list[str],
    plan: dict[str, Any],
    runtime_status: dict[str, Any],
    pier_bin: str,
    pier_command: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {
        "schemaVersion": 1,
        "generatedAt": datetime.now().astimezone().isoformat(),
        "argv": _redact_args(argv),
        "git": _git_metadata(),
        "tasks": tasks,
        "executionPlan": plan,
        "runtimeStatus": runtime_status,
        "pierVersion": _pier_version(pier_bin),
        "networkPolicy": _network_policy(plan),
        "pierCommand": _redact_args(pier_command),
    }
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _runtime_prepare(args: argparse.Namespace) -> int:
    spec = resolve_runtime_spec(
        REPO_ROOT,
        explicit_image=args.runtime_image,
        platform=args.runtime_platform,
    )
    manager = RuntimeImageManager(spec)
    status = (
        manager.inspect() if args.dry_run else manager.prepare(rebuild=args.rebuild)
    )
    print(json.dumps(status.to_dict(), indent=2, sort_keys=True))
    if args.dry_run and not status.matches:
        print("runtime prepare would build or replace this image")
    return 0


def _evaluate(args: argparse.Namespace, argv: list[str]) -> int:
    tasks_dir = args.tasks_dir.expanduser().resolve()
    task_lists = [path.expanduser().resolve() for path in args.task_list]
    tasks = resolve_tasks(
        tasks_dir,
        args.task,
        task_lists,
    )
    task_timeout = common_agent_timeout(tasks_dir, tasks)
    registry = ProfileRegistry.load(args.profiles.expanduser().resolve())
    spec = resolve_runtime_spec(
        REPO_ROOT,
        explicit_image=args.runtime_image,
        platform=args.runtime_platform,
    )
    if args.agent != "collab" and args.max_reviews is not None:
        raise ValueError("single mode does not accept --max-reviews")
    resolved_max_reviews = args.max_reviews if args.max_reviews is not None else 3
    plan = build_execution_plan(
        PlanRequest(
            agent=args.agent,
            modifier=args.modifier,
            reviewer=args.reviewer,
            model=args.model,
            effort=args.effort,
            modifier_model=args.modifier_model,
            modifier_effort=args.modifier_effort,
            reviewer_model=args.reviewer_model,
            reviewer_effort=args.reviewer_effort,
            allow_unverified=args.allow_unverified,
            task_timeout_seconds=task_timeout,
            agent_timeout_multiplier=args.agent_timeout_multiplier,
            cleanup_reserve_seconds=args.cleanup_reserve_seconds,
            runtime_manifest_digest=spec.manifest_digest,
            runtime_image=spec.image,
            max_reviews=resolved_max_reviews,
            max_agent_attempts=args.max_agent_attempts,
            reviewer_timeout_seconds=args.reviewer_timeout_seconds,
            revision_timeout_seconds=args.revision_timeout_seconds,
            min_turn_seconds=args.min_turn_seconds,
            strict=args.strict,
            keep_workspaces=args.keep_workspaces,
        ),
        registry,
    )
    if args.n_attempts < 1 or args.n_concurrent < 1:
        raise ValueError("--n-attempts and --n-concurrent must be positive")
    if not args.dry_run:
        _require_plan_credentials(plan.to_dict())
    manager = RuntimeImageManager(spec)
    runtime_status = (
        manager.inspect()
        if args.dry_run
        else manager.prepare(rebuild=args.rebuild_runtime or args.rebuild)
    )
    if args.job_name is not None:
        _validate_explicit_job_name(args.job_name)
    job_name = args.job_name or _default_job_name(args.agent, tasks, task_lists)
    jobs_dir = args.jobs_dir.expanduser().resolve()
    manifest_path = jobs_dir / ".agent-eval-manifests" / f"{job_name}.json"
    pier_args = list(args.pier_args)
    if pier_args and pier_args[0] == "--":
        pier_args = pier_args[1:]
    command = build_pier_command(
        pier_bin=args.pier_bin,
        tasks_dir=tasks_dir,
        task_names=tasks,
        jobs_dir=jobs_dir,
        job_name=job_name,
        n_attempts=args.n_attempts,
        n_concurrent=args.n_concurrent,
        plan=plan,
        run_manifest_path=manifest_path,
        runtime_target=args.runtime_target,
        extra_args=pier_args,
    )
    safe_command = _redact_args(command)
    output = {
        "jobName": job_name,
        "tasks": tasks,
        "executionPlan": plan.to_dict(),
        "runtimeStatus": runtime_status.to_dict(),
        "runManifest": str(manifest_path),
        "pierCommand": safe_command,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    print("command:", shlex.join(safe_command))
    if args.dry_run:
        return 0
    _write_run_manifest(
        path=manifest_path,
        argv=argv,
        tasks=tasks,
        plan=plan.to_dict(),
        runtime_status=runtime_status.to_dict(),
        pier_bin=args.pier_bin,
        pier_command=command,
    )
    return subprocess.run(command, cwd=REPO_ROOT, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    actual_argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(actual_argv)
    try:
        if args.command == "runtime":
            return _runtime_prepare(args)
        return _evaluate(args, actual_argv)
    except (ProfileError, RuntimeImageError, TaskSelectionError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
