from __future__ import annotations

import importlib.util
import copy
import time
import json
import tempfile
import unittest
from unittest import mock
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



class CligentCostFallbackTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.native = {"cost": {"amount": 2, "currency": "USD", "source": "agent-estimate"}}
        self.tokens = {"toolUses": 1, "tokens": {
            "coverage": "complete",
            "totals": {
                "input": {"total": 100, "uncached": 20, "cacheRead": 80, "cacheWrite": 0},
                "output": {"total": 10, "visible": 6, "reasoning": 4},
            },
        }}
        self.prices = {"input": 2, "output": 10, "cacheRead": 0.2, "cacheWrite": 2}

    def write_trial(self, reports: list, *, name: str = "trial", role: str = "modifier") -> Path:
        _write_json(self.root / name / "result.json", {"verifier_result": {"rewards": {"reward": 1}}})
        source = self.root / name / "agent/system/summary.json"
        _write_json(source, {
            "roles": {role: {"adapter": "unknown-backend", "model": "configured-model"}},
            "result": {"usage": {role: {"usageSchema": 2, "turns": len(reports),
                       "toolUses": 1, "wallMs": 1, "usageReports": reports}}},
        })
        return source

    def test_reported_cost_including_zero_never_invokes_node(self) -> None:
        zero = {"cost": {"amount": 0, "currency": "USD", "source": "provider-reported"}}
        self.write_trial([zero, self.native])
        with mock.patch.object(token_usage.subprocess, "run") as run:
            report = token_usage.build_report(self.root)
        run.assert_not_called()
        totals = report["jobTotals"]
        self.assertEqual(totals["observedCostUsd"], 2)
        self.assertEqual(totals["costReportTurns"], 2)
        self.assertEqual(totals["costEstimateTurns"], 0)
        self.assertEqual(totals["costCoverage"], "complete")

    def test_real_estimator_fills_only_missing_cost_and_preserves_reports(self) -> None:
        source = self.write_trial([self.native, self.tokens])
        before = source.read_bytes()
        report = token_usage.build_report(self.root, cost_options={"*": {"prices": self.prices}})
        totals = report["jobTotals"]
        self.assertAlmostEqual(totals["observedCostUsd"], 2.000156)
        self.assertAlmostEqual(totals["costUsd"], 2.000156)
        self.assertEqual(totals["reportedCostUsd"], 2)
        self.assertAlmostEqual(totals["estimatedCostUsd"], 0.000156)
        self.assertEqual(totals["costReportTurns"], 1)
        self.assertEqual(totals["costEstimateTurns"], 1)
        self.assertEqual(totals["costCoverage"], "complete")
        self.assertEqual(totals["usageReports"], [self.native, self.tokens])
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(totals["costResolutions"][1]["estimate"]["source"], {"type": "caller"})
        self.assertEqual(report["reportSchemaVersion"], 3)
        self.assertAlmostEqual(report["costs"]["modifier"]["totalUsd"], 2.000156)
        self.assertAlmostEqual(report["stats"]["modifier"]["observedCostUsd"]["mean"], 2.000156)
        self.assertAlmostEqual(report["passedVsFailed"]["passed"]["modifier"]["meanCostUsd"], 2.000156)

    def test_partial_and_missing_tokens_do_not_become_full_cost(self) -> None:
        self.tokens["tokens"]["coverage"] = "partial"
        self.write_trial([self.native, self.tokens, None])
        report = token_usage.build_report(self.root, cost_options={"*": {"prices": self.prices}})
        totals = report["jobTotals"]
        self.assertAlmostEqual(totals["observedCostUsd"], 2.000156)
        self.assertIsNone(totals["costUsd"])
        self.assertEqual(totals["costCoverage"], "partial")
        self.assertEqual(totals["partialCostEstimateTurns"], 1)
        self.assertEqual(totals["missingCostTurns"], 1)
        self.assertEqual(totals["costResolutions"][2]["estimate"]["reason"], "tokens-unavailable")
        # Even when every turn has an amount, a partial estimate stays partial.
        self.write_trial([self.tokens])
        partial = token_usage.build_report(self.root, cost_options={"*": {"prices": self.prices}})
        self.assertEqual(partial["jobTotals"]["missingCostTurns"], 0)
        self.assertEqual(partial["jobTotals"]["costCoverage"], "partial")
        self.assertIsNone(partial["costs"]["modifier"]["completeTotalUsd"])

    def test_bridge_failure_preserves_native_cost_and_tokens(self) -> None:
        self.write_trial([self.native, self.tokens])
        with mock.patch.object(token_usage.subprocess, "run", side_effect=FileNotFoundError("node")):
            report = token_usage.build_report(self.root)
        totals = report["jobTotals"]
        self.assertEqual(totals["observedCostUsd"], 2)
        self.assertEqual(totals["observedInputTokens"], 100)
        self.assertEqual(totals["costCoverage"], "partial")
        self.assertEqual(totals["costResolutions"][1]["estimate"]["reason"], "estimator-unavailable")

    def test_zero_estimate_and_invalid_prices_remain_distinguishable(self) -> None:
        self.write_trial([self.tokens])
        free = token_usage.build_report(self.root, cost_options={"*": {"prices": {
            "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0,
        }}})
        self.assertEqual(free["jobTotals"]["costUsd"], 0)
        self.assertEqual(free["jobTotals"]["costEstimateTurns"], 1)
        invalid = token_usage.build_report(self.root, cost_options={"*": {"prices": {
            "input": -1, "output": 0,
        }}})
        self.assertIsNone(invalid["jobTotals"]["observedCostUsd"])
        self.assertEqual(invalid["jobTotals"]["observedInputTokens"], 100)
        self.assertEqual(invalid["jobTotals"]["costResolutions"][0]["estimate"]["reason"], "invalid-prices")

    def test_provider_hints_are_generic_and_missing_provider_is_explicit(self) -> None:
        self.write_trial([self.tokens])
        report = token_usage.build_report(self.root)
        self.assertEqual(report["jobTotals"]["costResolutions"][0]["estimate"]["reason"], "missing-provider")
        with mock.patch.object(token_usage, "_estimate_costs", return_value=[{
            "status": "unavailable", "reason": "model-not-found", "message": "fixture",
        }]) as estimate:
            token_usage.build_report(self.root, cost_options={
                "*": {"provider": "default-provider"}, "modifier": {"provider": "chosen-provider"},
            })
        requests = estimate.call_args.args[0]
        self.assertEqual(requests[0]["options"], {
            "model": "configured-model", "provider": "chosen-provider",
        })
        self.assertNotIn("adapter", requests[0])

    def test_real_catalog_cache_multimodel_cli_and_output(self) -> None:
        record1 = {"model": "model-a", "tokens": copy.deepcopy(self.tokens["tokens"]["totals"])}
        record2 = {"model": "model-b", "tokens": copy.deepcopy(self.tokens["tokens"]["totals"])}
        usage = copy.deepcopy(self.tokens)
        usage["tokens"]["records"] = [record1, record2]
        for side in usage["tokens"]["totals"].values():
            for key in side:
                side[key] *= 2
        self.write_trial([usage])
        cache = self.root / "prices.json"
        _write_json(cache, {"version": 1, "fetchedAt": int(time.time() * 1000), "catalog": {
            "fixture-provider": {"models": {
                model: {"cost": {"input": 2 * factor, "output": 10 * factor,
                                  "cache_read": 0.2 * factor, "cache_write": 2 * factor}}
                for model, factor in [("model-a", 1), ("model-b", 2)]
            }},
        }})
        output = StringIO()
        with redirect_stdout(output):
            code = token_usage.main([str(self.root), "--cost-provider", "modifier=fixture-provider",
                                     "--cost-cache", str(cache), "--json"])
        self.assertEqual(code, 0)
        report = json.loads(output.getvalue())
        totals = report["jobTotals"]
        self.assertAlmostEqual(totals["costUsd"], 0.000468)
        estimate = totals["costResolutions"][0]["estimate"]
        self.assertEqual([r["model"] for r in estimate["records"]], ["model-a", "model-b"])
        self.assertFalse(estimate["source"]["stale"])
        self.assertEqual(estimate["source"]["type"], "models.dev")
        output = StringIO()
        with redirect_stdout(output):
            token_usage.print_report(report)
        self.assertIn("cligent-estimate", output.getvalue())
        self.assertIn("cost $0.000468 (complete)", output.getvalue())
        self.assertIn("assumption:", output.getvalue())


if __name__ == "__main__":
    unittest.main()
