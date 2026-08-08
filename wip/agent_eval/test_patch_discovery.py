from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from wip.agent_eval.fixture_collab import (
    make_failed_modifier_trial,
    make_task,
    make_trial,
)
from wip.agent_eval.patch_discovery import LayoutError, discover_trial_patches


REAL_JOB = (
    Path(__file__).resolve().parents[2]
    / "jobs"
    / "collab-codex-opencode-05_sample_confirm-12-tasks-20260806-224833"
)


class PatchDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.job_dir = root / "jobs" / "job-a"
        self.job_dir.mkdir(parents=True)
        self.task_dir = make_task(root / "tasks", "task-a")

    def test_maps_initial_revisions_and_final(self) -> None:
        trial = make_trial(
            self.job_dir,
            self.task_dir,
            "task-a__one",
            review_patches=["patch-0", "patch-1", "patch-2"],
            final_patch="patch-3",
            outcome="max_reviews_reached",
            eval_rewards={"reward": 1},
        )
        result = discover_trial_patches(trial)
        self.assertTrue(result.eligible)
        self.assertEqual(
            [s.stage_id for s in result.stages],
            ["initial", "revision-1", "revision-2", "final"],
        )
        self.assertEqual(
            [s.parent_stage_id for s in result.stages],
            [None, "initial", "revision-1", "revision-2"],
        )
        self.assertTrue(all(s.changed for s in result.stages))
        self.assertEqual(result.review_count, 3)
        self.assertEqual(result.revision_count, 3)
        self.assertTrue(result.completed_protocol)
        self.assertEqual(result.eval_final_rewards, {"reward": 1})

    def test_final_aliases_last_review_when_approved(self) -> None:
        trial = make_trial(
            self.job_dir,
            self.task_dir,
            "task-a__two",
            review_patches=["patch-0", "patch-1"],
            final_patch="patch-1",
            eval_rewards={"reward": 0},
        )
        result = discover_trial_patches(trial)
        final = result.final
        self.assertIsNotNone(final)
        self.assertFalse(final.changed)
        self.assertEqual(final.alias_of, "revision-1")

    def test_first_round_approve_final_aliases_initial(self) -> None:
        trial = make_trial(
            self.job_dir,
            self.task_dir,
            "task-a__three",
            review_patches=["patch-0"],
            final_patch="patch-0",
            eval_rewards={"reward": 1},
        )
        result = discover_trial_patches(trial)
        self.assertEqual(len(result.stages), 2)
        self.assertEqual(result.final.alias_of, "initial")
        self.assertTrue(result.completed_protocol)

    def test_degraded_reviewer_failure_is_eligible_but_not_completed(self) -> None:
        trial = make_trial(
            self.job_dir,
            self.task_dir,
            "task-a__four",
            review_patches=["patch-0"],
            final_patch="patch-0",
            outcome="degraded",
            degraded_reason="reviewer_failed",
            review_statuses=["error"],
            review_count=0,
            eval_rewards={"reward": 1},
        )
        result = discover_trial_patches(trial)
        self.assertTrue(result.eligible)
        self.assertFalse(result.completed_protocol)
        self.assertEqual(result.final.alias_of, "initial")

    def test_modifier_failure_is_ineligible_not_layout_error(self) -> None:
        trial = make_failed_modifier_trial(self.job_dir, self.task_dir, "task-a__five")
        result = discover_trial_patches(trial)
        self.assertFalse(result.eligible)
        self.assertEqual(result.ineligible_reason, "no_initial_patch")
        self.assertEqual(result.stages, [])

    def test_final_model_patch_mismatch_fails_closed(self) -> None:
        trial = make_trial(
            self.job_dir,
            self.task_dir,
            "task-a__six",
            review_patches=["patch-0"],
            final_patch="patch-0",
            model_patch="something-else",
            eval_rewards={"reward": 1},
        )
        with self.assertRaises(LayoutError) as ctx:
            discover_trial_patches(trial)
        self.assertIn("does not match artifacts/model.patch", str(ctx.exception))

    def test_unknown_round_directory_fails_closed(self) -> None:
        trial = make_trial(
            self.job_dir,
            self.task_dir,
            "task-a__seven",
            review_patches=["patch-0"],
            final_patch="patch-0",
            eval_rewards={"reward": 1},
        )
        (trial / "agent" / "system" / "rounds" / "99-mystery").mkdir()
        with self.assertRaises(LayoutError) as ctx:
            discover_trial_patches(trial)
        self.assertIn("unrecognized round directory", str(ctx.exception))

    def test_review_count_mismatch_fails_closed(self) -> None:
        trial = make_trial(
            self.job_dir,
            self.task_dir,
            "task-a__eight",
            review_patches=["patch-0"],
            final_patch="patch-0",
            review_count=3,
            eval_rewards={"reward": 1},
        )
        with self.assertRaises(LayoutError) as ctx:
            discover_trial_patches(trial)
        self.assertIn("inconsistent with reviewCount", str(ctx.exception))

    def test_more_changes_than_revisions_fails_closed(self) -> None:
        trial = make_trial(
            self.job_dir,
            self.task_dir,
            "task-a__nine",
            review_patches=["patch-0", "patch-1"],
            final_patch="patch-1",
            eval_rewards={"reward": 1},
        )
        # Tamper: drop the revise round and its count so the observed stage
        # change (initial -> revision-1) has no recorded revision behind it.
        import shutil

        shutil.rmtree(trial / "agent" / "system" / "rounds" / "02-revise")
        summary_path = trial / "agent" / "system" / "summary.json"
        summary = json.loads(summary_path.read_text())
        summary["result"]["revisionCount"] = 0
        summary_path.write_text(json.dumps(summary))
        with self.assertRaises(LayoutError) as ctx:
            discover_trial_patches(trial)
        self.assertIn("changed stages", str(ctx.exception))

    def test_non_collab_trial_fails_closed(self) -> None:
        trial = make_trial(
            self.job_dir,
            self.task_dir,
            "task-a__ten",
            review_patches=["patch-0"],
            final_patch="patch-0",
            topology="single",
            eval_rewards={"reward": 1},
        )
        with self.assertRaises(LayoutError) as ctx:
            discover_trial_patches(trial)
        self.assertIn("not a collab trial", str(ctx.exception))

    def test_symlink_escape_fails_closed(self) -> None:
        trial = make_trial(
            self.job_dir,
            self.task_dir,
            "task-a__eleven",
            review_patches=["patch-0"],
            final_patch="patch-0",
            eval_rewards={"reward": 1},
        )
        outside = Path(self._tmp.name) / "outside.patch"
        outside.write_text("outside")
        final = trial / "agent" / "system" / "final" / "patch.diff"
        final.unlink()
        final.symlink_to(outside)
        with self.assertRaises(LayoutError) as ctx:
            discover_trial_patches(trial)
        self.assertIn("escapes trial dir", str(ctx.exception))

    def test_missing_eval_reward_reported_as_none(self) -> None:
        trial = make_trial(
            self.job_dir,
            self.task_dir,
            "task-a__twelve",
            review_patches=["patch-0"],
            final_patch="patch-0",
            eval_rewards=None,
        )
        result = discover_trial_patches(trial)
        self.assertIsNone(result.eval_final_rewards)


@unittest.skipUnless(REAL_JOB.is_dir(), "historical fixture job not present")
class RealJobLayoutTests(unittest.TestCase):
    """Read-only validation of the pinned historical job's layout profile."""

    def test_all_trials_discover_and_match_recorded_facts(self) -> None:
        trial_dirs = sorted(
            child
            for child in REAL_JOB.iterdir()
            if child.is_dir() and (child / "result.json").is_file()
        )
        self.assertEqual(len(trial_dirs), 24)
        alias_final = 0
        for trial_dir in trial_dirs:
            result = discover_trial_patches(trial_dir)
            self.assertTrue(result.eligible, trial_dir.name)
            self.assertIsNotNone(result.initial, trial_dir.name)
            self.assertIsNotNone(result.final, trial_dir.name)
            self.assertIsNotNone(result.eval_final_rewards, trial_dir.name)
            summary = json.loads(
                (trial_dir / "agent" / "system" / "summary.json").read_text()
            )["result"]
            changed = sum(1 for s in result.stages[1:] if s.changed)
            self.assertLessEqual(changed, summary["revisionCount"], trial_dir.name)
            if result.final.alias_of == "initial":
                alias_final += 1
        self.assertEqual(alias_final, 9)

    def test_degraded_trial_not_completed_protocol(self) -> None:
        trial_dir = next(REAL_JOB.glob("prometheus-typed-label-sorting__afHT*"))
        result = discover_trial_patches(trial_dir)
        self.assertEqual(result.outcome, "degraded")
        self.assertTrue(result.eligible)
        self.assertFalse(result.completed_protocol)


if __name__ == "__main__":
    unittest.main()
