"""Tests for paw.curate — pending reconciliation, store/forget verification, classifier integration."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace
import unittest
from unittest import mock

from paw.curate import (
    ApplyReceipt,
    Decision,
    _bump_keywords,
    _escalate,
    _jaccard,
    _seen_of,
    _verify_forget_drained,
    _verify_visible,
    curate,
    list_pending,
    list_topic,
    pending_count,
    reconcile,
    trigger_from_pending,
)


def pending(summary: str, keywords=None, pid: str = "p1", importance: str = "medium") -> dict:
    return {"id": pid, "summary": summary, "importance": importance,
            "topic": "pending", "keywords": keywords or []}


def wiki(summary: str, keywords=None, wid: str = "w1", importance: str = "medium") -> dict:
    return {"id": wid, "summary": summary, "importance": importance,
            "topic": "mistakes", "keywords": keywords or []}


class HelperTests(unittest.TestCase):
    def test_jaccard(self) -> None:
        self.assertEqual(_jaccard({"a", "b"}, {"a", "b"}), 1.0)
        self.assertEqual(_jaccard({"a"}, {"b"}), 0.0)
        self.assertEqual(_jaccard(set(), {"a"}), 0.0)

    def test_seen_of(self) -> None:
        self.assertEqual(_seen_of(["x", "seen:4", "type:execution"]), 4)
        self.assertEqual(_seen_of(["x"]), 1)

    def test_trigger_from_structured_summary_uses_original_command(self) -> None:
        p = pending(
            "Bash failed: command=py broken.py | error=Traceback: boom "
            "→ no in-session fix found",
            keywords=["type:execution"],
        )
        self.assertEqual(trigger_from_pending(p), "py broken.py")

    def test_escalate(self) -> None:
        self.assertEqual(_escalate(1, "medium"), "medium")
        self.assertEqual(_escalate(2, "medium"), "high")
        self.assertEqual(_escalate(3, "medium"), "critical")

    def test_escalate_never_downgrades(self) -> None:
        self.assertEqual(_escalate(1, "critical"), "critical")

    def test_bump_keywords_replaces_seen(self) -> None:
        out = _bump_keywords(["type:execution", "seen:2", "py"], 3)
        self.assertIn("seen:3", out)
        self.assertNotIn("seen:2", out)
        self.assertIn("type:execution", out)


class ReconcileTests(unittest.TestCase):
    def test_add_when_no_match(self) -> None:
        d = reconcile(
            pending("use py launcher not python on windows",
                    keywords=["type:execution", "signal:fail-fix", "session:abc", "python", "windows"]),
            recall_fn=lambda q: [],
        )
        self.assertEqual(d.op, "add")
        self.assertIn("type:execution", d.keywords)
        self.assertIn("seen:1", d.keywords)
        # signal:/session: dropped from the promoted lesson
        self.assertNotIn("signal:fail-fix", d.keywords)
        self.assertNotIn("session:abc", d.keywords)

    def test_bump_when_near_duplicate(self) -> None:
        existing = wiki("use py launcher not python3 on windows always",
                        keywords=["seen:1", "py"], wid="w9", importance="high")
        d = reconcile(
            pending("use py launcher not python on windows always",
                    keywords=["type:execution", "py"]),
            recall_fn=lambda q: [existing],
        )
        self.assertEqual(d.op, "bump")
        self.assertEqual(d.target_id, "w9")
        self.assertIn("seen:2", d.keywords)
        self.assertEqual(d.importance, "high")   # seen=2 → high, existing already high

    def test_bump_escalates_to_critical_on_third(self) -> None:
        existing = wiki("docker stale socket recovery rename run secrets dirs",
                        keywords=["seen:2"], wid="w2")
        d = reconcile(
            pending("docker stale socket recovery rename run secrets dirs aside"),
            recall_fn=lambda q: [existing],
        )
        self.assertEqual(d.op, "bump")
        self.assertEqual(d.importance, "critical")  # seen 2→3

    def test_pending_topic_match_ignored(self) -> None:
        other_pending = {"id": "p2", "summary": "use py launcher not python on windows",
                         "topic": "pending", "keywords": []}
        d = reconcile(
            pending("use py launcher not python on windows", keywords=["type:execution"]),
            recall_fn=lambda q: [other_pending],
        )
        self.assertEqual(d.op, "add")

    # --- classifier integration ---

    def test_classifier_skip_test_noise(self) -> None:
        d = reconcile(
            pending("python -m pytest tests/ failed: AssertionError",
                    keywords=["type:execution"], pid="p100"),
            recall_fn=lambda q: [],
        )
        self.assertEqual(d.op, "skip")

    def test_classifier_skip_inline_probe(self) -> None:
        d = reconcile(
            pending("py -c 'import sys' failed: SyntaxError",
                    keywords=["type:execution"], pid="p101"),
            recall_fn=lambda q: [],
        )
        self.assertEqual(d.op, "skip")

    def test_classifier_promotes_reusable_command_mistake(self) -> None:
        d = reconcile(
            pending("Bash failed: command=python - <<'PY' | error=ParserError: missing file",
                    keywords=["type:execution"], pid="p102",
                    importance="medium"),
            recall_fn=lambda q: [],
        )
        self.assertEqual(d.op, "add")
        self.assertIn("PowerShell does not support Bash heredoc", d.content)
        self.assertIn("->", d.content)
        self.assertIn("python -", d.content)

    def test_one_off_with_fix_becomes_command_to_fix_lesson(self) -> None:
        d = reconcile(
            pending("Bash failed: command=paw nope | error=invalid choice "
                    "→ fixed by: paw --help",
                    keywords=["type:execution"], pid="p103"),
            recall_fn=lambda q: [],
        )
        self.assertEqual(d.op, "add")
        self.assertEqual(
            d.content,
            "Command `paw nope` failed with `invalid choice` -> use `paw --help`",
        )

    def test_one_off_with_fix_tolerates_missing_unicode_arrow(self) -> None:
        d = reconcile(
            pending("Bash failed: command=paw nope | error=invalid choice "
                    "fixed by: paw --help",
                    keywords=["type:execution"], pid="p103b"),
            recall_fn=lambda q: [],
        )
        self.assertEqual(d.op, "add")
        self.assertIn("-> use `paw --help`", d.content)

    def test_one_off_command_failure_without_fix_is_not_promoted(self) -> None:
        d = reconcile(
            pending("Bash failed: command=git commit | error=Exit code 128 "
                    "→ no in-session fix found",
            keywords=["type:execution"], pid="p104"),
            recall_fn=lambda q: [],
        )
        self.assertEqual(d.op, "skip")
        self.assertIn("no reusable fix", d.reason)

    def test_legacy_error_summary_with_fix_is_not_promoted_as_fake_command(self) -> None:
        d = reconcile(
            pending("shell_command failed: DB: C:\\Users\\x\\memories.db "
                    "→ fixed by: rg -n weight paw",
                    keywords=["type:execution"], pid="p105"),
            recall_fn=lambda q: [],
        )
        self.assertEqual(d.op, "skip")
        self.assertIn("no reusable fix", d.reason)


class CurateApplyTests(unittest.TestCase):
    def _runners(self):
        calls = {"store": [], "update": [], "forget": []}
        return calls, (
            lambda c: calls["store"].append(c) or 0,
            lambda c: calls["update"].append(c) or 0,
            lambda c: calls["forget"].append(c) or 0,
        )

    def test_add_stores_then_forgets(self) -> None:
        """Store succeeds and verification passes."""
        calls, (store, update, forget) = self._runners()
        with mock.patch("paw.curate._verify_visible", return_value=True):
            with mock.patch("paw.curate._verify_forget_drained", return_value=True):
                res = curate(
                    list_runner=lambda c: json.dumps([pending("brand new lesson xyz", keywords=["type:execution"])]),
                    recall_fn=lambda q: [],
                    store_runner=store, update_runner=update, forget_runner=forget,
                )
        self.assertEqual(res.applied, 1)
        self.assertEqual(res.counts["add"], 1)
        self.assertEqual(len(calls["store"]), 1)
        self.assertEqual(len(calls["forget"]), 1)
        self.assertEqual(len(calls["update"]), 0)

    def test_bump_updates_then_forgets(self) -> None:
        calls, (store, update, forget) = self._runners()
        existing = wiki("repeated lesson about token budget tool defs", keywords=["seen:1"], wid="w7")
        with mock.patch("paw.curate._verify_visible", return_value=True):
            with mock.patch("paw.curate._verify_forget_drained", return_value=True):
                res = curate(
                    list_runner=lambda c: json.dumps([pending("repeated lesson about token budget tool defs")]),
                    recall_fn=lambda q: [existing],
                    store_runner=store, update_runner=update, forget_runner=forget,
                )
        self.assertEqual(res.counts["bump"], 1)
        self.assertEqual(calls["update"][0][2], "w7")   # update <id>
        self.assertEqual(len(calls["forget"]), 1)

    def test_dry_run_writes_nothing(self) -> None:
        calls, (store, update, forget) = self._runners()
        res = curate(
            list_runner=lambda c: json.dumps([pending("anything at all here")]),
            recall_fn=lambda q: [],
            store_runner=store, update_runner=update, forget_runner=forget,
            write=False,
        )
        self.assertEqual(res.applied, 0)
        self.assertFalse(res.wrote)
        self.assertEqual(calls["store"], [])

    def test_store_failure_becomes_skip(self) -> None:
        calls, (_s, update, forget) = self._runners()
        res = curate(
            list_runner=lambda c: json.dumps([pending("doomed lesson")]),
            recall_fn=lambda q: [],
            store_runner=lambda c: 1,   # store fails
            update_runner=update, forget_runner=forget,
        )
        self.assertEqual(res.applied, 0)
        self.assertEqual(res.counts["skip"], 1)
        self.assertEqual(len(calls["forget"]), 0)   # not forgotten on failure

    def test_store_success_but_verification_fails(self) -> None:
        """REGRESSION: returncode 0 but memory not visible = skip, not applied."""
        calls, (store, update, forget) = self._runners()
        res = curate(
            list_runner=lambda c: json.dumps([pending("invisible lesson", keywords=["type:execution"])]),
            recall_fn=lambda q: [],
            store_runner=store, update_runner=update, forget_runner=forget,
        )
        self.assertEqual(res.applied, 0)                    # NOT applied
        self.assertEqual(res.counts["skip"], 1)
        self.assertEqual(len(calls["store"]), 1)             # store was called
        self.assertEqual(len(calls["forget"]), 0)            # NOT forgotten
        self.assertEqual(calls["store"][0][3], "mistakes")   # stored to mistakes topic

    def test_empty_pending(self) -> None:
        res = curate(list_runner=lambda c: "[]", recall_fn=lambda q: [])
        self.assertEqual(res.decisions, [])
        self.assertIn("empty", res.render())
        self.assertEqual(res.render(surface=True), "")

    def test_write_acquires_and_releases_curate_lock(self) -> None:
        calls, (store, update, forget) = self._runners()
        fake_mesh = mock.Mock()
        fake_mesh.acquire_lock.return_value = SimpleNamespace(status="success", locks=())

        with mock.patch("paw.curate.MemoryMesh", return_value=fake_mesh):
            with mock.patch("paw.curate._verify_visible", return_value=True):
                with mock.patch("paw.curate._verify_forget_drained", return_value=True):
                    res = curate(
                        list_runner=lambda c: json.dumps([pending("brand new locked lesson")]),
                        recall_fn=lambda q: [],
                        store_runner=store,
                        update_runner=update,
                        forget_runner=forget,
                    )

        self.assertEqual(res.applied, 1)
        self.assertTrue(res.wrote)
        fake_mesh.acquire_lock.assert_called_once()
        fake_mesh.release_lock.assert_called_once()
        self.assertEqual(len(calls["store"]), 1)
        self.assertEqual(len(calls["forget"]), 1)

    def test_write_is_blocked_when_another_host_holds_curate_lock(self) -> None:
        calls, (store, update, forget) = self._runners()
        fake_mesh = mock.Mock()
        fake_mesh.acquire_lock.return_value = SimpleNamespace(
            status="blocked",
            locks=(SimpleNamespace(owner="claude-code-1"),),
        )

        with mock.patch("paw.curate.MemoryMesh", return_value=fake_mesh):
            res = curate(
                list_runner=lambda c: json.dumps([pending("brand new blocked lesson")]),
                recall_fn=lambda q: [],
                store_runner=store,
                update_runner=update,
                forget_runner=forget,
            )

        self.assertEqual(res.applied, 0)
        self.assertFalse(res.wrote)
        self.assertIn("claude-code-1", res.reason)
        fake_mesh.acquire_lock.assert_called_once()
        fake_mesh.release_lock.assert_not_called()
        self.assertEqual(calls["store"], [])
        self.assertEqual(calls["forget"], [])

    def test_lock_can_be_opted_out_for_manual_single_host_curation(self) -> None:
        calls, (store, update, forget) = self._runners()

        with (
            mock.patch.dict(os.environ, {"PAW_CURATE_LOCK": "0"}),
            mock.patch("paw.curate.MemoryMesh") as mesh_cls,
            mock.patch("paw.curate._verify_visible", return_value=True),
            mock.patch("paw.curate._verify_forget_drained", return_value=True),
        ):
            res = curate(
                list_runner=lambda c: json.dumps([pending("brand new opt out lesson")]),
                recall_fn=lambda q: [],
                store_runner=store,
                update_runner=update,
                forget_runner=forget,
            )

        self.assertEqual(res.applied, 1)
        self.assertTrue(res.wrote)
        mesh_cls.assert_not_called()
        self.assertEqual(len(calls["store"]), 1)
        self.assertEqual(len(calls["forget"]), 1)


class ApplyReceiptTests(unittest.TestCase):
    """Decision receipt tracks store/visible/forgotten state."""

    def test_receipt_defaults(self) -> None:
        r = ApplyReceipt()
        self.assertFalse(r.stored)
        self.assertFalse(r.visible)
        self.assertFalse(r.forgotten)
        self.assertEqual(r.reason, "")

    def test_receipt_stored_not_visible(self) -> None:
        r = ApplyReceipt(stored=True, visible=False,
                         reason="store verification failed")
        self.assertTrue(r.stored)
        self.assertFalse(r.visible)
        self.assertIn("failed", r.reason)

    def test_decision_serializes_receipt(self) -> None:
        d = Decision(
            pending_id="p1", op="add", content="test",
            importance="medium",
            receipt=ApplyReceipt(stored=True, visible=True, forgotten=True, reason="ok"),
        )
        dd = d.to_dict()
        self.assertIn("receipt", dd)
        self.assertTrue(dd["receipt"]["visible"])


class VerifyVisibleTests(unittest.TestCase):
    def test_visible_when_wiki_has_matching_content(self) -> None:
        d = Decision(pending_id="p1", op="add", content="test lesson content",
                     importance="medium")
        runner = lambda c: json.dumps([
            {"id": "w1", "summary": "test lesson content", "topic": "mistakes",
             "importance": "medium", "keywords": []}
        ])
        self.assertTrue(_verify_visible(runner, d))

    def test_not_visible_when_wiki_has_no_match(self) -> None:
        d = Decision(pending_id="p1", op="add", content="totally different content",
                     importance="medium")
        runner = lambda c: json.dumps([
            {"id": "w1", "summary": "unrelated entry", "topic": "mistakes",
             "importance": "medium", "keywords": []}
        ])
        self.assertFalse(_verify_visible(runner, d))

    def test_visible_checks_target_id_for_bump(self) -> None:
        d = Decision(pending_id="p1", op="bump", content="updated content",
                     target_id="w99", importance="medium")
        runner = lambda c: json.dumps([
            {"id": "w99", "summary": "updated content", "topic": "mistakes",
             "importance": "high", "keywords": ["seen:2"]}
        ])
        self.assertTrue(_verify_visible(runner, d))

    def test_not_visible_on_bump_with_wrong_id(self) -> None:
        d = Decision(pending_id="p1", op="bump", content="updated content",
                     target_id="w99", importance="medium")
        runner = lambda c: json.dumps([
            {"id": "w55", "summary": "updated content", "topic": "mistakes",
             "importance": "high", "keywords": ["seen:2"]}
        ])
        self.assertFalse(_verify_visible(runner, d))

    def test_not_visible_on_empty_wiki(self) -> None:
        d = Decision(pending_id="p1", op="add", content="test", importance="medium")
        self.assertFalse(_verify_visible(lambda c: "[]", d))


class VerifyForgetDrainedTests(unittest.TestCase):
    def test_drained_when_pending_id_absent(self) -> None:
        runner = lambda c: json.dumps([
            {"id": "p2", "summary": "other", "topic": "pending"}
        ])
        self.assertTrue(_verify_forget_drained("p1", runner))

    def test_not_drained_when_pending_id_still_present(self) -> None:
        runner = lambda c: json.dumps([
            {"id": "p1", "summary": "test", "topic": "pending"},
            {"id": "p2", "summary": "other", "topic": "pending"},
        ])
        self.assertFalse(_verify_forget_drained("p1", runner))

    def test_drained_on_healthy_empty_pending(self) -> None:
        """Empty JSON array from healthy ICM = entry is drained."""
        self.assertTrue(_verify_forget_drained("p1", lambda c: "[]"))

    def test_not_drained_on_bad_json(self) -> None:
        """Bad JSON means ICM unreadable — NOT drained."""
        self.assertFalse(_verify_forget_drained("p1", lambda c: "not json"))


class ListTopicTests(unittest.TestCase):
    def test_parses_json_list(self) -> None:
        entries = list_topic("mistakes", runner=lambda c: json.dumps([{"id": "w1"}]))
        self.assertEqual(len(entries), 1)

    def test_bad_json_is_silent(self) -> None:
        self.assertEqual(list_topic("mistakes", runner=lambda c: "bad"), [])

    def test_filters_non_dict(self) -> None:
        entries = list_topic("mistakes", runner=lambda c: json.dumps([42, {"id": "w1"}]))
        self.assertEqual(len(entries), 1)


class ListPendingTests(unittest.TestCase):
    def test_parses_runner_json(self) -> None:
        out = list_pending(runner=lambda c: json.dumps([pending("x"), {"bad": 1}]))
        self.assertEqual(len(out), 2)

    def test_bad_json_is_silent(self) -> None:
        self.assertEqual(list_pending(runner=lambda c: "not json"), [])

    def test_pending_count_uses_list_pending_and_fails_closed(self) -> None:
        self.assertEqual(
            pending_count(runner=lambda c: json.dumps([pending("a"), pending("b")])),
            2,
        )
        self.assertEqual(pending_count(runner=lambda c: "not json"), 0)


if __name__ == "__main__":
    unittest.main()
