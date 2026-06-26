from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import json
import os

from paw.linker import (
    apply_plan,
    build_plan,
    ensure_bin_on_path,
    has_block,
    install_command,
    mcp_servers_for,
    read_mcp_servers,
    remove,
    resolve_binary,
    verify,
)
from paw.sets.loader import get_set


class LinkerSliceZeroTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.ctx = self.root / "CLAUDE.md"
        self.ctx.write_text("# project\n\noriginal content\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _plan(self):
        return build_plan("repo-pack", context=str(self.ctx), root=self.root)

    # --- plan ---------------------------------------------------------------
    def test_plan_for_cli_set_is_ok_with_inject_and_detect_actions(self) -> None:
        plan = self._plan()
        self.assertEqual(plan.status, "ok")
        kinds = {a.kind for a in plan.actions}
        self.assertIn("inject-context-block", kinds)
        self.assertIn("detect-binary", kinds)
        inject = next(a for a in plan.actions if a.kind == "inject-context-block")
        self.assertTrue(inject.requires_approval)

    def test_plan_blocks_an_mcp_set_on_a_host_without_mcp_config(self) -> None:
        # cursor has no MCP config file mapping -> blocked.
        plan = build_plan(
            "context-quality", host="cursor", context=str(self.ctx), root=self.root
        )
        self.assertEqual(plan.status, "blocked")
        self.assertTrue(any(w.startswith("BLOCK:") for w in plan.warnings))

    # --- apply --------------------------------------------------------------
    def test_apply_injects_block_preserves_content_and_records_ledger(self) -> None:
        result = apply_plan(self._plan(), root=self.root)
        self.assertEqual(result.status, "ok")
        text = self.ctx.read_text(encoding="utf-8")
        self.assertTrue(has_block(text, "repo-pack"))
        self.assertIn("original content", text)  # unrelated text untouched
        ledger = self.root / ".paw" / "state.json"
        self.assertTrue(ledger.exists())
        self.assertIn("repo-pack", ledger.read_text(encoding="utf-8"))

    def test_apply_is_idempotent(self) -> None:
        apply_plan(self._plan(), root=self.root)
        # rebuild plan against the now-injected file, then apply again
        apply_plan(self._plan(), root=self.root)
        text = self.ctx.read_text(encoding="utf-8")
        self.assertEqual(text.count("<!-- paw:repo-pack:start -->"), 1)

    def test_apply_refuses_a_stale_plan_after_drift(self) -> None:
        stale = self._plan()  # captures the pre-edit fingerprint
        self.ctx.write_text("# project\n\nedited elsewhere\n", encoding="utf-8")
        result = apply_plan(stale, root=self.root)
        self.assertEqual(result.status, "drifted")
        self.assertFalse(has_block(self.ctx.read_text(encoding="utf-8"), "repo-pack"))

    # --- verify -------------------------------------------------------------
    def test_verify_states(self) -> None:
        blocked = verify("repo-pack", context=str(self.ctx), root=self.root)
        self.assertEqual(blocked.health, "blocked")
        apply_plan(self._plan(), root=self.root)
        linked = verify("repo-pack", context=str(self.ctx), root=self.root)
        self.assertIn(linked.health, ("healthy", "degraded"))  # binary may be absent in CI

    def test_verify_detects_drift(self) -> None:
        apply_plan(self._plan(), root=self.root)
        self.ctx.write_text(
            self.ctx.read_text(encoding="utf-8") + "\nmanual edit\n", encoding="utf-8"
        )
        result = verify("repo-pack", context=str(self.ctx), root=self.root)
        self.assertEqual(result.health, "drifted")

    # --- remove -------------------------------------------------------------
    def test_remove_round_trips_to_original_content(self) -> None:
        apply_plan(self._plan(), root=self.root)
        result = remove("repo-pack", context=str(self.ctx), root=self.root)
        self.assertEqual(result.status, "ok")
        text = self.ctx.read_text(encoding="utf-8")
        self.assertFalse(has_block(text, "repo-pack"))
        self.assertIn("original content", text)
        ledger = self.root / ".paw" / "state.json"
        self.assertNotIn("\"repo-pack\"", ledger.read_text(encoding="utf-8"))

    def test_remove_refuses_after_user_drift(self) -> None:
        apply_plan(self._plan(), root=self.root)
        self.ctx.write_text(
            self.ctx.read_text(encoding="utf-8") + "\nuser touched this\n", encoding="utf-8"
        )
        result = remove("repo-pack", context=str(self.ctx), root=self.root)
        self.assertEqual(result.status, "drifted")
        self.assertTrue(has_block(self.ctx.read_text(encoding="utf-8"), "repo-pack"))


class BinaryResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_resolve_binary_finds_vendored_when_off_path(self) -> None:
        bindir = self.root / "bin"
        bindir.mkdir()
        (bindir / "code2prompt.exe").write_text("stub", encoding="utf-8")
        location, source = resolve_binary("code2prompt", self.root)
        self.assertEqual(source, "vendored")
        self.assertTrue(location.endswith("code2prompt.exe"))

    def test_resolve_binary_missing_when_absent_everywhere(self) -> None:
        location, source = resolve_binary("definitely-not-a-real-binary", self.root)
        self.assertIsNone(location)
        self.assertEqual(source, "missing")

    def test_vendored_binary_makes_plan_healthy(self) -> None:
        bindir = self.root / "bin"
        bindir.mkdir()
        (bindir / "code2prompt.exe").write_text("stub", encoding="utf-8")
        ctx = self.root / "CLAUDE.md"
        ctx.write_text("# project\n", encoding="utf-8")
        plan = build_plan("repo-pack", context=str(ctx), root=self.root)
        detect = next(a for a in plan.actions if a.kind == "detect-binary")
        self.assertIn("vendored", detect.summary)
        self.assertFalse(
            any("not on PATH" in w for w in plan.warnings),
            "vendored binary should not raise a degraded warning",
        )

    def test_plan_surfaces_install_command_when_missing(self) -> None:
        ctx = self.root / "CLAUDE.md"
        ctx.write_text("# project\n", encoding="utf-8")
        # api-quality ships hurl with a per-OS install recipe; not on PATH/bin here.
        plan = build_plan("api-quality", context=str(ctx), root=self.root)
        detect = next(a for a in plan.actions if a.kind == "detect-binary")
        self.assertIn("install:", detect.summary)

    def test_install_command_resolves_string_and_per_os_dict(self) -> None:
        self.assertEqual(
            install_command({"install": [{"cmd": "cargo install x"}]}),
            "cargo install x",
        )
        per_os = {"install": [{"cmd": {"windows": "winget x", "linux": "cargo x", "macos": "brew x"}}]}
        self.assertIsNotNone(install_command(per_os))
        self.assertIsNone(install_command({"install": []}))


class PathWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.bindir = self.root / "bin"
        self.bindir.mkdir()
        (self.bindir / "code2prompt.exe").write_text("stub", encoding="utf-8")
        self.ctx = self.root / "CLAUDE.md"
        self.ctx.write_text("# project\n\nkeep me\n", encoding="utf-8")
        self.env_file = self.root / ".claude" / "settings.local.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _plan(self):
        return build_plan(
            "repo-pack", host="claude-code", context=str(self.ctx), root=self.root
        )

    def test_plan_includes_wire_path_when_binary_vendored(self) -> None:
        kinds = {a.kind for a in self._plan().actions}
        self.assertIn("wire-path", kinds)

    def test_apply_prepends_bindir_and_preserves_other_keys(self) -> None:
        self.env_file.parent.mkdir()
        self.env_file.write_text(json.dumps({"model": "opus"}), encoding="utf-8")
        result = apply_plan(self._plan(), root=self.root)
        self.assertEqual(result.status, "ok")
        data = json.loads(self.env_file.read_text(encoding="utf-8"))
        self.assertEqual(data["model"], "opus")  # untouched
        first = data["env"]["PATH"].split(os.pathsep)[0]
        self.assertEqual(first, str(self.bindir.resolve()))

    def test_ensure_bin_on_path_is_idempotent(self) -> None:
        changed1, _ = ensure_bin_on_path(self.env_file, self.bindir)
        changed2, _ = ensure_bin_on_path(self.env_file, self.bindir)
        self.assertTrue(changed1)
        self.assertFalse(changed2)
        value = json.loads(self.env_file.read_text(encoding="utf-8"))["env"]["PATH"]
        self.assertEqual(value.split(os.pathsep).count(str(self.bindir.resolve())), 1)

    def test_remove_reverses_introduced_path_key(self) -> None:
        apply_plan(self._plan(), root=self.root)
        self.assertTrue(self.env_file.exists())
        remove("repo-pack", host="claude-code", context=str(self.ctx), root=self.root)
        # we introduced PATH (and the file) — it should be gone again
        leftover = (
            json.loads(self.env_file.read_text(encoding="utf-8")).get("env", {})
            if self.env_file.exists()
            else {}
        )
        self.assertNotIn("PATH", leftover)

    def test_remove_restores_prior_path_owner(self) -> None:
        self.env_file.parent.mkdir()
        self.env_file.write_text(
            json.dumps({"env": {"PATH": "/preexisting"}}), encoding="utf-8"
        )
        apply_plan(self._plan(), root=self.root)
        remove("repo-pack", host="claude-code", context=str(self.ctx), root=self.root)
        data = json.loads(self.env_file.read_text(encoding="utf-8"))
        self.assertEqual(data["env"]["PATH"], "/preexisting")


class CodexTomlMcpTests(unittest.TestCase):
    """slice-1b: comment-preserving MCP merge into Codex .codex/config.toml."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.cfg = self.root / ".codex" / "config.toml"
        self.cfg.parent.mkdir()
        self.cfg.write_text(
            "# user-owned codex layer\n"
            'approval_policy = "on-request"\n\n'
            "[mcp_servers.github]\n"
            "enabled = false  # keep disabled\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _plan(self, name="context-quality"):
        return build_plan(name, host="codex", root=self.root)

    def test_plan_ok_for_mcp_set_on_codex(self) -> None:
        plan = self._plan()
        self.assertEqual(plan.status, "ok")
        self.assertIn("inject-mcp", {a.kind for a in plan.actions})

    def test_apply_merges_toml_table_and_preserves_comments(self) -> None:
        result = apply_plan(self._plan(), root=self.root)
        self.assertEqual(result.status, "ok")
        text = self.cfg.read_text(encoding="utf-8")
        self.assertIn("# user-owned codex layer", text)  # comment survives
        self.assertIn("# keep disabled", text)           # inline comment survives
        self.assertIn("[mcp_servers.context7]", text)    # new table added
        servers = read_mcp_servers(self.cfg)
        self.assertIn("github", servers)
        self.assertIn("context7", servers)

    def test_apply_is_idempotent_on_toml(self) -> None:
        apply_plan(self._plan(), root=self.root)
        before = self.cfg.read_text(encoding="utf-8")
        apply_plan(self._plan(), root=self.root)
        self.assertEqual(self.cfg.read_text(encoding="utf-8"), before)

    def test_remove_strips_paw_table_keeps_user_servers(self) -> None:
        apply_plan(self._plan(), root=self.root)
        remove("context-quality", host="codex", root=self.root)
        servers = read_mcp_servers(self.cfg)
        self.assertIn("github", servers)        # user server kept
        self.assertNotIn("context7", servers)   # paw server gone
        self.assertIn("# user-owned codex layer", self.cfg.read_text(encoding="utf-8"))

    def test_n1_excludes_disabled_servers(self) -> None:
        # github is enabled=false -> should not count toward the ceiling.
        plan = self._plan()
        self.assertFalse(any(w.startswith("N1:") for w in plan.warnings))


class McpWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.mcp_file = self.root / ".mcp.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _plan(self, name="context-quality"):
        return build_plan(name, host="claude-code", root=self.root)

    def test_host_anchor_picks_codegraph_on_claude_code(self) -> None:
        servers = mcp_servers_for(get_set("efficiency-starter"), "claude-code")
        self.assertIn("codegraph", servers)
        self.assertNotIn("semble", servers)  # semble is the codex/gemini anchor

    def test_host_anchor_picks_semble_on_gemini(self) -> None:
        servers = mcp_servers_for(get_set("efficiency-starter"), "gemini")
        self.assertIn("semble", servers)
        self.assertNotIn("codegraph", servers)

    def test_resolved_config_strips_annotation_keys(self) -> None:
        servers = mcp_servers_for(get_set("efficiency-starter"), "claude-code")
        self.assertFalse(any(k.startswith("_") for k in servers["codegraph"]))

    def test_plan_for_mcp_set_on_json_host_is_ok_with_inject_mcp(self) -> None:
        plan = self._plan()
        self.assertEqual(plan.status, "ok")
        self.assertIn("inject-mcp", {a.kind for a in plan.actions})

    def test_apply_merges_servers_and_preserves_existing(self) -> None:
        self.mcp_file.write_text(
            json.dumps({"mcpServers": {"keep-me": {"command": "x"}}}), encoding="utf-8"
        )
        result = apply_plan(self._plan(), root=self.root)
        self.assertEqual(result.status, "ok")
        servers = read_mcp_servers(self.mcp_file)
        self.assertIn("keep-me", servers)   # untouched
        self.assertIn("context7", servers)  # merged in

    def test_apply_is_idempotent_for_mcp(self) -> None:
        apply_plan(self._plan(), root=self.root)
        apply_plan(self._plan(), root=self.root)
        servers = read_mcp_servers(self.mcp_file)
        self.assertEqual(list(servers).count("context7"), 1)

    def test_verify_reports_mcp_health(self) -> None:
        self.assertEqual(verify("context-quality", root=self.root).health, "blocked")
        apply_plan(self._plan(), root=self.root)
        linked = verify("context-quality", root=self.root)
        self.assertIn(linked.health, ("healthy", "degraded"))

    def test_remove_strips_only_paw_servers_and_keeps_others(self) -> None:
        self.mcp_file.write_text(
            json.dumps({"mcpServers": {"keep-me": {"command": "x"}}}), encoding="utf-8"
        )
        apply_plan(self._plan(), root=self.root)
        remove("context-quality", host="claude-code", root=self.root)
        servers = read_mcp_servers(self.mcp_file)
        self.assertIn("keep-me", servers)
        self.assertNotIn("context7", servers)

    def test_n1_ceiling_warns_when_too_many_servers(self) -> None:
        self.mcp_file.write_text(
            json.dumps({"mcpServers": {"a": {}, "b": {}, "c": {}}}), encoding="utf-8"
        )
        plan = self._plan()  # adds context7 -> 4 total > ceiling 3
        self.assertTrue(any(w.startswith("N1:") for w in plan.warnings))


if __name__ == "__main__":
    unittest.main()
