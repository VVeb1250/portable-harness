from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from paw.memory_governance import (
    build_proposals,
    load_proposals,
    record_observation,
    run_governance,
)


class MemoryGovernanceTests(unittest.TestCase):
    def test_record_observation_counts_misses(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            obs1 = record_observation(
                "command not found|python",
                lesson_id="lesson-1",
                root=root,
                today="2026-06-29",
            )
            obs2 = record_observation(
                "command not found|python",
                lesson_id="lesson-1",
                root=root,
                today="2026-06-30",
            )
        self.assertEqual(obs1.count, 1)
        self.assertEqual(obs2.count, 2)
        self.assertEqual(obs2.linked_at_count, 1)
        self.assertEqual(obs2.post_link_misses, 1)

    def test_build_proposal_after_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for _ in range(4):
                record_observation("command not found|python", lesson_id="lesson-1", root=root)
            result = run_governance(root=root, threshold=3, today="2026-07-01")
            proposals = load_proposals(root)
        self.assertEqual(len(result.created), 1)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].target_id, "lesson-1")
        self.assertEqual(proposals[0].action, "rewrite")
        self.assertEqual(proposals[0].evidence["post_link_misses"], 3)

    def test_existing_pending_proposal_is_not_duplicated(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for _ in range(4):
                record_observation("permission denied|python", lesson_id="lesson-2", root=root)
            first = run_governance(root=root, threshold=3)
            second = run_governance(root=root, threshold=3)
        self.assertEqual(len(first.created), 1)
        self.assertEqual(second.created, [])

    def test_unlinked_observation_does_not_create_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for _ in range(5):
                record_observation("random failure", root=root)
            result = run_governance(root=root, threshold=1)
        self.assertEqual(result.created, [])

    def test_build_proposals_is_pure(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for _ in range(4):
                record_observation("again", lesson_id="lesson-3", root=root)
            observations = run_governance(root=root, threshold=99, write=False).observations
            proposals = build_proposals(observations, threshold=3, today="2026-07-02")
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].created, "2026-07-02")


if __name__ == "__main__":
    unittest.main()
