#!/usr/bin/env python3
"""Executable wrapper for :mod:`wip.agent_eval.cli`.

Credentials (e.g. ``CLAUDE_CODE_OAUTH_TOKEN``) are auto-loaded from the
gitignored ``wip/scripts/.env``; already-exported variables win.

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

    # Re-score the frozen stage patches of a finished collab job.
    uv run python scripts/run_agent_eval.py score-patches \
        --job-path ../jobs/<job-name>

Every subcommand accepts ``--help`` (for example ``eval --help``) and lists
all of its options with defaults.
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Load credentials such as CLAUDE_CODE_OAUTH_TOKEN from wip/scripts/.env
# (gitignored); variables already present in the environment take precedence.
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

from wip.agent_eval.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
