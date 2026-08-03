from __future__ import annotations

import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from wip.agent_eval.runtime_image import (
    RuntimeImageManager,
    RuntimeSpec,
    runtime_build_args,
    runtime_input_digest,
)


ROOT = Path(__file__).resolve().parents[2]


class RuntimeImageTests(unittest.TestCase):
    def test_manifest_versions_match_package_and_dockerfile(self) -> None:
        manifest = json.loads((ROOT / "wip/config/runtime-manifest.json").read_text())
        package = json.loads(
            (ROOT / "wip/agents/deep_swe_agent/runtime/package.json").read_text()
        )
        lock_text = (
            ROOT / "wip/agents/deep_swe_agent/runtime/package-lock.json"
        ).read_text()
        self.assertNotIn("registry.npmmirror.com", lock_text)
        for name, version in manifest["packages"].items():
            self.assertEqual(package["dependencies"][name], version)
        dockerfile = (ROOT / "wip/docker/agent-runtime/Dockerfile").read_text()
        expected_args = {
            "GEMINI_VERSION": manifest["global_packages"]["@google/gemini-cli"],
            "KIMI_VERSION": manifest["global_packages"]["@moonshot-ai/kimi-code"],
            "OPENCODE_VERSION": manifest["global_packages"]["opencode-ai"],
            "RIPGREP_VERSION": manifest["assets"]["ripgrep"]["version"],
            "RIPGREP_AMD64_SHA256": manifest["assets"]["ripgrep"]["sha256"][
                "amd64"
            ],
            "RIPGREP_ARM64_SHA256": manifest["assets"]["ripgrep"]["sha256"][
                "arm64"
            ],
            "OPENCODE_MODELS_SHA256": manifest["assets"]["opencode_models"][
                "sha256"
            ],
        }
        for name, version in expected_args.items():
            self.assertIn(f"ARG {name}={version}", dockerfile)
        self.assertEqual(runtime_build_args(manifest), expected_args)

        snapshot = gzip.decompress(
            (
                ROOT
                / "wip/docker/agent-runtime/assets/opencode-models.json.gz"
            ).read_bytes()
        )
        self.assertEqual(
            hashlib.sha256(snapshot).hexdigest(),
            manifest["assets"]["opencode_models"]["sha256"],
        )

    def test_digest_covers_orchestrator_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "wip/agents/deep_swe_agent/runtime/src/main.ts"
            source.parent.mkdir(parents=True)
            source.write_text("one")
            first = runtime_input_digest(root, {"schema_version": 1})
            source.write_text("two")
            second = runtime_input_digest(root, {"schema_version": 1})
            self.assertNotEqual(first, second)

    def test_inspect_requires_matching_label_and_platform(self) -> None:
        spec = RuntimeSpec(
            manifest={},
            manifest_digest="abc",
            image="runtime:test",
            platform="linux/amd64",
            dockerfile=Path("Dockerfile"),
            context_dir=Path("."),
        )
        inspect = [
            {
                "Id": "sha256:image",
                "Os": "linux",
                "Architecture": "amd64",
                "Config": {
                    "Labels": {
                        "io.merico.deep-swe.agent-runtime.manifest-digest": "abc"
                    }
                },
            }
        ]
        process = SimpleNamespace(returncode=0, stdout=json.dumps(inspect))
        with mock.patch("subprocess.run", return_value=process):
            status = RuntimeImageManager(spec).inspect()
        self.assertTrue(status.exists)
        self.assertTrue(status.matches)
        self.assertEqual(status.image_id, "sha256:image")


if __name__ == "__main__":
    unittest.main()
