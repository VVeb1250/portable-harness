from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Sequence
from unittest.mock import patch

from paw.semantic_router import default_semantic_scorer
from paw.skill_graph import SkillGraph, load_skill_graph
from paw.skill_router import (
    SkillRecord,
    build_task_capsule,
    discover_skills,
    suggest_skill,
)


def _skill(
    name: str,
    description: str,
    *,
    path: str | None = None,
    routing_text: str = "",
    requires_evidence: tuple[str, ...] = (),
    substitute_group: str | None = None,
) -> SkillRecord:
    return SkillRecord(
        name=name,
        description=description,
        path=path or f"/skills/{name}/SKILL.md",
        routing_text=routing_text or f"{name}. {description}",
        requires_evidence=requires_evidence,
        substitute_group=substitute_group,
    )


class TaskCapsuleTests(unittest.TestCase):
    def test_capsule_keeps_bounded_goal_without_requiring_translation_rules(self) -> None:
        capsule = build_task_capsule(
            "日本語でエージェントのスキルルーターを設計する"
        )

        self.assertEqual(
            capsule.goal,
            "日本語でエージェントのスキルルーターを設計する",
        )
        self.assertLessEqual(len(capsule.goal), 240)


class SkillSuggestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skills = (
            _skill(
                "agent-harness-construction",
                (
                    "Design and optimize AI agent action spaces, tool definitions, "
                    "observation formatting, routing, and context budgets."
                ),
            ),
            _skill(
                "design-quality",
                "Review user interfaces for visual quality and design fidelity.",
            ),
            _skill(
                "security-review",
                "Review authentication, secrets, permissions, and vulnerable code.",
            ),
            _skill(
                "tdd-workflow",
                "Implement features and fixes with tests first and verify coverage.",
            ),
            _skill(
                "write-a-skill",
                (
                    "Create new agent skills with proper structure, progressive "
                    "disclosure, and bundled resources."
                ),
            ),
            _skill(
                "deploy-model",
                (
                    "Deploy Azure OpenAI models with intelligent intent-based "
                    "routing, capacity discovery, agent creation, and MCP tool "
                    "configuration."
                ),
            ),
            _skill(
                "django-security",
                "Django authentication, authorization, CSRF, and input security.",
                requires_evidence=("django",),
                substitute_group="framework-security",
            ),
            _skill(
                "quarkus-security",
                "Quarkus authentication, authorization, OIDC, and JWT security.",
                requires_evidence=("quarkus",),
                substitute_group="framework-security",
            ),
        )

    @staticmethod
    def semantic_scores(
        task: str,
        skills: Sequence[SkillRecord],
    ) -> dict[str, float]:
        text = task.casefold()
        scores = {skill.name: 0.10 for skill in skills}
        if "router" in text or "routing" in text:
            scores["agent-harness-construction"] = 0.91
        if "authentication" in text:
            scores["security-review"] = 0.86
            if "django" in text:
                scores["django-security"] = 0.93
            if "quarkus" in text:
                scores["quarkus-security"] = 0.93
        if "test" in text or "coverage" in text:
            scores["tdd-workflow"] = 0.88
        return scores

    def test_clear_match_pushes_skill_ids_without_skill_bodies(self) -> None:
        result = suggest_skill(
            "Make the PUSH skill router smarter and reduce context use.",
            self.skills,
            semantic_scorer=self.semantic_scores,
            reranker=self.semantic_scores,
        )

        self.assertEqual(result.status, "suggested")
        self.assertEqual(result.mode, "shadow")
        self.assertEqual(result.match, "clear")
        self.assertEqual(
            tuple(item.skill for item in result.suggestions),
            ("agent-harness-construction",),
        )
        self.assertEqual(result.suggestions[0].action, "load_skill")
        self.assertIn("relevance", result.suggestions[0].reason)
        self.assertNotIn(
            "agent action spaces",
            json.dumps(result.to_dict()).casefold(),
        )

    def test_complementary_clear_matches_can_push_two_skills(self) -> None:
        result = suggest_skill(
            "Implement authentication safely using tests first and check coverage.",
            self.skills,
            semantic_scorer=self.semantic_scores,
            reranker=self.semantic_scores,
        )

        self.assertEqual(
            {item.skill for item in result.suggestions},
            {"security-review", "tdd-workflow"},
        )
        self.assertLessEqual(len(result.suggestions), 2)

    def test_framework_skill_requires_catalog_evidence_not_router_hard_code(
        self,
    ) -> None:
        generic = suggest_skill(
            "Implement authentication safely.",
            self.skills,
            semantic_scorer=self.semantic_scores,
            reranker=self.semantic_scores,
        )
        django = suggest_skill(
            "Implement authentication safely in Django.",
            self.skills,
            semantic_scorer=self.semantic_scores,
            reranker=self.semantic_scores,
        )

        self.assertNotIn(
            "django-security",
            {item.skill for item in generic.suggestions},
        )
        self.assertIn(
            "django-security",
            {item.skill for item in django.suggestions},
        )

    def test_generic_design_word_does_not_trigger_ui_skill(self) -> None:
        result = suggest_skill(
            "Design a smarter agent router for skill selection.",
            self.skills,
            semantic_scorer=self.semantic_scores,
            reranker=self.semantic_scores,
        )

        self.assertEqual(result.suggestions[0].skill, "agent-harness-construction")
        self.assertNotIn(
            "write-a-skill",
            {item.skill for item in result.suggestions},
        )
        self.assertNotIn(
            "deploy-model",
            {item.skill for item in result.suggestions},
        )

    def test_weak_match_stays_silent(self) -> None:
        result = suggest_skill("ช่วยสรุปประชุมเมื่อวานให้หน่อย", self.skills)

        self.assertEqual(result.status, "silent")
        self.assertEqual(result.match, "none")
        self.assertEqual(result.suggestions, ())

    def test_ambiguous_top_candidates_stay_silent(self) -> None:
        tied = (
            _skill("alpha", "Analyze Python application performance."),
            _skill("beta", "Analyze Python application performance."),
        )

        def tied_scores(
            task: str,
            skills: Sequence[SkillRecord],
        ) -> dict[str, float]:
            del task
            return {skill.name: 0.90 for skill in skills}

        result = suggest_skill(
            "Analyze Python application performance.",
            tied,
            semantic_scorer=tied_scores,
            reranker=tied_scores,
        )

        self.assertEqual(result.suggestions, ())
        self.assertIn("ambiguous", result.reason)

    def test_active_skill_is_not_suggested_again(self) -> None:
        result = suggest_skill(
            "Design a smarter skill router with a smaller context budget.",
            self.skills,
            active_skills=("agent-harness-construction",),
            semantic_scorer=self.semantic_scores,
            reranker=self.semantic_scores,
        )

        self.assertNotIn(
            "agent-harness-construction",
            {item.skill for item in result.suggestions},
        )
        self.assertNotIn(
            "agent-harness-construction",
            {item.skill for item in result.candidates},
        )

    def test_multilingual_semantic_scorer_does_not_need_language_dictionaries(
        self,
    ) -> None:
        def semantic_scores(
            task: str,
            skills: Sequence[SkillRecord],
        ) -> dict[str, float]:
            del task
            return {
                skill.name: (
                    0.91 if skill.name == "agent-harness-construction" else 0.10
                )
                for skill in skills
            }

        tasks = (
            "ออกแบบเราเตอร์ที่เลือกทักษะให้เอเจนต์",
            "设计一个为智能代理选择技能的路由器",
            "エージェントのスキルを選ぶルーターを設計する",
            "Diseña un enrutador que seleccione habilidades para el agente",
        )
        for task in tasks:
            with self.subTest(task=task):
                result = suggest_skill(
                    task,
                    self.skills,
                    semantic_scorer=semantic_scores,
                )

                self.assertEqual(result.status, "candidates")
                self.assertIn(
                    "agent-harness-construction",
                    {item.skill for item in result.candidates},
                )

    def test_graph_intent_anchor_recovers_skill_from_noisy_direct_ranking(
        self,
    ) -> None:
        graph = SkillGraph.from_dict(
            {
                "nodes": [
                    {
                        "id": "intent:agent-routing",
                        "kind": "intent",
                        "text": (
                            "Design agent routing, action spaces, observation "
                            "formats, and context-efficient skill selection."
                        ),
                    }
                ],
                "edges": [
                    {
                        "from": "intent:agent-routing",
                        "to": "agent-harness-construction",
                        "relation": "routes_to",
                    }
                ],
            },
            self.skills,
        )

        def noisy_scores(
            task: str,
            records: Sequence[SkillRecord],
        ) -> dict[str, float]:
            del task
            return {
                record.name: {
                    "intent:agent-routing": 0.94,
                    "skill-creator": 0.91,
                    "write-a-skill": 0.88,
                    "agent-harness-construction": 0.41,
                }.get(record.name, 0.10)
                for record in records
            }

        result = suggest_skill(
            "设计一个为智能代理选择技能的路由器",
            self.skills,
            semantic_scorer=noisy_scores,
            graph=graph,
        )

        self.assertEqual(result.status, "candidates")
        self.assertIn(
            "agent-harness-construction",
            {item.skill for item in result.candidates},
        )

    def test_graph_collapses_substitutes_and_expands_complements(self) -> None:
        graph = SkillGraph.from_dict(
            {
                "nodes": [],
                "edges": [
                    {
                        "from": "security-review",
                        "to": "tdd-workflow",
                        "relation": "complements",
                    },
                    {
                        "from": "skill-creator",
                        "to": "write-a-skill",
                        "relation": "substitutes",
                    },
                ],
            },
            self.skills,
        )

        def scores(
            task: str,
            records: Sequence[SkillRecord],
        ) -> dict[str, float]:
            del task
            return {
                record.name: {
                    "security-review": 0.90,
                    "skill-creator": 0.84,
                    "write-a-skill": 0.82,
                    "tdd-workflow": 0.20,
                }.get(record.name, 0.10)
                for record in records
            }

        result = suggest_skill(
            "Implement authentication safely with regression tests.",
            self.skills,
            semantic_scorer=scores,
            graph=graph,
        )
        names = [item.skill for item in result.candidates]

        self.assertIn("security-review", names)
        self.assertIn("tdd-workflow", names)
        self.assertLessEqual(
            len({"skill-creator", "write-a-skill"} & set(names)),
            1,
        )

    def test_graph_output_is_bounded_and_weak_anchor_stays_silent(self) -> None:
        graph = SkillGraph.from_dict({"nodes": [], "edges": []}, self.skills)

        def weak_scores(
            task: str,
            records: Sequence[SkillRecord],
        ) -> dict[str, float]:
            del task
            return {
                record.name: 0.31 - (index * 0.001)
                for index, record in enumerate(records)
            }

        result = suggest_skill(
            "ช่วยสรุปประชุมเมื่อวานให้หน่อย",
            self.skills,
            semantic_scorer=weak_scores,
            graph=graph,
        )

        self.assertEqual(result.status, "silent")
        self.assertEqual(result.candidates, ())

        strong = suggest_skill(
            "Design an agent skill router.",
            self.skills,
            semantic_scorer=self.semantic_scores,
            graph=graph,
        )
        self.assertLessEqual(len(strong.candidates), 3)
        self.assertLess(len(json.dumps(strong.to_dict())), 1800)


class SkillDiscoveryTests(unittest.TestCase):
    def test_discovers_name_and_description_from_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_dir = Path(directory) / "routing-skill"
            skill_dir.mkdir()
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(
                "---\n"
                "name: routing-skill\n"
                "description: Route agent work using bounded task state.\n"
                "---\n\n"
                "# Large body that must not be returned in a suggestion\n",
                encoding="utf-8",
            )

            skills = discover_skills((Path(directory),))

        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0].name, "routing-skill")
        self.assertEqual(
            skills[0].description,
            "Route agent work using bounded task state.",
        )
        self.assertEqual(skills[0].path, str(skill_file.resolve()))
        self.assertIn(
            "Large body that must not be returned",
            skills[0].routing_text,
        )

    def test_cli_emits_shadow_suggestion_for_pull_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_dir = Path(directory) / "agent-harness-construction"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: agent-harness-construction\n"
                "description: Design PUSH skill router action spaces and context budget.\n"
                "---\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "paw",
                    "suggest",
                    "Design a PUSH skill router with a small context budget.",
                    "--skills-root",
                    directory,
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["mode"], "shadow")
        self.assertEqual(payload["status"], "candidates")
        self.assertEqual(
            payload["candidates"][0]["skill"],
            "agent-harness-construction",
        )
        self.assertEqual(
            payload["candidates"][0]["action"],
            "consider_skill",
        )
        self.assertTrue(
            payload["candidates"][0]["skill_path"].endswith("SKILL.md")
        )

    def test_graph_loader_compiles_overlay_against_discovered_skills(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill_dir = root / "agent-harness-construction"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: agent-harness-construction\n"
                "description: Design agent routing and action spaces.\n"
                "---\n",
                encoding="utf-8",
            )
            graph_path = root / "skill-graph.json"
            graph_path.write_text(
                json.dumps(
                    {
                        "nodes": [
                            {
                                "id": "intent:agent-routing",
                                "kind": "intent",
                                "text": "Design agent routing and skill selection.",
                            }
                        ],
                        "edges": [
                            {
                                "from": "intent:agent-routing",
                                "to": "agent-harness-construction",
                                "relation": "routes_to",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            skills = discover_skills((root,))

            graph = load_skill_graph(graph_path, skills)
            expanded = graph.expand({"intent:agent-routing": 0.90})

        self.assertEqual(
            tuple(item.skill.name for item in expanded),
            ("agent-harness-construction",),
        )


class SemanticRouterIntegrationTests(unittest.TestCase):
    def test_local_multilingual_model_ranks_related_skill_above_distractor(
        self,
    ) -> None:
        scorer = default_semantic_scorer()
        if scorer is None:
            self.skipTest("local multilingual ONNX model is unavailable")
        skills = (
            _skill(
                "agent-routing",
                "Design agent routing, action spaces, and skill selection.",
            ),
            _skill(
                "cooking",
                "Prepare recipes, ingredients, and meals in a kitchen.",
            ),
        )

        scores = scorer(
            "エージェントのスキルを選択するルーターを設計する",
            skills,
        )

        self.assertGreater(scores["agent-routing"], scores["cooking"])

    def test_missing_optional_dependencies_degrade_to_no_scorer(self) -> None:
        with patch("paw.semantic_router.importlib.util.find_spec", return_value=None):
            self.assertIsNone(default_semantic_scorer())


class EmbeddingCacheTests(unittest.TestCase):
    """The doc-embedding cache must persist, warm-start, and embed only deltas."""

    def _counting_scorer(self, cache_path: Path):
        import numpy as np

        from paw.semantic_router import OnnxSemanticScorer

        class _Counting(OnnxSemanticScorer):
            embeds = 0

            def _encode(self, texts):
                _Counting.embeds += len(texts)
                rows = []
                for text in texts:
                    seed = abs(hash(text)) % 9973
                    vector = np.array(
                        [seed % 7 + 1, seed % 5 + 1, seed % 3 + 1],
                        dtype=np.float32,
                    )
                    rows.append(vector / np.linalg.norm(vector))
                return np.stack(rows)

        return _Counting(Path("absent-model"), cache_path=cache_path)

    def test_cache_warm_starts_and_embeds_only_new_documents(self) -> None:
        skills = tuple(
            _skill(f"s{i}", f"desc {i}", routing_text=f"routing {i}")
            for i in range(6)
        )
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "vecs.npz"

            cold = self._counting_scorer(cache)
            type(cold).embeds = 0
            cold("task one", skills)
            self.assertEqual(type(cold).embeds, len(skills) + 1)  # docs + query

            warm = self._counting_scorer(cache)
            type(warm).embeds = 0
            first = warm("task two", skills)
            self.assertEqual(type(warm).embeds, 1)  # query only; docs from disk

            grown = skills + (_skill("s6", "new", routing_text="brand new"),)
            delta = self._counting_scorer(cache)
            type(delta).embeds = 0
            delta("task three", grown)
            self.assertEqual(type(delta).embeds, 2)  # one new doc + query

            self.assertTrue(cache.is_file())
            # cached scores equal a fresh, cacheless computation
            fresh = self._counting_scorer(Path(tmp) / "other.npz")
            fresh_scores = fresh("task two", skills)
            for name in fresh_scores:
                self.assertAlmostEqual(first[name], fresh_scores[name], places=6)


if __name__ == "__main__":
    unittest.main()
