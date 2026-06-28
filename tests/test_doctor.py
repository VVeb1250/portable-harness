from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paw.doctor import (
    DoctorReport,
    ICMCheck,
    default_init_sets,
    render_report,
    run_doctor,
)


class DoctorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_default_init_sets_are_the_foundation_core(self) -> None:
        names = [item.name for item in default_init_sets()]

        self.assertEqual(
            names,
            ["efficiency-min", "local-memory", "secure-agent", "doc-data-min"],
        )

    def test_doctor_reports_missing_default_tools_with_install_hints(self) -> None:
        with mock.patch("paw.doctor.resolve_binary", return_value=(None, "missing")):
            report = run_doctor(root=self.root, hosts=("codex",))

        self.assertEqual(report.status, "degraded")
        missing = {
            tool.tool: tool.install_hint
            for set_report in report.sets
            for tool in set_report.tools
            if tool.status == "missing"
        }

        self.assertIn("rg", missing)
        self.assertIn("winget install BurntSushi.ripgrep.MSVC", missing["rg"])
        self.assertIn("icm", missing)
        self.assertIn("ICM installer", missing["icm"])
        self.assertIn("gitleaks", missing)
        self.assertIn("winget install Gitleaks.Gitleaks", missing["gitleaks"])

    def test_doctor_reports_hosts_that_need_restart_after_config_wiring(self) -> None:
        ledger = self.root / ".paw" / "state.json"
        ledger.parent.mkdir()
        ledger.write_text(
            json.dumps(
                {
                    "schema": "paw-ownership-ledger/v1",
                    "sets": {
                        "codex:context-quality": {
                            "host": "codex",
                            "mcp_wiring": {
                                "mcp_file": str(self.root / ".codex" / "config.toml"),
                                "servers": ["context7"],
                            },
                        },
                        "claude-code:repo-pack": {
                            "host": "claude-code",
                            "path_wiring": {
                                "env_file": str(
                                    self.root / ".claude" / "settings.local.json"
                                ),
                                "introduced": True,
                            },
                        },
                    },
                }
            ),
            encoding="utf-8",
        )

        report = run_doctor(root=self.root, hosts=("codex", "claude-code"))
        restart = {host.host: host for host in report.hosts if host.restart_required}

        self.assertIn("codex", restart)
        self.assertIn("claude-code", restart)
        self.assertTrue(any("MCP config" in reason for reason in restart["codex"].restart_reasons))
        self.assertTrue(any("PATH/env" in reason for reason in restart["claude-code"].restart_reasons))

    def test_render_report_names_missing_tools_and_restart_hosts(self) -> None:
        with mock.patch("paw.doctor.resolve_binary", return_value=(None, "missing")):
            report = run_doctor(root=self.root, hosts=("codex",))

        text = render_report(report, command="doctor")

        self.assertIn("paw doctor: degraded", text)
        self.assertIn("missing: rg", text)
        self.assertIn("install:", text)
        self.assertIn("hosts:", text)

    def test_icm_check_in_report_when_installed(self) -> None:
        icm_topic_output = (
            "Topic                          Count\n"
            "----------------------------------------\n"
            "decisions                      22\n"
            "pending                        5\n"
            "lessons                        3\n"
        )
        mock_proc = mock.Mock(spec=subprocess.CompletedProcess)
        mock_proc.returncode = 0
        mock_proc.stdout = icm_topic_output
        mock_proc.stderr = ""

        with (
            mock.patch("paw.doctor._query_icm") as q,
            mock.patch("paw.doctor.resolve_binary", return_value=("/usr/bin/rg", "path")),
        ):
            q.return_value = ICMCheck(
                status="healthy",
                topics=(("decisions", 22), ("pending", 5), ("lessons", 3)),
                pending_count=5,
                summary="3 topics, 30 total memories",
            )
            report = run_doctor(root=self.root, hosts=("codex",))

        self.assertIsNotNone(report.icm)
        self.assertEqual(report.icm.status, "healthy")
        self.assertEqual(report.icm.pending_count, 5)
        self.assertEqual(len(report.icm.topics), 3)

        text = render_report(report)
        self.assertIn("icm: 3 topics", text)
        self.assertIn("pending: 5", text)

    def test_icm_absent_does_not_block_report(self) -> None:
        with (
            mock.patch("paw.doctor._query_icm", return_value=None),
            mock.patch("paw.doctor.resolve_binary", return_value=("/usr/bin/rg", "path")),
        ):
            report = run_doctor(root=self.root, hosts=("codex",))

        self.assertIsNone(report.icm)
        text = render_report(report)
        self.assertIn("icm: not detected", text)

    def test_hook_check_detects_paw_memory_hooks(self) -> None:
        claude_config = self.root / "settings.json"
        claude_config.write_text(
            json.dumps({
                "hooks": {
                    "Stop": [
                        {"hooks": [{"type": "command", "command": "py -m paw reflect --capture"}]},
                    ],
                    "SessionStart": [
                        {"hooks": [{"type": "command", "command": "py -m paw curate --surface"}]},
                    ],
                    "UserPromptSubmit": [
                        {"hooks": [{"type": "command", "command": "py -m paw memory hook --host claude-code --event user-prompt"}]},
                    ],
                }
            }),
            encoding="utf-8",
        )

        with (
            mock.patch("paw.doctor._check_host_hooks") as check_hooks,
            mock.patch("paw.doctor.resolve_binary", return_value=("/usr/bin/rg", "path")),
        ):
            check_hooks.return_value = mock.Mock(
                host="claude-code",
                config_path=str(claude_config),
                config_present=True,
                memory_hooks=("py -m paw reflect --capture", "py -m paw curate --surface", "py -m paw memory hook --host claude-code --event user-prompt"),
                coverage=mock.Mock(
                    recall_push=False,
                    mesh_hook=True,
                    reflect_stop=True,
                    curate_start=True,
                    team_sink=False,
                    memoir_sync=False,
                ),
            )
            report = run_doctor(root=self.root, hosts=("claude-code",))

        self.assertEqual(len(report.hooks), 1)
        text = render_report(report)
        # Coverage matrix includes lane markers
        self.assertIn("recall-push", text)
        self.assertIn("reflect-stop", text)
        self.assertIn("curate-start", text)

    def test_hook_check_no_config(self) -> None:
        with (
            mock.patch("paw.doctor._check_host_hooks", return_value=mock.Mock(
                host="claude-code",
                config_path=None,
                config_present=False,
                memory_hooks=(),
            )),
            mock.patch("paw.doctor.resolve_binary", return_value=("/usr/bin/rg", "path")),
        ):
            report = run_doctor(root=self.root, hosts=("claude-code",))

        text = render_report(report)
        self.assertIn("no hook config", text)

    def test_mesh_check_in_report(self) -> None:
        mesh_dir = Path.home() / ".paw" / "state" / "memory-mesh" / "portable-harness"
        mesh_dir.mkdir(parents=True, exist_ok=True)
        mesh_file = mesh_dir / "live.json"
        mesh_file.write_text(
            json.dumps({
                "schema": "paw-memory-mesh/v1",
                "project": "portable-harness",
                "members": {
                    "codex-abc": {
                        "member": "codex-abc",
                        "host": "codex",
                        "role": "codex",
                        "first_seen": 1000.0,
                        "last_seen": 1000.0,
                        "ttl_seconds": 300,
                        "session_id": "s1",
                        "capabilities": [],
                    },
                    "claude-xyz": {
                        "member": "claude-xyz",
                        "host": "claude-code",
                        "role": "claude-code",
                        "first_seen": 2000.0,
                        "last_seen": 2000.0,
                        "ttl_seconds": 300,
                        "session_id": "s2",
                        "capabilities": [],
                    },
                },
                "events": [],
                "locks": {},
                "next_seq": 3,
            }),
            encoding="utf-8",
        )

        try:
            with (
                mock.patch("paw.doctor._query_icm", return_value=None),
                mock.patch("paw.doctor.resolve_binary", return_value=("/usr/bin/rg", "path")),
            ):
                report = run_doctor(root=self.root, hosts=("codex",))

            self.assertIsNotNone(report.mesh)
            self.assertEqual(report.mesh.member_count, 2)
            text = render_report(report)
            self.assertIn("mesh:", text)
        finally:
            if mesh_file.exists():
                mesh_file.unlink()
            if mesh_dir.exists():
                mesh_dir.rmdir()

    def test_doctor_pending_icm_shows_next_action(self) -> None:
        with (
            mock.patch("paw.doctor._query_icm") as q,
            mock.patch("paw.doctor.resolve_binary", return_value=("/usr/bin/rg", "path")),
        ):
            q.return_value = ICMCheck(
                status="degraded",
                topics=(("pending", 25),),
                pending_count=25,
                summary="1 topic, 25 pending items",
            )
            report = run_doctor(root=self.root, hosts=("codex",))

        self.assertEqual(report.status, "degraded")
        actions = " ".join(report.next_actions)
        self.assertIn("curate 25 pending", actions)


if __name__ == "__main__":
    unittest.main()
