from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paw.zcode import render_paw_bundle_skill, setup_zcode


class ZCodeSetupTests(unittest.TestCase):
    def test_rendered_skill_mentions_router_and_memory(self) -> None:
        text = render_paw_bundle_skill()

        self.assertIn("python -m paw surface", text)
        self.assertIn("--audit", text)
        self.assertIn("python -m paw memory hook --host z-code", text)
        self.assertIn("python -m paw route", text)
        self.assertIn("Sensitive or proprietary", text)

    def test_setup_writes_paw_bundle_skill(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_dir = Path(directory) / ".zcode" / "skills" / "paw-bundle"
            app = Path(directory) / "ZCode.exe"
            app.write_text("stub", encoding="utf-8")
            with (
                mock.patch("paw.zcode.find_zcode_app", return_value=app),
                mock.patch("paw.zcode.zcode_app_dir_on_path", return_value=True),
            ):
                result = setup_zcode(skill_dir=skill_dir)

            self.assertEqual(result.status, "healthy")
            skill = skill_dir / "SKILL.md"
            self.assertTrue(skill.exists())
            self.assertIn("paw-bundle", skill.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
