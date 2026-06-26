"""Lock the paraphrase-fair scoring + the deterministic heuristic arm of the
reflection A/B bench. The DeepSeek arm needs the network and is not unit-tested."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bench import _reflection_ab as ab  # noqa: E402


class ScoreTests(unittest.TestCase):
    def test_perfect(self) -> None:
        s = ab.score(["py -m paw bogis failed", "assertion error", "wrong approach", "flaky test"])
        self.assertEqual((s["precision"], s["recall"]), (1.0, 1.0))

    def test_paraphrase_is_fair(self) -> None:
        # natural substrings survive an LLM rewrite that drops verbatim noise
        s = ab.score([
            "Typo in command py -m paw bogis",
            "Test failure: assertion expected 3 got 4",
            "user said wrong approach to the change",
            "Flaky timing assertion in test_foo",
        ])
        self.assertEqual(s["recall"], 1.0)
        self.assertEqual(s["fp"], 0)

    def test_distractor_leak_is_false_positive(self) -> None:
        s = ab.score(["assistant could not proceed, permission denied"])  # NEG 'proceed'
        self.assertEqual(s["fp"], 1)
        self.assertEqual(s["tp"], 0)

    def test_spurious_capture_is_false_positive(self) -> None:
        s = ab.score(["some unrelated chatter with no marker"])
        self.assertEqual(s["fp"], 1)

    def test_partial_recall(self) -> None:
        s = ab.score(["py -m paw bogis"])  # 1 of 4 POS
        self.assertEqual(s["recall"], 0.25)
        self.assertEqual(s["precision"], 1.0)


class HeuristicArmTests(unittest.TestCase):
    def test_deterministic_profile(self) -> None:
        # heuristic catches the explicit signals, is blind to the silent bug
        s, detail = ab.arm_heuristic(ab.gold_transcript())
        self.assertEqual(s["precision"], 1.0)
        self.assertEqual(s["recall"], 0.75)            # misses the is_error=False failure
        self.assertEqual(s["llm_in_tok"], 0)
        self.assertEqual(s["usd"], 0.0)
        blob = " ".join(detail["candidates"]).lower()
        self.assertNotIn("flaky", blob)               # the silent bug it cannot see


if __name__ == "__main__":
    unittest.main()
