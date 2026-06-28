from __future__ import annotations

import unittest

from paw.sets.loader import get_set, load_all


class CatalogCompositionTests(unittest.TestCase):
    def test_catalog_contains_the_promoted_and_vetted_capability_sets(self) -> None:
        names = {item.name for item in load_all()}

        self.assertTrue(
            {
                "efficiency-min",
                "code-intelligence",
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
            "efficiency-min": ("ready", {"rg", "rtk", "ast-grep"}),
            "code-intelligence": ("conditional", {"codegraph", "semble"}),
            "doc-data-min": ("ready", {"duckdb", "jq", "markitdown"}),
            "harness-foundation": ("detect-first", {"ecc"}),
            "context-workbench": ("conditional", {"context-mode"}),
            "repo-pack": ("ready", {"code2prompt"}),
            "test-affected": ("conditional", {"pytest-testmon"}),
            "quality-gate": ("ready", {"prek", "actionlint", "lychee"}),
            "api-quality": ("ready", {"hurl"}),
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

    def test_all_sets_expose_init_scope_and_evidence_metadata(self) -> None:
        for item in load_all():
            with self.subTest(item=item.name):
                self.assertIn(item.catalog_status, {"ready", "conditional", "detect-first"})
                self.assertIn(
                    item.link_scope,
                    {"global", "project", "conditional", "detect-first"},
                )
                self.assertIn(
                    item.foundation_tier,
                    {"core", "optional-foundation", "specific", "detect"},
                )
                self.assertIsInstance(item.default_init, bool)
                self.assertTrue(item.bench_status)
                self.assertEqual(
                    set(item.platforms),
                    {"windows", "macos", "linux"},
                )
                for os_name, support in item.platforms.items():
                    self.assertIn(
                        support,
                        {"supported", "partial", "blocked"},
                        msg=f"{item.name} has invalid {os_name} support={support}",
                    )
                self.assertIn("idle_mcp", item.token_tax)
                self.assertTrue(item.evidence)
                self.assertIn("telemetry", item.privacy)
                self.assertIn("powershell", item.windows_ergonomics)

    def test_default_init_is_limited_to_global_no_mcp_core_sets(self) -> None:
        default_sets = {item.name for item in load_all() if item.default_init}

        self.assertEqual(default_sets, {"local-memory", "efficiency-min", "secure-agent", "doc-data-min"})
        for item in load_all():
            if item.default_init:
                self.assertEqual(item.foundation_tier, "core")
                self.assertEqual(item.link_scope, "global")
                self.assertEqual(item.mcp_count, 0)
                self.assertEqual(item.bench_status, "local-pass")

    def test_dev_efficiency_split_keeps_global_cli_separate_from_project_mcp(self) -> None:
        efficiency = get_set("efficiency-min")
        intelligence = get_set("code-intelligence")
        legacy = get_set("efficiency-starter")

        self.assertTrue(efficiency.default_init)
        self.assertEqual(efficiency.link_scope, "global")
        self.assertEqual(efficiency.foundation_tier, "core")
        self.assertEqual(efficiency.mcp_count, 0)
        self.assertEqual({tool["tool"] for tool in efficiency.non_mcp}, {"rg", "rtk", "ast-grep"})
        self.assertEqual(efficiency.evidence["local_bench"], "docs/FOUNDATION-BENCH-2026-06-28.md")

        self.assertFalse(intelligence.default_init)
        self.assertEqual(intelligence.link_scope, "project")
        self.assertEqual(intelligence.foundation_tier, "optional-foundation")
        self.assertEqual({tool["tool"] for tool in intelligence.mcp}, {"codegraph", "semble"})

        self.assertEqual(legacy.raw["deprecated_by"], ["efficiency-min", "code-intelligence"])

    def test_doc_data_min_replaces_split_data_and_doc_defaults(self) -> None:
        doc_data = get_set("doc-data-min")

        self.assertTrue(doc_data.default_init)
        self.assertEqual(doc_data.link_scope, "global")
        self.assertEqual(doc_data.foundation_tier, "core")
        self.assertEqual(doc_data.mcp_count, 0)
        self.assertEqual({tool["tool"] for tool in doc_data.non_mcp}, {"duckdb", "jq", "markitdown"})
        self.assertFalse(get_set("data-query").default_init)
        self.assertFalse(get_set("doc-extract").default_init)
        self.assertEqual(get_set("data-query").raw["deprecated_by"], ["doc-data-min"])
        self.assertEqual(get_set("doc-extract").raw["deprecated_by"], ["doc-data-min"])

    def test_local_memory_is_a_cross_os_foundation_core_set(self) -> None:
        memory = get_set("local-memory")

        self.assertTrue(memory.default_init)
        self.assertEqual(memory.link_scope, "global")
        self.assertEqual(memory.foundation_tier, "core")
        self.assertEqual(memory.mcp_count, 0)
        self.assertEqual({tool["tool"] for tool in memory.non_mcp}, {"icm"})
        self.assertEqual(memory.windows_ergonomics["powershell"], "use icm.exe to avoid Invoke-Command alias")

    def test_gortex_is_an_optional_augment_not_a_default_anchor(self) -> None:
        efficiency = get_set("code-intelligence")
        gortex = next(
            source
            for source in efficiency.raw["optional_sources"]
            if source["tool"] == "gortex"
        )

        self.assertEqual(gortex["catalog_status"], "deferred")
        self.assertEqual(gortex["adoption_mode"], "cli-augment-only")
        self.assertNotIn("gortex", {item["tool"] for item in efficiency.mcp})

    def test_code_intelligence_candidates_are_visible_but_not_default(self) -> None:
        intelligence = get_set("code-intelligence")
        sources = {source["tool"]: source for source in intelligence.raw["optional_sources"]}

        for tool in ("codebase-memory-mcp", "Serena", "grepai"):
            self.assertIn(tool, sources)
            self.assertEqual(sources[tool]["catalog_status"], "candidate")
        self.assertEqual(sources["graphify"]["catalog_status"], "deferred")
        self.assertFalse(intelligence.default_init)

    def test_ecc_foundation_points_to_the_integration_ledger(self) -> None:
        harness = get_set("harness-foundation")

        self.assertEqual(harness.raw["catalog_status"], "detect-first")
        self.assertIn("rich installed harness pack", harness.raw["compat_notes"])
        self.assertIn("docs/ECC-INTEGRATION-LEDGER.md", harness.raw["compat_notes"])
        self.assertIn("docs/WIRE-DECISION-MATRIX.md", harness.raw["compat_notes"])


if __name__ == "__main__":
    unittest.main()
