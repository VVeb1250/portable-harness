from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from paw import memory_hook
from paw.memory_hook import (
    PENDING_COUNT_TTL_SECONDS,
    build_config,
    hook_stdout,
    install_memory_hooks,
    load_hook_payload,
    run_memory_hook,
)
from paw.memory_mesh import MemoryMesh, MeshScope


class MemoryHookTests(unittest.TestCase):
    def setUp(self) -> None:
        # The resume builder reads the live ICM/git; for mesh-silence tests we
        # stub it to "" so they assert mesh behaviour, not resume content.
        # Tests that exercise resume set their own builder.
        self._prev_builder = memory_hook._resume_builder
        memory_hook._resume_builder = lambda config: ""

    def tearDown(self) -> None:
        memory_hook._resume_builder = self._prev_builder

    def test_user_prompt_hook_registers_polls_and_advances_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_dir = Path(directory) / "mesh"
            hook_state_dir = Path(directory) / "hooks"
            mesh = MemoryMesh(root=state_dir)
            scope = MeshScope(project="portable-harness", run_id="live")
            mesh.post(
                scope,
                member="claude-1",
                lane="shared",
                kind="handoff",
                content="Reviewer found a failing edge case.",
            )
            payload = {"cwd": str(Path.cwd()), "session_id": "codex-session"}
            config = build_config(
                payload,
                host="codex",
                event="user-prompt",
                project="portable-harness",
                run_id="live",
                state_dir=state_dir,
                hook_state_dir=hook_state_dir,
            )

            first = run_memory_hook(config, count_runner=lambda: 0)
            second = run_memory_hook(config, count_runner=lambda: 0)

            self.assertIn("Reviewer found", first.additional_context)
            self.assertIn("cursor:", first.additional_context)
            self.assertEqual(second.additional_context, "")

    def test_hook_stdout_uses_host_hook_json_shape(self) -> None:
        # Use an EMPTY cwd so the resume block stays silent (no markdown); this
        # test asserts the lone-presence-event silence, not resume content.
        directory = tempfile.mkdtemp()
        workdir = Path(directory) / "work"
        workdir.mkdir()
        result = run_memory_hook(
            build_config(
                {"cwd": str(workdir), "session_id": "s"},
                host="claude-code",
                event="session-start",
                project="p",
                run_id="r",
                state_dir=Path(directory) / "mesh",
                hook_state_dir=Path(directory) / "hooks",
            ),
            count_runner=lambda: 0,
        )

        out = hook_stdout(result, hook_event_name="SessionStart")

        # A lone presence event from this same member is intentionally silent.
        self.assertEqual(out, "")

    def test_load_hook_payload_is_fail_silent(self) -> None:
        self.assertEqual(load_hook_payload("not-json"), {})
        self.assertEqual(load_hook_payload("[]"), {})

    def test_pending_nudge_is_silent_below_warn_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            # Use an EMPTY cwd so the resume block finds no markdown and stays
            # silent — this test asserts pending-nudge silence, not resume.
            workdir = Path(directory) / "work"
            workdir.mkdir()
            config = build_config(
                {"cwd": str(workdir), "session_id": "s"},
                host="codex",
                event="session-start",
                project="p",
                run_id="r",
                state_dir=Path(directory) / "mesh",
                hook_state_dir=Path(directory) / "hooks",
            )

            result = run_memory_hook(config, count_runner=lambda: 29, now=lambda: 1000.0)

        self.assertEqual(result.additional_context, "")

    def test_pending_nudge_surfaces_above_warn_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workdir = Path(directory) / "work"
            workdir.mkdir()
            config = build_config(
                {"cwd": str(workdir), "session_id": "s"},
                host="codex",
                event="session-start",
                project="p",
                run_id="r",
                state_dir=Path(directory) / "mesh",
                hook_state_dir=Path(directory) / "hooks",
            )

            result = run_memory_hook(config, count_runner=lambda: 30, now=lambda: 1000.0)

        self.assertIn("30 pending", result.additional_context)
        self.assertIn("paw curate --dry-run", result.additional_context)

    def test_critical_pending_uses_preview_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = build_config(
                {"cwd": str(Path.cwd()), "session_id": "s"},
                host="codex",
                event="stop",
                project="p",
                run_id="r",
                state_dir=Path(directory) / "mesh",
                hook_state_dir=Path(directory) / "hooks",
            )

            result = run_memory_hook(
                config,
                count_runner=lambda: 80,
                preview_runner=lambda: "🧹 paw: 80 pending → would ADD 80",
                now=lambda: 1000.0,
            )

        self.assertEqual(
            result.additional_context,
            "🧹 paw: 80 pending → would ADD 80",
        )

    def test_pending_count_is_cached_per_member_until_ttl_expires(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            calls = {"count": 0}

            def count_runner() -> int:
                calls["count"] += 1
                return 30 + calls["count"]

            config = build_config(
                {"cwd": str(Path.cwd()), "session_id": "s"},
                host="codex",
                event="user-prompt",
                project="p",
                run_id="r",
                state_dir=Path(directory) / "mesh",
                hook_state_dir=Path(directory) / "hooks",
            )

            first = run_memory_hook(config, count_runner=count_runner, now=lambda: 1000.0)
            second = run_memory_hook(
                config,
                count_runner=count_runner,
                now=lambda: 1000.0 + PENDING_COUNT_TTL_SECONDS - 1,
            )
            third = run_memory_hook(
                config,
                count_runner=count_runner,
                now=lambda: 1000.0 + PENDING_COUNT_TTL_SECONDS + 1,
            )

        self.assertEqual(calls["count"], 2)
        self.assertIn("31 pending", first.additional_context)
        self.assertIn("31 pending", second.additional_context)
        self.assertIn("32 pending", third.additional_context)


class MemoryHookInstallTests(unittest.TestCase):
    def test_install_hooks_is_idempotent_for_claude_and_codex(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            claude = Path(directory) / "settings.json"
            codex = Path(directory) / "hooks.json"
            claude.write_text(json.dumps({"hooks": {"Stop": []}}), encoding="utf-8")
            codex.write_text(json.dumps({"hooks": {"Stop": []}}), encoding="utf-8")

            c1 = install_memory_hooks(host="claude-code", config_path=claude)
            c2 = install_memory_hooks(host="claude-code", config_path=claude)
            x1 = install_memory_hooks(host="codex", config_path=codex)
            x2 = install_memory_hooks(host="codex", config_path=codex)

            self.assertEqual(c1.status, "success")
            self.assertEqual(c2.added, ())
            self.assertEqual(x1.status, "success")
            self.assertEqual(x2.added, ())
            claude_data = json.loads(claude.read_text(encoding="utf-8"))
            codex_data = json.loads(codex.read_text(encoding="utf-8"))
            claude_commands = _commands(claude_data)
            codex_commands = _commands(codex_data)
            self.assertEqual(
                claude_commands.count(
                    "py -m paw memory hook --host claude-code --event user-prompt"
                ),
                1,
            )
            self.assertEqual(
                codex_commands.count("py -m paw memory hook --host codex --event user-prompt"),
                1,
            )

    def test_cli_hook_json_mode_works_for_claude_host(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "paw",
                    "memory",
                    "hook",
                    "--host",
                    "claude-code",
                    "--event",
                    "user-prompt",
                    "--project",
                    "p",
                    "--run-id",
                    "r",
                    "--state-dir",
                    str(Path(directory) / "mesh"),
                    "--hook-state-dir",
                    str(Path(directory) / "hooks"),
                    "--json",
                ],
                input=json.dumps({"cwd": str(Path.cwd()), "session_id": "s"}),
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "success")

    def test_cli_hook_json_mode_accepts_z_code_host(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "paw",
                    "memory",
                    "hook",
                    "--host",
                    "z-code",
                    "--event",
                    "user-prompt",
                    "--project",
                    "p",
                    "--run-id",
                    "r",
                    "--state-dir",
                    str(Path(directory) / "mesh"),
                    "--hook-state-dir",
                    str(Path(directory) / "hooks"),
                    "--json",
                ],
                input=json.dumps({"cwd": str(Path.cwd()), "session_id": "s"}),
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "success")


def _commands(data: dict) -> list[str]:
    out: list[str] = []
    for entries in data.get("hooks", {}).values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                if "command" in hook:
                    out.append(hook["command"])
    return out


if __name__ == "__main__":
    unittest.main()
