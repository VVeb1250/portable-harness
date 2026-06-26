from __future__ import annotations

import json
import unittest

from paw.router_block import match_sets, paw_block


class SetMatchingTests(unittest.TestCase):
    def test_security_prompt_matches_secure_agent(self) -> None:
        names = {s.name for s, _ in match_sets("how do I stop a leaked api key / secret")}
        self.assertIn("secure-agent", names)

    def test_unrelated_prompt_matches_nothing(self) -> None:
        self.assertEqual(match_sets("the weather is nice today friend"), [])

    def test_scores_are_above_floor(self) -> None:
        hits = match_sets("query a csv file with sql, structured data")
        self.assertTrue(all(score >= 2.0 for _, score in hits))


class PawBlockTests(unittest.TestCase):
    def test_short_prompt_is_silent(self) -> None:
        self.assertEqual(paw_block("hi"), "")

    def test_sets_block_uses_apply_verb(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
