from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paw.codebase_memory import (
    CodebaseMemoryResult,
    SearchOutput,
    SearchRow,
    codebase_memory_project_name,
    default_codebase_memory_binary,
    format_search_output,
    parse_search_output,
    run_codebase_memory_tool,
)


class CodebaseMemoryWrapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.binary = self.root / "codebase-memory-mcp.exe"
        self.binary.write_text("stub", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_project_name_matches_foundation_bench_convention(self) -> None:
        path = Path("E:/portable-harness/bench/dev_foundation/worktree")

        self.assertEqual(
            codebase_memory_project_name(path),
            "E-portable-harness-bench-dev_foundation-worktree",
        )

    def test_default_binary_prefers_repo_local_bench_tool(self) -> None:
        local = self.root / "bench" / "_tools" / "codebase-memory-mcp"
        local.mkdir(parents=True)
        expected = local / "codebase-memory-mcp.exe"
        expected.write_text("stub", encoding="utf-8")

        found = default_codebase_memory_binary(root=self.root)

        self.assertEqual(found, expected)

    def test_run_tool_passes_json_as_one_argv_without_shell(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="indexed",
            stderr="",
        )
        with mock.patch("subprocess.run", return_value=completed) as run:
            result = run_codebase_memory_tool(
                "index_repository",
                {"repo_path": "E:/portable-harness"},
                binary=self.binary,
            )

        self.assertEqual(result.returncode, 0)
        command = run.call_args.args[0]
        self.assertEqual(command[:3], [str(self.binary), "cli", "index_repository"])
        self.assertFalse(run.call_args.kwargs.get("shell", False))
        self.assertEqual(json.loads(command[3]), {"repo_path": "E:/portable-harness"})


    def test_parse_search_output_list_of_dicts(self) -> None:
        items = [
            {"name": "run_doctor", "kind": "function", "file": "paw/doctor.py", "qualified_name": "paw.doctor.run_doctor"},
            {"name": "DoctorReport", "kind": "class", "file": "paw/doctor.py", "qualified_name": "paw.doctor.DoctorReport"},
        ]
        result = CodebaseMemoryResult(
            command=("bin", "cli", "search_graph", "{}"),
            returncode=0,
            stdout=json.dumps(items),
            stderr="",
        )
        output = parse_search_output(result)
        self.assertEqual(output.total, 2)
        self.assertEqual(output.rows[0].name, "run_doctor")
        self.assertEqual(output.rows[0].label, "function")

    def test_parse_search_output_dict_with_results_key(self) -> None:
        items = [
            {"name": "DoctorTests", "label": "class", "file_path": "tests/test_doctor.py"},
        ]
        result = CodebaseMemoryResult(
            command=("bin", "cli", "search_graph", "{}"),
            returncode=0,
            stdout=json.dumps({"results": items}),
            stderr="",
        )
        output = parse_search_output(result)
        self.assertEqual(output.total, 1)
        self.assertEqual(output.rows[0].name, "DoctorTests")

    def test_parse_search_output_empty(self) -> None:
        result = CodebaseMemoryResult(
            command=("bin", "cli", "search_graph", "{}"),
            returncode=0,
            stdout="",
            stderr="",
        )
        output = parse_search_output(result)
        self.assertEqual(output.total, 0)
        self.assertEqual(len(output.rows), 0)

    def test_format_search_output_default_limit(self) -> None:
        rows = tuple(SearchRow(name=f"sym{i}", label="var", file_path=f"file{i}.py") for i in range(15))
        output = SearchOutput(total=15, rows=rows, raw="{}")
        text = format_search_output(output, limit=10)
        self.assertIn("found 15 symbol(s)", text)
        self.assertIn("showing 10/15", text)
        self.assertIn("... 5 more", text)

    def test_format_search_output_json_mode(self) -> None:
        output = SearchOutput(total=2, rows=(), raw='[{"name": "test"}]')
        text = format_search_output(output, json_mode=True)
        self.assertEqual(text, '[{"name": "test"}]')

    def test_format_search_output_no_rows(self) -> None:
        output = SearchOutput(total=0, rows=(), raw="")
        text = format_search_output(output)
        self.assertIn("found 0 symbol(s)", text)
        self.assertNotIn("showing", text)


if __name__ == "__main__":
    unittest.main()
