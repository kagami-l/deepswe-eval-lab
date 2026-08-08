"""Post-hoc paired scoring of collab stage patches.

Deep module behind ``score_patch_job(job_dir, options, verifier)``: it hides
trial discovery, fingerprint identity, the job-local cache, verifier
concurrency and retry, final conformance, pair construction and the summary
statistics. The CLI only parses arguments, calls this, prints the summary and
maps the outcome to an exit code.
"""

from __future__ import annotations

import asyncio
import csv
import fnmatch
import hashlib
import json
import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .patch_discovery import (
    LayoutError,
    StagePatch,
    TrialPatchSet,
    discover_trial_patches,
)
from .patch_verifier import (
    ADAPTER_SCHEMA_VERSION,
    PatchVerifier,
    VerificationRequest,
)


SCORING_SCHEMA_VERSION = 1
_MAX_VERIFY_ATTEMPTS = 2
_BOOTSTRAP_ITERATIONS = 10_000
_BOOTSTRAP_SEED = 20260807

_STAGE_CSV_COLUMNS = [
    "task",
    "trial",
    "stage",
    "ordinal",
    "parent",
    "changed",
    "alias_of",
    "patch_sha256",
    "fingerprint_id",
    "score_source",
    "status",
    "reward",
    "f2p_passed",
    "f2p_total",
    "p2p_passed",
    "p2p_total",
    "partial",
    "final_conformance",
]
_PAIR_CSV_COLUMNS = [
    "task",
    "trial",
    "outcome",
    "degraded_reason",
    "review_count",
    "revision_count",
    "initial_reward",
    "final_reward",
    "delta",
    "classification",
    "final_score_source",
    "final_conformance",
    "itt_included",
    "completed_protocol",
]


class ScoringError(RuntimeError):
    """Fatal scoring problem; carries the process exit code."""

    def __init__(self, message: str, *, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


class LayoutIncompatibilityError(ScoringError):
    def __init__(self, errors: list[LayoutError]):
        details = "\n".join(str(error) for error in errors)
        super().__init__(
            "unsupported trial layout; no scores were written:\n" + details,
            exit_code=2,
        )
        self.errors = errors


@dataclass(frozen=True)
class ScoreOptions:
    trial_glob: str | None = None
    concurrency: int = 2
    reuse_final_score: bool = False
    force: bool = False


@dataclass
class _StageScore:
    stage: StagePatch
    fingerprint: dict[str, str]
    fingerprint_id: str
    score_source: str = "direct"  # "direct" | "eval" | "missing"
    status: str = "missing"
    rewards: dict[str, Any] | None = None
    scored_in_trial: str | None = None
    cached: bool = False

    @property
    def reward(self) -> float | None:
        if self.rewards is None:
            return None
        value = self.rewards.get("reward")
        return float(value) if isinstance(value, (int, float)) else None


@dataclass
class _UniqueWork:
    fingerprint: dict[str, str]
    fingerprint_id: str
    trial: TrialPatchSet
    stage: StagePatch
    result_dir: Path
    record: dict[str, Any] | None = None
    cached: bool = False


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_context_digest(tests_dir: Path) -> str:
    """Content digest of the verifier image build context (the tests dir)."""
    parts: list[str] = []
    for path in sorted(tests_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(tests_dir).as_posix()
        parts.append(f"{relative}:{hashlib.sha256(path.read_bytes()).hexdigest()}")
    return _sha256_text("\n".join(parts))


def task_config_digest(task_dir: Path) -> str:
    """Digest of the task definition the direct runner will actually read.

    The recorded ``task_checksum`` describes the task as it was at eval time,
    but the adapter loads the *current* ``task.toml`` (verifier image, user,
    timeout, environment). Hashing it keeps a changed task from silently
    reusing scores produced under the old definition.
    """
    return _sha256_text((task_dir / "task.toml").read_text())


def _verifier_config_digest(trial: TrialPatchSet) -> str:
    return _sha256_text(
        _canonical_json(
            {
                "environment": trial.environment_config,
                "verifier": trial.verifier_config,
                "timeoutMultiplier": trial.timeout_multiplier,
                "verifierTimeoutMultiplier": trial.verifier_timeout_multiplier,
            }
        )
    )


def _fingerprint(
    trial: TrialPatchSet,
    stage: StagePatch,
    *,
    identity: dict[str, str],
    context_digest: str,
    task_digest: str,
    verifier_digest: str,
) -> dict[str, str]:
    return {
        "schemaVersion": str(SCORING_SCHEMA_VERSION),
        "taskChecksum": trial.task_checksum,
        "taskConfigDigest": task_digest,
        "baseCommit": trial.base_commit,
        "patchSha256": stage.patch_sha256,
        "pierVersion": identity.get("pierVersion", ""),
        "verifierConfigDigest": verifier_digest,
        "buildContextDigest": context_digest,
        "adapterSchemaVersion": str(ADAPTER_SCHEMA_VERSION),
    }


def _fingerprint_id(fingerprint: dict[str, str]) -> str:
    return _sha256_text(_canonical_json(fingerprint))[:16]


def mcnemar_exact_p(improved: int, harmed: int) -> float | None:
    """Two-sided exact binomial (sign) test on the discordant pairs."""
    n = improved + harmed
    if n == 0:
        return None
    tail = min(improved, harmed)
    cumulative = sum(math.comb(n, k) for k in range(tail + 1)) / 2**n
    return min(1.0, 2.0 * cumulative)


def task_clustered_bootstrap_ci(
    deltas_by_task: dict[str, list[float]],
    *,
    iterations: int = _BOOTSTRAP_ITERATIONS,
    seed: int = _BOOTSTRAP_SEED,
) -> dict[str, float] | None:
    """95% CI of the mean paired delta, resampling tasks with replacement."""
    tasks = [task for task, deltas in deltas_by_task.items() if deltas]
    if not tasks:
        return None
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(iterations):
        drawn: list[float] = []
        for _ in range(len(tasks)):
            drawn.extend(deltas_by_task[rng.choice(tasks)])
        means.append(sum(drawn) / len(drawn))
    means.sort()

    def percentile(q: float) -> float:
        index = min(len(means) - 1, max(0, round(q * (len(means) - 1))))
        return means[index]

    return {
        "low": round(percentile(0.025), 6),
        "high": round(percentile(0.975), 6),
        "iterations": iterations,
        "seed": seed,
    }


def _select_trial_dirs(job_dir: Path, trial_glob: str | None) -> list[Path]:
    trials = [
        child
        for child in sorted(job_dir.iterdir())
        if child.is_dir()
        and not child.name.startswith(".")
        and child.name != "patch-scores"
        and (child / "result.json").is_file()
    ]
    if trial_glob is not None:
        trials = [t for t in trials if fnmatch.fnmatch(t.name, trial_glob)]
    return trials


def _is_reusable_record(record: Any, fingerprint_id: str) -> bool:
    """A cached record may be reused only if it carries a usable reward.

    A success record whose rewards are missing or malformed is treated as
    absent, so a plain re-run repairs it without needing ``--force``.
    """
    if not isinstance(record, dict):
        return False
    if record.get("status") != "success":
        return False
    if not isinstance(record.get("fingerprint"), dict):
        return False
    if record.get("fingerprintId") != fingerprint_id:
        return False
    rewards = record.get("rewards")
    if not isinstance(rewards, dict):
        return False
    return isinstance(rewards.get("reward"), (int, float)) and not isinstance(
        rewards.get("reward"), bool
    )


def _scan_cached_results(
    trial_dirs: list[Path],
) -> dict[str, tuple[Path, dict[str, Any]]]:
    """Index reusable result files by fingerprint id."""
    cache: dict[str, tuple[Path, dict[str, Any]]] = {}
    for trial_dir in trial_dirs:
        results_dir = trial_dir / "patch-scores" / "results"
        if not results_dir.is_dir():
            continue
        for result_dir in sorted(results_dir.iterdir()):
            result_path = result_dir / "result.json"
            if not result_path.is_file():
                continue
            try:
                record = json.loads(result_path.read_text())
            except (OSError, ValueError):
                continue
            if _is_reusable_record(record, result_dir.name):
                cache.setdefault(result_dir.name, (result_dir, record))
    return cache


async def _run_unique_work(
    work: _UniqueWork,
    verifier: PatchVerifier,
    semaphore: asyncio.Semaphore,
    identity: dict[str, str],
) -> None:
    attempts: list[dict[str, Any]] = []
    async with semaphore:
        for attempt in range(1, _MAX_VERIFY_ATTEMPTS + 1):
            record = await verifier.verify_patch(
                VerificationRequest(
                    task_dir=work.trial.task_dir,
                    patch_path=work.stage.patch_path,
                    output_dir=work.result_dir,
                    session_key=f"ps-{work.fingerprint_id}-a{attempt}",
                    environment_config=work.trial.environment_config,
                    verifier_config=work.trial.verifier_config,
                    timeout_multiplier=work.trial.timeout_multiplier,
                    verifier_timeout_multiplier=work.trial.verifier_timeout_multiplier,
                )
            )
            attempts.append(
                {
                    "attempt": attempt,
                    "status": record.status,
                    "errorType": record.error_type,
                    "errorMessage": record.error_message,
                    "startedAt": record.started_at,
                    "finishedAt": record.finished_at,
                    "durationSeconds": record.duration_seconds,
                }
            )
            if record.status == "success" or not record.retryable:
                break
    work.record = {
        "schemaVersion": SCORING_SCHEMA_VERSION,
        "fingerprintId": work.fingerprint_id,
        "fingerprint": work.fingerprint,
        "status": record.status,
        "rewards": record.rewards,
        "attempts": attempts,
        "identity": identity,
        "task": work.trial.task_name,
        "sourceTrial": work.trial.trial_name,
        "stage": work.stage.stage_id,
        "patchSha256": work.stage.patch_sha256,
        "generatedAt": _now(),
    }
    work.result_dir.mkdir(parents=True, exist_ok=True)
    (work.result_dir / "result.json").write_text(
        json.dumps(work.record, indent=2, sort_keys=True) + "\n"
    )


def _rewards_diff(
    eval_rewards: dict[str, Any], direct_rewards: dict[str, Any]
) -> dict[str, Any]:
    diff: dict[str, Any] = {}
    for key in sorted({*eval_rewards, *direct_rewards}):
        eval_value = eval_rewards.get(key)
        direct_value = direct_rewards.get(key)
        if eval_value != direct_value:
            diff[key] = {"eval": eval_value, "direct": direct_value}
    return diff


def _classify(delta: float | None) -> str:
    if delta is None:
        return "incomplete"
    if delta > 0:
        return "improved"
    if delta < 0:
        return "harmed"
    return "unchanged"


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(_canonical_json(row) + "\n" for row in rows))


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in columns})


def _pair_stats(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    complete = [p for p in pairs if p["delta"] is not None]
    improved = sum(1 for p in complete if p["classification"] == "improved")
    harmed = sum(1 for p in complete if p["classification"] == "harmed")
    unchanged = sum(1 for p in complete if p["classification"] == "unchanged")
    failed_both = sum(
        1
        for p in complete
        if p["initial_reward"] != 1 and p["final_reward"] != 1
    )
    passed_both = sum(
        1
        for p in complete
        if p["initial_reward"] == 1 and p["final_reward"] == 1
    )
    deltas_by_task: dict[str, list[float]] = {}
    for pair in complete:
        deltas_by_task.setdefault(pair["task"], []).append(pair["delta"])
    mean_delta = (
        sum(p["delta"] for p in complete) / len(complete) if complete else None
    )
    return {
        "pairs": len(pairs),
        "complete": len(complete),
        "initialPassRate": (
            sum(1 for p in complete if p["initial_reward"] == 1) / len(complete)
            if complete
            else None
        ),
        "finalPassRate": (
            sum(1 for p in complete if p["final_reward"] == 1) / len(complete)
            if complete
            else None
        ),
        "improved": improved,
        "harmed": harmed,
        "unchanged": unchanged,
        # Full paired 2x2 over the binary outcome; improved/harmed above are
        # the discordant cells, these two split `unchanged`.
        "twoByTwo": {
            "failedBoth": failed_both,
            "improved": improved,
            "harmed": harmed,
            "passedBoth": passed_both,
        },
        "meanPairedDelta": mean_delta,
        "mcnemarExactP": mcnemar_exact_p(improved, harmed),
        "taskClusteredBootstrap95CI": task_clustered_bootstrap_ci(deltas_by_task),
        "discordantTrials": {
            "improved": [
                f"{p['task']}/{p['trial']}"
                for p in complete
                if p["classification"] == "improved"
            ],
            "harmed": [
                f"{p['task']}/{p['trial']}"
                for p in complete
                if p["classification"] == "harmed"
            ],
        },
    }


async def score_patch_job(
    job_dir: Path,
    options: ScoreOptions,
    verifier: PatchVerifier,
    *,
    identity: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Score every unique stage patch in the job and build the paired summary.

    Returns the summary dict; raises ``ScoringError`` for fatal problems. The
    summary carries ``exitCode`` describing coverage/conformance health.
    """
    job_dir = job_dir.resolve()
    if not job_dir.is_dir():
        raise ScoringError(f"job directory not found: {job_dir}", exit_code=2)
    identity = dict(identity or {})
    identity.setdefault("adapterSchemaVersion", str(ADAPTER_SCHEMA_VERSION))

    trial_dirs = _select_trial_dirs(job_dir, options.trial_glob)
    if not trial_dirs:
        raise ScoringError(
            f"no trials matched in {job_dir}"
            + (f" (glob {options.trial_glob!r})" if options.trial_glob else ""),
            exit_code=2,
        )

    # Read-only compatibility scan over the full selection before any verifier
    # starts; unsupported layouts fail closed without partial writes.
    trials: list[TrialPatchSet] = []
    layout_errors: list[LayoutError] = []
    for trial_dir in trial_dirs:
        try:
            trials.append(discover_trial_patches(trial_dir))
        except LayoutError as error:
            layout_errors.append(error)
    if layout_errors:
        raise LayoutIncompatibilityError(layout_errors)

    eligible = [t for t in trials if t.eligible]
    ineligible = [t for t in trials if not t.eligible]

    # A trial that declared job-level artifacts cannot be reproduced from the
    # frozen patch alone: those files came from the agent container, which is
    # gone. Fail closed rather than score a different verifier input.
    with_job_artifacts = [t for t in eligible if t.job_artifacts]
    if with_job_artifacts:
        raise ScoringError(
            "these trials declare job-level artifacts that cannot be replayed "
            "from a frozen patch: "
            + ", ".join(t.trial_name for t in with_job_artifacts),
            exit_code=2,
        )

    context_digests: dict[Path, str] = {}
    task_digests: dict[Path, str] = {}
    verifier_digests: dict[str, str] = {}
    stage_scores: dict[tuple[str, str], _StageScore] = {}
    unique_work: dict[str, _UniqueWork] = {}

    for trial in eligible:
        tests_dir = trial.task_dir / "tests"
        if tests_dir not in context_digests:
            if not tests_dir.is_dir():
                raise ScoringError(
                    f"task tests directory missing: {tests_dir}", exit_code=2
                )
            context_digests[tests_dir] = build_context_digest(tests_dir)
            task_digests[tests_dir] = task_config_digest(trial.task_dir)
        verifier_digests.setdefault(trial.trial_name, _verifier_config_digest(trial))
        for stage in trial.stages:
            fingerprint = _fingerprint(
                trial,
                stage,
                identity=identity,
                context_digest=context_digests[tests_dir],
                task_digest=task_digests[tests_dir],
                verifier_digest=verifier_digests[trial.trial_name],
            )
            fp_id = _fingerprint_id(fingerprint)
            stage_scores[(trial.trial_name, stage.stage_id)] = _StageScore(
                stage=stage, fingerprint=fingerprint, fingerprint_id=fp_id
            )
            skip_direct = (
                options.reuse_final_score
                and stage.stage_id == "final"
                and not any(
                    s.stage_id != "final" and s.patch_sha256 == stage.patch_sha256
                    for s in trial.stages
                )
            )
            if fp_id not in unique_work and not skip_direct:
                unique_work[fp_id] = _UniqueWork(
                    fingerprint=fingerprint,
                    fingerprint_id=fp_id,
                    trial=trial,
                    stage=stage,
                    result_dir=trial.trial_dir
                    / "patch-scores"
                    / "results"
                    / fp_id,
                )

    cached = {} if options.force else _scan_cached_results(trial_dirs)
    pending: list[_UniqueWork] = []
    for fp_id, work in unique_work.items():
        hit = cached.get(fp_id)
        if hit is not None and hit[1].get("fingerprint") == work.fingerprint:
            work.record = hit[1]
            work.cached = True
        else:
            pending.append(work)

    semaphore = asyncio.Semaphore(max(1, options.concurrency))
    await asyncio.gather(
        *(
            _run_unique_work(work, verifier, semaphore, identity)
            for work in pending
        )
    )

    # Attach unique results back onto every stage occurrence.
    for (trial_name, stage_id), score in stage_scores.items():
        work = unique_work.get(score.fingerprint_id)
        if work is not None and work.record is not None:
            score.status = str(work.record.get("status"))
            rewards = work.record.get("rewards")
            score.rewards = rewards if isinstance(rewards, dict) else None
            score.scored_in_trial = str(work.record.get("sourceTrial"))
            score.cached = work.cached
            score.score_source = "direct"

    stage_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    verifier_error_kinds: dict[str, int] = {}

    for trial in eligible:
        conformance = "unavailable"
        rewards_diff: dict[str, Any] = {}
        final_score = stage_scores[(trial.trial_name, "final")]
        final_source = "direct"
        eval_rewards = trial.eval_final_rewards

        if options.reuse_final_score:
            final_source = "eval"
            conformance = "skipped"
            if eval_rewards is not None:
                final_score.score_source = "eval"
                final_score.status = "success"
                final_score.rewards = dict(eval_rewards)
                final_score.scored_in_trial = trial.trial_name
        else:
            direct_rewards = final_score.rewards
            if eval_rewards is None or final_score.status != "success":
                conformance = "unavailable"
            else:
                rewards_diff = _rewards_diff(eval_rewards, direct_rewards or {})
                eval_reward = eval_rewards.get("reward")
                direct_reward = (direct_rewards or {}).get("reward")
                conformance = (
                    "matched" if eval_reward == direct_reward else "mismatched"
                )

        for stage in trial.stages:
            score = stage_scores[(trial.trial_name, stage.stage_id)]
            if score.status not in {"success", "missing"}:
                # Tally terminal verifier failures once per unique fingerprint.
                work = unique_work.get(score.fingerprint_id)
                if work is not None and work.stage is stage and work.trial is trial:
                    for attempt in (work.record or {}).get("attempts", []):
                        kind = attempt.get("errorType")
                        if kind:
                            verifier_error_kinds[kind] = (
                                verifier_error_kinds.get(kind, 0) + 1
                            )
            rewards = score.rewards or {}
            stage_rows.append(
                {
                    "task": trial.task_name,
                    "trial": trial.trial_name,
                    "stage": stage.stage_id,
                    "ordinal": stage.ordinal,
                    "parent": stage.parent_stage_id or "",
                    "changed": stage.changed,
                    "alias_of": stage.alias_of or "",
                    "patch_sha256": stage.patch_sha256,
                    "fingerprint_id": score.fingerprint_id,
                    "score_source": score.score_source,
                    "status": score.status,
                    "reward": rewards.get("reward", ""),
                    "f2p_passed": rewards.get("f2p_passed", ""),
                    "f2p_total": rewards.get("f2p_total", ""),
                    "p2p_passed": rewards.get("p2p_passed", ""),
                    "p2p_total": rewards.get("p2p_total", ""),
                    "partial": rewards.get("partial", ""),
                    "final_conformance": (
                        conformance if stage.stage_id == "final" else ""
                    ),
                }
            )

        initial_score = stage_scores[(trial.trial_name, "initial")]
        initial_reward = initial_score.reward
        final_reward = final_score.reward
        delta = (
            final_reward - initial_reward
            if initial_reward is not None and final_reward is not None
            else None
        )
        itt_included = delta is not None and conformance in {"matched", "skipped"}
        revision_deltas = []
        for stage in trial.stages[1:]:
            if not stage.changed:
                continue
            child = stage_scores[(trial.trial_name, stage.stage_id)]
            parent = stage_scores[(trial.trial_name, stage.parent_stage_id)]
            if child.reward is None or parent.reward is None:
                continue
            revision_deltas.append(
                {
                    "stage": stage.stage_id,
                    "parent": stage.parent_stage_id,
                    "delta": child.reward - parent.reward,
                }
            )
        pair = {
            "task": trial.task_name,
            "trial": trial.trial_name,
            "outcome": trial.outcome,
            "degraded_reason": trial.degraded_reason or "",
            "review_count": trial.review_count,
            "revision_count": trial.revision_count,
            "initial_reward": initial_reward,
            "final_reward": final_reward,
            "delta": delta,
            "classification": _classify(delta),
            "final_score_source": final_source,
            "final_conformance": conformance,
            "final_rewards_diff": rewards_diff,
            "itt_included": itt_included,
            "completed_protocol": trial.completed_protocol,
            "revision_deltas": revision_deltas,
        }
        pair_rows.append(pair)

        trial_scores_dir = trial.trial_dir / "patch-scores"
        trial_scores_dir.mkdir(parents=True, exist_ok=True)
        (trial_scores_dir / "stages.json").write_text(
            json.dumps(
                {
                    "schemaVersion": SCORING_SCHEMA_VERSION,
                    "generatedAt": _now(),
                    "trial": trial.trial_name,
                    "task": trial.task_name,
                    "outcome": trial.outcome,
                    "evalFinalRewards": eval_rewards,
                    "finalScoreSource": final_source,
                    "finalConformance": conformance,
                    "finalRewardsDiff": rewards_diff,
                    "pair": pair,
                    "stages": [
                        {
                            "stageId": s.stage_id,
                            "parentStageId": s.parent_stage_id,
                            "ordinal": s.ordinal,
                            "originRound": s.origin_round,
                            "changed": s.changed,
                            "aliasOf": s.alias_of,
                            "patchPath": str(
                                s.patch_path.relative_to(trial.trial_dir)
                            ),
                            "patchSha256": s.patch_sha256,
                            "fingerprintId": stage_scores[
                                (trial.trial_name, s.stage_id)
                            ].fingerprint_id,
                            "scoreSource": stage_scores[
                                (trial.trial_name, s.stage_id)
                            ].score_source,
                            "scoredInTrial": stage_scores[
                                (trial.trial_name, s.stage_id)
                            ].scored_in_trial,
                            "status": stage_scores[
                                (trial.trial_name, s.stage_id)
                            ].status,
                            "rewards": stage_scores[
                                (trial.trial_name, s.stage_id)
                            ].rewards,
                        }
                        for s in trial.stages
                    ],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

    itt_pairs = [p for p in pair_rows if p["itt_included"]]
    cp_pairs = [p for p in itt_pairs if p["completed_protocol"]]
    incomplete_pairs = [p for p in pair_rows if p["delta"] is None]
    mismatched = [p for p in pair_rows if p["final_conformance"] == "mismatched"]
    unavailable = [p for p in pair_rows if p["final_conformance"] == "unavailable"]

    exit_code = 0
    problems: list[str] = []
    if incomplete_pairs:
        exit_code = 1
        problems.append(
            f"{len(incomplete_pairs)} pair(s) lack a verifier score; "
            "re-run score-patches to fill missing stages"
        )
    if not options.reuse_final_score:
        if mismatched:
            exit_code = 1
            problems.append(
                f"{len(mismatched)} pair(s) have nonconformant final rewards"
            )
        if unavailable:
            exit_code = 1
            problems.append(
                f"{len(unavailable)} pair(s) lack an eval final reward to compare"
            )

    summary = {
        "schemaVersion": SCORING_SCHEMA_VERSION,
        "generatedAt": _now(),
        "jobPath": str(job_dir),
        "options": {
            "trialGlob": options.trial_glob,
            "concurrency": options.concurrency,
            "reuseFinalScore": options.reuse_final_score,
            "force": options.force,
        },
        "identity": identity,
        "coverage": {
            "totalTrials": len(trials),
            "eligibleTrials": len(eligible),
            "ineligibleTrials": [
                {"trial": t.trial_name, "reason": t.ineligible_reason}
                for t in ineligible
            ],
            "completePairs": len(pair_rows) - len(incomplete_pairs),
            "incompletePairs": [
                f"{p['task']}/{p['trial']}" for p in incomplete_pairs
            ],
            "uniquePatches": len(unique_work),
            "scoredPatches": sum(1 for w in unique_work.values() if not w.cached),
            "cachedPatches": sum(1 for w in unique_work.values() if w.cached),
        },
        "finalConformance": {
            "matched": sum(
                1 for p in pair_rows if p["final_conformance"] == "matched"
            ),
            "mismatched": [
                f"{p['task']}/{p['trial']}" for p in mismatched
            ],
            "skipped": sum(
                1 for p in pair_rows if p["final_conformance"] == "skipped"
            ),
            "unavailable": [
                f"{p['task']}/{p['trial']}" for p in unavailable
            ],
        },
        "intentionToTreat": _pair_stats(itt_pairs),
        "completedProtocol": _pair_stats(cp_pairs),
        "verifierErrors": verifier_error_kinds,
        "problems": problems,
        "exitCode": exit_code,
    }

    scores_dir = job_dir / "patch-scores"
    scores_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schemaVersion": SCORING_SCHEMA_VERSION,
        "generatedAt": summary["generatedAt"],
        "jobPath": str(job_dir),
        "options": summary["options"],
        "identity": identity,
        "selectedTrials": [t.trial_name for t in trials],
    }
    (scores_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    _write_jsonl(scores_dir / "stages.jsonl", stage_rows)
    _write_csv(scores_dir / "stages.csv", _STAGE_CSV_COLUMNS, stage_rows)
    _write_jsonl(scores_dir / "pairs.jsonl", pair_rows)
    _write_csv(scores_dir / "pairs.csv", _PAIR_CSV_COLUMNS, pair_rows)
    (scores_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    return summary
