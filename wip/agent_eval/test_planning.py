from __future__ import annotations

import unittest
from pathlib import Path

from wip.agent_eval.planning import PlanRequest, build_execution_plan
from wip.agent_eval.profiles import ProfileRegistry


ROOT = Path(__file__).resolve().parents[2]


def request(**overrides: object) -> PlanRequest:
    values: dict[str, object] = {
        "agent": "codex",
        "modifier": None,
        "reviewer": None,
        "model": None,
        "effort": None,
        "modifier_model": None,
        "modifier_effort": None,
        "reviewer_model": None,
        "reviewer_effort": None,
        "allow_unverified": False,
        "task_timeout_seconds": 5400.0,
        "agent_timeout_multiplier": 2.0,
        "cleanup_reserve_seconds": 300.0,
        "runtime_manifest_digest": "abc",
        "runtime_image": "deep-swe/agent-runtime:abc",
        "max_reviews": 3,
        "max_agent_attempts": 2,
        "reviewer_timeout_seconds": 600.0,
        "revision_timeout_seconds": 900.0,
        "min_turn_seconds": 120.0,
        "strict": False,
        "keep_workspaces": False,
    }
    values.update(overrides)
    return PlanRequest(**values)  # type: ignore[arg-type]


class PlanningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = ProfileRegistry.load(ROOT / "wip/config/agent-profiles.json")

    def test_single_has_no_reviewer_and_uses_full_budget(self) -> None:
        plan = build_execution_plan(request(), self.registry)
        self.assertEqual(plan.topology, "single")
        self.assertIsNone(plan.reviewer)
        self.assertEqual(plan.budget.hard_timeout_seconds, 10800.0)
        self.assertEqual(plan.budget.soft_deadline_seconds, 10500.0)

    def test_collab_resolves_roles(self) -> None:
        plan = build_execution_plan(
            request(agent="collab", modifier="kimi", reviewer="codex"),
            self.registry,
        )
        self.assertEqual(plan.workflow, "review-loop")
        self.assertEqual(plan.modifier.adapter, "kimi")
        self.assertEqual(plan.modifier.model, "kimi-code/k3")
        self.assertIsNotNone(plan.modifier.model_config)
        self.assertEqual(plan.reviewer.adapter, "codex")  # type: ignore[union-attr]

    def test_kimi_model_override_requires_versioned_profile(self) -> None:
        with self.assertRaisesRegex(ValueError, "versioned profile"):
            build_execution_plan(
                request(agent="kimi", model="kimi-code/k3-256k"), self.registry
            )

    def test_single_rejects_role_arguments(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not accept"):
            build_execution_plan(request(modifier="kimi"), self.registry)

    def test_collab_rejects_zero_reviews(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 1"):
            build_execution_plan(
                request(
                    agent="collab",
                    modifier="kimi",
                    reviewer="codex",
                    max_reviews=0,
                ),
                self.registry,
            )


if __name__ == "__main__":
    unittest.main()
