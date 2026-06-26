from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paw.blackboard import BlackboardEntry, BlackboardScope
from paw.router import RouteDecision
from paw.team_adapters import (
    AdapterError,
    CodexCliTextAdapter,
    DeepSeekTextAdapter,
    build_codex_deepseek_adapters,
)
from paw.team_kernel import TeamKernelContext


def _context(entries: tuple[BlackboardEntry, ...] = ()) -> TeamKernelContext:
    return TeamKernelContext(
        task="Fix the parser bug.",
        decision=RouteDecision(
            status="success",
            summary="team",
            strategy="team",
            roles={"planner": "codex", "implementer": "deepseek", "reviewer": "codex"},
            max_iterations=3,
        ),
        scope=BlackboardScope(project="portable-harness", run_id="adapter-test"),
        iteration=1,
        entries=entries,
    )


class Completed:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeHttpResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeHttpResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class TeamAdapterTests(unittest.TestCase):
    def test_codex_adapter_uses_read_only_exec_and_parses_usage(self) -> None:
        calls: list[dict[str, object]] = []

        def runner(**kwargs: object) -> Completed:
            calls.append(kwargs)
            command = str(kwargs["args"])
            output_path = command.split('-o "', 1)[1].split('"', 1)[0]
            Path(output_path).write_text("Plan: inspect parser.py", encoding="utf-8")
            stdout = "\n".join(
                [
                    json.dumps(
                        {
                            "type": "item.completed",
                            "item": {"type": "command_execution"},
                        }
                    ),
                    json.dumps(
                        {
                            "type": "turn.completed",
                            "usage": {"input_tokens": 10, "output_tokens": 3},
                        }
                    ),
                ]
            )
            return Completed(0, stdout=stdout)

        adapter = CodexCliTextAdapter(repo=Path.cwd(), runner=runner)
        output = adapter.planner(_context())

        self.assertEqual(output.content, "Plan: inspect parser.py")
        self.assertIn("codex:", output.artifact or "")
        self.assertIn("-s read-only", str(calls[0]["args"]))
        self.assertIn("--json", str(calls[0]["args"]))
        self.assertIn("Produce a concise implementation plan", str(calls[0]["input"]))

    def test_codex_adapter_surfaces_nonzero_exit(self) -> None:
        adapter = CodexCliTextAdapter(
            repo=Path.cwd(),
            runner=lambda **kwargs: Completed(7, stderr="auth failed"),
        )

        with self.assertRaises(AdapterError):
            adapter.planner(_context())

    def test_deepseek_adapter_posts_anthropic_compatible_payload(self) -> None:
        requests: list[object] = []

        def opener(request: object, timeout: int = 0) -> FakeHttpResponse:
            requests.append(request)
            return FakeHttpResponse(
                {
                    "content": [{"text": "Implemented according to plan."}],
                    "usage": {"input_tokens": 12, "output_tokens": 4},
                }
            )

        context = _context(
            (
                BlackboardEntry(role="planner", kind="plan", content="Plan: edit parser.py"),
            )
        )
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            output = DeepSeekTextAdapter(opener=opener).implementer(context)

        self.assertEqual(output.content, "Implemented according to plan.")
        self.assertIn("deepseek:", output.artifact or "")
        request = requests[0]
        self.assertEqual(request.full_url, "https://api.deepseek.com/anthropic/v1/messages")
        self.assertEqual(request.headers["X-api-key"], "test-key")
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["model"], "deepseek-v4-flash")
        self.assertIn("Plan: edit parser.py", body["messages"][0]["content"])

    def test_deepseek_adapter_requires_key_without_http_call(self) -> None:
        called = False

        def opener(request: object, timeout: int = 0) -> FakeHttpResponse:
            nonlocal called
            called = True
            return FakeHttpResponse({})

        with patch.dict(os.environ, {}, clear=True):
            adapter = DeepSeekTextAdapter(opener=opener)
            with self.assertRaises(AdapterError):
                adapter.implementer(_context())

        self.assertFalse(called)

    def test_codex_deepseek_profile_keeps_claude_out_of_default_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            adapters = build_codex_deepseek_adapters(repo=Path(directory))

        self.assertEqual(adapters.planner.__self__.__class__, CodexCliTextAdapter)
        self.assertEqual(adapters.reviewer.__self__.__class__, CodexCliTextAdapter)
        self.assertEqual(adapters.implementer.__self__.__class__, DeepSeekTextAdapter)


if __name__ == "__main__":
    unittest.main()
