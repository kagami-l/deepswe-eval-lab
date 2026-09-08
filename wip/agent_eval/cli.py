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
    DEFAULT_EVENT_SILENCE_TIMEOUT_SECONDS,
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


_EPILOG = """\
subcommands:
  runtime prepare   build or verify the shared Agent runtime image
  eval              plan and launch a single-Agent or collab evaluation via pier run
  score-patches     re-score the frozen stage patches of a finished collab job

run from the wip/ directory, for example:
  uv run python scripts/run_agent_eval.py runtime prepare
  uv run python scripts/run_agent_eval.py eval --task <task> --agent codex --dry-run
  uv run python scripts/run_agent_eval.py eval \\
      --task-list data/selection/05_sample_dev.txt \\
      --agent collab --modifier kimi --reviewer codex
  uv run python scripts/run_agent_eval.py score-patches --job-path ../jobs/<job-name>

environment:
  PIER_BIN             default for --pier-bin
  KIMI_AUTH_HOME_PATH  Kimi login home checked before a live kimi eval
                       (default: ~/.kimi-code)
  wip/scripts/.env     gitignored credentials auto-loaded by run_agent_eval.py,
                       e.g. CLAUDE_CODE_OAUTH_TOKEN; exported variables win
"""

_PREPARE_DESCRIPTION = """\
Build or verify the shared Agent runtime image.

Fingerprints wip/config/runtime-manifest.json and the runtime build inputs it
references, then resolves the default image deep-swe/agent-runtime:<digest>.
A missing image is built. An existing image whose manifest digest or platform
does not match is an error unless --rebuild is given.
"""

_EVAL_DESCRIPTION = """\
Run a single-Agent or collab DeepSWE evaluation through pier.

Resolves the selected tasks and Agent profiles into an execution plan, prepares
the shared runtime image, writes a run manifest to
<jobs-dir>/.agent-eval-manifests/<job-name>.json and launches `pier run`.
Single mode takes one profile via --agent. Collab mode (--agent collab) runs a
modifier/reviewer review loop and requires --modifier and --reviewer.
With --dry-run only the plan and the redacted pier command are printed.
"""

_SCORE_DESCRIPTION = """\
Post-hoc score the stage patches of a finished collab job.

Replays every frozen stage patch of each collab trial through pier's direct
verifier so per-stage rewards can be compared. No model is invoked. Trials
whose execution plan is not a collab topology are reported as ineligible.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the unified DeepSWE single/collab evaluation baseline.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    runtime = subparsers.add_parser(
        "runtime",
        help="Manage the shared Agent runtime image",
        description="Manage the shared Agent runtime image used by every eval.",
    )
    runtime_subcommands = runtime.add_subparsers(dest="runtime_command", required=True)
    prepare = runtime_subcommands.add_parser(
        "prepare",
        help="Build or verify the shared runtime image",
        description=_PREPARE_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_runtime_args(prepare, include_target=False)
    prepare.add_argument(
        "--dry-run",
        action="store_true",
        help="Only inspect the local image and report whether prepare would build it",
    )

    evaluate = subparsers.add_parser(
        "eval",
        help="Run a single-Agent or collab DeepSWE evaluation through pier",
        description=_EVAL_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    tasks = evaluate.add_argument_group("task selection")
    tasks.add_argument(
        "--task",
        action="append",
        default=[],
        metavar="NAME",
        help="Task directory name under --tasks-dir; repeatable. "
        "At least one --task or --task-list is required",
    )
    tasks.add_argument(
        "--task-list",
        action="append",
        type=Path,
        default=[],
        metavar="PATH",
        help="Text file with one task name per line (blank lines and # comments are "
        "ignored); repeatable",
    )
    tasks.add_argument(
        "--tasks-dir",
        type=Path,
        default=DEFAULT_TASKS_DIR,
        metavar="PATH",
        help="DeepSWE tasks directory (default: <repo>/tasks)",
    )

    roles = evaluate.add_argument_group("agent roles")
    roles.add_argument(
        "--profiles",
        type=Path,
        default=DEFAULT_PROFILES,
        metavar="PATH",
        help="Agent profile registry JSON (default: wip/config/agent-profiles.json)",
    )
    roles.add_argument(
        "--agent",
        required=True,
        metavar="PROFILE|collab",
        help="Profile name for single mode (e.g. claude, codex, kimi, opencode) or "
        "'collab' for the modifier/reviewer review loop",
    )
    roles.add_argument(
        "--modifier",
        metavar="PROFILE",
        help="Collab only: profile that writes patches (required with --agent collab)",
    )
    roles.add_argument(
        "--reviewer",
        metavar="PROFILE",
        help="Collab only: profile that reviews patches (required with --agent collab)",
    )
    roles.add_argument("--model", help="Single mode only: override the profile model")
    roles.add_argument(
        "--effort", help="Single mode only: override the profile reasoning effort"
    )
    roles.add_argument(
        "--modifier-model",
        metavar="MODEL",
        help="Collab only: override the modifier profile model",
    )
    roles.add_argument(
        "--modifier-effort",
        metavar="EFFORT",
        help="Collab only: override the modifier profile reasoning effort",
    )
    roles.add_argument(
        "--reviewer-model",
        metavar="MODEL",
        help="Collab only: override the reviewer profile model",
    )
    roles.add_argument(
        "--reviewer-effort",
        metavar="EFFORT",
        help="Collab only: override the reviewer profile reasoning effort",
    )
    roles.add_argument(
        "--allow-unverified",
        action="store_true",
        help="Allow profiles whose status is 'unverified' (currently gemini)",
    )

    budget = evaluate.add_argument_group("workflow budget")
    budget.add_argument(
        "--max-reviews",
        type=int,
        metavar="N",
        help="Collab only: maximum review rounds (default: 3)",
    )
    budget.add_argument(
        "--max-agent-attempts",
        type=int,
        default=2,
        metavar="N",
        help="Maximum attempts per Agent turn (default: %(default)s)",
    )
    budget.add_argument(
        "--reviewer-timeout-seconds",
        type=float,
        metavar="SECONDS",
        help="Collab only: optional review-attempt cap; defaults to the remaining "
        "workflow time",
    )
    budget.add_argument(
        "--revision-timeout-seconds",
        type=float,
        metavar="SECONDS",
        help="Collab only: optional revision-attempt cap; defaults to the remaining "
        "workflow time",
    )
    budget.add_argument(
        "--event-silence-timeout-seconds",
        type=float,
        default=DEFAULT_EVENT_SILENCE_TIMEOUT_SECONDS,
        metavar="SECONDS",
        help="Abort a turn after this many seconds without any Agent event "
        "(default: %(default)s)",
    )
    budget.add_argument(
        "--min-turn-seconds",
        type=float,
        default=120.0,
        metavar="SECONDS",
        help="Skip a turn when fewer than this many seconds remain in the workflow "
        "budget (default: %(default)s)",
    )
    budget.add_argument(
        "--cleanup-reserve-seconds",
        type=float,
        default=DEFAULT_CLEANUP_RESERVE_SECONDS,
        metavar="SECONDS",
        help="Seconds reserved before the hard Agent timeout for cleanup; must be "
        "smaller than that timeout (default: %(default)s)",
    )
    budget.add_argument(
        "--agent-timeout-multiplier",
        type=float,
        default=1.0,
        metavar="X",
        help="Multiplier on the tasks' agent.timeout_sec for the hard Agent timeout; "
        "also forwarded to pier run (default: %(default)s)",
    )
    budget.add_argument(
        "--strict",
        action="store_true",
        help="Fail the workflow instead of delivering a degraded checkpoint",
    )
    budget.add_argument(
        "--keep-workspaces",
        action="store_true",
        help="Keep the per-review isolated workspace copies for inspection",
    )

    job = evaluate.add_argument_group("pier job")
    job.add_argument(
        "--n-attempts",
        type=int,
        default=1,
        metavar="N",
        help="Forwarded to pier run --n-attempts (default: %(default)s)",
    )
    job.add_argument(
        "--n-concurrent",
        type=int,
        default=2,
        metavar="N",
        help="Forwarded to pier run --n-concurrent (default: %(default)s)",
    )
    job.add_argument(
        "--jobs-dir",
        type=Path,
        default=DEFAULT_JOBS_DIR,
        metavar="PATH",
        help="Pier jobs directory; run manifests go to <jobs-dir>/.agent-eval-manifests "
        "(default: <repo>/jobs)",
    )
    job.add_argument(
        "--job-name",
        metavar="NAME",
        help="Explicit job name using [A-Za-z0-9._-], at most 200 characters "
        "(default: <agent[-modifier-reviewer]>-<scope>-<timestamp>)",
    )
    job.add_argument(
        "--pier-bin",
        default=os.environ.get("PIER_BIN", "pier"),
        metavar="PATH",
        help="pier executable (default: $PIER_BIN or 'pier')",
    )
    job.add_argument(
        "pier_args",
        nargs=argparse.REMAINDER,
        metavar="PIER_ARGS",
        help="Additional pier run arguments, given after --",
    )

    runtime_image = evaluate.add_argument_group("runtime image")
    _add_runtime_args(runtime_image, include_target=True)
    runtime_image.add_argument(
        "--rebuild-runtime", action="store_true", help="Alias of --rebuild"
    )
    evaluate.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the execution plan, runtime status and redacted pier command; "
        "skip building, credential checks and pier run",
    )

    score = subparsers.add_parser(
        "score-patches",
        help="Post-hoc score the stage patches of a finished collab job",
        description=_SCORE_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    score.add_argument(
        "--job-path",
        type=Path,
        required=True,
        metavar="PATH",
        help="Existing Pier job directory of a finished collab job (e.g. ../jobs/<job-name>)",
    )
    score.add_argument(
        "--trial",
        metavar="GLOB",
        help="Only scan and score trial directories matching this glob",
    )
    score.add_argument(
        "--concurrency",
        type=int,
        default=2,
        metavar="N",
        help="Concurrent direct verifier environments (default: %(default)s)",
    )
    score.add_argument(
        "--reuse-final-score",
        action="store_true",
        help="Skip the direct final verifier and reuse the validated eval reward",
    )
    score.add_argument(
        "--force",
        action="store_true",
        help="Ignore cached direct scores and re-run applicable verifiers",
    )
    score.add_argument(
        "--pier-bin",
        default=os.environ.get("PIER_BIN", "pier"),
        metavar="PATH",
        help="pier executable (default: $PIER_BIN or 'pier')",
    )
    return parser


def _add_runtime_args(parser: argparse._ActionsContainer, *, include_target: bool) -> None:
    parser.add_argument(
        "--runtime-image",
        metavar="IMAGE",
        help="Explicit runtime image reference "
        "(default: deep-swe/agent-runtime:<manifest digest>)",
    )
    parser.add_argument(
        "--runtime-platform",
        choices=["linux/amd64", "linux/arm64"],
        help="Docker platform to build and verify "
        "(default: the manifest's default_platform, currently linux/amd64)",
    )
    if include_target:
        parser.add_argument(
            "--runtime-target",
            default=DEFAULT_RUNTIME_TARGET,
            metavar="PATH",
            help="Container mount path of the read-only runtime image (default: %(default)s)",
        )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild the runtime image even when a matching image already exists",
    )


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
    agent: str,
    tasks: list[str],
    task_lists: list[Path] | None = None,
    *,
    modifier: str | None = None,
    reviewer: str | None = None,
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
    agent_label = (
        f"{agent}-{modifier}-{reviewer}"
        if agent == "collab" and modifier and reviewer
        else agent
    )
    base = _safe_job_component(f"{agent_label}-{scope}").strip("._-")
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
            event_silence_timeout_seconds=args.event_silence_timeout_seconds,
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
    job_name = args.job_name or _default_job_name(
        args.agent,
        tasks,
        task_lists,
        modifier=plan.modifier.name,
        reviewer=plan.reviewer.name if plan.reviewer is not None else None,
    )
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


def _score_patches(args: argparse.Namespace) -> int:
    import asyncio

    from .patch_scoring import (
        ScoreOptions,
        ScoringError,
        enable_progress_logging,
        score_patch_job,
    )
    from .patch_verifier import PierContractError, PierPatchVerifier

    if args.concurrency < 1:
        raise ValueError("--concurrency must be positive")
    enable_progress_logging()
    options = ScoreOptions(
        trial_glob=args.trial,
        concurrency=args.concurrency,
        reuse_final_score=args.reuse_final_score,
        force=args.force,
    )
    try:
        verifier = PierPatchVerifier(pier_bin=args.pier_bin)
        summary = asyncio.run(
            score_patch_job(
                args.job_path.expanduser(),
                options,
                verifier,
                identity=verifier.identity,
            )
        )
    except (PierContractError, ScoringError) as exc:
        print(str(exc), file=sys.stderr)
        return getattr(exc, "exit_code", 1)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["problems"]:
        for problem in summary["problems"]:
            print(f"problem: {problem}", file=sys.stderr)
    return int(summary["exitCode"])


def main(argv: list[str] | None = None) -> int:
    actual_argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(actual_argv)
    try:
        if args.command == "runtime":
            return _runtime_prepare(args)
        if args.command == "score-patches":
            return _score_patches(args)
        return _evaluate(args, actual_argv)
    except (ProfileError, RuntimeImageError, TaskSelectionError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
