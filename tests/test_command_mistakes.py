"""Tests for paw.command_mistakes deterministic classifier."""
from __future__ import annotations

import unittest

from paw.command_mistakes import classify, ClassifyResult


class PromoteTests(unittest.TestCase):
    """Cases that SHOULD be promoted to reusable mistakes."""

    def test_powershell_heredoc_in_python(self) -> None:
        r = classify(
            "python - <<'PY'",
            "The string is missing the terminator",
        )
        self.assertEqual(r.op, "promote")
        self.assertEqual(r.category, "shell-contract")

    def test_icm_keywords_repeated(self) -> None:
        r = classify(
            "icm.exe store --keywords a --keywords b",
            "error: the argument '--keywords <KEYWORDS>' cannot be used "
            "multiple times",
        )
        self.assertEqual(r.op, "promote")
        self.assertEqual(r.category, "cli-contract")

    def test_format_hex_on_older_powershell(self) -> None:
        r = classify(
            "Format-Hex -Count 16 file.bin",
            "Format-Hex : The term 'Format-Hex' is not recognized",
        )
        self.assertEqual(r.op, "promote")
        self.assertEqual(r.category, "platform-gotcha")

    def test_cannot_overwrite_variable_host(self) -> None:
        r = classify(
            "$Host = 'server01'",
            "Cannot overwrite variable 'Host' because it is read-only",
        )
        self.assertEqual(r.op, "promote")
        self.assertEqual(r.category, "platform-gotcha")

    def test_icm_without_exe(self) -> None:
        r = classify(
            "icm recall test --read-only",
            "(no output)",
        )
        self.assertEqual(r.op, "promote")
        self.assertEqual(r.category, "cli-contract")
        self.assertIn("icm.exe", r.fix)

    def test_powershell_stderr_redirect_on_native_exe(self) -> None:
        r = classify(
            "python -c 'print(1)' 2>&1",
            "NativeCommandError",
        )
        self.assertEqual(r.op, "promote")

    def test_powershell_51_rejects_double_ampersand(self) -> None:
        r = classify(
            "rg pattern file && Get-Content file",
            "At line:2 char:104",
        )
        self.assertEqual(r.op, "promote")
        self.assertEqual(r.category, "shell-contract")
        self.assertIn("PowerShell", r.summary)

    def test_pytest_unrecognized_args(self) -> None:
        r = classify(
            "py -m pytest --forked tests/",
            "ERROR: could not find",
        )
        self.assertEqual(r.op, "promote")
        self.assertEqual(r.category, "cli-contract")

    def test_missing_python_module(self) -> None:
        r = classify(
            "python -m requests",
            "ModuleNotFoundError: No module named 'requests'",
        )
        self.assertEqual(r.op, "promote")
        self.assertEqual(r.category, "cli-contract")

    def test_mistake_keywords_are_reasonable(self) -> None:
        r = classify(
            "icm.exe store --keywords a --keywords b",
            "error: the argument '--keywords <KEYWORDS>' cannot be used",
        )
        kw = r.mistake_keywords()
        self.assertTrue(any("cli-contract" in k for k in kw))
        self.assertTrue(any(len(k) >= 4 for k in kw))


class SkipTests(unittest.TestCase):
    """Cases that should NOT become durable memory."""

    def test_pytest_red_phase(self) -> None:
        r = classify(
            "python -m pytest tests/",
            "FAILED tests/test_foo.py::test_bar - AssertionError",
        )
        self.assertEqual(r.op, "skip")
        self.assertEqual(r.category, "test-noise")

    def test_inline_probe_py_c(self) -> None:
        r = classify(
            "py -c 'import sys; print(sys.version)'",
            "SyntaxError: invalid syntax",
        )
        self.assertEqual(r.op, "skip")
        self.assertEqual(r.category, "probe")

    def test_inline_probe_node_e(self) -> None:
        r = classify(
            "node -e 'console.log(1)'",
            "ReferenceError",
        )
        self.assertEqual(r.op, "skip")
        self.assertEqual(r.category, "probe")

    def test_missing_file_exploration(self) -> None:
        r = classify(
            "cat /nonexistent/file",
            "No such file or directory",
        )
        self.assertEqual(r.op, "skip")
        self.assertEqual(r.category, "exploration")

    def test_which_command_probe(self) -> None:
        r = classify(
            "which nonexistent-tool",
            "(no output)",
        )
        self.assertEqual(r.op, "skip")
        self.assertEqual(r.category, "probe")

    def test_git_diff_empty(self) -> None:
        r = classify(
            "git diff --stat",
            "(no output)",
        )
        self.assertEqual(r.op, "skip")
        self.assertEqual(r.category, "exploration")

    def test_rg_no_results(self) -> None:
        r = classify(
            "rg nonexistent_function src/",
            "(no output)",
        )
        self.assertEqual(r.op, "skip")
        self.assertEqual(r.category, "exploration")


class DefaultPromoteTests(unittest.TestCase):
    """Unrecognised errors get promoted as one-off by default."""

    def test_unknown_error_promotes_as_one_off(self) -> None:
        r = classify(
            "some-unknown-command --flag value",
            "Something went wrong: exit code 1",
        )
        self.assertEqual(r.op, "promote")
        self.assertEqual(r.category, "one-off")


class ClassifyResultTests(unittest.TestCase):
    def test_to_dict(self) -> None:
        r = ClassifyResult(
            op="promote",
            category="cli-contract",
            summary="test summary",
            trigger="test trigger",
            fix="test fix",
            keywords=["k1", "k2"],
        )
        d = r.to_dict()
        self.assertEqual(d["op"], "promote")
        self.assertEqual(d["category"], "cli-contract")
        self.assertEqual(d["summary"], "test summary")


if __name__ == "__main__":
    unittest.main()
