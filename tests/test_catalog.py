from __future__ import annotations

import unittest

from paw.sets.loader import get_set, load_all


class CatalogCompositionTests(unittest.TestCase):
    def test_catalog_contains_the_promoted_and_vetted_capability_sets(self) -> None:
        names = {item.name for item in load_all()}

        self.assertTrue(
            {
                "harness-foundation",
                "context-workbench",
                "repo-pack",
                "test-affected",
                "quality-gate",
                "api-quality",
            }.issubset(names)
        )

    def test_new_sets_expose_readiness_and_portability_metadata(self) -> None:
        expected = {
            "harness-foundation": ("detect-first", {"ecc"}),
            "context-workbench": ("conditional", {"context-mode"}),
            "repo-pack": ("ready", {"code2prompt"}),
            "test-affected": ("conditional", {"pytest-testmon"}),
            "quality-gate": ("candidate", {"prek", "actionlint", "lychee"}),
            "api-quality": ("candidate", {"hurl"}),
        }

        for name, (status, tools) in expected.items():
            item = get_set(name)
            present = {
                component["tool"]
                for component in (*item.mcp, *item.non_mcp)
            }
            self.assertEqual(item.raw["catalog_status"], status)
            self.assertEqual(present, tools)
            self.assertTrue(item.raw["decision"]["portable"])
            self.assertIn("token", item.raw["decision"])
            self.assertIn("quality", item.raw["decision"])

    def test_gortex_is_an_optional_augment_not_a_default_anchor(self) -> None:
        efficiency = get_set("efficiency-starter")
        gortex = next(
            source
            for source in efficiency.raw["optional_sources"]
            if source["tool"] == "gortex"
        )

        self.assertEqual(gortex["catalog_status"], "deferred")
        self.assertEqual(gortex["adoption_mode"], "cli-augment-only")
        self.assertNotIn("gortex", {item["tool"] for item in efficiency.mcp})


if __name__ == "__main__":
    unittest.main()
