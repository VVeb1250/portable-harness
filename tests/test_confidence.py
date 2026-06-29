"""Tests for confidence field end-to-end: reflection encode → curate bump → recall parse."""
from __future__ import annotations

import unittest

from paw.curate import _bump_confidence, _bump_keywords, _conf_of
from paw.reflection import Candidate
from paw.recall import _confidence_of


class CandidateDefaultsTests(unittest.TestCase):
    def test_default_confidence_is_0_5(self) -> None:
        # a Candidate constructed without confidence defaults to mid
        c = Candidate(type="execution", signal="is_error", trigger="x", detail="y")
        self.assertAlmostEqual(c.confidence, 0.5)


class ConfidenceParseTests(unittest.TestCase):
    def test_conf_of_from_keywords(self) -> None:
        self.assertAlmostEqual(_conf_of(["type:execution", "conf:0.85", "seen:1"]), 0.85)

    def test_conf_of_missing_returns_none(self) -> None:
        self.assertIsNone(_conf_of(["type:execution", "seen:1"]))
        self.assertIsNone(_conf_of(None))

    def test_conf_of_garbage_returns_none(self) -> None:
        self.assertIsNone(_conf_of(["conf:not-a-number"]))

    def test_recall_confidence_of_dict_list_keywords(self) -> None:
        m = {"summary": "x", "keywords": ["type:execution", "conf:0.7"]}
        self.assertAlmostEqual(_confidence_of(m), 0.7)

    def test_recall_confidence_of_dict_string_keywords(self) -> None:
        m = {"summary": "x", "keywords": "type:execution,conf:0.7"}
        self.assertAlmostEqual(_confidence_of(m), 0.7)

    def test_recall_confidence_none_for_legacy(self) -> None:
        self.assertIsNone(_confidence_of({"summary": "x", "keywords": ["seen:2"]}))
        self.assertIsNone(_confidence_of({"summary": "x"}))


class ConfidenceBumpTests(unittest.TestCase):
    def test_bump_increases_with_seen(self) -> None:
        kws = ["type:silent-bug", "conf:0.45", "seen:1"]
        # seen=2 → 0.45 + 0.1 = 0.55
        self.assertAlmostEqual(_bump_confidence(kws, 2), 0.55)
        # seen=3 → 0.45 + 0.2 = 0.65
        self.assertAlmostEqual(_bump_confidence(kws, 3), 0.65)

    def test_bump_caps_at_1(self) -> None:
        kws = ["conf:0.9", "seen:5"]
        # 0.9 + 0.1*4 = 1.3 → capped 1.0
        self.assertAlmostEqual(_bump_confidence(kws, 5), 1.0)

    def test_bump_legacy_defaults_to_0_5(self) -> None:
        kws = ["type:execution", "seen:1"]  # no conf
        # 0.5 + 0.1*(2-1) = 0.6
        self.assertAlmostEqual(_bump_confidence(kws, 2), 0.6)

    def test_bump_keywords_replaces_seen_and_conf(self) -> None:
        kws = ["type:execution", "conf:0.7", "seen:1", "term:foo"]
        out = _bump_keywords(kws, 3)
        # exactly one seen and one conf
        self.assertEqual([k for k in out if k.startswith("seen:")], ["seen:3"])
        self.assertEqual(len([k for k in out if k.startswith("conf:")]), 1)
        # non-conf/non-seen keywords preserved
        self.assertIn("type:execution", out)
        self.assertIn("term:foo", out)
        # old conf stripped, new conf present
        self.assertNotIn("conf:0.7", out)


if __name__ == "__main__":
    unittest.main()
