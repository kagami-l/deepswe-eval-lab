#!/usr/bin/env python3
"""Executable wrapper for :mod:`wip.agent_eval.cli`.

Run these examples from the repository's ``wip`` directory::

    # Prepare the shared runtime image before starting an evaluation.
    uv run python scripts/run_agent_eval.py runtime prepare

    # Inspect a single-Agent evaluation without running it.
    uv run python scripts/run_agent_eval.py eval \
        --task abs-module-cache-flags --agent codex --dry-run

    # Inspect a Kimi modifier + Codex reviewer collaboration.
    uv run python scripts/run_agent_eval.py eval \
        --task abs-module-cache-flags --agent collab \
        --modifier kimi --reviewer codex --dry-run

    # Run a task list after reviewing the dry-run output.
    uv run python scripts/run_agent_eval.py eval \
        --task-list data/selection/05_sample_dev.txt \
        --agent opencode --n-concurrent 2
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wip.agent_eval.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
