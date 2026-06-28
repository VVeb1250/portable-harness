"""Tests for paw/repo_pack.py — scope guard."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from paw.repo_pack import GuardRefused, guard_broad_pack, is_repo_root, repo_name, size_hint


class RepoPackGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # ── is_repo_root ───────────────────────────────────────────────────

    def test_is_repo_root_true_when_git_dir_present(self) -> None:
        (self.root / ".git").mkdir()
        self.assertTrue(is_repo_root(self.root))

    def test_is_repo_root_false_when_no_git_dir(self) -> None:
        self.assertFalse(is_repo_root(self.root))

    def test_is_repo_root_false_on_subdir(self) -> None:
        sub = self.root / "sub"
        sub.mkdir()
        self.assertFalse(is_repo_root(sub))

    # ── repo_name ──────────────────────────────────────────────────────

    def test_repo_name_from_path_basename(self) -> None:
        p = Path("/some/repo-name")
        self.assertEqual(repo_name(p), "repo-name")

    # ── size_hint ───────────────────────────────────────────────────────

    def test_size_hint_empty(self) -> None:
        self.assertEqual(size_hint(self.root), "0")

    def test_size_hint_counts_files(self) -> None:
        (self.root / "a.py").write_text("x")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "b.py").write_text("y")
        self.assertEqual(size_hint(self.root), "2")

    def test_size_hint_ignores_git(self) -> None:
        (self.root / ".git").mkdir()
        (self.root / ".git" / "objects").mkdir()
        (self.root / "readme.md").write_text("x")
        self.assertEqual(size_hint(self.root), "1")

    def test_size_hint_ignores_node_modules(self) -> None:
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules" / "dep").mkdir()
        (self.root / "package.json").write_text("{}")
        self.assertEqual(size_hint(self.root), "1")

    # ── guard_broad_pack ───────────────────────────────────────────────

    def test_guard_passes_non_root(self) -> None:
        sub = self.root / "sub"
        sub.mkdir()
        (sub / "file.txt").write_text("x")
        guard_broad_pack(sub)  # should not raise

    def test_guard_refuses_root_without_scope(self) -> None:
        (self.root / ".git").mkdir()
        (self.root / "a.py").write_text("x")
        with self.assertRaises(GuardRefused):
            guard_broad_pack(self.root)

    def test_guard_passes_with_include(self) -> None:
        (self.root / ".git").mkdir()
        guard_broad_pack(self.root, has_include=True)  # should not raise

    def test_guard_passes_with_diff(self) -> None:
        (self.root / ".git").mkdir()
        guard_broad_pack(self.root, has_diff=True)  # should not raise

    def test_guard_passes_with_allow_large(self) -> None:
        (self.root / ".git").mkdir()
        guard_broad_pack(self.root, allow_large=True)  # should not raise

    def test_guard_error_message_includes_hint(self) -> None:
        (self.root / ".git").mkdir()
        (self.root / "a.py").write_text("x")
        with self.assertRaises(GuardRefused) as ctx:
            guard_broad_pack(self.root)
        self.assertIn("--include", str(ctx.exception.message))
        self.assertIn("--diff", str(ctx.exception.message))

    def test_guard_error_message_includes_repo_name_and_size(self) -> None:
        (self.root / ".git").mkdir()
        (self.root / "a.py").write_text("x")
        with self.assertRaises(GuardRefused) as ctx:
            guard_broad_pack(self.root)
        msg = str(ctx.exception.message)
        name = self.root.resolve().name
        self.assertIn(name, msg)
        self.assertIn("~1 files", msg)


if __name__ == "__main__":
    unittest.main()
