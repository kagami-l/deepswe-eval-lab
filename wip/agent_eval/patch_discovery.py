"""Discover and validate the stage patches recorded inside a collab trial.

Deep module: callers get a validated ``TrialPatchSet`` (initial / revision-N /
final stages with SHA identity and parent links) or a ``LayoutError`` listing
every incompatibility. All knowledge about the collab runtime's on-disk round
layout lives here; scoring and CLI code never parse ``rounds/`` themselves.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DISCOVERY_SCHEMA_VERSION = 1

_ROUND_DIR = re.compile(r"^(\d{2})-(modify|review|revise|final-revision)$")
_DELIVERABLE_OUTCOMES = {"approved", "max_reviews_reached", "degraded"}
_COMPLETED_PROTOCOL_OUTCOMES = {"approved", "max_reviews_reached"}


class LayoutError(Exception):
    """The trial does not match the supported collab layout profile."""

    def __init__(self, trial_dir: Path, reasons: list[str]):
        self.trial_dir = trial_dir
        self.reasons = reasons
        details = "; ".join(reasons)
        super().__init__(f"{trial_dir.name}: {details}")


@dataclass(frozen=True)
class StagePatch:
    """One scored state of the trial's working tree, as a frozen patch."""

    stage_id: str  # "initial" | "revision-N" | "final"
    parent_stage_id: str | None
    ordinal: int
    patch_path: Path
    patch_sha256: str
    origin_round: str | None  # rounds/<dir> the patch was captured for
    changed: bool  # differs from parent stage
    alias_of: str | None  # earlier stage with identical content


@dataclass
class TrialPatchSet:
    """Everything the scorer needs to know about one trial."""

    trial_dir: Path
    trial_name: str
    task_name: str
    task_dir: Path
    task_checksum: str
    base_commit: str
    outcome: str
    degraded_reason: str | None
    review_count: int
    revision_count: int
    no_change_revision: bool
    eligible: bool
    ineligible_reason: str | None
    completed_protocol: bool
    stages: list[StagePatch] = field(default_factory=list)
    eval_final_rewards: dict[str, Any] | None = None
    # Raw sections of the recorded trial config needed to reproduce the
    # verifier environment exactly.
    environment_config: dict[str, Any] = field(default_factory=dict)
    verifier_config: dict[str, Any] = field(default_factory=dict)
    timeout_multiplier: float = 1.0
    verifier_timeout_multiplier: float | None = None

    @property
    def initial(self) -> StagePatch | None:
        return next((s for s in self.stages if s.stage_id == "initial"), None)

    @property
    def final(self) -> StagePatch | None:
        return next((s for s in self.stages if s.stage_id == "final"), None)

    def stage(self, stage_id: str) -> StagePatch | None:
        return next((s for s in self.stages if s.stage_id == stage_id), None)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path, reasons: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        reasons.append(f"missing {path.name}")
        return None
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        reasons.append(f"unreadable {path.name}: {exc}")
        return None
    if not isinstance(value, dict):
        reasons.append(f"{path.name} is not a JSON object")
        return None
    return value


def _safe_child(trial_dir: Path, relative: str, reasons: list[str]) -> Path | None:
    """Resolve a path inside the trial dir, rejecting escapes."""
    candidate = (trial_dir / relative).resolve()
    if not candidate.is_relative_to(trial_dir.resolve()):
        reasons.append(f"path escapes trial dir: {relative}")
        return None
    return candidate


def _round_entries(rounds_dir: Path, reasons: list[str]) -> list[tuple[int, str, Path]]:
    if not rounds_dir.is_dir():
        reasons.append("missing agent/system/rounds directory")
        return []
    entries: list[tuple[int, str, Path]] = []
    for child in sorted(rounds_dir.iterdir()):
        if not child.is_dir():
            continue
        match = _ROUND_DIR.match(child.name)
        if match is None:
            reasons.append(f"unrecognized round directory: {child.name}")
            continue
        entries.append((int(match.group(1)), match.group(2), child))
    entries.sort(key=lambda item: item[0])
    if entries and (entries[0][0] != 0 or entries[0][1] != "modify"):
        reasons.append("rounds do not start with 00-modify")
    return entries


def _round_role(round_dir: Path) -> str | None:
    metadata = round_dir / "metadata.json"
    if not metadata.is_file():
        return None
    try:
        value = json.loads(metadata.read_text())
    except (OSError, ValueError):
        return None
    return value.get("role") if isinstance(value, dict) else None


def _round_succeeded(round_dir: Path) -> bool:
    """True when the round's last recorded attempt succeeded."""
    metadata = round_dir / "metadata.json"
    if not metadata.is_file():
        return False
    try:
        value = json.loads(metadata.read_text())
    except (OSError, ValueError):
        return False
    attempts = value.get("attempts") if isinstance(value, dict) else None
    if not isinstance(attempts, list) or not attempts:
        return False
    last = attempts[-1]
    return isinstance(last, dict) and last.get("status") == "success"


def discover_trial_patches(trial_dir: Path) -> TrialPatchSet:
    """Map one collab trial directory into a validated ``TrialPatchSet``.

    Raises ``LayoutError`` when the trial does not match the supported
    layout profile. A recognized trial whose modifier never produced an
    initial patch is returned with ``eligible=False`` instead.
    """
    trial_dir = trial_dir.resolve()
    reasons: list[str] = []

    result = _load_json(trial_dir / "result.json", reasons)
    system_dir = trial_dir / "agent" / "system"
    summary = _load_json(system_dir / "summary.json", reasons)
    if result is None or summary is None:
        raise LayoutError(trial_dir, reasons)

    config = result.get("config")
    if not isinstance(config, dict):
        reasons.append("result.json has no config object")
        raise LayoutError(trial_dir, reasons)

    plan = (
        config.get("agent", {}).get("kwargs", {}).get("execution_plan_json", {})
        if isinstance(config.get("agent"), dict)
        else {}
    )
    if plan.get("topology") != "collab":
        reasons.append(f"not a collab trial (topology={plan.get('topology')!r})")

    task_path_raw = (config.get("task") or {}).get("path")
    task_dir = Path(task_path_raw) if isinstance(task_path_raw, str) else None
    if task_dir is None or not (task_dir / "task.toml").is_file():
        reasons.append(f"task directory unavailable: {task_path_raw!r}")

    task_checksum = result.get("task_checksum")
    if not isinstance(task_checksum, str) or not task_checksum:
        reasons.append("result.json has no task_checksum")

    summary_result = summary.get("result")
    if not isinstance(summary_result, dict):
        reasons.append("summary.json has no result object")
        raise LayoutError(trial_dir, reasons)

    outcome = summary_result.get("outcome")
    base_commit = summary_result.get("baseCommit")
    if not isinstance(base_commit, str) or not base_commit:
        reasons.append("summary.json has no baseCommit")
    review_count = summary_result.get("reviewCount")
    revision_count = summary_result.get("revisionCount")
    if not isinstance(review_count, int) or not isinstance(revision_count, int):
        reasons.append("summary.json lacks reviewCount/revisionCount")
        review_count = review_count if isinstance(review_count, int) else 0
        revision_count = revision_count if isinstance(revision_count, int) else 0

    entries = _round_entries(system_dir / "rounds", reasons)
    review_rounds = [(n, path) for n, kind, path in entries if kind == "review"]
    revise_rounds = [
        (n, kind, path)
        for n, kind, path in entries
        if kind in {"revise", "final-revision"}
    ]

    final_rel = "agent/system/final/patch.diff"
    final_path = _safe_child(trial_dir, final_rel, reasons)
    model_path = _safe_child(trial_dir, "artifacts/model.patch", reasons)

    # Modifier failure: recognized layout, but nothing to pair.
    if not review_rounds and (final_path is None or not final_path.is_file()):
        if reasons:
            raise LayoutError(trial_dir, reasons)
        return TrialPatchSet(
            trial_dir=trial_dir,
            trial_name=trial_dir.name,
            task_name=str(summary_result.get("taskName") or task_dir.name),
            task_dir=task_dir,
            task_checksum=str(task_checksum),
            base_commit=str(base_commit),
            outcome=str(outcome),
            degraded_reason=summary_result.get("degradedReason"),
            review_count=review_count,
            revision_count=revision_count,
            no_change_revision=bool(summary_result.get("noChangeRevision")),
            eligible=False,
            ineligible_reason="no_initial_patch",
            completed_protocol=False,
            stages=[],
            eval_final_rewards=None,
            environment_config=config.get("environment") or {},
            verifier_config=config.get("verifier") or {},
            timeout_multiplier=float(config.get("timeout_multiplier") or 1.0),
            verifier_timeout_multiplier=config.get("verifier_timeout_multiplier"),
        )

    if not review_rounds:
        reasons.append("no review rounds with a pre-review patch")
    if final_path is None or not final_path.is_file():
        reasons.append(f"missing {final_rel}")
    if model_path is None or not model_path.is_file():
        reasons.append("missing artifacts/model.patch")
    if reasons:
        raise LayoutError(trial_dir, reasons)

    # Review round sanity: each has role=reviewer metadata and a patch.
    review_patches: list[tuple[int, Path, Path]] = []
    for number, round_dir in review_rounds:
        role = _round_role(round_dir)
        if role != "reviewer":
            reasons.append(f"{round_dir.name}: unexpected role {role!r}")
        patch = round_dir / "patch.diff"
        if not patch.is_file() or patch.stat().st_size == 0:
            reasons.append(f"{round_dir.name}: missing or empty patch.diff")
            continue
        review_patches.append((number, round_dir, patch))
    for _, kind, round_dir in revise_rounds:
        role = _round_role(round_dir)
        if role != "modifier":
            reasons.append(f"{round_dir.name}: unexpected role {role!r} for {kind}")

    # Cross-validation against the trial summary: a review round may exist
    # without counting (patch captured, reviewer failed), never the reverse.
    if not review_count <= len(review_patches) <= review_count + 1:
        reasons.append(
            f"review rounds ({len(review_patches)}) inconsistent with "
            f"reviewCount={review_count}"
        )
    if len(revise_rounds) != revision_count:
        reasons.append(
            f"revision rounds ({len(revise_rounds)}) inconsistent with "
            f"revisionCount={revision_count}"
        )
    if outcome not in _DELIVERABLE_OUTCOMES:
        reasons.append(f"unsupported workflow outcome {outcome!r}")

    final_sha = sha256_file(final_path)
    model_sha = sha256_file(model_path)
    if final_sha != model_sha:
        reasons.append(
            "final/patch.diff does not match artifacts/model.patch; "
            "the logged final is not the graded submission"
        )
    if final_path.stat().st_size == 0:
        reasons.append("final/patch.diff is empty")
    if reasons:
        raise LayoutError(trial_dir, reasons)

    # Stage mapping: first review patch is the initial; every later review
    # patch is the state after the previous revision; the final patch is the
    # last revision's result when it changed, otherwise an alias.
    stages: list[StagePatch] = []
    sha_to_stage: dict[str, str] = {}

    def add_stage(
        stage_id: str, patch_path: Path, sha: str, origin_round: str | None
    ) -> None:
        parent = stages[-1].stage_id if stages else None
        parent_sha = stages[-1].patch_sha256 if stages else None
        stages.append(
            StagePatch(
                stage_id=stage_id,
                parent_stage_id=parent,
                ordinal=len(stages),
                patch_path=patch_path,
                patch_sha256=sha,
                origin_round=origin_round,
                changed=sha != parent_sha,
                alias_of=sha_to_stage.get(sha),
            )
        )
        sha_to_stage.setdefault(sha, stage_id)

    first_number, first_dir, first_patch = review_patches[0]
    add_stage("initial", first_patch, sha256_file(first_patch), first_dir.name)
    for index, (number, round_dir, patch) in enumerate(review_patches[1:], start=1):
        add_stage(f"revision-{index}", patch, sha256_file(patch), round_dir.name)
    add_stage("final", final_path, final_sha, None)

    changed_after_initial = sum(1 for s in stages[1:] if s.changed)
    if changed_after_initial > revision_count:
        raise LayoutError(
            trial_dir,
            [
                f"observed {changed_after_initial} changed stages after initial "
                f"but summary records only revisionCount={revision_count}"
            ],
        )

    verifier_result = result.get("verifier_result")
    rewards = (
        verifier_result.get("rewards")
        if isinstance(verifier_result, dict)
        else None
    )
    eval_rewards = rewards if isinstance(rewards, dict) and "reward" in rewards else None

    completed_protocol = (
        outcome in _COMPLETED_PROTOCOL_OUTCOMES
        and all(_round_succeeded(path) for _, path in review_rounds)
        and all(_round_succeeded(path) for _, _, path in revise_rounds)
    )

    return TrialPatchSet(
        trial_dir=trial_dir,
        trial_name=trial_dir.name,
        task_name=str(summary_result.get("taskName") or task_dir.name),
        task_dir=task_dir,
        task_checksum=str(task_checksum),
        base_commit=str(base_commit),
        outcome=str(outcome),
        degraded_reason=summary_result.get("degradedReason"),
        review_count=review_count,
        revision_count=revision_count,
        no_change_revision=bool(summary_result.get("noChangeRevision")),
        eligible=True,
        ineligible_reason=None,
        completed_protocol=completed_protocol,
        stages=stages,
        eval_final_rewards=eval_rewards,
        environment_config=config.get("environment") or {},
        verifier_config=config.get("verifier") or {},
        timeout_multiplier=float(config.get("timeout_multiplier") or 1.0),
        verifier_timeout_multiplier=config.get("verifier_timeout_multiplier"),
    )
