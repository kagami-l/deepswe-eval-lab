from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wip.agent_eval.profiles import ProfileError, ProfileRegistry


ROOT = Path(__file__).resolve().parents[2]


class ProfileRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ProfileRegistry.load(ROOT / "wip/config/agent-profiles.json")

    def test_verified_profile_resolves_with_override(self) -> None:
        profile = self.registry.resolve("codex", model="override")
        self.assertEqual(profile.adapter, "codex")
        self.assertEqual(profile.model, "override")
        self.assertEqual(profile.effort, "high")

    def test_unverified_profile_requires_opt_in(self) -> None:
        with self.assertRaisesRegex(ProfileError, "unverified"):
            self.registry.resolve("gemini")
        self.assertEqual(
            self.registry.resolve("gemini", allow_unverified=True).adapter,
            "gemini",
        )

    def test_rejects_dynamic_model_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.json"
            path.write_text(
                '{"schema_version":1,"profiles":{"bad":{'
                '"status":"verified","adapter":"codex","model":"",'
                '"auth":"x","permissions":"bypass"}}}'
            )
            with self.assertRaisesRegex(ProfileError, "model"):
                ProfileRegistry.load(path)

    def test_rejects_adapter_incompatible_effort_override(self) -> None:
        with self.assertRaisesRegex(ProfileError, "unsupported for kimi"):
            self.registry.resolve("kimi", effort="high")


if __name__ == "__main__":
    unittest.main()
