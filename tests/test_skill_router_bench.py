from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from bench.skill_router.runner import (
    ARMS,
    build_manifest,
    evaluate_predictions,
    expand_cohort,
    load_cohort,
    token_count,
)


class SkillRouterBenchTests(unittest.TestCase):
    def test_frozen_cohort_expands_to_180_balanced_queries(self) -> None:
        source = load_cohort(
            Path("bench/skill_router/cohort_2026-06-26.json")
        )
        cases = expand_cohort(source)

        self.assertEqual(len(source["languages"]), 12)
        self.assertEqual(len(cases), 180)
        self.assertEqual(
            {case.language for case in cases},
            set(source["languages"]),
        )
        for language in source["languages"]:
            per_language = [
                case for case in cases if case.language == language
            ]
            self.assertEqual(len(per_language), 15)
            self.assertEqual(
                sum(bool(case.required_skills) for case in per_language),
                10,
            )
            self.assertEqual(
                sum(not case.required_skills for case in per_language),
                5,
            )

    def test_metrics_cover_recall_precision_mrr_silence_and_context(self) -> None:
        predictions = [
            {
                "required": ["alpha"],
                "predicted": ["alpha", "beta"],
                "context_tokens": 20,
                "latency_ms": 10.0,
                "language": "en",
            },
            {
                "required": [],
                "predicted": [],
                "context_tokens": 4,
                "latency_ms": 5.0,
                "language": "en",
            },
        ]

        metrics = evaluate_predictions(predictions)

        self.assertEqual(metrics["cases"], 2)
        self.assertEqual(metrics["positive_cases"], 1)
        self.assertEqual(metrics["silence_cases"], 1)
        self.assertEqual(metrics["recall_at_k"], 1.0)
        self.assertEqual(metrics["full_coverage"], 1.0)
        self.assertEqual(metrics["mrr"], 1.0)
        self.assertEqual(metrics["silence_accuracy"], 1.0)
        self.assertEqual(metrics["precision_at_k"], 0.5)
        self.assertEqual(metrics["mean_context_tokens"], 12.0)

    def test_manifest_hashes_inputs_and_names_all_arms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cohort = Path(directory) / "cohort.json"
            graph = Path(directory) / "graph.json"
            cohort.write_text('{"languages":[],"intents":[]}', encoding="utf-8")
            graph.write_text('{"nodes":[],"edges":[]}', encoding="utf-8")

            manifest = build_manifest(
                cohort_path=cohort,
                graph_path=graph,
                catalog_hash="catalog-sha",
                case_count=180,
            )

        self.assertEqual(set(manifest["arms"]), set(ARMS))
        self.assertEqual(manifest["case_count"], 180)
        self.assertEqual(len(manifest["cohort_sha256"]), 64)
        self.assertEqual(len(manifest["graph_sha256"]), 64)
        self.assertEqual(manifest["catalog_sha256"], "catalog-sha")
        json.dumps(manifest)

    def test_token_counter_is_deterministic_and_nonzero(self) -> None:
        text = "skill: agent-harness-construction\nreason: agent routing"

        first = token_count(text)
        second = token_count(text)

        self.assertEqual(first, second)
        self.assertGreater(first, 0)


if __name__ == "__main__":
    unittest.main()
