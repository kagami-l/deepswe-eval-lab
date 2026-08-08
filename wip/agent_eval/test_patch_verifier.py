from __future__ import annotations

import unittest
from unittest import mock

from wip.agent_eval import patch_verifier
from wip.agent_eval.patch_verifier import (
    PierContractError,
    _check_signature,
    _session_id,
    check_pier_contract,
)


class PierContractTests(unittest.TestCase):
    """Guards on the pinned datacurve-pier private surface."""

    def test_contract_check_passes_on_pinned_install(self) -> None:
        identity = check_pier_contract(pier_bin=None)
        self.assertEqual(identity["pierVersion"], patch_verifier.REQUIRED_PIER_VERSION)
        self.assertEqual(
            identity["adapterSchemaVersion"],
            str(patch_verifier.ADAPTER_SCHEMA_VERSION),
        )

    def test_version_mismatch_fails_closed(self) -> None:
        with mock.patch("importlib.metadata.version", return_value="0.4.0"):
            with self.assertRaises(PierContractError) as ctx:
                check_pier_contract(pier_bin=None)
        self.assertIn("0.3.0", str(ctx.exception))

    def test_missing_package_fails_closed(self) -> None:
        with mock.patch(
            "importlib.metadata.version", side_effect=ModuleNotFoundError("gone")
        ):
            with self.assertRaises(PierContractError):
                check_pier_contract(pier_bin=None)

    def test_cli_version_mismatch_fails_closed(self) -> None:
        completed = mock.Mock(returncode=0, stdout="pier 9.9.9\n")
        with (
            mock.patch("shutil.which", return_value="/usr/bin/pier"),
            mock.patch("subprocess.run", return_value=completed),
        ):
            with self.assertRaises(PierContractError) as ctx:
                check_pier_contract(pier_bin="pier")
        self.assertIn("refusing to mix versions", str(ctx.exception))

    def test_missing_cli_binary_is_tolerated(self) -> None:
        with mock.patch("shutil.which", return_value=None):
            identity = check_pier_contract(pier_bin="pier")
        self.assertEqual(identity["pierCliVersion"], "")

    def test_signature_guard_detects_removed_parameter(self) -> None:
        def stale(task, environment):  # noqa: ANN001 - simulated old surface
            return None

        with self.assertRaises(PierContractError) as ctx:
            _check_signature(stale, {"task", "trial_paths"}, "example")
        self.assertIn("trial_paths", str(ctx.exception))


class SessionIdTests(unittest.TestCase):
    def test_sanitizes_and_bounds_length(self) -> None:
        self.assertEqual(_session_id("ps-abc123-a1"), "ps-abc123-a1")
        self.assertEqual(_session_id("has/slash and space"), "has_slash_and_space")
        long_id = _session_id("x" * 200)
        self.assertLessEqual(len(long_id), 63)
        self.assertEqual(long_id, _session_id("x" * 200))
        self.assertNotEqual(long_id, _session_id("x" * 201))


if __name__ == "__main__":
    unittest.main()
