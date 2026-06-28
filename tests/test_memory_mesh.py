from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from paw.memory_mesh import MemoryMesh, MeshScope


class FakeClock:
    def __init__(self, start: float = 1_000.0) -> None:
        self.value = start

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class MemoryMeshTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = FakeClock()
        self.mesh = MemoryMesh(root=Path(self.tmp.name), now=self.clock)
        self.scope = MeshScope(project="portable-harness", run_id="parallel-1")

    def test_register_tracks_members_and_staleness(self) -> None:
        first = self.mesh.register(
            self.scope,
            member="codex-1",
            host="codex",
            role="planner",
            session_id="s1",
            capabilities=("review", "patch"),
            ttl_seconds=30,
        )
        self.mesh.register(
            self.scope,
            member="claude-1",
            host="claude-code",
            role="reviewer",
            ttl_seconds=300,
        )

        self.assertEqual(first.status, "success")
        self.clock.advance(31)
        result = self.mesh.members(self.scope)

        members = {member.member: member for member in result.members}
        self.assertFalse(members["codex-1"].active)
        self.assertTrue(members["claude-1"].active)
        self.assertEqual(members["codex-1"].capabilities, ("review", "patch"))

    def test_private_lane_is_owner_visible_until_promoted(self) -> None:
        self.mesh.register(self.scope, member="codex-1", host="codex")
        self.mesh.register(self.scope, member="claude-1", host="claude-code")
        private = self.mesh.post(
            self.scope,
            member="codex-1",
            lane="private",
            kind="observation",
            content="Parser clue from Codex scratchpad.",
        )
        shared = self.mesh.post(
            self.scope,
            member="claude-1",
            lane="shared",
            kind="handoff",
            content="Claude shared handoff.",
        )

        codex_poll = self.mesh.poll(self.scope, member="codex-1", since=0)
        claude_poll = self.mesh.poll(self.scope, member="claude-1", since=0)

        self.assertIn(private.events[0].seq, {event.seq for event in codex_poll.events})
        self.assertNotIn(private.events[0].seq, {event.seq for event in claude_poll.events})
        self.assertIn(shared.events[0].seq, {event.seq for event in claude_poll.events})

        promoted = self.mesh.promote(
            self.scope,
            member="codex-1",
            seq=private.events[0].seq,
            kind="observation",
        )
        after = self.mesh.poll(self.scope, member="claude-1", since=shared.cursor)

        self.assertEqual(promoted.status, "success")
        self.assertEqual(after.events[0].promoted_from, private.events[0].seq)
        self.assertEqual(after.events[0].lane, "shared")

    def test_locks_block_conflicting_writer_and_expire(self) -> None:
        first = self.mesh.acquire_lock(
            self.scope,
            name="files-paw",
            owner="codex-1",
            purpose="editing paw memory files",
            ttl_seconds=60,
        )
        blocked = self.mesh.acquire_lock(
            self.scope,
            name="files-paw",
            owner="claude-1",
            ttl_seconds=60,
        )
        self.clock.advance(61)
        acquired = self.mesh.acquire_lock(
            self.scope,
            name="files-paw",
            owner="claude-1",
            ttl_seconds=60,
        )

        self.assertEqual(first.status, "success")
        self.assertEqual(blocked.status, "blocked")
        self.assertIn("codex-1", blocked.summary)
        self.assertEqual(acquired.status, "success")
        self.assertEqual(acquired.locks[0].owner, "claude-1")

    def test_release_requires_owner_unless_forced(self) -> None:
        self.mesh.acquire_lock(self.scope, name="docs", owner="codex-1")

        blocked = self.mesh.release_lock(self.scope, name="docs", owner="claude-1")
        forced = self.mesh.release_lock(
            self.scope,
            name="docs",
            owner="claude-1",
            force=True,
        )

        self.assertEqual(blocked.status, "blocked")
        self.assertEqual(forced.status, "success")
        self.assertEqual(self.mesh.poll(self.scope).locks, ())

    def test_secret_like_content_is_rejected_before_state_write(self) -> None:
        result = self.mesh.post(
            self.scope,
            member="codex-1",
            content="DEEPSEEK_API_KEY=do-not-store",
        )

        self.assertEqual(result.status, "error")
        self.assertFalse((Path(self.tmp.name) / "portable-harness").exists())


class MemoryMeshCliTests(unittest.TestCase):
    def test_cli_register_post_poll_uses_isolated_state_dir(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            common = [
                "--project",
                "portable-harness",
                "--run-id",
                "cli-1",
                "--state-dir",
                directory,
                "--json",
            ]
            register = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "paw",
                    "memory",
                    "register",
                    *common,
                    "--member",
                    "codex-1",
                    "--host",
                    "codex",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(register.returncode, 0, register.stderr)

            post = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "paw",
                    "memory",
                    "post",
                    *common,
                    "--member",
                    "codex-1",
                    "--kind",
                    "handoff",
                    "--content",
                    "Shared finding from Codex.",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(post.returncode, 0, post.stderr)

            poll = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "paw",
                    "memory",
                    "poll",
                    *common,
                    "--member",
                    "claude-1",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(poll.returncode, 0, poll.stderr)
            payload = json.loads(poll.stdout)
            self.assertEqual(payload["status"], "success")
            self.assertTrue(
                any(event["content"] == "Shared finding from Codex." for event in payload["events"])
            )


if __name__ == "__main__":
    unittest.main()
