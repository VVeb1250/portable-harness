from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from paw.mutation import (
    EditMiss,
    apply_edits,
    apply_to_tree,
    parse_edits,
)


def _block(path: str, search: str, replace: str) -> str:
    return (
        f"@@@FILE {path}\n"
        f"<<<<<<< SEARCH\n{search}\n=======\n{replace}\n>>>>>>> REPLACE\n"
        f"@@@ENDFILE\n"
    )


class ParseTests(unittest.TestCase):
    def test_parse_single_edit(self) -> None:
        edits = parse_edits(_block("a.py", "old", "new"))
        self.assertEqual(len(edits), 1)
        self.assertEqual((edits[0].path, edits[0].search, edits[0].replace), ("a.py", "old", "new"))

    def test_parse_multiple_files_and_blocks(self) -> None:
        text = _block("a.py", "x", "y") + _block("a.py", "p", "q") + _block("sub/b.py", "m", "n")
        edits = parse_edits(text)
        self.assertEqual([e.path for e in edits], ["a.py", "a.py", "sub/b.py"])

    def test_parse_empty_text(self) -> None:
        self.assertEqual(parse_edits(""), [])
        self.assertEqual(parse_edits("just prose, no blocks"), [])


class ApplyEditsTests(unittest.TestCase):
    def test_exact_substring(self) -> None:
        self.assertEqual(apply_edits("def f(): return 1", [("return 1", "return 2")]), "def f(): return 2")

    def test_empty_search_overwrites(self) -> None:
        self.assertEqual(apply_edits("old content", [("", "brand new")]), "brand new")

    def test_flex_trailing_whitespace(self) -> None:
        # search has no trailing spaces, file line does → flex fallback matches
        out = apply_edits("    x = 1   \n", [("    x = 1", "    x = 2")])
        self.assertIn("x = 2", out)

    def test_miss_raises(self) -> None:
        with self.assertRaises(EditMiss):
            apply_edits("hello world", [("not present", "z")])


class ApplyToTreeTests(unittest.TestCase):
    def _tree(self) -> Path:
        d = Path(tempfile.mkdtemp(prefix="paw_mut_"))
        (d / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
        return d

    def test_happy_apply_writes_and_backs_up(self) -> None:
        root = self._tree()
        res = apply_to_tree(_block("a.py", "    return 1", "    return 2"), root)
        self.assertEqual(res.status, "applied")
        self.assertEqual(res.applied, ["a.py"])
        self.assertIn("return 2", (root / "a.py").read_text(encoding="utf-8"))
        self.assertTrue(res.backup_dir)
        # backup holds the original
        backup = Path(res.backup_dir) / "a.py"
        self.assertIn("return 1", backup.read_text(encoding="utf-8"))
        self.assertIn("-    return 1", res.diff)
        self.assertIn("+    return 2", res.diff)

    def test_miss_is_transactional_nothing_written(self) -> None:
        root = self._tree()
        text = (
            _block("a.py", "    return 1", "    return 2")
            + _block("a.py", "NONEXISTENT", "z")
        )
        res = apply_to_tree(text, root)
        self.assertEqual(res.status, "aborted")
        self.assertEqual(res.misses, ["a.py"])
        # the good edit must NOT have been written — transactional all-or-nothing
        self.assertIn("return 1", (root / "a.py").read_text(encoding="utf-8"))
        self.assertNotIn("return 2", (root / "a.py").read_text(encoding="utf-8"))

    def test_path_traversal_rejected(self) -> None:
        root = self._tree()
        res = apply_to_tree(_block("../evil.py", "", "pwned"), root)
        self.assertEqual(res.status, "aborted")
        self.assertEqual(res.rejected, ["../evil.py"])
        self.assertFalse((root.parent / "evil.py").exists())

    def test_absolute_path_rejected(self) -> None:
        root = self._tree()
        res = apply_to_tree(_block("/tmp/evil.py", "", "x"), root)
        self.assertEqual(res.status, "aborted")
        self.assertTrue(res.rejected)

    def test_dry_run_computes_diff_without_writing(self) -> None:
        root = self._tree()
        res = apply_to_tree(_block("a.py", "    return 1", "    return 2"), root, dry_run=True)
        self.assertEqual(res.status, "applied")
        self.assertIn("+    return 2", res.diff)
        self.assertEqual(res.backup_dir, "")
        self.assertIn("return 1", (root / "a.py").read_text(encoding="utf-8"))  # untouched

    def test_create_new_file(self) -> None:
        root = self._tree()
        res = apply_to_tree(_block("sub/new.py", "", "fresh = True\n"), root)
        self.assertEqual(res.status, "applied")
        self.assertEqual((root / "sub" / "new.py").read_text(encoding="utf-8"), "fresh = True\n")

    def test_noop_when_no_edits(self) -> None:
        res = apply_to_tree("no blocks here", self._tree())
        self.assertEqual(res.status, "noop")

    def test_noop_when_edit_produces_no_change(self) -> None:
        root = self._tree()
        res = apply_to_tree(_block("a.py", "    return 1", "    return 1"), root)
        self.assertEqual(res.status, "noop")


class MutationRunnerAdapterTests(unittest.TestCase):
    def _ctx(self, impl_content: str):
        from paw.blackboard import BlackboardEntry, BlackboardScope
        from paw.team_kernel import TeamKernelContext
        from paw.router import RouteDecision

        entry = BlackboardEntry(role="implementer", kind="result", content=impl_content)
        return TeamKernelContext(
            task="t",
            decision=RouteDecision(
                status="success", strategy="team", summary="s",
                max_iterations=1, next_actions=(),
            ),
            scope=BlackboardScope(project="p", run_id="r"),
            iteration=1,
            entries=(entry,),
        )

    def test_runner_dry_run_reports_diff_does_not_write(self) -> None:
        from paw.team_adapters import make_mutation_runner

        root = Path(tempfile.mkdtemp(prefix="paw_mut_"))
        (root / "a.py").write_text("v = 1\n", encoding="utf-8")
        runner = make_mutation_runner(repo=root, dry_run=True)
        out = runner(self._ctx(_block("a.py", "v = 1", "v = 2")))
        self.assertIn("applied", out.content)
        self.assertIn("would change", out.content)
        self.assertIsNotNone(out.artifact)
        self.assertIn("v = 1", (root / "a.py").read_text(encoding="utf-8"))  # not written

    def test_runner_no_implementer_entry(self) -> None:
        from paw.team_adapters import make_mutation_runner
        from paw.blackboard import BlackboardScope
        from paw.team_kernel import TeamKernelContext
        from paw.router import RouteDecision

        runner = make_mutation_runner(repo=Path(tempfile.mkdtemp()), dry_run=True)
        ctx = TeamKernelContext(
            task="t",
            decision=RouteDecision(status="success", strategy="team", summary="s",
                                   max_iterations=1, next_actions=()),
            scope=BlackboardScope(project="p", run_id="r"),
            iteration=1, entries=(),
        )
        out = runner(ctx)
        self.assertIn("no implementer handoff", out.content)


if __name__ == "__main__":
    unittest.main()
