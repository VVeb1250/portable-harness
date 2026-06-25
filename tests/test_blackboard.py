from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from paw.blackboard import BlackboardEntry, BlackboardScope, IcmBlackboard


class RecordingRunner:
    def __init__(self, outputs: list[str] | None = None) -> None:
        self.commands: list[list[str]] = []
        self.outputs = list(outputs or [])

    def __call__(self, command: list[str]) -> str:
        self.commands.append(command)
        return self.outputs.pop(0) if self.outputs else "stored"


class FailingRunner:
    def __call__(self, command: list[str]) -> str:
        raise RuntimeError("simulated ICM failure")


class BlackboardContractTests(unittest.TestCase):
    def test_write_uses_run_scoped_topic_and_versioned_payload(self) -> None:
        runner = RecordingRunner()
        board = IcmBlackboard(executable="icm.exe", runner=runner)

        result = board.write(
            BlackboardScope(project="portable-harness", run_id="run 42"),
            BlackboardEntry(
                role="planner",
                kind="plan",
                content="Inspect parser.py, then add focused regression tests.",
                artifact="plans/run-42.md",
            ),
        )

        self.assertEqual(result.status, "success")
        command = runner.commands[0]
        self.assertEqual(command[0:2], ["icm.exe", "store"])
        self.assertIn("portable-harness/blackboard/run-42", command)
        payload = json.loads(command[command.index("--content") + 1])
        self.assertEqual(payload["schema"], "paw-blackboard/v1")
        self.assertEqual(payload["role"], "planner")
        self.assertEqual(payload["kind"], "plan")
        self.assertEqual(payload["artifact"], "plans/run-42.md")
        keywords = command[command.index("--keywords") + 1]
        self.assertIn("role:planner", keywords)
        self.assertIn("kind:plan", keywords)

    def test_read_is_bounded_and_filters_parsed_entries(self) -> None:
        memories = [
            {
                "content": json.dumps(
                    {
                        "schema": "paw-blackboard/v1",
                        "project": "portable-harness",
                        "run_id": "r1",
                        "role": "reviewer",
                        "kind": "review",
                        "content": "REVISE: add the missing regression test.",
                        "artifact": None,
                    }
                )
            },
            {"content": "legacy memory that is not a blackboard entry"},
        ]
        runner = RecordingRunner([json.dumps(memories)])
        board = IcmBlackboard(executable="icm.exe", runner=runner)

        result = board.read(
            BlackboardScope(project="portable-harness", run_id="r1"),
            query="regression",
            role="reviewer",
            kind="review",
            limit=3,
        )

        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.entries), 1)
        self.assertEqual(result.entries[0].role, "reviewer")
        command = runner.commands[0]
        self.assertEqual(command[0:2], ["icm.exe", "recall"])
        self.assertEqual(command[command.index("--limit") + 1], "3")
        self.assertIn("--no-embeddings", command)
        self.assertIn("--read-only", command)

    def test_database_override_is_passed_without_touching_global_memory(self) -> None:
        runner = RecordingRunner(["[]"])
        board = IcmBlackboard(
            executable="icm.exe",
            database=Path("scratch/icm.db"),
            runner=runner,
        )

        board.read(BlackboardScope(project="p", run_id="r"))

        command = runner.commands[0]
        self.assertEqual(
            command[command.index("--db") + 1],
            str(Path("scratch/icm.db")),
        )

    def test_secret_like_content_is_rejected_before_icm_is_called(self) -> None:
        runner = RecordingRunner()
        board = IcmBlackboard(executable="icm.exe", runner=runner)

        result = board.write(
            BlackboardScope(project="p", run_id="r"),
            BlackboardEntry(
                role="implementer",
                kind="observation",
                content="OPENAI_API_KEY=do-not-store-this",
            ),
        )

        self.assertEqual(result.status, "error")
        self.assertEqual(runner.commands, [])
        self.assertIn("secret", result.summary.lower())

    def test_scope_and_entry_validation_fail_without_side_effects(self) -> None:
        runner = RecordingRunner()
        board = IcmBlackboard(executable="icm.exe", runner=runner)

        bad_scope = board.write(
            BlackboardScope(project="../escape", run_id="r"),
            BlackboardEntry(role="planner", kind="plan", content="plan"),
        )
        bad_entry = board.write(
            BlackboardScope(project="p", run_id="r"),
            BlackboardEntry(role="", kind="plan", content="plan"),
        )

        self.assertEqual(bad_scope.status, "error")
        self.assertEqual(bad_entry.status, "error")
        self.assertEqual(runner.commands, [])

    def test_icm_failures_and_invalid_json_return_recovery_guidance(self) -> None:
        scope = BlackboardScope(project="p", run_id="r")
        entry = BlackboardEntry(role="planner", kind="plan", content="plan")

        write = IcmBlackboard(runner=FailingRunner()).write(scope, entry)
        read_failure = IcmBlackboard(runner=FailingRunner()).read(scope)
        invalid_json = IcmBlackboard(runner=RecordingRunner(["not-json"])).read(scope)

        self.assertEqual(write.status, "error")
        self.assertEqual(read_failure.status, "error")
        self.assertEqual(invalid_json.status, "error")
        self.assertTrue(write.next_actions)
        self.assertTrue(read_failure.next_actions)

    def test_validation_covers_entry_and_read_boundaries(self) -> None:
        runner = RecordingRunner()
        board = IcmBlackboard(runner=runner)
        scope = BlackboardScope(project="p", run_id="r")

        results = [
            board.write(scope, BlackboardEntry(role="planner", kind="plan", content="")),
            board.write(
                scope,
                BlackboardEntry(role="planner", kind="plan", content="x" * 4_001),
            ),
            board.write(
                scope,
                BlackboardEntry(
                    role="planner",
                    kind="plan",
                    content="plan",
                    artifact="bad\npath",
                ),
            ),
            board.read(scope, query="x" * 501),
            board.read(scope, kind="unknown"),  # type: ignore[arg-type]
            board.read(scope, limit=0),
        ]

        self.assertTrue(all(result.status == "error" for result in results))
        self.assertEqual(runner.commands, [])

    def test_parser_accepts_wrapped_json_and_ignores_invalid_entries(self) -> None:
        valid = {
            "summary": json.dumps(
                {
                    "schema": "paw-blackboard/v1",
                    "project": "p",
                    "run_id": "r",
                    "role": "reviewer",
                    "kind": "review",
                    "content": "PASS",
                    "artifact": "review.txt",
                }
            )
        }
        invalid = [
            {"summary": 42},
            {"summary": "not-json"},
            {"summary": json.dumps({"schema": "other"})},
        ]
        runner = RecordingRunner(
            [json.dumps({"memories": [*invalid, valid, "not-a-memory"]})]
        )
        result = IcmBlackboard(runner=runner).read(
            BlackboardScope(project="p", run_id="r")
        )

        self.assertEqual(len(result.entries), 1)
        self.assertEqual(result.artifacts, ("review.txt",))
        self.assertEqual(result.to_dict()["status"], "success")


class BlackboardCliIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("icm.exe"), "ICM CLI is not installed")
    def test_cli_round_trip_uses_isolated_icm_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "blackboard.db")
            write = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "paw",
                    "blackboard",
                    "write",
                    "--project",
                    "portable-harness",
                    "--run-id",
                    "integration-1",
                    "--role",
                    "planner",
                    "--kind",
                    "plan",
                    "--content",
                    "Implement the adapter, then run isolated integration tests.",
                    "--artifact",
                    "plans/integration-1.md",
                    "--db",
                    database,
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(write.returncode, 0, write.stderr)

            read = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "paw",
                    "blackboard",
                    "read",
                    "--project",
                    "portable-harness",
                    "--run-id",
                    "integration-1",
                    "--query",
                    "adapter integration tests",
                    "--limit",
                    "5",
                    "--db",
                    database,
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(read.returncode, 0, read.stderr)
            payload = json.loads(read.stdout)
            self.assertEqual(payload["status"], "success")
            self.assertEqual(len(payload["entries"]), 1)
            self.assertEqual(payload["entries"][0]["role"], "planner")
            self.assertEqual(payload["entries"][0]["kind"], "plan")


if __name__ == "__main__":
    unittest.main()
