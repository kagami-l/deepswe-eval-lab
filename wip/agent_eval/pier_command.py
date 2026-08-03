"""Translate an ExecutionPlan into the public `pier run` CLI surface."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ExecutionPlan


def model_label(plan: ExecutionPlan) -> str:
    if plan.reviewer is None:
        return f"{plan.modifier.adapter}/{plan.modifier.model}"
    return (
        "collab/"
        f"{plan.modifier.name}-{plan.modifier.model}+"
        f"{plan.reviewer.name}-{plan.reviewer.model}"
    )


def build_pier_command(
    *,
    pier_bin: str,
    tasks_dir: Path,
    task_names: list[str],
    jobs_dir: Path,
    job_name: str,
    n_attempts: int,
    n_concurrent: int,
    plan: ExecutionPlan,
    run_manifest_path: Path,
    runtime_target: str,
    extra_args: list[str],
) -> list[str]:
    plan_json = json.dumps(plan.to_dict(), sort_keys=True, separators=(",", ":"))
    command = [pier_bin, "run", "--path", str(tasks_dir)]
    for task in task_names:
        command.extend(["--include-task-name", task])
    command.extend(
        [
            "--agent-import-path",
            "wip.agents.deep_swe_agent.pier_agent:DeepSweAgent",
            "--agent-kwarg",
            f"execution_plan_json={plan_json}",
            "--agent-kwarg",
            f"run_manifest_path={run_manifest_path}",
            "--environment-import-path",
            "wip.environments.agent_runtime:SharedAgentRuntimeDockerEnvironment",
            "--environment-kwarg",
            f"runtime_image={plan.runtime_image}",
            "--environment-kwarg",
            f"runtime_target={runtime_target}",
            "--model",
            model_label(plan),
            "--env",
            "docker",
            "--enable-verification",
            "--no-force-build",
            "--delete",
            "--n-attempts",
            str(n_attempts),
            "--n-concurrent",
            str(n_concurrent),
            "--agent-timeout-multiplier",
            str(plan.budget.agent_timeout_multiplier),
            "--job-name",
            job_name,
            "--jobs-dir",
            str(jobs_dir),
        ]
    )
    command.extend(extra_args)
    return command
