from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paw.reflection import (
    Candidate,
    _store_cmd,
    capture,
    iter_entries,
    load_watermark,
    read_entries,
    save_watermark,
    scan_transcript,
)


def asst(name: str, tid: str, **inp) -> dict:
    return {"type": "assistant", "message": {"role": "assistant",
            "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}}


def result(tid: str, is_error=None, content: str = "ok") -> dict:
    block: dict = {"tool_use_id": tid, "type": "tool_result", "content": content}
    if is_error is not None:
        block["is_error"] = is_error
    return {"type": "user", "message": {"role": "user", "content": [block]}}


def user_text(text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": text}}


class ScanExecutionTests(unittest.TestCase):
    def test_fail_then_fix_pairs(self) -> None:
        entries = [
            asst("Bash", "a", command="py -m paw bogus"),
            result("a", is_error=True, content="error: invalid choice 'bogus'"),
            asst("Bash", "b", command="py -m paw sets list"),
            result("b", is_error=False),
        ]
        cands = scan_transcript(entries)
        self.assertEqual(len(cands), 1)
        c = cands[0]
        self.assertEqual(c.type, "execution")
        self.assertEqual(c.signal, "fail-fix")
        self.assertIn("fixed by", c.detail)
        self.assertIn("invalid choice", c.raw)

    def test_fail_without_fix(self) -> None:
        entries = [
            asst("Bash", "a", command="py broken.py"),
            result("a", is_error=True, content="Traceback: boom"),
        ]
        cands = scan_transcript(entries)
        self.assertEqual(cands[0].signal, "is_error")
        self.assertIn("no in-session fix", cands[0].detail)

    def test_clean_transcript_no_candidates(self) -> None:
        entries = [asst("Bash", "a", command="ls"), result("a", is_error=False)]
        self.assertEqual(scan_transcript(entries), [])

    def test_dedup_identical_failures(self) -> None:
        entries = [
            asst("Bash", "a", command="py x"),
            result("a", is_error=True, content="same error"),
            asst("Bash", "b", command="py x"),
            result("b", is_error=True, content="same error"),
        ]
        self.assertEqual(len(scan_transcript(entries)), 1)

    def test_cap_at_eight(self) -> None:
        entries = []
        for i in range(12):
            entries.append(asst("Bash", str(i), command=f"py cmd{i}"))
            entries.append(result(str(i), is_error=True, content=f"err number {i}"))
        self.assertEqual(len(scan_transcript(entries)), 8)


class ScanMisalignmentTests(unittest.TestCase):
    def test_correction_marker_captured(self) -> None:
        entries = [user_text("ไม่ใช่ อันนี้ผิด แก้ใหม่")]
        cands = scan_transcript(entries)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0].type, "misalignment")

    def test_english_revert_marker(self) -> None:
        cands = scan_transcript([user_text("please revert that change")])
        self.assertEqual(cands[0].signal, "correction")

    def test_plain_user_turn_ignored(self) -> None:
        self.assertEqual(scan_transcript([user_text("add a new feature please")]), [])

    def test_tool_result_turn_not_treated_as_correction(self) -> None:
        # is_error result content mentioning "wrong" must not become misalignment
        entries = [result("a", is_error=None, content="that's wrong output")]
        self.assertEqual(scan_transcript(entries), [])


class NoiseControlTests(unittest.TestCase):
    """The owner's core worry: capture must not flood pending with non-mistakes."""

    def test_permission_denial_not_captured(self) -> None:
        entries = [
            asst("Edit", "a", file_path="x.py"),
            result("a", is_error=True, content="The user doesn't want to proceed with this tool use. The tool use was rejected"),
        ]
        self.assertEqual(scan_transcript(entries), [])

    def test_nah_guard_block_not_captured(self) -> None:
        entries = [
            asst("Edit", "a", file_path="hook.py"),
            result("a", is_error=True, content="nah blocked: this tries to modify Claude Code hooks."),
        ]
        self.assertEqual(scan_transcript(entries), [])

    def test_compact_summary_turn_ignored(self) -> None:
        e = {"type": "user", "isCompactSummary": True,
             "message": {"role": "user", "content": "ไม่ใช่ ... revert ... wrong approach " * 3}}
        self.assertEqual(scan_transcript([e]), [])

    def test_long_turn_mentioning_correction_word_ignored(self) -> None:
        spec = user_text("เพิ่มฟีเจอร์ใหม่ " + "x" * 260 + " revert")
        self.assertEqual(scan_transcript([spec]), [])


class CaptureTests(unittest.TestCase):
    def _transcript(self, entries) -> str:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
        for e in entries:
            tmp.write(json.dumps(e) + "\n")
        tmp.close()
        return tmp.name

    def test_capture_writes_via_runner(self) -> None:
        path = self._transcript([
            asst("Bash", "a", command="py boom"),
            result("a", is_error=True, content="boom error"),
        ])
        calls: list[list[str]] = []
        res = capture(path, session_id="sess-1234567890ab", store_runner=lambda c: calls.append(c) or 0)
        self.assertEqual(res.stored, 1)
        self.assertTrue(res.wrote)
        self.assertEqual(len(calls), 1)
        Path(path).unlink()

    def test_dry_run_does_not_store(self) -> None:
        path = self._transcript([
            asst("Bash", "a", command="py boom"),
            result("a", is_error=True, content="boom"),
        ])
        called = []
        res = capture(path, store_runner=lambda c: called.append(c) or 0, write=False)
        self.assertEqual(res.stored, 0)
        self.assertFalse(res.wrote)
        self.assertEqual(called, [])
        self.assertEqual(len(res.candidates), 1)
        Path(path).unlink()

    def test_missing_transcript_is_silent(self) -> None:
        res = capture("E:/nope/missing.jsonl", store_runner=lambda c: 0)
        self.assertEqual(res.candidates, [])
        self.assertEqual(res.stored, 0)

    def test_iter_entries_skips_bad_lines(self) -> None:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
        tmp.write('{"type":"user"}\n')
        tmp.write("not json\n")
        tmp.write("\n")
        tmp.write('{"type":"assistant"}\n')
        tmp.close()
        self.assertEqual(len(list(iter_entries(tmp.name))), 2)
        Path(tmp.name).unlink()


class IncrementalTests(unittest.TestCase):
    def _transcript(self, entries) -> str:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
        for e in entries:
            tmp.write(json.dumps(e) + "\n")
        tmp.close()
        return tmp.name

    def test_read_entries_slices_and_counts(self) -> None:
        path = self._transcript([user_text("one"), user_text("two"), user_text("three")])
        entries, total = read_entries(path, start_line=2)
        self.assertEqual(total, 3)
        self.assertEqual(len(entries), 1)
        Path(path).unlink()

    def test_capture_only_scans_new_lines(self) -> None:
        # a fail in the first turn, already past the watermark → not re-captured
        path = self._transcript([
            asst("Bash", "a", command="py boom"),
            result("a", is_error=True, content="boom error"),
            user_text("plain follow up"),
        ])
        calls: list = []
        res = capture(path, start_line=2, store_runner=lambda c: calls.append(c) or 0)
        self.assertEqual(res.candidates, [])
        self.assertEqual(res.next_line, 3)
        Path(path).unlink()

    def test_watermark_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "sess.json"
            with mock.patch("paw.reflection._watermark_path", return_value=target):
                self.assertEqual(load_watermark("sess"), 0)
                save_watermark("sess", 42)
                self.assertEqual(load_watermark("sess"), 42)

    def test_watermark_empty_session_is_noop(self) -> None:
        save_watermark("", 5)        # must not raise / not write
        self.assertEqual(load_watermark(""), 0)


class StoreCmdTests(unittest.TestCase):
    def test_store_cmd_shape(self) -> None:
        c = Candidate("execution", "fail-fix", "Bash failed: boom", "fixed by: py ok",
                      raw="$ py boom\nboom", terms=("boom", "paw"))
        cmd = _store_cmd(c, "sess-abcdef123456")
        self.assertIn("store", cmd)
        self.assertIn("pending", cmd)
        kw = cmd[cmd.index("-k") + 1]
        self.assertIn("type:execution", kw)
        self.assertIn("signal:fail-fix", kw)
        self.assertIn("session:sess-abcdef1", kw)
        self.assertIn("-r", cmd)


if __name__ == "__main__":
    unittest.main()
