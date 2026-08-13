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


class TokenUsageCostTest(unittest.TestCase):
    def _job(self, root: Path) -> Path:
        job_dir = root / "job"
        _write_json(
            job_dir / "config.json",
            {
                "agents": [
                    {
                        "kwargs": {
                            "execution_plan_json": {
                                "roles": {
                                    "planner": {"adapter": "codex", "model": "gpt-5-6-sol"},
                                    "reviewer": {
                                        "adapter": "claude",
                                        "model": "claude-opus-4-8",
                                    },
                                    "other": {"adapter": "other", "model": "unpriced-model"},
                                }
                            }
                        }
                    }
                ]
            },
        )
        _write_json(job_dir / "result.json", {"stats": {}})
        self._trial(
            job_dir,
            "trial-a",
            reward=1,
            usage={
                "planner": self._usage(1_000_000, 100_000),
                "reviewer": self._usage(2_000_000, 200_000, cache_tokens=1_500_000),
                "other": self._usage(123, 456),
            },
        )
        self._trial(
            job_dir,
            "trial-b",
            reward=0,
            usage={"planner": self._usage(500_000, 50_000, cache_tokens=0)},
        )
        return job_dir

    @staticmethod
    def _usage(
        input_tokens: int, output_tokens: int, *, cache_tokens: int | None = None
    ) -> dict[str, object]:
        usage = {
            "tokenAvailability": "reported",
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "toolUses": 1,
            "turns": 1,
            "wallMs": 1_000,
        }
        if cache_tokens is not None:
            usage["cacheTokens"] = cache_tokens
        return usage

    @staticmethod
    def _trial(
        job_dir: Path,
        name: str,
        *,
        reward: int,
        usage: dict[str, dict[str, object]],
    ) -> None:
        trial_dir = job_dir / name
        _write_json(
            trial_dir / "result.json",
            {"verifier_result": {"rewards": {"reward": reward}}},
        )
        _write_json(
            trial_dir / "agent" / "system" / "summary.json",
            {"result": {"outcome": "ok", "usage": usage}},
        )

    def test_report_calculates_costs_and_matches_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = token_usage.build_report(self._job(Path(temp_dir)))

        self.assertEqual(report["costs"]["planner"]["model"], "gpt-5.6-sol")
        self.assertEqual(report["costs"]["planner"]["inputUsd"], 7.5)
        self.assertIsNone(report["costs"]["planner"]["cacheUsd"])
        self.assertEqual(report["costs"]["planner"]["outputUsd"], 4.5)
        self.assertEqual(report["costs"]["planner"]["totalUsd"], 12.0)
        self.assertEqual(report["costs"]["reviewer"]["inputUsd"], 2.5)
        self.assertEqual(report["costs"]["reviewer"]["cacheUsd"], 0.75)
        self.assertEqual(report["costs"]["reviewer"]["outputUsd"], 5.0)
        self.assertEqual(report["costs"]["reviewer"]["totalUsd"], 8.25)
        self.assertEqual(
            report["costs"]["reviewer"]["breakdownUsd"],
            {"in": 2.5, "cache": 0.75, "out": 5.0},
        )
        self.assertEqual(report["trials"][0]["costs"]["planner"]["totalUsd"], 8.0)
        self.assertEqual(report["pricing"]["unpricedRoles"], ["other"])
        self.assertTrue(report["costs"]["planner"]["estimated"])
        self.assertEqual(report["stats"]["planner"]["costInUsd"]["mean"], 3.75)
        self.assertEqual(report["stats"]["planner"]["costCacheUsd"], {})
        self.assertEqual(report["stats"]["planner"]["costOutUsd"]["mean"], 2.25)
        self.assertEqual(report["stats"]["planner"]["costTotalUsd"]["mean"], 6.0)
        self.assertEqual(report["stats"]["reviewer"]["costCacheUsd"]["mean"], 0.75)

    def test_text_report_shows_estimated_cost_and_unpriced_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = token_usage.build_report(self._job(Path(temp_dir)))
        output = StringIO()
        with redirect_stdout(output):
            token_usage.print_report(report)

        text = output.getvalue()
        self.assertIn("planner cache$", text)
        self.assertIn("$0.750000", text)
        self.assertIn("cost n/a", text)
        self.assertIn("API-rate estimate", text)
        self.assertIn("costInUsd", text)
        self.assertEqual(text.count("costCacheUsd"), 2)
        self.assertIn("costOutUsd", text)
        self.assertIn("costTotalUsd", text)

    def test_invalid_pricing_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            job_dir = self._job(root)
            pricing_path = root / "bad-pricing.json"
            _write_json(pricing_path, {"unitTokens": 1_000_000})

            with self.assertRaisesRegex(ValueError, "invalid model pricing file"):
                token_usage.build_report(job_dir, pricing_path)

    def test_unavailable_tokens_remain_unknown_but_tool_uses_are_counted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            job_dir = self._job(Path(temp_dir))
            unavailable = self._usage(0, 0)
            unavailable.update(
                {
                    "tokenAvailability": "unavailable",
                    "inputTokens": None,
                    "outputTokens": None,
                    "toolUses": 7,
                }
            )
            self._trial(
                job_dir,
                "trial-c",
                reward=0,
                usage={"planner": unavailable},
            )
            report = token_usage.build_report(job_dir)

        planner = report["totals"]["planner"]
        self.assertEqual(planner["tokenAvailability"], "unavailable")
        self.assertIsNone(planner["inputTokens"])
        self.assertIsNone(planner["outputTokens"])
        self.assertEqual(planner["reportedInputTokens"], 1_500_000)
        self.assertEqual(planner["toolUses"], 9)
        self.assertEqual(planner["reportedTokenTrials"], 2)
        self.assertEqual(planner["unavailableTokenTrials"], 1)
        self.assertNotIn("planner", report["costs"])
        self.assertNotIn("planner", report["pricing"]["unpricedRoles"])
        self.assertIn("planner", report["pricing"]["unavailableTokenRoles"])
        self.assertEqual(report["stats"]["planner"]["inputTokens"]["mean"], 750_000)

    def test_legacy_usage_without_discriminator_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            job_dir = self._job(Path(temp_dir))
            legacy = self._usage(123, 45)
            del legacy["tokenAvailability"]
            self._trial(
                job_dir,
                "trial-c",
                reward=0,
                usage={"planner": legacy},
            )
            report = token_usage.build_report(job_dir)

        row = next(row for row in report["trials"] if row["trial"] == "trial-c")
        self.assertEqual(row["usage"]["planner"]["tokenAvailability"], "unavailable")
        self.assertIsNone(row["usage"]["planner"]["inputTokens"])

    def test_reported_usage_without_token_numbers_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            job_dir = self._job(Path(temp_dir))
            malformed = self._usage(123, 45)
            malformed["inputTokens"] = None
            self._trial(
                job_dir,
                "trial-c",
                reward=0,
                usage={"planner": malformed},
            )
            report = token_usage.build_report(job_dir)

        row = next(row for row in report["trials"] if row["trial"] == "trial-c")
        self.assertEqual(row["usage"]["planner"]["tokenAvailability"], "unavailable")
        self.assertIsNone(row["usage"]["planner"]["inputTokens"])


if __name__ == "__main__":
    unittest.main()
