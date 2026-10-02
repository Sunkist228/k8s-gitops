"""Exercise the Dex init command with POSIX permissions and a non-root user."""

import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

import yaml


class DexConfigRenderTests(unittest.TestCase):
    def setUp(self):
        if os.name != "posix" or os.geteuid() == 0:
            self.skipTest("requires a non-root POSIX user to enforce file permissions")
        manifest = Path(__file__).resolve().parents[1] / "apps/outline/dex.yaml"
        deployment = next(
            doc for doc in yaml.safe_load_all(manifest.read_text())
            if doc["kind"] == "Deployment"
        )
        container = next(
            item for item in deployment["spec"]["template"]["spec"]["initContainers"]
            if item["name"] == "render-config"
        )
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "source"
        self.rendered = root / "rendered"
        self.source.mkdir()
        self.rendered.mkdir()
        script = container["args"][0].replace("/source/", f"{self.source}/")
        script = script.replace("/rendered/", f"{self.rendered}/")
        self.command = [*container["command"], script]
        self.config = self.rendered / "config.yaml"
        self.input = self.source / "config.yaml"
        self.input.write_text("issuer: https://outline.deflux.ru/dex\n")

    def render(self):
        return subprocess.run(self.command, capture_output=True, text=True, timeout=10)

    def test_restart_replaces_readonly_config(self):
        first = self.render()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o440)
        self.input.write_text("issuer: https://outline.deflux.ru/dex\nchanged: true\n")
        second = self.render()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(
            self.config.read_text(),
            "issuer: https://outline.devflux.ru/dex\nchanged: true\n",
        )
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o440)
        self.assertEqual([item.name for item in self.rendered.iterdir()], ["config.yaml"])

    def test_failed_render_preserves_config_and_removes_temporary_file(self):
        first = self.render()
        self.assertEqual(first.returncode, 0, first.stderr)
        original = self.config.read_text()
        self.input.unlink()
        failed = self.render()
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(self.config.read_text(), original)
        self.assertEqual(stat.S_IMODE(self.config.stat().st_mode), 0o440)
        self.assertEqual([item.name for item in self.rendered.iterdir()], ["config.yaml"])


if __name__ == "__main__":
    unittest.main()
