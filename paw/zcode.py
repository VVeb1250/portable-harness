"""Z Code host setup for paw.

Z Code is primarily a GUI/ADE host, so the durable integration surface is a
user skill that tells Z Code agents how to pull paw's router and memory context.
This avoids patching undocumented Electron state while still making the bundle
available to Z Code sessions.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path


SKILL_NAME = "paw-bundle"


@dataclass(frozen=True)
class ZCodeSetupResult:
    status: str
    skill_path: str
    app_path: str | None
    path_ready: bool
    summary: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def default_zcode_skill_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".zcode" / "skills" / SKILL_NAME


def find_zcode_app() -> Path | None:
    found = shutil.which("zcode") or shutil.which("ZCode.exe")
    if found:
        return Path(found)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidate = Path(local) / "Programs" / "ZCode" / "ZCode.exe"
        if candidate.exists():
            return candidate
    return None


def zcode_app_dir_on_path(app_path: Path | None = None) -> bool:
    app_path = app_path or find_zcode_app()
    if app_path is None:
        return False
    app_dir = str(app_path.parent.resolve()).casefold()
    entries = [Path(p).resolve() for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    return any(str(entry).casefold() == app_dir for entry in entries)


def render_paw_bundle_skill() -> str:
    return """---
name: paw-bundle
description: Use in Z Code before non-trivial repository work to load paw bundle routing, local memory, and cross-agent handoff discipline.
---

# Paw Bundle For Z Code

Use this skill when a Z Code task is about code, repo maintenance, agent routing,
bundle tools, or project memory.

## Start Of Task

1. Run the paw surface query for the user's actual task:

```powershell
python -m paw surface "<task text>" --cwd "<repo path>" --audit
```

When Z Code knows more than the raw prompt, pass the smallest useful action
context too:

```powershell
python -m paw surface "<task text>" --cwd "<repo path>" --phase verify --changed-file "paw/router_block.py" --audit
python -m paw surface "<task text>" --cwd "<repo path>" --phase handoff --intent "repo handoff" --audit
python -m paw surface "<task text>" --cwd "<repo path>" --active-tool shell --last-command "python -m pytest -q" --audit
```

Follow any `paw sets` and `paw memory` hints it returns. If it returns nothing,
continue normally.

2. Register this Z Code session in the local memory mesh:

```powershell
python -m paw memory hook --host z-code --event session-start --project "<repo-name>" --run-id live --json
```

3. Poll shared memory before making or reviewing substantial changes:

```powershell
python -m paw memory hook --host z-code --event user-prompt --project "<repo-name>" --run-id live --json
```

## During Work

- Use `python -m paw sets list` and `python -m paw sets show <set>` to inspect
  available bundle capabilities.
- Use `python -m paw verify <set> --host z-code` before assuming a capability is
  wired into this repository.
- Use `python -m paw route "<task>" --available codex deepseek` for team routing
  decisions; do not launch external/paid agents without explicit approval.
- For durable handoff notes, post bounded summaries:

```powershell
python -m paw memory post --project "<repo-name>" --run-id live --member "z-code" --kind handoff --content "<short summary>"
```

## Privacy

Sensitive or proprietary repository code must not be routed to GLM/Z.ai unless
the repository policy explicitly allows it. Prefer local tools, Codex, or the
repo's approved provider route for restricted work.
"""


def setup_zcode(
    *,
    skill_dir: Path | None = None,
    overwrite: bool = False,
) -> ZCodeSetupResult:
    target_dir = skill_dir or default_zcode_skill_dir()
    target = target_dir / "SKILL.md"
    target_dir.mkdir(parents=True, exist_ok=True)
    if overwrite or not target.exists():
        target.write_text(render_paw_bundle_skill(), encoding="utf-8")

    app_path = find_zcode_app()
    path_ready = zcode_app_dir_on_path(app_path)
    if app_path and path_ready:
        summary = "Z Code app found; paw bundle skill installed."
        status = "healthy"
    elif app_path:
        summary = "Z Code app found and paw bundle skill installed; restart shell/host for PATH."
        status = "degraded"
    else:
        summary = "paw bundle skill installed; Z Code app binary not found."
        status = "degraded"

    return ZCodeSetupResult(
        status=status,
        skill_path=str(target),
        app_path=str(app_path) if app_path else None,
        path_ready=path_ready,
        summary=summary,
    )
