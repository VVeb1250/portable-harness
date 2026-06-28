from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import paw.router_block as rb
from paw.surface_context import build_surface_context, infer_intents
from paw.router_block import match_sets, paw_block, set_adoption_posture, set_routing
from paw.linker import apply_plan, build_plan
from paw.sets.loader import get_set


class SetMatchingTests(unittest.TestCase):
    def test_security_prompt_matches_secure_agent(self) -> None:
        names = {s.name for s, _ in match_sets("how do I stop a leaked api key / secret")}
        self.assertIn("secure-agent", names)

    def test_memory_prompt_matches_local_memory(self) -> None:
        names = {s.name for s, _ in match_sets("what did we decide about bundle init memory")}
        self.assertIn("local-memory", names)

    def test_dev_prompt_splits_efficiency_from_code_intelligence(self) -> None:
        codemod_names = {s.name for s, _ in match_sets("rename across files with ast codemod")}
        caller_names = {s.name for s, _ in match_sets("find all callers and impact of estimate_cost")}

        self.assertIn("efficiency-min", codemod_names)
        self.assertIn("code-intelligence", caller_names)
        self.assertNotIn("efficiency-starter", codemod_names | caller_names)

    def test_unrelated_prompt_matches_nothing(self) -> None:
        self.assertEqual(match_sets("the weather is nice today friend"), [])

    def test_scores_are_above_floor(self) -> None:
        hits = match_sets("query a csv file with sql, structured data")
        self.assertTrue(all(score >= 2.0 for _, score in hits))

    def test_word_boundaries_prevent_code_identifier_false_positives(self) -> None:
        surface_names = {s.name for s, _ in match_sets("find where SurfaceDecision is defined")}
        caller_names = {
            s.name for s, _ in match_sets("find all callers of build_plan and impact")
        }
        browser_names = {
            s.name
            for s, _ in match_sets(
                "open a browser, fill the login form, click submit, and verify the dashboard"
            )
        }

        self.assertNotIn("local-memory", surface_names)
        self.assertNotIn("design-quality", caller_names)
        self.assertNotIn("doc-data-min", browser_names)

    def test_context_intent_boosts_specific_optional_sets(self) -> None:
        handoff = build_surface_context(
            "package the current git diff and relevant repo context",
            intent="repo handoff",
            phase="handoff",
        )
        affected = build_surface_context(
            "run only tests for this change",
            changed_files=("paw/router_block.py",),
        )

        self.assertEqual(match_sets(handoff.task, context=handoff)[0][0].name, "repo-pack")
        self.assertIn("affected_tests", infer_intents(affected))
        self.assertIn(
            "test-affected",
            {s.name for s, _ in match_sets(affected.task, context=affected)},
        )


class PawBlockTests(unittest.TestCase):
    def test_short_prompt_is_silent(self) -> None:
        self.assertEqual(paw_block("hi"), "")

    def test_sets_block_uses_apply_verb(self) -> None:
        with mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "absent"):
            block = paw_block(
                "review for secret credential and api key leaks", recall_runner=lambda p: "[]"
            )
        self.assertIn("🐾 paw sets:", block)
        self.assertIn("paw apply secure-agent", block)

    def test_silent_when_no_set_and_no_memory(self) -> None:
        block = paw_block("the weather is nice today", recall_runner=lambda p: "[]")
        self.assertEqual(block, "")

    def test_memory_surfaces_on_keyword_overlap_and_importance(self) -> None:
        canned = json.dumps([
            {"importance": "high", "summary": "docker stale socket fix",
             "keywords": ["docker", "socket"]},
            {"importance": "low", "summary": "ignored low importance",
             "keywords": ["docker"]},
        ])
        block = paw_block("my docker daemon won't boot", recall_runner=lambda p: canned)
        self.assertIn("🧠 paw memory", block)
        self.assertIn("docker stale socket fix", block)
        self.assertNotIn("ignored low importance", block)  # importance filtered

    def test_memory_silent_without_keyword_overlap(self) -> None:
        canned = json.dumps([
            {"importance": "critical", "summary": "unrelated lesson",
             "keywords": ["kubernetes", "helm"]},
        ])
        block = paw_block("writing a python parser", recall_runner=lambda p: canned)
        self.assertNotIn("🧠 paw memory", block)

    def test_recall_failure_is_silent_not_fatal(self) -> None:
        def boom(_p):
            raise RuntimeError("icm down")

        # set still surfaces; memory simply absent; no exception escapes
        block = paw_block("query a csv with sql structured data", recall_runner=boom)
        self.assertNotIn("🧠", block)

    def test_host_scoped_ledger_makes_foundation_set_live(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ctx = root / "AGENTS.md"
            ctx.write_text("# project\n", encoding="utf-8")
            apply_plan(
                build_plan("efficiency-min", host="codex", context=str(ctx), root=root),
                root=root,
            )
            with (
                mock.patch("paw.linker.resolve_binary", lambda b, root: (b, "path")),
                mock.patch.object(rb, "_PATH_PROBE", lambda b: "/usr/bin/" + b),
            ):
                block = paw_block(
                    "rename across files with ast codemod",
                    cwd=str(root),
                    recall_runner=lambda p: "[]",
                )

        self.assertIn("efficiency-min (live)", block)
        self.assertNotIn("paw apply efficiency-min", block)


class SetRoutingTests(unittest.TestCase):
    """Router pushes concrete rungs only after the relevant set is live."""

    def setUp(self) -> None:
        self.eff = get_set("efficiency-min")
        self.code = get_set("code-intelligence")

    def test_path_alone_does_not_make_set_live(self) -> None:
        with (
            mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "absent"),
            mock.patch.object(rb, "_PATH_PROBE", lambda b: "/usr/bin/" + b),
        ):
            self.assertIsNone(set_routing(self.code, "find all callers of estimate_cost"))

    def test_linked_healthy_set_routes_to_codegraph_for_callers(self) -> None:
        with (
            mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "healthy"),
            mock.patch.object(rb, "_PATH_PROBE", lambda b: "/usr/bin/" + b),
        ):
            hits = set_routing(self.code, "find all callers of estimate_cost")
        self.assertTrue(any("codegraph" in h for h in hits))
        self.assertFalse(any("ast-grep run" in h for h in hits))

    def test_linked_healthy_set_routes_to_astgrep_for_codemod(self) -> None:
        with (
            mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "healthy"),
            mock.patch.object(rb, "_PATH_PROBE", lambda b: "/usr/bin/" + b),
        ):
            hits = set_routing(self.eff, "rename across files with a structural codemod")
        self.assertTrue(any("ast-grep" in h for h in hits))

    def test_only_installed_rung_surfaces(self) -> None:
        # ast-grep present, codegraph missing -> a callers prompt yields no rung
        probe = lambda b: "/usr/bin/ast-grep" if b == "ast-grep" else None
        with (
            mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "healthy"),
            mock.patch.object(rb, "_PATH_PROBE", probe),
        ):
            hits = set_routing(self.code, "find all callers of estimate_cost")
        self.assertEqual(hits, [])  # codegraph rung filtered, but set is healthy -> no use hint

    def test_no_rung_installed_returns_none_for_apply_fallback(self) -> None:
        with mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "absent"):
            self.assertIsNone(set_routing(self.code, "find all callers"))

    def test_set_without_routing_returns_none(self) -> None:
        with mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "absent"):
            self.assertIsNone(set_routing(get_set("secure-agent"), "secret api key leak"))

    def test_paw_block_pushes_use_not_apply_when_live(self) -> None:
        with (
            mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "healthy"),
            mock.patch.object(rb, "_PATH_PROBE", lambda b: "/usr/bin/" + b),
        ):
            block = paw_block(
                "find all callers of estimate_cost then rename across files",
                recall_runner=lambda p: "[]",
            )
        self.assertIn("code-intelligence (live)", block)
        self.assertIn("efficiency-min (live)", block)
        self.assertIn("codegraph", block)
        self.assertNotIn("paw apply efficiency-min", block)
        self.assertNotIn("paw apply code-intelligence", block)

    def test_paw_block_pushes_verify_when_linked_but_unhealthy(self) -> None:
        with mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "drifted"):
            block = paw_block(
                "find all callers of estimate_cost", recall_runner=lambda p: "[]"
            )
        self.assertIn("code-intelligence (drifted)", block)
        self.assertIn("paw verify code-intelligence", block)
        self.assertNotIn("paw apply code-intelligence", block)
        self.assertNotIn("→ use:", block)

    def test_paw_block_routes_conditional_project_set_to_plan(self) -> None:
        with mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "absent"):
            block = paw_block(
                "find all callers of estimate_cost", recall_runner=lambda p: "[]"
            )
        self.assertIn("paw plan code-intelligence (conditional)", block)
        self.assertNotIn("paw apply code-intelligence", block)

    def test_conditional_set_routes_to_plan_before_apply(self) -> None:
        with mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "absent"):
            block = paw_block(
                "search indexed content from a huge log after compaction",
                recall_runner=lambda p: "[]",
            )
        self.assertIn("context-workbench", block)
        self.assertIn("paw plan context-workbench (conditional)", block)
        self.assertNotIn("paw apply context-workbench", block)

    def test_ready_non_default_set_routes_to_task_specific_plan(self) -> None:
        with mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "absent"):
            block = paw_block(
                "package the current git diff and relevant repo context",
                recall_runner=lambda p: "[]",
            )
        self.assertIn("repo-pack", block)
        self.assertIn("paw plan repo-pack (task-specific)", block)
        self.assertNotIn("paw apply repo-pack", block)

    def test_adoption_posture_distinguishes_default_from_task_specific(self) -> None:
        self.assertEqual(set_adoption_posture(get_set("efficiency-min")), "default")
        self.assertEqual(set_adoption_posture(get_set("repo-pack")), "task-specific")
        self.assertEqual(set_adoption_posture(get_set("context-workbench")), "conditional")


class OutcomeLoopTests(unittest.TestCase):
    """Router demotes sets the user keeps ignoring (loop closure at match_sets).

    Uses the _OUTCOMES_PROBE seam so these assertions never touch the real
    ~/.paw ledger — match_sets is called by every prompt, so polluting it would
    silently change real routing for every other test.
    """

    def setUp(self) -> None:
        self._saved_probe = rb._OUTCOMES_PROBE

    def tearDown(self) -> None:
        rb._OUTCOMES_PROBE = self._saved_probe

    def test_demoted_set_is_filtered_from_match_sets(self) -> None:
        logged: list[list[str]] = []
        rb._OUTCOMES_PROBE = ({"secure-agent"}, lambda names: logged.append(names))
        names = {s.name for s, _ in match_sets("how do I stop a leaked api key / secret")}
        self.assertNotIn("secure-agent", names)

    def test_used_set_is_not_demoted(self) -> None:
        # empty demoted set → secure-agent (which the prompt matches) still surfaces
        rb._OUTCOMES_PROBE = (set(), lambda _names: None)
        names = {s.name for s, _ in match_sets("how do I stop a leaked api key / secret")}
        self.assertIn("secure-agent", names)

    def test_match_sets_logs_suggestion(self) -> None:
        """A surfaced set gets its suggestion counter bumped."""
        logged: list[list[str]] = []
        rb._OUTCOMES_PROBE = (set(), lambda names: logged.append(names))
        list(match_sets("how do I stop a leaked api key / secret"))
        self.assertTrue(logged)  # mark_suggested was called
        self.assertTrue(any("secure-agent" in batch for batch in logged))

    def test_demoted_set_not_counted_as_suggestion(self) -> None:
        """Filtering happens BEFORE logging — a demoted set is never suggested."""
        logged: list[list[str]] = []
        rb._OUTCOMES_PROBE = ({"secure-agent"}, lambda names: logged.append(names))
        list(match_sets("how do I stop a leaked api key / secret"))
        for batch in logged:
            self.assertNotIn("secure-agent", batch)


class SessionDedupTests(unittest.TestCase):
    """A lesson already injected in a session doesn't re-inject (loop closure)."""

    def test_lesson_injects_first_time(self) -> None:
        canned = json.dumps([{
            "id": "mem-1", "summary": "use py launcher on windows",
            "importance": "high", "topic": "mistakes", "keywords": ["py", "windows"],
        }])
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                with mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "absent"):
                    block = paw_block(
                        "python windows launcher",
                        session_id="sess-unique-1",
                        recall_runner=lambda p: canned,
                    )
        self.assertIn("use py launcher", block)

    def test_same_lesson_not_re_injected_same_session(self) -> None:
        canned = json.dumps([{
            "id": "mem-1", "summary": "use py launcher on windows",
            "importance": "high", "topic": "mistakes", "keywords": ["py", "windows"],
        }])
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                with mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "absent"):
                    first = paw_block(
                        "python windows launcher", session_id="sess-x",
                        recall_runner=lambda p: canned,
                    )
                    second = paw_block(
                        "python windows launcher", session_id="sess-x",
                        recall_runner=lambda p: canned,
                    )
        self.assertIn("use py launcher", first)
        self.assertNotIn("use py launcher", second)  # deduped within session

    def test_different_session_re_injects(self) -> None:
        canned = json.dumps([{
            "id": "mem-1", "summary": "use py launcher on windows",
            "importance": "high", "topic": "mistakes", "keywords": ["py", "windows"],
        }])
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"PAW_HOME": d}):
                with mock.patch.object(rb, "_LINK_STATE_PROBE", lambda s, cwd: "absent"):
                    paw_block("python windows", session_id="sess-a",
                              recall_runner=lambda p: canned)
                    block_b = paw_block("python windows", session_id="sess-b",
                                        recall_runner=lambda p: canned)
        self.assertIn("use py launcher", block_b)  # different session → re-injects


if __name__ == "__main__":
    unittest.main()
