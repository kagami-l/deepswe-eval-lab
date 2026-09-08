from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from pier.models.agent.context import AgentContext

from wip.agents.deep_swe_agent.atif import events_to_trajectory
from wip.agents.deep_swe_agent.test_pier_agent import agent, plan
from wip.scripts.token_usage import build_report, print_report


REPORT = {
    "toolUses": 2,
    "tokens": {
        "coverage": "complete",
        "totals": {
            "input": {"total": 100, "uncached": 30, "cacheRead": 60, "cacheWrite": 10},
            "output": {"total": 20, "visible": 5, "reasoning": 15},
        },
        "records": [
            {"model": "main", "tokens": {"input": {"total": 70}, "output": {"total": 12}}},
            {"model": "child", "tokens": {"input": {"total": 30}, "output": {"total": 8}}},
        ],
    },
    "cost": {"amount": 0.125, "currency": "USD", "source": "agent-estimate"},
}


def summary_usage(report):
    tokens = report.get("tokens")
    cost = report.get("cost")
    return {
        "usageSchema": 2,
        "usageReports": [report],
        "tokens": tokens,
        "tokenCoverage": tokens["coverage"] if tokens else "unavailable",
        "tokenAvailability": "reported" if tokens else "unavailable",
        "inputTokens": tokens["totals"]["input"]["total"] if tokens else None,
        "outputTokens": tokens["totals"]["output"]["total"] if tokens else None,
        "costUsd": cost["amount"] if cost else None,
        "costCoverage": "complete" if cost else "unavailable",
        "toolUses": report["toolUses"],
        "turns": 1,
        "wallMs": 10,
    }


def event(report, label="modify-a1"):
    return {
        "label": label,
        "sessionId": "fixture",
        "agent": "claude-code",
        "type": "done",
        "payload": {"status": "success", "result": "fixed", "usage": report},
    }


class UsageUpgradeTests(unittest.TestCase):
    def test_atif_preserves_complete_partial_missing_and_cost_only(self):
        for coverage in ("complete", "partial"):
            report = copy.deepcopy(REPORT)
            report["tokens"]["coverage"] = coverage
            trajectory = events_to_trajectory(
                events=[event(report)], instruction="fix", summary=None, agent_version="test"
            )
            metrics = trajectory.steps[1].metrics
            self.assertEqual(metrics.prompt_tokens, 100)
            self.assertEqual(metrics.completion_tokens, 20)
            self.assertEqual(metrics.cached_tokens, 60)
            self.assertEqual(metrics.extra["usage"], report)
            self.assertEqual(metrics.extra["token_coverage"], coverage)
            self.assertEqual(
                trajectory.final_metrics.total_prompt_tokens,
                100 if coverage == "complete" else None,
            )
            self.assertEqual(trajectory.final_metrics.extra["observed_prompt_tokens"], 100)
        cost_only = {
            "toolUses": 0,
            "cost": {"amount": 0, "currency": "USD", "source": "provider-reported"},
        }
        trajectory = events_to_trajectory(
            events=[event(REPORT), event(cost_only, "review-1")],
            instruction="fix",
            summary=None,
            agent_version="test",
        )
        self.assertIsNone(trajectory.final_metrics.total_prompt_tokens)
        self.assertEqual(trajectory.final_metrics.extra["token_coverage"], "partial")
        self.assertEqual(trajectory.final_metrics.total_cost_usd, 0.125)
        self.assertEqual(trajectory.steps[2].metrics.cost_usd, 0)

    def test_context_does_not_promote_partial_usage_in_summary_or_raw_events(self):
        for coverage in ("complete", "partial"):
            report = copy.deepcopy(REPORT)
            report["tokens"]["coverage"] = coverage
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                system = root / "system"
                system.mkdir()
                usage = {"modifier": summary_usage(report)}
                (system / "summary.json").write_text(json.dumps({"result": {"usage": usage}}))
                (system / "events.jsonl").write_text(json.dumps(event(report)) + "\n")
                context = AgentContext()
                agent(root, plan()).populate_context_post_run(context)
                self.assertEqual(context.n_input_tokens, 100 if coverage == "complete" else None)
                self.assertEqual(context.cost_usd, 0.125)
                self.assertEqual(context.n_cache_tokens, 60 if coverage == "complete" else None)
                self.assertEqual(context.metadata["unified_agent_evaluation"]["usage"], usage)
                self.assertTrue((root / "trajectory.json").exists())

    def test_cost_report_uses_upstream_multimodel_cost_and_labels_partial_totals(self):
        from contextlib import redirect_stdout
        from io import StringIO

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, native in (("measured", REPORT), ("missing", {"toolUses": 3})):
                trial = root / name
                (trial / "agent/system").mkdir(parents=True)
                (trial / "result.json").write_text(
                    json.dumps({"verifier_result": {"rewards": {"reward": 1}}})
                )
                (trial / "agent/system/summary.json").write_text(
                    json.dumps({"result": {"usage": {"modifier": summary_usage(native)}}})
                )
            result = build_report(root)
            totals = result["totals"]["modifier"]
            self.assertEqual(totals["tokenCoverage"], "partial")
            self.assertEqual(totals["observedInputTokens"], 100)
            self.assertIsNone(totals["inputTokens"])
            cost = result["costs"]["modifier"]
            self.assertEqual(cost["totalUsd"], 0.125)
            self.assertEqual(cost["models"], ["child", "main"])
            self.assertEqual(cost["sources"], ["agent-estimate"])
            self.assertEqual(cost["coverage"], "partial")
            self.assertNotIn("inputUsd", cost)
            with redirect_stdout(StringIO()) as output:
                print_report(result)
            self.assertIn("cost coverage partial", output.getvalue())
            self.assertIn("observed subtotal", output.getvalue())

    def test_new_tokens_without_cost_are_not_priced_as_the_requested_model(self):
        from wip.scripts.token_usage import _usage_cost

        report = copy.deepcopy(REPORT)
        del report["cost"]
        cost = _usage_cost(summary_usage(report))
        self.assertIsNone(cost)

    def test_mixed_historical_and_current_events_do_not_claim_complete_coverage(self):
        historical = {
            "tokenAvailability": "reported",
            "inputTokens": 7,
            "outputTokens": 3,
            "toolUses": 0,
        }
        trajectory = events_to_trajectory(
            events=[event(REPORT), event(historical, "review-1")],
            instruction="fix",
            summary=None,
            agent_version="test",
        )
        self.assertIsNone(trajectory.final_metrics.total_prompt_tokens)
        self.assertEqual(trajectory.final_metrics.extra["observed_prompt_tokens"], 107)
        self.assertEqual(trajectory.final_metrics.extra["token_coverage"], "partial")

    def test_unavailable_raw_events_do_not_become_zero_in_pier_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            system = root / "system"
            system.mkdir()
            (system / "events.jsonl").write_text(json.dumps(event({"toolUses": 3})) + "\n")
            context = AgentContext()
            agent(root, plan()).populate_context_post_run(context)
            self.assertIsNone(context.n_input_tokens)
            self.assertIsNone(context.n_output_tokens)
            self.assertIsNone(context.cost_usd)
