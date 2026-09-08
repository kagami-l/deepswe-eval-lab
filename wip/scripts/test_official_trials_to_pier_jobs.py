"""Check that viewer error filtering preserves official scoring decisions."""

import unittest

from official_trials_to_pier_jobs import build_trial_result


class OfficialScoringTest(unittest.TestCase):
    def test_viewer_filter_matches_official_scoring(self):
        cases = [
            ("AgentTimeoutError", True, False, 0.0),
            ("AgentTimeoutError", True, False, 1.0),
            ("NonZeroAgentExitCodeError", True, False, 0.0),
            ("VerifierTimeoutError", False, True, 0.0),
            (None, True, False, 1.0),
        ]
        for exception_type, included, errored, reward in cases:
            with self.subTest(exception_type=exception_type, reward=reward):
                exception = (
                    {
                        "exception_type": exception_type,
                        "exception_message": "Captured official exception",
                        "exception_traceback": "",
                        "occurred_at": "2026-09-01T00:00:00Z",
                    }
                    if exception_type
                    else None
                )
                row = {
                    "trial_name": "sample-task__trial",
                    "task_name": "sample-task",
                    "harness": "mini-swe-agent",
                    "provider": "openai",
                    "model": "sample-model",
                    "source": "deep-swe",
                    "config": "sample-config",
                    "included_in_score": included,
                    "errored": errored,
                    "reward": reward,
                    "exception": exception,
                }
                result = build_trial_result(row, "https://example.com/artifacts")
                # Pier's exclude-errored filter drops any exception_info.
                self.assertEqual(result.exception_info is None, included and not errored)
                self.assertEqual(result.verifier_result.rewards["reward"], reward)
                self.assertEqual(result.agent_result.metadata["official_exception"], exception)


if __name__ == "__main__":
    unittest.main()
