from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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
) -> SkillRecord:
    return SkillRecord(
        name=name,
        description=description,
        path=path or f"/skills/{name}/SKILL.md",
    )


class TaskCapsuleTests(unittest.TestCase):
    def test_thai_router_request_gets_canonical_state(self) -> None:
        capsule = build_task_capsule(
            "ออกแบบ PUSH skill router ให้เลือก skill โดยไม่กิน context เยอะ"
        )

        self.assertIn("agent-routing", capsule.domains)
        self.assertEqual(capsule.operation, "design")
        self.assertIn("low-context", capsule.constraints)


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
        )

    def test_clear_match_pushes_skill_ids_without_skill_bodies(self) -> None:
        result = suggest_skill(
            "ทำให้ PUSH skill router ฉลาดขึ้นและประหยัด context",
            self.skills,
        )

        self.assertEqual(result.status, "suggested")
        self.assertEqual(result.mode, "shadow")
        self.assertEqual(result.match, "clear")
        self.assertEqual(
            tuple(item.skill for item in result.suggestions),
            ("agent-harness-construction",),
        )
        self.assertEqual(result.suggestions[0].action, "load_skill")
        self.assertIn("agent-routing", result.suggestions[0].reason)
        self.assertNotIn("Design and optimize", json.dumps(result.to_dict()))

    def test_complementary_clear_matches_can_push_two_skills(self) -> None:
        result = suggest_skill(
            "Implement authentication safely using tests first and check coverage.",
            self.skills,
        )

        self.assertEqual(
            {item.skill for item in result.suggestions},
            {"security-review", "tdd-workflow"},
        )
        self.assertLessEqual(len(result.suggestions), 2)

    def test_generic_design_word_does_not_trigger_ui_skill(self) -> None:
        result = suggest_skill(
            "Design a smarter agent router for skill selection.",
            self.skills,
        )

        self.assertEqual(result.suggestions[0].skill, "agent-harness-construction")
        self.assertNotIn(
            "write-a-skill",
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

        result = suggest_skill("Analyze Python application performance.", tied)

        self.assertEqual(result.status, "silent")
        self.assertIn("ambiguous", result.reason)

    def test_active_skill_is_not_suggested_again(self) -> None:
        result = suggest_skill(
            "Design a smarter skill router with a smaller context budget.",
            self.skills,
            active_skills=("agent-harness-construction",),
        )

        self.assertEqual(result.status, "silent")
        self.assertEqual(result.suggestions, ())


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

    def test_cli_emits_shadow_suggestion_for_pull_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            skill_dir = Path(directory) / "agent-harness-construction"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: agent-harness-construction\n"
                "description: Design agent routing, action spaces, and context budgets.\n"
                "---\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "paw",
                    "suggest",
                    "ออกแบบ PUSH skill router แบบประหยัด context",
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
        self.assertEqual(
            payload["suggestions"][0]["skill"],
            "agent-harness-construction",
        )
        self.assertEqual(payload["suggestions"][0]["action"], "load_skill")
        self.assertTrue(
            payload["suggestions"][0]["skill_path"].endswith("SKILL.md")
        )


if __name__ == "__main__":
    unittest.main()
