from __future__ import annotations

import json
import unittest

from paw.curate import (
    Decision,
    _bump_keywords,
    _escalate,
    _jaccard,
    _seen_of,
    curate,
    list_pending,
    reconcile,
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
        # a recall hit that is itself pending must not be treated as the wiki dup
        other_pending = {"id": "p2", "summary": "use py launcher not python on windows",
                         "topic": "pending", "keywords": []}
        d = reconcile(
            pending("use py launcher not python on windows", keywords=["type:execution"]),
            recall_fn=lambda q: [other_pending],
        )
        self.assertEqual(d.op, "add")


class CurateApplyTests(unittest.TestCase):
    def _runners(self):
        calls = {"store": [], "update": [], "forget": []}
        return calls, (
            lambda c: calls["store"].append(c) or 0,
            lambda c: calls["update"].append(c) or 0,
            lambda c: calls["forget"].append(c) or 0,
        )

    def test_add_stores_then_forgets(self) -> None:
        calls, (store, update, forget) = self._runners()
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

    def test_empty_pending(self) -> None:
        res = curate(list_runner=lambda c: "[]", recall_fn=lambda q: [])
        self.assertEqual(res.decisions, [])
        self.assertIn("empty", res.render())
        self.assertEqual(res.render(surface=True), "")


class ListPendingTests(unittest.TestCase):
    def test_parses_runner_json(self) -> None:
        out = list_pending(runner=lambda c: json.dumps([pending("x"), {"bad": 1}]))
        self.assertEqual(len(out), 2)

    def test_bad_json_is_silent(self) -> None:
        self.assertEqual(list_pending(runner=lambda c: "not json"), [])


if __name__ == "__main__":
    unittest.main()
