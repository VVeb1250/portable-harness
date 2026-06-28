# DeepSeek Handoff — Memory Repair and ICM Memories/Memoirs

Date: 2026-06-29
Repo: `E:\portable-harness`
Owner intent: save Codex context/tokens; DeepSeek should implement the next memory slice, then Codex will review.

## Current State

The repo has uncommitted work unrelated to this handoff:

- `paw/__main__.py`
- `paw/router_block.py`
- `paw/surface_audit.py`
- `tests/test_router_block.py`
- `tests/test_surface_audit.py`

Those files contain the new router adoption-posture work. Do not revert them.
Avoid editing them unless absolutely necessary for this memory task.

The active memory problem is real:

- Old sessions wrote too many `pending` memories.
- This session mostly did not write useful durable memory.
- `paw memory hook` covers mesh/poll/heartbeat, but not all durable-write lanes.
- `paw reflect --capture` writes coarse mistake candidates to ICM `pending`.
- `paw curate` is intended to promote `pending` into durable ICM `mistakes`, but a live smoke found unreliable behavior.
- ICM has both **Memories** and **Memoirs**; the system should use both, not treat them as synonyms.

## Live Evidence Already Observed

Do not rerun destructive memory commands blindly.

Safe observations:

```powershell
python -m paw doctor --host codex --json
python -m paw curate --dry-run --limit 10
icm.exe topics --read-only
icm.exe list -t pending --format json --no-embeddings --read-only
icm.exe memoir --help
```

Observed facts:

- `pending` count is around `99`.
- `paw curate --dry-run --limit 10` shows many command/probe failures.
- Command/probe failures are **not automatically noise**. Many are useful recurring mistakes.
- `paw curate --limit 1 --json` reported `applied=1`, but follow-up checks showed:
  - `pending` did not decrease.
  - `mistakes` did not increase.
  - the same pending item was still recallable.
- Direct smoke:

```powershell
icm.exe store -t curate-smoke -c "paw curate smoke test" -i low -k "curate-smoke"
icm.exe list -t curate-smoke --format json --no-embeddings --read-only
```

The store printed `Stored: <id>`, but `list -t curate-smoke` returned `[]`.
This suggests an ICM write/read contract mismatch, topic listing issue, DB/backend mismatch, or a store false-success path.
Do not assume `returncode == 0` means the memory is visible.

## Design Decisions to Preserve

### Memories vs Memoirs

Use ICM **Memories** as atomic, searchable evidence:

- `pending`: unreconciled reflection candidates; never treated as truth.
- `decisions`: user-approved decisions.
- `mistakes`: trigger -> fix lessons, especially reusable command/platform/tool mistakes.
- `lessons`: durable observations that are not exactly mistakes.
- `portable-harness/blackboard/<run-id>`: run-scoped team handoff.

Use ICM **Memoirs** as curated concept graph:

- project mental model;
- stable architecture concepts;
- relationships among concepts;
- refined definitions from curated Memories only.

Never distill raw transcript or `pending` directly into Memoirs.
First safe Memoir: `portable-harness`, distilled only from curated `decisions` and `lessons`.

### Command/Probe Failure Policy

Do not blanket-drop command failures.

Promote when reusable:

- shell/platform contract mistake, e.g. Bash heredoc in PowerShell;
- CLI argument contract, e.g. repeated `--keywords` vs comma-separated keywords;
- alias/path ambiguity, e.g. `icm` vs PowerShell `Invoke-Command`, use `icm.exe`;
- Windows JSON/argv/quoting failure;
- PowerShell-specific command mismatch;
- command failed, then a clear fixed command succeeded.

Skip when not reusable:

- intentional availability probe;
- TDD red-phase test failure;
- one-off typo;
- missing file while exploring paths;
- failure without a reusable fix pattern.

Target warning shape:

```text
trigger: shell=powershell + command contains "python - <<"
warn: PowerShell does not support Bash heredoc. Use @' ... '@ | python -
```

## Full Memory Design Context

The memory repair task is not only a `paw curate` bug fix. It is part of a
larger design discussion about making memory productive across ordinary Codex
sessions, Claude Code, Z Code, and the Team runtime.

The current design has four lanes:

1. **Working Memory**
   - `paw memory` mesh and ICM blackboard.
   - Short-lived coordination: member registry, heartbeat, shared/private lanes,
     locks, cursors, and run-scoped handoff.
   - This is allowed to be chatty because it is not durable wiki memory.

2. **Pending Reflection**
   - `paw reflect --capture` scans transcript deltas on Stop and writes coarse
     candidates to ICM `pending`.
   - It is not truth. It is raw ore.
   - It must be bounded, classified, and curated before becoming durable memory.

3. **Decision / Lesson Memories**
   - ICM Memories topics such as `decisions`, `mistakes`, and `lessons`.
   - These are atomic, searchable, durable entries.
   - Decisions need explicit user signal or manual write; mistakes can come from
     curated pending when reusable.

4. **Memoirs**
   - ICM Memoirs are the permanent concept graph / mental model layer.
   - Only curated Memories may feed Memoirs.
   - Memoirs should model architecture and trade-offs, not raw events.

The system needs one policy point:

```text
hook / reflect / team / z-code / manual
        ↓
MemoryEvent
        ↓
MemorySink / MemoryPolicy
        ↓
drop | mesh | pending | memories | memoirs
```

This is the main anti-wander anchor: do not build separate ad hoc write paths
for hooks, TeamKernel, Z Code, and manual commands.

## Hook Coverage Design

The owner specifically wants hook coverage audited and made legible. Current
coverage is easy to misunderstand because several hooks exist but cover different
lanes.

Existing behavior:

- `paw memory hook`
  - SessionStart: register member + poll mesh + pending hygiene nudge.
  - UserPromptSubmit: heartbeat + poll mesh + pending hygiene nudge.
  - Stop: heartbeat + pending hygiene nudge.
  - It does **not** write durable Memories.

- `paw reflect --capture`
  - Stop hook.
  - Reads transcript delta through watermark.
  - Writes coarse candidates to `pending`.

- `paw curate --surface`
  - SessionStart hook.
  - Currently previews pending; when pending is high this can be too noisy.
  - Should be one-line hygiene by default, with detailed preview only when
    explicitly requested by the user.

- `paw surface`
  - Prompt/context router for hosts without native hook parity, including Z Code
    manual integration.

Required hook coverage output:

`paw doctor` should clearly report per host and per lane:

```text
host           recall-push  mesh-hook  reflect-stop  curate-start  team-sink  memoir-sync
codex          yes/no       yes/no     yes/no        yes/no        yes/no     yes/no
claude-code    yes/no       yes/no     yes/no        yes/no        yes/no     yes/no
z-code         manual       manual     no/manual     no/manual     no/manual  no
```

Do not report "memory hooks present" as one vague status. That is exactly how we
got confused.

Efficiency expectation:

- Hook output must be silent unless there is new mesh info, held locks, or a
  short hygiene warning.
- Pending preview in hooks must be bounded to one line by default.
- No hook should auto-promote durable wiki memory.
- Stop capture must use transcript watermark/delta, not rescan whole sessions.

## Team Runtime Memory Design

Team runtime is currently sequential in-process but writes/reads the ICM
blackboard. It must participate in the same MemorySink policy instead of having
its own durable write logic.

Desired TeamKernel memory behavior:

1. At run start:
   - write/ensure a blackboard run scope;
   - optionally post a mesh event that a team run has started.

2. During run:
   - planner/implementer/mutator/reviewer/evaluator write bounded blackboard
     entries only;
   - no direct durable `decisions`/`mistakes` writes during role chatter.

3. At run end:
   - create one `MemoryEvent(kind="handoff" | "result")` summary through
     MemorySink;
   - on success, the sink may plan a durable `lessons`/`decisions` write only
     if the summary contains explicit decision or reusable lesson signals;
   - on failure, the sink may plan a `pending` mistake candidate if there is a
     clear reusable failure/fix.

4. Review gate:
   - evaluator/reviewer result is the earliest place where a run summary is
     trustworthy enough for memory promotion.

Minimum first slice for Team runtime:

- add a pure planning hook/seam in TeamKernel or adapter layer that produces the
  intended MemorySink event at completion;
- unit-test it without live ICM writes;
- keep actual write disabled or injectable until curate/write verification is
  trustworthy.

## Z Code / Manual Host Design

Z Code currently has skill/manual integration, not full hook parity.

The design should keep Z Code honest:

- `paw surface` at task start for routing/memory hints;
- `paw memory hook --host z-code ...` can be called manually/skill-assisted for
  mesh poll/register;
- durable handoff uses `paw memory post` or future `paw remember`;
- no claim of automatic transcript Stop capture unless verified.

Doctor should report Z Code as `manual` rather than `healthy automatic`.

## Implementation Goal

Implement a small, test-first memory repair slice:

1. Make `paw curate` honest.
2. Add a reusable command-mistake classifier.
3. Add a MemorySink policy skeleton that all future hook/team/z-code/manual writes can share.
4. Add hook coverage reporting design/tests, at least for doctor output structure.
5. Add Team runtime memory planning seam/tests, with no live durable writes yet.
6. Add a Memoirs/Memories plan wrapper or docs scaffold, but do not auto-write Memoirs yet.

Keep this scoped. Do not add a daemon. Do not add MCP memory servers.

## Required TDD Work

Start with failing tests. Suggested files:

- `tests/test_curate.py`
- `tests/test_memory_sink.py` (new)
- optionally `tests/test_memoir_policy.py` (new)

### Test 1: Curate Does Not Report False Success

Add a regression test where:

- store runner returns `0`;
- verification runner/list/recall cannot see the new memory;
- result must mark the decision as `skip` or `failed`;
- `applied` must remain `0`;
- render must include a reason like `store verification failed`.

If the current design lacks a verification seam, add one.

### Test 2: Forget Must Be Verified

Add a test where:

- store succeeds and verifies visible;
- forget returns `0`;
- pending item still appears after forget;
- result must not claim pending drained.

Either downgrade to `skip` or report `applied=1, drained=0`; choose the clearer model and update render/JSON.

### Test 3: Command Mistake Classifier

Add classifier tests:

Promote:

- `python - <<'PY'` in PowerShell -> fix `@' ... '@ | python -`
- `icm store ... --keywords a --keywords b` -> fix comma-separated keywords
- `Format-Hex -Count` unsupported -> fix available PowerShell-compatible command
- `Cannot overwrite variable Host` -> fix use `$hostName` instead of `$Host`

Skip:

- pytest red-phase failure
- missing file during exploration
- `Get-Command` availability probe with no reusable fix

Classifier output should be deterministic:

```python
{
  "op": "promote" | "skip",
  "category": "shell-contract" | "cli-contract" | "probe" | ...,
  "summary": "...",
  "trigger": "...",
  "fix": "...",
}
```

### Test 4: MemorySink Policy Skeleton

Add a small module, likely `paw/memory_sink.py`.

It should classify write intent:

- `decision` -> Memories topic `decisions`, explicit/manual only
- `mistake` -> Memories topic `mistakes`, only after curate/classifier confidence
- `handoff` -> blackboard topic or mesh, depending durability
- `memoir` -> blocked unless source is curated `decisions`/`lessons`
- `pending` -> allowed from reflect only

No live ICM writes are needed for the first slice. A pure planning function is enough.

### Test 5: Memoir Gate

Add a test that raw `pending` cannot be distilled into Memoir by the paw wrapper/policy.

Allowed sources:

- `decisions`
- `lessons`
- maybe `mistakes` only after recurrence threshold, if you choose to support it

Blocked sources:

- `pending`
- raw transcript
- blackboard run entries unless explicitly promoted first

### Test 6: Hook Coverage Matrix

Add tests for a small hook coverage model, probably in `paw.doctor` or a new
helper module.

It should distinguish these lanes:

- recall push / `paw surface` or `paw_block`
- mesh hook / `paw memory hook`
- reflect stop / `paw reflect --capture`
- curate session start / `paw curate --surface`
- team sink
- memoir sync

The important behavior is that a host with only `paw memory hook` is not reported
as having complete durable memory coverage.

### Test 7: Team Runtime Memory Planning

Add tests for a pure planning seam. Example:

- successful TeamKernel run -> planned MemorySink event kind `result` or `handoff`;
- failed evaluator -> planned MemorySink event kind `pending` or `mistake-candidate`;
- no live ICM write is performed by default;
- event includes project, run_id, status, summary, artifacts, and route metadata.

Keep this injectable, so Codex can review without external agent calls.

## Suggested Code Shape

Do not overbuild. Suggested modules:

```text
paw/command_mistakes.py
paw/memory_sink.py
```

`paw.curate` should call the command classifier during `reconcile`.

Possible minimal model:

```python
@dataclass
class ApplyReceipt:
    stored: bool
    visible: bool
    forgotten: bool
    reason: str = ""
```

The important rule:

```text
returncode == 0 is necessary but not sufficient
```

Store is successful only if the new memory is visible through read path.
Forget is successful only if the pending id disappears from pending list.

## Commands to Verify

Focused first:

```powershell
python -m pytest -q tests/test_curate.py tests/test_memory_sink.py
python -m compileall -q paw
```

Then:

```powershell
python -m pytest -q tests/test_memory_hook.py tests/test_reflection.py tests/test_curate.py
```

Before stopping:

```powershell
rtk git diff --stat
rtk git status --short --branch
```

Full suite currently has a known unrelated live-state failure:

- `tests/test_doctor.py::DoctorTests::test_mesh_check_in_report`
- Cause: test touches live `~/.paw/state/memory-mesh/portable-harness` and cannot remove a non-empty live directory.

Do not spend the memory repair budget on that unless directly asked.

## Hard Constraints

- Do not run `python -m paw curate` without `--dry-run` or without a very small `--limit`.
- Do not run `icm.exe forget -t pending`.
- Do not auto-create Memoirs from `pending`.
- Do not add a daemon.
- Do not add an MCP memory server.
- Do not rewrite unrelated router posture changes.
- Preserve user worktree changes.
- Use `python -m paw`, not `py -m paw`.
- On PowerShell call `icm.exe` explicitly, not `icm`.

## Prompt To Give DeepSeek

Use this prompt, not the shorter curate-only prompt:

```text
Read E:\portable-harness\docs\HANDOFF-DEEPSEEK-MEMORY-REPAIR-2026-06-29.md and implement the memory repair/design slice exactly.

This is not only a paw curate bugfix. Keep the full memory design in scope:
1. honest paw curate verification,
2. reusable command/probe mistake classifier,
3. MemorySink/MemoryPolicy skeleton shared by hooks, Team runtime, Z Code, and manual writes,
4. hook coverage matrix so doctor can distinguish mesh hook vs reflect Stop vs curate SessionStart vs recall push vs team sink vs memoir sync,
5. TeamKernel memory planning seam with no live durable write by default,
6. Memories vs Memoirs gate: Memoirs only from curated Memories, never pending/raw transcript.

Start with failing tests. Do not touch unrelated router posture files. Do not run unbounded paw curate. Do not auto-write Memoirs. Keep the first slice small and reviewable.
```

## Deliverable Expected From DeepSeek

Return:

- files changed;
- tests added;
- exact verification commands and outputs;
- whether live ICM write/read mismatch is fixed, worked around, or still blocked;
- any remaining unsafe memory operations that Codex should review.

Codex will review the diff afterwards.
