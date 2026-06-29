"""Tests for paw.memory.facts — ICM structured-facts wrapper.

Most tests stub the runner with a fake ``subprocess.CompletedProcess`` so the
suite never touches a live ICM DB. One integration smoke test (gated on
``PAW_FACTS_LIVE``) exercises the real ``icm.exe`` against a throwaway entity.
"""
from __future__ import annotations

import os
import subprocess
import unittest
from typing import List
from unittest import mock

from paw.memory import facts


def _proc(stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


class FakeRunner:
    """Records calls and returns canned responses keyed by subcommand token."""

    def __init__(self, responses: List[subprocess.CompletedProcess]):
        # responses are consumed in call order.
        self._responses = list(responses)
        self.calls: List[list[str]] = []

    def __call__(self, cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess:
        self.calls.append(cmd)
        if not self._responses:
            return _proc("", returncode=1)
        return self._responses.pop(0)


class ParseGetTests(unittest.TestCase):
    def test_parse_two_line_output(self) -> None:
        out = "value1\n  source: paw | created: 2026-06-29 06:18 | id: 01KW81HX7\n"
        row = facts._parse_get(out, "project:paw", "status")
        self.assertIsNotNone(row)
        assert row is not None  # narrow for type-checker
        self.assertEqual(row.value, "value1")
        self.assertEqual(row.source, "paw")
        self.assertEqual(row.id, "01KW81HX7")
        self.assertEqual(row.slot, "project:paw.status")

    def test_parse_empty_returns_none(self) -> None:
        self.assertIsNone(facts._parse_get("", "e", "k"))
        self.assertIsNone(facts._parse_get("   \n", "e", "k"))

    def test_parse_value_only_no_meta(self) -> None:
        # Older / stripped output: just the value line.
        row = facts._parse_get("plain-value\n", "e", "k")
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row.value, "plain-value")
        self.assertEqual(row.source, "")


class GetFactTests(unittest.TestCase):
    def test_get_returns_parsed_row(self) -> None:
        out = "value1\n  source: paw | created: 2026-06-29 06:18 | id: ABC\n"
        runner = FakeRunner([_proc(stdout=out)])
        row = facts.get_fact("project:paw", "status", runner=runner)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row.value, "value1")
        # facts reads must NOT pass --read-only (verified live: read-only misses
        # freshly-written rows), but must pass --no-embeddings (facts never embed).
        self.assertNotIn("--read-only", runner.calls[0])
        self.assertIn("--no-embeddings", runner.calls[0])

    def test_get_missing_returns_none(self) -> None:
        # exit 1 = absent slot → None, not an exception
        runner = FakeRunner([_proc(stdout="no active fact for x\n", returncode=1)])
        self.assertIsNone(facts.get_fact("e", "k", runner=runner))

    def test_get_subprocess_failure_returns_none(self) -> None:
        def boom(cmd, *, timeout):
            raise subprocess.SubprocessError("icm missing")
        self.assertIsNone(facts.get_fact("e", "k", runner=boom))

    def test_get_empty_args_returns_none(self) -> None:
        self.assertIsNone(facts.get_fact("", "k"))
        self.assertIsNone(facts.get_fact("e", ""))


class ListFactsTests(unittest.TestCase):
    def test_list_parses_table(self) -> None:
        table = (
            "key                              value\n"
            "------------------------------------------------------------\n"
            "smoke_test                       value1\n"
            "status                           building memory\n"
        )
        runner = FakeRunner([_proc(stdout=table)])
        rows = facts.list_facts("project:paw", runner=runner)
        self.assertEqual([r.key for r in rows], ["smoke_test", "status"])
        self.assertEqual(rows[1].value, "building memory")

    def test_list_skips_header_and_separator(self) -> None:
        table = "key     value\n------  -----\nfoo     bar\n"
        runner = FakeRunner([_proc(stdout=table)])
        rows = facts.list_facts("e", runner=runner)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].key, "foo")

    def test_list_failure_returns_empty(self) -> None:
        runner = FakeRunner([_proc(returncode=1)])
        self.assertEqual(facts.list_facts("e", runner=runner), [])


class SetFactTests(unittest.TestCase):
    def test_set_re_reads_and_confirms(self) -> None:
        # set succeeds, then get returns our exact value → True
        out = "v\n  source: paw | created: x | id: y\n"
        runner = FakeRunner([_proc(stdout="set: e.k = v (id=y)\n"), _proc(stdout=out)])
        self.assertTrue(facts.set_fact("e", "k", "v", runner=runner))
        # two calls: set then get
        self.assertEqual(len(runner.calls), 2)
        self.assertIn("set", runner.calls[0])
        self.assertIn("get", runner.calls[1])

    def test_set_detects_honesty_failure(self) -> None:
        # set prints success, but get returns a DIFFERENT value → False
        out = "WRONG\n  source: paw | created: x | id: y\n"
        runner = FakeRunner([_proc(stdout="set: e.k = v (id=y)\n"), _proc(stdout=out)])
        self.assertFalse(facts.set_fact("e", "k", "v", runner=runner))

    def test_set_detects_absent_after_write(self) -> None:
        # set succeeds, get exits 1 (not visible) → False
        runner = FakeRunner([
            _proc(stdout="set: e.k = v (id=y)\n"),
            _proc(stdout="no active fact\n", returncode=1),
        ])
        self.assertFalse(facts.set_fact("e", "k", "v", runner=runner))

    def test_set_no_verify_skips_re_read(self) -> None:
        runner = FakeRunner([_proc(stdout="set: e.k = v\n")])
        self.assertTrue(facts.set_fact("e", "k", "v", runner=runner, verify=False))
        self.assertEqual(len(runner.calls), 1)  # only set, no get

    def test_set_subprocess_failure_returns_false(self) -> None:
        def boom(cmd, *, timeout):
            raise OSError("no icm")
        self.assertFalse(facts.set_fact("e", "k", "v", runner=boom))

    def test_set_empty_args_returns_false(self) -> None:
        self.assertFalse(facts.set_fact("", "k", "v"))
        self.assertFalse(facts.set_fact("e", "", "v"))
        self.assertFalse(facts.set_fact("e", "k", ""))

    def test_set_passes_source_flag(self) -> None:
        runner = FakeRunner([_proc(stdout="set: e.k = v\n")])
        facts.set_fact("e", "k", "v", source="paw:status", runner=runner, verify=False)
        joined = " ".join(runner.calls[0])
        self.assertIn("--source paw:status", joined)


class ForgetFactTests(unittest.TestCase):
    def test_forget_success(self) -> None:
        runner = FakeRunner([_proc(stdout="forgot 1 row(s) under e.k\n")])
        self.assertTrue(facts.forget_fact("e", "k", runner=runner))

    def test_forget_nothing_removed(self) -> None:
        runner = FakeRunner([_proc(stdout="forgot 0 row(s) under e.k\n")])
        # "forgot" keyword present but 0 rows — still counts as a clean no-op
        self.assertTrue(facts.forget_fact("e", "k", runner=runner))

    def test_forget_failure(self) -> None:
        runner = FakeRunner([_proc(stderr="boom", returncode=2)])
        self.assertFalse(facts.forget_fact("e", "k", runner=runner))


@unittest.skipUnless(
    os.environ.get("PAW_FACTS_LIVE"),
    "live ICM smoke — set PAW_FACTS_LIVE=1 to exercise the real icm.exe",
)
class LiveFactsSmokeTests(unittest.TestCase):
    """Round-trips a throwaway entity through the real icm.exe.

    Skipped by default so the unit suite is hermetic. Run with
    ``PAW_FACTS_LIVE=1 python -m pytest tests/test_memory_facts.py -k Live``.
    """

    ENTITY = "project:paw-facts-test"
    KEY = "round_trip"

    def tearDown(self) -> None:
        facts.forget_fact(self.ENTITY, self.KEY)

    def test_live_round_trip(self) -> None:
        self.assertTrue(
            facts.set_fact(self.ENTITY, self.KEY, "hello", source="paw-test")
        )
        row = facts.get_fact(self.ENTITY, self.KEY)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row.value, "hello")
        self.assertEqual(row.source, "paw-test")


if __name__ == "__main__":
    unittest.main()
