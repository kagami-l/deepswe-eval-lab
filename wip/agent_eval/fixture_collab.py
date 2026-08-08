"""Synthetic collab job/trial builders shared by the patch-scoring tests.

The builders reproduce the collab runtime's on-disk layout profile (rounds,
final patch, summary, Pier result) closely enough for discovery and scoring
tests without running any model or container.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_task(tasks_root: Path, name: str) -> Path:
    task_dir = tasks_root / name
    tests = task_dir / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.toml").write_text(
        'schema_version = "1.3"\n'
        f'[task]\nname = "datacurve/{name}"\n'
        "[verifier]\n"
        'environment_mode = "separate"\n'
        "timeout_sec = 1800.0\n"
        "[agent]\ntimeout_sec = 5400.0\n"
        '[environment]\ndocker_image = "example/image:1"\nos = "linux"\n'
    )
    (tests / "Dockerfile").write_text("FROM example/image:1\nCOPY . /tests\n")
    (tests / "test.sh").write_text("#!/bin/sh\nexit 0\n")
    (tests / "config.json").write_text('{"f2p_node_ids": ["t::a"]}\n')
    return task_dir


def _metadata(role: str, status: str, kind: str | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "role": role,
        "attempts": [{"attempt": 1, "status": status}],
    }
    if kind is not None:
        value["kind"] = kind
    return value


def make_trial(
    job_dir: Path,
    task_dir: Path,
    trial_name: str,
    *,
    review_patches: list[str],
    final_patch: str,
    outcome: str = "approved",
    eval_rewards: dict[str, Any] | None = None,
    review_statuses: list[str] | None = None,
    revise_statuses: list[str] | None = None,
    review_count: int | None = None,
    revision_count: int | None = None,
    no_change_revision: bool = False,
    degraded_reason: str | None = None,
    topology: str = "collab",
    model_patch: str | None = None,
    base_commit: str = "b" * 40,
) -> Path:
    """Write one synthetic collab trial and return its directory.

    ``review_patches`` are the pre-review snapshots in round order (the first
    one is the initial patch). Revise rounds are interleaved between reviews;
    a trailing ``final-revision`` round is added when the final patch differs
    from the last review snapshot.
    """
    trial_dir = job_dir / trial_name
    system = trial_dir / "agent" / "system"
    rounds = system / "rounds"
    rounds.mkdir(parents=True, exist_ok=True)
    (system / "final").mkdir(parents=True, exist_ok=True)
    (trial_dir / "artifacts").mkdir(parents=True, exist_ok=True)

    review_statuses = review_statuses or ["success"] * len(review_patches)
    modify_dir = rounds / "00-modify"
    modify_dir.mkdir(exist_ok=True)
    (modify_dir / "metadata.json").write_text(
        json.dumps(_metadata("modifier", "success", "modify"))
    )

    number = 1
    revise_dirs: list[Path] = []
    for index, patch in enumerate(review_patches):
        if index > 0:
            revise_dir = rounds / f"{number:02d}-revise"
            revise_dir.mkdir(exist_ok=True)
            revise_dirs.append(revise_dir)
            number += 1
        review_dir = rounds / f"{number:02d}-review"
        review_dir.mkdir(exist_ok=True)
        (review_dir / "patch.diff").write_text(patch)
        (review_dir / "metadata.json").write_text(
            json.dumps(_metadata("reviewer", review_statuses[index]))
        )
        number += 1
    if final_patch != review_patches[-1]:
        revise_dir = rounds / f"{number:02d}-final-revision"
        revise_dir.mkdir(exist_ok=True)
        revise_dirs.append(revise_dir)
    revise_statuses = revise_statuses or ["success"] * len(revise_dirs)
    for revise_dir, status in zip(revise_dirs, revise_statuses):
        kind = (
            "final-revision" if revise_dir.name.endswith("final-revision") else "revise"
        )
        (revise_dir / "metadata.json").write_text(
            json.dumps(_metadata("modifier", status, kind))
        )

    (system / "final" / "patch.diff").write_text(final_patch)
    (trial_dir / "artifacts" / "model.patch").write_text(
        final_patch if model_patch is None else model_patch
    )

    resolved_review_count = (
        review_count
        if review_count is not None
        else sum(1 for status in review_statuses if status == "success")
    )
    resolved_revision_count = (
        revision_count if revision_count is not None else len(revise_dirs)
    )
    checkpoint_labels = ["collab: initial implementation"] + [
        (
            "collab: final revision"
            if revise_dir.name.endswith("final-revision")
            else f"collab: revision {index + 1}"
        )
        for index, revise_dir in enumerate(revise_dirs)
    ]
    (system / "summary.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "result": {
                    "outcome": outcome,
                    "degradedReason": degraded_reason,
                    "deliverable": True,
                    "baseCommit": base_commit,
                    "checkpoints": [
                        {"label": label, "commit": f"{index:040d}"}
                        for index, label in enumerate(checkpoint_labels)
                    ],
                    "reviewCount": resolved_review_count,
                    "revisionCount": resolved_revision_count,
                    "noChangeRevision": no_change_revision,
                },
            }
        )
    )
    (trial_dir / "result.json").write_text(
        json.dumps(
            {
                "task_checksum": f"checksum-{task_dir.name}",
                "config": {
                    "task": {"path": str(task_dir)},
                    "timeout_multiplier": 1.0,
                    "verifier_timeout_multiplier": None,
                    "agent": {
                        "kwargs": {"execution_plan_json": {"topology": topology}}
                    },
                    "environment": {"import_path": "example:Env", "kwargs": {}},
                    "verifier": {
                        "override_timeout_sec": None,
                        "max_timeout_sec": None,
                        "env": {},
                    },
                },
                "verifier_result": (
                    {"rewards": eval_rewards} if eval_rewards is not None else None
                ),
                "exception_info": None,
            }
        )
    )
    return trial_dir


def make_failed_modifier_trial(
    job_dir: Path,
    task_dir: Path,
    trial_name: str,
    *,
    outcome: str = "modifier_failed",
) -> Path:
    """Trial whose modifier never produced an initial patch.

    Mirrors the real runtime: ``finalize()`` runs on the failure path too, so
    ``final/patch.diff``, ``final/git-status.txt`` and ``artifacts/model.patch``
    all exist but are empty, and ``checkpoints`` is empty.
    """
    trial_dir = job_dir / trial_name
    system = trial_dir / "agent" / "system"
    rounds = system / "rounds"
    rounds.mkdir(parents=True, exist_ok=True)
    (system / "final").mkdir(parents=True, exist_ok=True)
    (trial_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    modify_dir = rounds / "00-modify"
    modify_dir.mkdir(exist_ok=True)
    (modify_dir / "metadata.json").write_text(
        json.dumps(_metadata("modifier", "error", "modify"))
    )
    (system / "final" / "patch.diff").write_text("")
    (system / "final" / "git-status.txt").write_text("")
    (trial_dir / "artifacts" / "model.patch").write_text("")
    (system / "summary.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "result": {
                    "outcome": outcome,
                    "degradedReason": None,
                    "deliverable": False,
                    "baseCommit": "b" * 40,
                    "checkpoints": [],
                    "reviewCount": 0,
                    "revisionCount": 0,
                    "noChangeRevision": False,
                },
            }
        )
    )
    (trial_dir / "result.json").write_text(
        json.dumps(
            {
                "task_checksum": f"checksum-{task_dir.name}",
                "config": {
                    "task": {"path": str(task_dir)},
                    "timeout_multiplier": 1.0,
                    "verifier_timeout_multiplier": None,
                    "agent": {
                        "kwargs": {"execution_plan_json": {"topology": "collab"}}
                    },
                    "environment": {},
                    "verifier": {},
                },
                "verifier_result": {
                    "rewards": {
                        "reward": 0,
                        "f2p_total": 1,
                        "f2p_passed": 0,
                        "p2p_total": 2,
                        "p2p_passed": 2,
                        "partial": 0.667,
                    }
                },
                "exception_info": None,
            }
        )
    )
    return trial_dir
