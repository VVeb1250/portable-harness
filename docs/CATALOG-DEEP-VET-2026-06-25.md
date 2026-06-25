# Catalog deep-vet — 2026-06-25

## Goal

Expand paw's Catalog around three product constraints:

1. portable across agent hosts and operating systems,
2. reduce context, tool calls, or feedback-loop output,
3. improve deterministic quality without creating an always-on tool tax.

This review treats a tool as a catalog component only when its role, adoption
mode, and evidence level are explicit. Being useful is not enough to make a
tool a default install.

## Decision summary

| Set | Anchor | Catalog status | Decision |
|---|---|---:|---|
| `harness-foundation` | Everything Claude Code (ECC) | `detect-first` | Reuse an existing ECC installation. Do not stack plugin and full/manual installs. |
| `context-workbench` | context-mode | `conditional` | Project-scoped retrieval layer for bulky material; not a global default because its static schema cost can exceed its savings on small work. |
| `repo-pack` | code2prompt | `ready` | Portable, host-neutral repo packaging. Keep Repomix as an optional feature-rich challenger. |
| `test-affected` | pytest-testmon | `conditional` | Adopt for Python projects with a full-suite fallback. Add other languages through their native runners, not a premature universal wrapper. |
| `quality-gate` | prek, actionlint, lychee | `candidate` | Good deterministic fit, but require pinned Windows/Linux/macOS smoke tests before linker support. |
| `api-quality` | Hurl | `candidate` | Strong browser-free API contract layer; require cross-OS fixture and compact-output verification before promotion. |
| optional code intelligence | Gortex | `deferred` | CLI augmentation only. Never run invasive repository initialization by default and never register the full MCP surface globally. |

## Load-bearing findings

### Context-mode

- Official package reviewed at v1.0.166.
- Supports Codex and multiple operating systems, with hooks and an MCP surface.
- Local retrieval probes showed very large savings for indexed lexical
  retrieval, but the live tool definitions add roughly 7,900 tokens to a
  load-all session.
- Correct adoption mode: enable per project when repeated bulky retrieval is
  expected; keep it absent for small or direct read/edit sessions.

Verdict: valuable workbench, poor universal default.

### Everything Claude Code

- Official v2.0.0 project is MIT licensed and supports multiple agent hosts.
- ECC is a harness foundation and curated component distribution, not another
  always-on MCP server.
- Its installer modes can overlap. paw must detect and describe the existing
  install before offering a host-specific installation path.

Verdict: detect and reuse; never blindly layer installations.

### Gortex

- Official v0.52.0 release and Apache-2.0 license were verified.
- Local Windows binary and repository probes showed strong symbol, semantic,
  and multi-repository capabilities.
- Default initialization is invasive and the daemon/index carries disk and
  memory cost. Its broad MCP surface also conflicts with paw's low-idle-tax
  goal.

Verdict: defer from default bundles. Permit explicit, scoped CLI augmentation
without `gortex init`; reconsider a minimal read-only MCP preset only after a
measured workload justifies it.

### Repo packaging

- code2prompt v4.2.0 provides a Rust CLI, git-aware filtering, templates, token
  counting, and official binaries for Windows, Linux, Intel macOS, and Apple
  Silicon macOS.
- Repomix adds Secretlint, Tree-sitter compression, budget controls, and
  remote-repository support, but introduces a Node runtime.

Verdict: code2prompt is the portable default. Repomix is an opt-in alternative,
not a second default installation.

### Affected-test selection

- pytest-testmon v2.2.0 was locally exercised.
- No-change and comment-only probes selected zero tests.
- A real router edit selected 4 of 14 router tests and was about eight times
  faster on this small repository.

Verdict: adopt for Python with explicit cache-miss/config uncertainty fallback
to the complete suite.

### Missing deterministic quality categories

The prior catalog covered security, code navigation, research, browser
automation, data, documents, and design, but lacked portable deterministic
gates around repository lifecycle:

- `prek`: fast pre-commit-compatible hook orchestration;
- `actionlint`: static GitHub Actions validation, including expression and
  script-injection checks;
- `lychee`: documentation and website link validation;
- `Hurl`: language-neutral HTTP contract tests with compact test output.

These tools avoid MCP schema cost and can fail early before an expensive agent
or CI repair loop. They remain candidates until installer commands and output
behavior pass the cross-OS workflow.

## Catalog policy derived from the review

- Prefer CLI, hook, or project dependency when it provides the same capability
  as an MCP server.
- A default set must have a bounded role and no unnecessary duplicate anchor.
- Detect-first tools modify an existing harness and require install-state
  discovery before any action.
- Conditional tools need a workload or project predicate.
- Candidate tools are discoverable but must not be installed by the linker.
- Deferred tools remain documented evidence, not an install choice.
- Every promoted set must pass:
  - Windows, Linux, Intel macOS, and Apple Silicon macOS smoke coverage where
    the vendor ships those targets;
  - Claude Code and Codex host-shape validation;
  - install, verify, unlink, and rollback behavior;
  - a compact-output or token/turn measurement appropriate to its role.

## Primary sources

- context-mode: <https://github.com/mksglu/context-mode>
- Everything Claude Code: <https://github.com/affaan-m/everything-claude-code>
- Gortex: <https://github.com/robertpiosik/gortex>
- code2prompt: <https://github.com/mufeedvh/code2prompt>
- Repomix: <https://github.com/yamadashy/repomix>
- pytest-testmon: <https://github.com/tarpas/pytest-testmon>
- prek: <https://github.com/j178/prek>
- actionlint: <https://github.com/rhysd/actionlint>
- Lychee: <https://github.com/lycheeverse/lychee>
- Hurl: <https://github.com/Orange-OpenSource/hurl>

## Next implementation boundary

The linker should initially expose only `ready` sets. `conditional` and
`detect-first` sets require a preflight explanation and explicit user choice.
`candidate` and `deferred` sets are listable but not installable.

The next implementation slice is therefore:

1. formalize status-aware catalog commands,
2. add Claude Code and Codex host adapters,
3. link one ready set safely,
4. verify, unlink, and rollback,
5. execute the cross-OS GitHub Actions matrix,
6. promote candidates only after their evidence gates pass.
