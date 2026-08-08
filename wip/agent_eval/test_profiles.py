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

    def test_opencode_profile_uses_frozen_v4_flash_default(self) -> None:
        profile = self.registry.resolve("opencode")
        self.assertEqual(profile.model, "deepseek/deepseek-v4-flash")
        self.assertEqual(profile.effort, "max")

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

    def test_kimi_profile_resolves_registered_model(self) -> None:
        profile = self.registry.resolve("kimi")
        self.assertEqual(profile.model, "kimi-code/k3")
        self.assertIsNotNone(profile.model_config)
        assert profile.model_config is not None
        self.assertEqual(profile.model_config.provider, "managed:kimi-code")
        self.assertEqual(profile.model_config.provider_type, "kimi")
        self.assertEqual(
            profile.model_config.base_url, "https://api.kimi.com/coding/v1"
        )
        self.assertEqual(profile.model_config.upstream_model, "k3")
        self.assertEqual(profile.model_config.max_context_size, 1048576)
        self.assertIn("always_thinking", profile.model_config.capabilities)
        self.assertEqual(
            profile.model_config.support_efforts, ("low", "high", "max")
        )
        self.assertEqual(profile.model_config.default_effort, "high")

    def test_kimi_rejects_unregistered_model_override(self) -> None:
        with self.assertRaisesRegex(ProfileError, "versioned profile"):
            self.registry.resolve("kimi", model="kimi-code/k3-256k")

    def test_kimi_requires_model_registration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.json"
            path.write_text(
                '{"schema_version":1,"profiles":{"kimi":{'
                '"status":"verified","adapter":"kimi",'
                '"model":"kimi-code/k3","effort":"on","auth":"x",'
                '"permissions":"auto"}}}'
            )
            with self.assertRaisesRegex(ProfileError, "model_config"):
                ProfileRegistry.load(path)


if __name__ == "__main__":
    unittest.main()
