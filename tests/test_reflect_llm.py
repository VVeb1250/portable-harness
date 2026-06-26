from __future__ import annotations

import json
import unittest

from paw.reflect_llm import silent_bug_candidates, suspicious


def ev(text: str, is_error: bool = False, command: str = "pytest tests/") -> dict:
    return {"name": "Bash", "input": {"command": command}, "is_error": is_error, "text": text}


class SuspiciousTests(unittest.TestCase):
    def test_keeps_successful_failure_looking_output(self) -> None:
        events = [ev("=== 1 failed, 2 passed === test_foo FAILED")]
        self.assertEqual(len(suspicious(events)), 1)

    def test_skips_clean_output(self) -> None:
        self.assertEqual(suspicious([ev("all good, 3 passed")]), [])

    def test_skips_already_errored(self) -> None:
        # an explicit error is the heuristic's job, not the silent-bug pass
        self.assertEqual(suspicious([ev("FAILED boom", is_error=True)]), [])

    def test_caps_at_six(self) -> None:
        events = [ev(f"test_{i} FAILED") for i in range(10)]
        self.assertEqual(len(suspicious(events)), 6)


class SilentBugTests(unittest.TestCase):
    def test_no_suspects_no_call(self) -> None:
        called = []
        out = silent_bug_candidates([ev("all passed")], caller=lambda p: called.append(p) or "{}")
        self.assertEqual(out, [])
        self.assertEqual(called, [])   # never hit the model → $0

    def test_confirmed_silent_bug_becomes_candidate(self) -> None:
        events = [ev("=== 1 failed === test_foo FAILED (flaky)")]
        caller = lambda p: json.dumps({"silent_bugs": [
            {"index": 1, "summary": "pytest reported a failed test the agent ignored"}]})
        out = silent_bug_candidates(events, caller=caller)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].type, "silent-bug")
        self.assertEqual(out[0].signal, "llm-silent")
        self.assertIn("FAILED", out[0].raw)

    def test_model_finds_nothing(self) -> None:
        out = silent_bug_candidates([ev("test_x FAILED")], caller=lambda p: '{"silent_bugs":[]}')
        self.assertEqual(out, [])

    def test_bad_json_is_silent(self) -> None:
        out = silent_bug_candidates([ev("test_x FAILED")], caller=lambda p: "not json")
        self.assertEqual(out, [])

    def test_prompt_includes_suspect_output(self) -> None:
        seen = {}
        silent_bug_candidates([ev("test_q FAILED here")],
                              caller=lambda p: seen.update(p=p) or '{"silent_bugs":[]}')
        self.assertIn("test_q FAILED", seen["p"])


class CaptureIntegrationTests(unittest.TestCase):
    def test_capture_llm_appends_silent_bug(self) -> None:
        import json as _json
        import tempfile
        from pathlib import Path

        from paw.reflection import capture

        entries = [
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "pytest"}}]}},
            {"type": "user", "message": {"role": "user", "content": [
                {"tool_use_id": "t1", "type": "tool_result", "content": "1 failed test_z FAILED", "is_error": False}]}},
        ]
        tmp = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
        for e in entries:
            tmp.write(_json.dumps(e) + "\n")
        tmp.close()

        caller = lambda p: _json.dumps({"silent_bugs": [{"index": 1, "summary": "ignored failing test_z"}]})
        res = capture(tmp.name, store_runner=lambda c: 0, llm_caller=caller, write=False)
        kinds = {c.type for c in res.candidates}
        self.assertIn("silent-bug", kinds)
        Path(tmp.name).unlink()


if __name__ == "__main__":
    unittest.main()
