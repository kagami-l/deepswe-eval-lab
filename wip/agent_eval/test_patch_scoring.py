from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from wip.agent_eval.fixture_collab import (
    make_failed_modifier_trial,
    make_task,
    make_trial,
)
from wip.agent_eval.patch_scoring import (
    LayoutIncompatibilityError,
    ScoreOptions,
    ScoringError,
    mcnemar_exact_p,
    score_patch_job,
    task_clustered_bootstrap_ci,
)
from wip.agent_eval.patch_verifier import VerificationRecord, VerificationRequest


def _rewards(reward: int, f2p_passed: int = 1, f2p_total: int = 1) -> dict[str, Any]:
    return {
        "reward": reward,
        "f2p_total": f2p_total,
        "f2p_passed": f2p_passed,
        "p2p_total": 2,
        "p2p_passed": 2,
        "partial": 1.0,
    }


class FakeVerifier:
    """Scores patches by content; can script failures per patch content."""

    def __init__(
        self,
        rewards_by_content: dict[str, dict[str, Any]],
        *,
        scripted_failures: dict[str, list[VerificationRecord]] | None = None,
    ):
        self.rewards_by_content = rewards_by_content
        self.scripted_failures = {
            key: list(records) for key, records in (scripted_failures or {}).items()
        }
        self.calls: list[str] = []
        self.active = 0
        self.max_active = 0

    async def verify_patch(self, request: VerificationRequest) -> VerificationRecord:
        content = request.patch_path.read_text()
        self.calls.append(content)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.01)
            queued = self.scripted_failures.get(content)
            if queued:
                return queued.pop(0)
            rewards = self.rewards_by_content.get(content)
            if rewards is None:
                return VerificationRecord(
                    status="error",
                    error_type="RewardFileNotFoundError",
                    error_message=f"no scripted reward for {content!r}",
                    retryable=True,
                )
            return VerificationRecord(status="success", rewards=dict(rewards))
        finally:
            self.active -= 1


def _run(job_dir: Path, verifier: FakeVerifier, **kwargs: Any) -> dict[str, Any]:
    options = ScoreOptions(**kwargs)
    return asyncio.run(
        score_patch_job(job_dir, options, verifier, identity={"pierVersion": "0.3.0"})
    )


class PatchScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.job_dir = self.root / "jobs" / "job-a"
        self.job_dir.mkdir(parents=True)
        self.task_a = make_task(self.root / "tasks", "task-a")
        self.task_b = make_task(self.root / "tasks", "task-b")

    def _standard_job(self) -> FakeVerifier:
        # task-a trial one: review fixed the patch (0 -> 1), eval agrees.
        make_trial(
            self.job_dir,
            self.task_a,
            "task-a__one",
            review_patches=["a-initial", "a-revised"],
            final_patch="a-revised",
            eval_rewards=_rewards(1),
        )
        # task-a trial two: first-round approve, final aliases initial.
        make_trial(
            self.job_dir,
            self.task_a,
            "task-a__two",
            review_patches=["a2-initial"],
            final_patch="a2-initial",
            eval_rewards=_rewards(1),
        )
        # task-b: review harmed the patch (1 -> 0); degraded workflow.
        make_trial(
            self.job_dir,
            self.task_b,
            "task-b__one",
            review_patches=["b-initial", "b-revised"],
            final_patch="b-revised",
            outcome="degraded",
            degraded_reason="timeout",
            review_count=2,
            eval_rewards=_rewards(0, f2p_passed=0),
        )
        return FakeVerifier(
            {
                "a-initial": _rewards(0, f2p_passed=0),
                "a-revised": _rewards(1),
                "a2-initial": _rewards(1),
                "b-initial": _rewards(1),
                "b-revised": _rewards(0, f2p_passed=0),
            }
        )

    def test_end_to_end_summary_and_outputs(self) -> None:
        verifier = self._standard_job()
        summary = _run(self.job_dir, verifier)
        self.assertEqual(summary["exitCode"], 0)
        coverage = summary["coverage"]
        self.assertEqual(coverage["totalTrials"], 3)
        self.assertEqual(coverage["eligibleTrials"], 3)
        self.assertEqual(coverage["uniquePatches"], 5)
        self.assertEqual(coverage["scoredPatches"], 5)
        self.assertEqual(sorted(verifier.calls), sorted(verifier.rewards_by_content))

        itt = summary["intentionToTreat"]
        self.assertEqual(itt["pairs"], 3)
        self.assertEqual(itt["improved"], 1)
        self.assertEqual(itt["harmed"], 1)
        self.assertEqual(itt["unchanged"], 1)
        self.assertEqual(itt["meanPairedDelta"], 0.0)
        self.assertEqual(itt["mcnemarExactP"], 1.0)
        self.assertEqual(
            itt["discordantTrials"]["harmed"], ["task-b/task-b__one"]
        )

        # Degraded trial is ITT-only; completed-protocol keeps the other two.
        cp = summary["completedProtocol"]
        self.assertEqual(cp["pairs"], 2)
        self.assertEqual(cp["harmed"], 0)

        conformance = summary["finalConformance"]
        self.assertEqual(conformance["matched"], 3)
        self.assertEqual(conformance["mismatched"], [])

        scores_dir = self.job_dir / "patch-scores"
        for name in (
            "manifest.json",
            "stages.jsonl",
            "stages.csv",
            "pairs.jsonl",
            "pairs.csv",
            "summary.json",
        ):
            self.assertTrue((scores_dir / name).is_file(), name)
        pairs = [
            json.loads(line)
            for line in (scores_dir / "pairs.jsonl").read_text().splitlines()
        ]
        self.assertEqual(len(pairs), 3)
        stage_rows = [
            json.loads(line)
            for line in (scores_dir / "stages.jsonl").read_text().splitlines()
        ]
        self.assertEqual(len(stage_rows), 3 + 2 + 3)
        trial_stages = json.loads(
            (self.job_dir / "task-a__one" / "patch-scores" / "stages.json").read_text()
        )
        self.assertEqual(trial_stages["finalConformance"], "matched")
        self.assertEqual(
            trial_stages["pair"]["revision_deltas"],
            [{"stage": "revision-1", "parent": "initial", "delta": 1.0}],
        )

    def test_idempotent_rerun_uses_cache(self) -> None:
        verifier = self._standard_job()
        first = _run(self.job_dir, verifier)
        calls_after_first = len(verifier.calls)
        second = _run(self.job_dir, verifier)
        self.assertEqual(len(verifier.calls), calls_after_first)
        self.assertEqual(second["coverage"]["cachedPatches"], 5)
        self.assertEqual(second["coverage"]["scoredPatches"], 0)
        self.assertEqual(first["exitCode"], second["exitCode"])

    def test_force_rescoring_ignores_cache(self) -> None:
        verifier = self._standard_job()
        _run(self.job_dir, verifier)
        calls_after_first = len(verifier.calls)
        _run(self.job_dir, verifier, force=True)
        self.assertEqual(len(verifier.calls), calls_after_first * 2)

    def test_cache_requires_fingerprint_match(self) -> None:
        verifier = self._standard_job()
        _run(self.job_dir, verifier)
        calls_after_first = len(verifier.calls)
        # Corrupt one cached fingerprint; only that patch is re-scored.
        results = list((self.job_dir / "task-a__one" / "patch-scores" / "results").iterdir())
        record_path = results[0] / "result.json"
        record = json.loads(record_path.read_text())
        record["fingerprint"]["pierVersion"] = "9.9.9"
        record_path.write_text(json.dumps(record))
        _run(self.job_dir, verifier)
        self.assertEqual(len(verifier.calls), calls_after_first + 1)

    def test_reward_zero_is_not_retried(self) -> None:
        make_trial(
            self.job_dir,
            self.task_a,
            "task-a__one",
            review_patches=["zero"],
            final_patch="zero",
            eval_rewards=_rewards(0, f2p_passed=0),
        )
        verifier = FakeVerifier({"zero": _rewards(0, f2p_passed=0)})
        summary = _run(self.job_dir, verifier)
        self.assertEqual(len(verifier.calls), 1)
        self.assertEqual(summary["exitCode"], 0)

    def test_infrastructure_failure_retries_once_then_succeeds(self) -> None:
        make_trial(
            self.job_dir,
            self.task_a,
            "task-a__one",
            review_patches=["flaky"],
            final_patch="flaky",
            eval_rewards=_rewards(1),
        )
        verifier = FakeVerifier(
            {"flaky": _rewards(1)},
            scripted_failures={
                "flaky": [
                    VerificationRecord(
                        status="timeout",
                        error_type="VerifierTimeoutError",
                        error_message="slow",
                        retryable=True,
                    )
                ]
            },
        )
        summary = _run(self.job_dir, verifier)
        self.assertEqual(len(verifier.calls), 2)
        self.assertEqual(summary["exitCode"], 0)
        record = json.loads(
            next(
                (self.job_dir / "task-a__one" / "patch-scores" / "results").glob(
                    "*/result.json"
                )
            ).read_text()
        )
        self.assertEqual(len(record["attempts"]), 2)
        self.assertEqual(record["status"], "success")

    def test_retry_exhaustion_marks_pair_incomplete(self) -> None:
        make_trial(
            self.job_dir,
            self.task_a,
            "task-a__one",
            review_patches=["broken"],
            final_patch="broken",
            eval_rewards=_rewards(1),
        )
        failure = VerificationRecord(
            status="error",
            error_type="AddTestsDirError",
            error_message="boom",
            retryable=True,
        )
        verifier = FakeVerifier(
            {}, scripted_failures={"broken": [failure, failure]}
        )
        summary = _run(self.job_dir, verifier)
        self.assertEqual(len(verifier.calls), 2)
        self.assertEqual(summary["exitCode"], 1)
        self.assertEqual(
            summary["coverage"]["incompletePairs"], ["task-a/task-a__one"]
        )
        self.assertEqual(summary["verifierErrors"], {"AddTestsDirError": 2})
        self.assertEqual(summary["intentionToTreat"]["pairs"], 0)

    def test_conformance_mismatch_is_nonconformant_and_nonzero(self) -> None:
        make_trial(
            self.job_dir,
            self.task_a,
            "task-a__one",
            review_patches=["drift"],
            final_patch="drift",
            eval_rewards=_rewards(1),
        )
        verifier = FakeVerifier({"drift": _rewards(0, f2p_passed=0)})
        summary = _run(self.job_dir, verifier)
        self.assertEqual(summary["exitCode"], 1)
        self.assertEqual(
            summary["finalConformance"]["mismatched"], ["task-a/task-a__one"]
        )
        self.assertEqual(summary["intentionToTreat"]["pairs"], 0)
        pair = json.loads(
            (self.job_dir / "patch-scores" / "pairs.jsonl").read_text()
        )
        self.assertEqual(pair["final_conformance"], "mismatched")
        self.assertIn("reward", pair["final_rewards_diff"])

    def test_reuse_final_score_skips_direct_final(self) -> None:
        make_trial(
            self.job_dir,
            self.task_a,
            "task-a__one",
            review_patches=["r-initial"],
            final_patch="r-final",
            outcome="max_reviews_reached",
            eval_rewards=_rewards(1),
        )
        verifier = FakeVerifier({"r-initial": _rewards(0, f2p_passed=0)})
        summary = _run(self.job_dir, verifier, reuse_final_score=True)
        self.assertEqual(verifier.calls, ["r-initial"])
        self.assertEqual(summary["exitCode"], 0)
        self.assertEqual(summary["finalConformance"]["skipped"], 1)
        pair = json.loads(
            (self.job_dir / "patch-scores" / "pairs.jsonl").read_text()
        )
        self.assertEqual(pair["final_score_source"], "eval")
        self.assertEqual(pair["delta"], 1.0)
        self.assertTrue(pair["itt_included"])

    def test_reuse_final_score_still_scores_alias_of_initial(self) -> None:
        make_trial(
            self.job_dir,
            self.task_a,
            "task-a__one",
            review_patches=["same"],
            final_patch="same",
            eval_rewards=_rewards(1),
        )
        verifier = FakeVerifier({"same": _rewards(1)})
        summary = _run(self.job_dir, verifier, reuse_final_score=True)
        # The shared patch is scored once for the initial stage; the final
        # stage still reports the eval reward with conformance skipped.
        self.assertEqual(verifier.calls, ["same"])
        self.assertEqual(summary["exitCode"], 0)
        self.assertEqual(summary["finalConformance"]["skipped"], 1)

    def test_trial_glob_filters_selection(self) -> None:
        verifier = self._standard_job()
        summary = _run(self.job_dir, verifier, trial_glob="task-a__*")
        self.assertEqual(summary["coverage"]["totalTrials"], 2)
        self.assertEqual(
            sorted({call for call in verifier.calls}),
            ["a-initial", "a-revised", "a2-initial"],
        )

    def test_concurrency_is_bounded(self) -> None:
        verifier = self._standard_job()
        _run(self.job_dir, verifier, concurrency=2)
        self.assertLessEqual(verifier.max_active, 2)

    def test_ineligible_trial_counts_in_coverage_not_pairs(self) -> None:
        verifier = self._standard_job()
        make_failed_modifier_trial(self.job_dir, self.task_a, "task-a__failed")
        summary = _run(self.job_dir, verifier)
        self.assertEqual(summary["coverage"]["totalTrials"], 4)
        self.assertEqual(summary["coverage"]["eligibleTrials"], 3)
        self.assertEqual(
            summary["coverage"]["ineligibleTrials"],
            [{"trial": "task-a__failed", "reason": "no_initial_patch"}],
        )
        self.assertEqual(summary["intentionToTreat"]["pairs"], 3)
        self.assertEqual(summary["exitCode"], 0)

    def test_layout_error_fails_closed_without_writes(self) -> None:
        verifier = self._standard_job()
        make_trial(
            self.job_dir,
            self.task_b,
            "task-b__broken",
            review_patches=["x"],
            final_patch="x",
            model_patch="mismatch",
            eval_rewards=_rewards(1),
        )
        with self.assertRaises(LayoutIncompatibilityError):
            _run(self.job_dir, verifier)
        self.assertEqual(verifier.calls, [])
        self.assertFalse((self.job_dir / "patch-scores").exists())

    def test_missing_job_dir_raises(self) -> None:
        with self.assertRaises(ScoringError):
            _run(self.root / "jobs" / "missing", FakeVerifier({}))

    def test_original_trial_files_untouched(self) -> None:
        verifier = self._standard_job()

        def digest_tree(base: Path) -> dict[str, str]:
            return {
                str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(base.rglob("*"))
                if p.is_file() and "patch-scores" not in p.parts
            }

        before = digest_tree(self.job_dir)
        _run(self.job_dir, verifier)
        self.assertEqual(digest_tree(self.job_dir), before)


class StatsTests(unittest.TestCase):
    def test_mcnemar_exact_two_sided(self) -> None:
        self.assertIsNone(mcnemar_exact_p(0, 0))
        self.assertEqual(mcnemar_exact_p(1, 0), 1.0)
        self.assertAlmostEqual(mcnemar_exact_p(8, 1), 0.0390625)
        self.assertAlmostEqual(mcnemar_exact_p(5, 5), 1.0)

    def test_bootstrap_ci_is_deterministic_and_bounded(self) -> None:
        deltas = {"t1": [1.0, 0.0], "t2": [0.0], "t3": [-1.0, 0.0]}
        first = task_clustered_bootstrap_ci(deltas, iterations=500)
        second = task_clustered_bootstrap_ci(deltas, iterations=500)
        self.assertEqual(first, second)
        self.assertLessEqual(first["low"], first["high"])
        self.assertGreaterEqual(first["low"], -1.0)
        self.assertLessEqual(first["high"], 1.0)
        self.assertIsNone(task_clustered_bootstrap_ci({}))


if __name__ == "__main__":
    unittest.main()
