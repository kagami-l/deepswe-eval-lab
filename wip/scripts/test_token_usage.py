from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("token_usage.py")
SPEC = importlib.util.spec_from_file_location("token_usage", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
token_usage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(token_usage)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class NativeUsagePresentationTest(unittest.TestCase):
    def _report(self, reports: list | None = None) -> dict:
        tokens = {
            "coverage": "partial",
            "totals": {
                "input": {"total": 1500, "uncached": 100, "cacheRead": 1400},
                "output": {"total": 30, "visible": 10, "reasoning": 20},
            },
        }
        usage = {
            "usageSchema": 2,
            "tokenAvailability": "unavailable",
            "inputTokens": None,
            "outputTokens": None,
            "turns": 2,
            "toolUses": 3,
            "wallMs": 1000,
            "tokens": tokens,
            "tokenCoverage": "partial",
            "costCoverage": "unavailable",
            "usageReports": [{"tokens": tokens, "toolUses": 2}, {"toolUses": 1}],
        }
        if reports is not None:
            usage["usageReports"] = reports
            usage["turns"] = len(reports)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_json(root / "trial/result.json", {"verifier_result": {"rewards": {"reward": 0}}})
            _write_json(root / "trial/agent/system/summary.json",
                        {"result": {"usage": {"modifier": usage}}})
            return token_usage.build_report(root)

    def test_missing_native_cost_is_not_labelled_legacy_estimate(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            token_usage.print_report(self._report())
        self.assertNotIn("cost coverage legacy estimate", output.getvalue())

    def test_native_cache_and_reasoning_are_visible(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            token_usage.print_report(self._report())
        self.assertIn("cacheRead", output.getvalue())
        self.assertIn("reasoning", output.getvalue())

    def test_missing_turn_keeps_observed_subtotal_and_stats(self) -> None:
        report = self._report()
        totals = report["totals"]["modifier"]
        self.assertEqual(totals["tokenReportTurns"], 1)
        self.assertEqual(totals["missingTokenTurns"], 1)
        self.assertIsNone(totals["inputTokens"])
        self.assertEqual(totals["observedInputTokens"], 1500)
        self.assertEqual(totals["tokenDetails"]["input.cacheRead"]["observed"], 1400)
        self.assertEqual(report["stats"]["modifier"]["observedInputTokens"]["mean"], 1500)
        failed = report["passedVsFailed"]["failed"]["modifier"]
        self.assertEqual(failed["meanObservedInput"], 1500)
        self.assertIsNone(failed["meanInput"])

    def test_cost_only_zero_and_missing_token_details_are_independent(self) -> None:
        reports = [
            {"tokens": {
                "coverage": "complete",
                "totals": {"input": {"total": 0, "cacheRead": 0}, "output": {"total": 0}},
            }, "cost": {"amount": 0, "currency": "USD", "source": "provider-reported"}},
            {"cost": {"amount": 0.5, "currency": "USD", "source": "agent-estimate"}},
        ]
        report = self._report(reports)
        totals = report["totals"]["modifier"]
        self.assertEqual(totals["observedInputTokens"], 0)
        self.assertIsNone(totals["inputTokens"])
        self.assertEqual(totals["tokenDetails"]["input.cacheRead"]["observed"], 0)
        self.assertEqual(totals["tokenDetails"]["input.cacheRead"]["reportedTurns"], 1)
        self.assertIsNone(totals["tokenDetails"]["output.reasoning"]["observed"])
        self.assertEqual(report["jobTotals"]["costUsd"], 0.5)
        self.assertEqual(report["jobTotals"]["costCoverage"], "complete")
        cost_only = self._report([reports[1]])
        self.assertIsNone(cost_only["jobTotals"]["observedInputTokens"])
        self.assertEqual(cost_only["passedVsFailed"]["failed"]["modifier"]["meanCostUsd"], 0.5)

    def test_multimodel_cost_is_not_added_to_terminal_cost_twice(self) -> None:
        native = {
            "tokens": {
                "coverage": "complete",
                "totals": {"input": {"total": 100}, "output": {"total": 20}},
                "records": [
                    {"model": "main", "tokens": {"input": {"total": 70}, "output": {"total": 12}}},
                    {"model": "child", "tokens": {"input": {"total": 30}, "output": {"total": 8}}},
                ],
            },
            "cost": {"amount": 0.125, "currency": "USD", "source": "agent-estimate"},
        }
        for record in native["tokens"]["records"]:
            record["cost"] = {"amount": 0.0625, "currency": "USD", "source": "agent-estimate"}
        report = self._report([native])
        self.assertEqual(report["jobTotals"]["costUsd"], 0.125)
        self.assertEqual(report["jobTotals"]["inputTokens"], 100)
        self.assertEqual(report["jobTotals"]["outputTokens"], 20)
        self.assertEqual(len(report["totals"]["modifier"]["modelUsage"]), 2)
        output = StringIO()
        with redirect_stdout(output):
            token_usage.print_report(report)
        self.assertIn("child", output.getvalue())
        self.assertIn("main", output.getvalue())

    def test_missing_optional_detail_is_not_filled_with_zero(self) -> None:
        first = {"tokens": {
            "coverage": "complete",
            "totals": {"input": {"total": 10, "cacheRead": 0}, "output": {"total": 2}},
        }}
        second = {"tokens": {
            "coverage": "complete",
            "totals": {"input": {"total": 20}, "output": {"total": 3}},
        }}
        totals = self._report([first, second])["totals"]["modifier"]
        self.assertEqual(totals["inputTokens"], 30)
        self.assertEqual(totals["outputTokens"], 5)
        self.assertEqual(totals["tokenDetails"]["input.cacheRead"], {
            "observed": 0, "reportedTurns": 1, "total": None,
        })

    def test_missing_terminal_slot_keeps_cost_partial(self) -> None:
        report = self._report([
            {"cost": {"amount": 0, "currency": "USD", "source": "account-estimate"}},
            None,
        ])
        totals = report["jobTotals"]
        self.assertEqual(totals["observedCostUsd"], 0)
        self.assertIsNone(totals["costUsd"])
        self.assertEqual(totals["costCoverage"], "partial")
        self.assertEqual(totals["costSources"], ["account-estimate"])
        self.assertEqual(totals["missingTokenTurns"], 2)
        self.assertEqual(totals["missingCostTurns"], 1)

    def test_rejects_legacy_and_mismatched_turn_slots(self) -> None:
        for usage, message in [
            ({"turns": 1, "inputTokens": 100}, "only usageSchema=2"),
            ({"usageSchema": 2, "turns": 2, "usageReports": [None]}, "one slot per turn"),
        ]:
            with self.subTest(usage=usage), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _write_json(root / "trial/result.json", {})
                _write_json(root / "trial/agent/system/summary.json", {
                    "result": {"usage": {"modifier": usage}},
                })
                with self.assertRaisesRegex(ValueError, message):
                    token_usage.build_report(root)
                with redirect_stdout(StringIO()):
                    from contextlib import redirect_stderr
                    with redirect_stderr(StringIO()):
                        self.assertEqual(token_usage.main([str(root)]), 2)

    def test_invalid_native_numbers_fail_instead_of_becoming_zero(self) -> None:
        for value in [-1, True, "123", float("nan")]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "input.total"):
                self._report([{"tokens": {
                    "coverage": "complete",
                    "totals": {"input": {"total": value}, "output": {"total": 0}},
                }}])

    def test_skipped_trial_prevents_complete_job_claim(self) -> None:
        report = self._report([
            {"tokens": {
                "coverage": "complete",
                "totals": {"input": {"total": 10}, "output": {"total": 5}},
            }, "cost": {"amount": 1, "currency": "USD", "source": "provider-reported"}},
        ])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_json(root / "trial/result.json", {})
            _write_json(root / "trial/agent/system/summary.json", {
                "result": {"usage": report["trials"][0]["usage"]},
            })
            (root / "incomplete").mkdir()
            (root / "patch-scores").mkdir()
            new = token_usage.build_report(root)
        self.assertEqual(new["skippedTrials"], ["incomplete"])
        self.assertEqual(new["jobTotals"]["observedInputTokens"], 10)
        self.assertIsNone(new["jobTotals"]["inputTokens"])
        self.assertEqual(new["jobTotals"]["costCoverage"], "partial")
        self.assertIsNone(new["jobTotals"]["costUsd"])

    def test_stats_keep_reported_sample_counts_and_unscored_separate(self) -> None:
        seed = self._report()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, reward, usage in [
                ("partial", 0, seed["trials"][0]["usage"]["modifier"]),
                ("unknown", None, {"usageSchema": 2, "usageReports": [None],
                                   "turns": 1, "wallMs": 0, "toolUses": 0}),
            ]:
                _write_json(root / name / "result.json", {
                    "verifier_result": {"rewards": {"reward": reward}},
                })
                _write_json(root / name / "agent/system/summary.json", {
                    "result": {"usage": {"modifier": usage}},
                })
            report = token_usage.build_report(root)
        self.assertEqual(report["stats"]["modifier"]["observedInputTokens"]["samples"], 1)
        self.assertEqual(report["stats"]["modifier"]["observedInputTokens"]["mean"], 1500)
        self.assertEqual(report["passedVsFailed"]["failed"]["modifier"]["trials"], 1)
        self.assertEqual(report["passedVsFailed"]["unscored"]["modifier"]["trials"], 1)


if __name__ == "__main__":
    unittest.main()
