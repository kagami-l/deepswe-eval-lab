"""DeepSWE task selection and timeout resolution."""

from __future__ import annotations

import tomllib
import re
from pathlib import Path


class TaskSelectionError(ValueError):
    pass


_SAFE_TASK_NAME = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]*$")


def read_task_list(path: Path) -> list[str]:
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError as exc:
        raise TaskSelectionError(f"Task list not found: {path}") from exc
    return [
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]


def resolve_tasks(
    tasks_dir: Path, explicit: list[str], task_lists: list[Path]
) -> list[str]:
    names = [*explicit]
    for path in task_lists:
        names.extend(read_task_list(path))
    names = list(dict.fromkeys(names))
    if not names:
        raise TaskSelectionError("Select at least one task with --task or --task-list")
    for name in names:
        if not _SAFE_TASK_NAME.fullmatch(name):
            raise TaskSelectionError(f"Invalid task name: {name!r}")
        if not (tasks_dir / name / "task.toml").is_file():
            raise TaskSelectionError(f"Task does not exist or lacks task.toml: {name}")
    return names


def common_agent_timeout(tasks_dir: Path, task_names: list[str]) -> float:
    timeouts: dict[str, float] = {}
    for name in task_names:
        path = tasks_dir / name / "task.toml"
        raw = tomllib.loads(path.read_text())
        agent = raw.get("agent")
        value = agent.get("timeout_sec") if isinstance(agent, dict) else None
        if not isinstance(value, (int, float)) or value <= 0:
            raise TaskSelectionError(f"Task {name} has no positive agent.timeout_sec")
        timeouts[name] = float(value)
    unique = sorted(set(timeouts.values()))
    if len(unique) != 1:
        detail = ", ".join(f"{name}={value:g}" for name, value in timeouts.items())
        raise TaskSelectionError(
            "Selected tasks have different Agent timeouts; split them into separate jobs: "
            + detail
        )
    return unique[0]
