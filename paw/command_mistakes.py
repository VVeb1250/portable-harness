"""Deterministic command/probe mistake classifier.

Classifies shell execution errors as reusable lessons or transient noise.
Zero LLM — pure pattern matching. Used by paw.curate during reconcile to
decide whether a pending command-failure candidate should become a durable
mistake entry.

Classifier output:

    {"op": "promote", "category": "shell-contract",  "summary": "...",
     "trigger": "...", "fix": "..."}
    {"op": "skip",    "category": "probe",            "summary": "...",
     "trigger": "", "fix": ""}

The classification is flat and deterministic.  Every category has a
promote-able fix pattern so the caller can format a mistake candidate
on the spot.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

ClassifierOp = Literal["promote", "skip"]
ClassifierCategory = Literal[
    "shell-contract",
    "cli-contract",
    "platform-gotcha",
    "probe",
    "test-noise",
    "exploration",
    "one-off",
]

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_STOP = {
    "the", "and", "for", "that", "this", "with", "not", "was", "are", "from",
    "have", "you", "your", "use", "using", "into", "out", "via", "but", "all",
}

# -- promote patterns ----------------------------------------------------------

class Rule:
    def match(self, cmd: str, text: str) -> ClassifyResult | None:
        raise NotImplementedError


@dataclass
class PatternRule(Rule):
    """Match a regex against command + error text → promote with structured fix."""

    trigger_re: re.Pattern
    category: ClassifierCategory
    summary: str
    fix: str
    cmd_re: re.Pattern | None = None

    def match(self, cmd: str, text: str) -> ClassifyResult | None:
        clean = cmd.split("→", 1)[0]
        if self.cmd_re and not self.cmd_re.search(clean):
            return None
        m = self.trigger_re.search(text)
        if not m:
            return None
        return ClassifyResult(
            op="promote",
            category=self.category,
            summary=self.summary,
            trigger=m.group(0) if m.lastindex is None else m.group(0),
            fix=self.fix,
        )


@dataclass
class CmdRule(Rule):
    """Match a command pattern only (no error text needed).

    Only matches against the cmd text *before* any ``→`` marker — the
    post-arrow text (e.g. ``→ fixed by:``) is a heuristic suffix, not
    part of the original command, and must not influence classification.
    """

    cmd_re: re.Pattern
    category: ClassifierCategory
    summary: str
    fix: str

    def match(self, cmd: str, text: str) -> ClassifyResult | None:
        clean = cmd.split("→", 1)[0]
        m = self.cmd_re.search(clean)
        if not m:
            return None
        return ClassifyResult(
            op="promote",
            category=self.category,
            summary=self.summary,
            trigger=m.group(0) if m.lastindex is None else m.group(0),
            fix=self.fix,
        )


_PROMOTE_RULES: list[Rule] = [
    # PowerShell heredoc — Bash <<'PY' in PowerShell
    CmdRule(
        cmd_re=re.compile(r'(?:py|python)\s+-{1,2}\s*(?:c\s+)?<<', re.I),
        category="shell-contract",
        summary="PowerShell does not support Bash heredoc ('<<'). "
                "Use at-sign here-string with pipeline.",
        fix=r"@'...'@ | python -",
    ),
    PatternRule(
        trigger_re=re.compile(
            r"&&.*not a valid statement separator|"
            r"The token '&&' is not a valid statement separator|"
            r"At line:\d+ char:\d+",
            re.I,
        ),
        cmd_re=re.compile(r"&&"),
        category="shell-contract",
        summary=(
            "Windows PowerShell 5.1 does not support '&&' as a statement "
            "separator."
        ),
        fix="Run commands separately, use ';', or use explicit if ($LASTEXITCODE -eq 0).",
    ),
    # icm --keywords multiple args vs comma-separated (icm expects one -k value)
    # NOTE: cmd_re intentionally omitted — the error text mentioning
    # ``--keywords <KEYWORDS>`` is uniquely icm; no other CLI tool has
    # this flag name or error message.  A cmd_re would miss entries
    # where the raw command was not captured in the pending summary.
    PatternRule(
        trigger_re=re.compile(
            r"the argument .--keywords <KEYWORDS>. cannot be used",
            re.I,
        ),
        category="cli-contract",
        summary=(
            "icm --keywords may not accept multiple --keywords flags. "
            "Use a single comma-separated value."
        ),
        fix="--keywords keyword1,keyword2 instead of --keywords k1 --keywords k2",
    ),
    # Format-Hex -Count not available on older PS or Windows.
    # Also catches "A parameter cannot be found that matches parameter name 'Count'".
    PatternRule(
        trigger_re=re.compile(
            r"(?:Format-Hex|format-hex)\b.*(?:not recognized|not found|"
            r"is not a valid|Could not find|cannot be found|"
            r"cannot find|matches parameter name)",
            re.I,
        ),
        cmd_re=re.compile(r"Format-Hex", re.I),
        category="platform-gotcha",
        summary=(
            "Format-Hex with -Count is not available in some PowerShell versions. "
            "Use an alternative or check PS version."
        ),
        fix=(
            "Use `Format-Hex -Count` only on PS 5.1+ or Windows 10+; "
            "fall back to `certutil -encodehex` or format via .NET."
        ),
    ),
    # Cannot overwrite variable Host
    PatternRule(
        trigger_re=re.compile(
            r"overwrite variable\s+'?Host'?",
            re.I,
        ),
        cmd_re=re.compile(r"\$Host\b", re.I),
        category="platform-gotcha",
        summary=(
            "$Host is a PowerShell automatic variable and cannot be set. "
            "Use a different variable name."
        ),
        fix="Use $hostName or $hostAddr instead of $Host",
    ),
    # icm without .exe in PowerShell (Invoke-Command alias)
    CmdRule(
        cmd_re=re.compile(r'(?<![.\w])icm\s(?!\.exe\b)'),
        category="cli-contract",
        summary=(
            "PowerShell has a built-in 'icm' alias for Invoke-Command. "
            "Always use 'icm.exe' to call the ICM CLI."
        ),
        fix="Use icm.exe instead of icm",
    ),
    # PowerShell redirect stderr to stdout
    PatternRule(
        trigger_re=re.compile(
            r"2>&1|The string is missing the terminator",
            re.I,
        ),
        cmd_re=re.compile(
            r"\b(?:powershell|pwsh)\b|@'|@\"|<#",
            re.I,
        ),
        category="platform-gotcha",
        summary=(
            "PowerShell stderr redirection wrapping can produce 'NativeCommandError' "
            "error records. Avoid 2>&1 on native exes in PowerShell 5.1."
        ),
        fix="Capture stderr separately or use `--%` stop-parsing token; "
             "on native exes use `cmd /c <command>` to avoid PS wrapping.",
    ),
    # pytest --forked or xdist not installed
    PatternRule(
        trigger_re=re.compile(
            r"ERROR:\s*could not find|pytest: error:|unrecognized arguments",
            re.I,
        ),
        cmd_re=re.compile(r"pytest|pytest\.exe|py\s+-m\s+pytest", re.I),
        category="cli-contract",
        summary="Missing pytest plugin or unrecognized flag.",
        fix="Install missing plugin (pip install <pkg>) or remove unrecognized flags.",
    ),
    # ast-grep no files found for pattern
    PatternRule(
        trigger_re=re.compile(
            r"Could not find files for the given pattern",
            re.I,
        ),
        category="cli-contract",
        summary="ast-grep pattern matched no files.",
        fix="Check the pattern syntax and the target directory; try a broader pattern.",
    ),
    # gitleaks detect on stdin issue
    PatternRule(
        trigger_re=re.compile(
            r"gitleaks.*(?:not find|no leaks|no source)",
            re.I,
        ),
        cmd_re=re.compile(r"gitleaks", re.I),
        category="cli-contract",
        summary="gitleaks detected no source or found no leaks.",
        fix="gitleaks needs either stdin pipe or --source flag pointing to a git repo.",
    ),
    # Python module not found (import error in CLI context)
    PatternRule(
        trigger_re=re.compile(
            r"ModuleNotFoundError|No module named",
            re.I | re.M,
        ),
        cmd_re=re.compile(
            r"(?:py|python)\s+(?:-m\s+)?",
            re.I,
        ),
        category="cli-contract",
        summary="Python module not installed or not on sys.path.",
        fix="Install the module: `pip install <module>` or activate the right venv.",
    ),
]

# -- skip patterns -------------------------------------------------------------

_SKIP_RULES: list[Rule] = [
    # pytest red-phase (test failure during normal TDD) — expected iteration.
    # PatternRule with error-text check so missing-plugin errors (e.g.
    # "ERROR: could not find") are promoted as cli-contract, not skipped.
    PatternRule(
        trigger_re=re.compile(
            r"(?:FAILED\s+\S+::\S+|failed:\s+(?:AssertionError|Error|Failed))",
            re.I,
        ),
        cmd_re=re.compile(
            r"(?:py|python)\s+(?:-m\s+)?pytest",
            re.I,
        ),
        category="test-noise",
        summary="TDD red-phase test failure — expected iteration, not a reusable mistake.",
        fix="",
    ),
    # Inline probe commands: py -c, python -c, node -e.
    # PatternRule with error-text check so a PS stderr-gotcha on `python -c 2>&1`
    # is still promoted rather than swallowed by a broad command-only rule.
    PatternRule(
        trigger_re=re.compile(
            r"SyntaxError|ModuleNotFoundError|ImportError|ReferenceError|type error",
            re.I,
        ),
        cmd_re=re.compile(
            r"^\s*(?:py|python\d?|python|node)\s+-[ce]\b",
            re.I,
        ),
        category="probe",
        summary="Inline one-liner probe failure — exploration noise, not durable.",
        fix="",
    ),
    # Missing file during exploration (globbing the wrong path)
    PatternRule(
        trigger_re=re.compile(
            r"(?:No such file|not found|Cannot find path|could not find file)",
            re.I,
        ),
        cmd_re=re.compile(r"ls|dir|Get-ChildItem|cat|less|type|globb|glob\.glob", re.I),
        category="exploration",
        summary="Missing file while exploring paths — not a reusable pattern.",
        fix="",
    ),
    # Availability probe (Get-Command, which, where) — always disposable
    CmdRule(
        cmd_re=re.compile(
            r"\b(?:Get-Command|which\b|where\b|gcm\b|type\s+python)",
            re.I,
        ),
        category="probe",
        summary="Command availability probe — not a mistake worth remembering.",
        fix="",
    ),
    # Rg empty match / no results — exploration.
    # Only skip when rg itself reports no matches or missing-path;
    # authentic rg failures (regex syntax, OS error on specific file)
    # are genuine mistakes worth promoting.
    PatternRule(
        trigger_re=re.compile(
            r"(?:no output|No results found|"
            r"the system cannot find the file|os error 2|"
            r"could not find file)",
            re.I,
        ),
        cmd_re=re.compile(r"\brg\b"),
        category="exploration",
        summary="ripgrep returned no results — exploration noise.",
        fix="",
    ),
    # Git diff empty or no changes
    CmdRule(
        cmd_re=re.compile(r"\bgit\s+diff"),
        category="exploration",
        summary="Git diff returned nothing — not a reusable mistake.",
        fix="",
    ),
    # Truncated traceback — no specific error, just traceback header
    PatternRule(
        trigger_re=re.compile(
            r"shell_command failed: Traceback \(most recent call last\)",
        ),
        category="exploration",
        summary="Truncated traceback capture — no specific error to learn from.",
        fix="",
    ),
    # Truncated test runner output (dots + F + percentage)
    PatternRule(
        trigger_re=re.compile(
            r"(?:shell_command failed:\s+)?[.F]{2,}\s*\[?\s*\d+%\s*\]?\s*$",
        ),
        category="test-noise",
        summary="Truncated test runner output — not a durable mistake.",
        fix="",
    ),
    # Daemon startup logs, not command mistakes
    PatternRule(
        trigger_re=re.compile(
            r"level=\w+\s+msg=(?:mem\.init|budget_mb)",
        ),
        category="exploration",
        summary="Daemon startup log — not a command mistake.",
        fix="",
    ),
    # Paw doctor / status output
    PatternRule(
        trigger_re=re.compile(
            r"(?:^|shell_command failed: )paw doctor:|"
            r"efficiency-min: drifted|^status= degraded|pending= \d+",
        ),
        category="exploration",
        summary="Paw doctor/status output — not a command mistake.",
        fix="",
    ),
    # MCP tool execution failures (transient)
    PatternRule(
        trigger_re=re.compile(
            r"^mcp__\w+ failed:",
        ),
        category="exploration",
        summary="MCP tool execution failure — transient or config issue, "
                "not a reusable mistake.",
        fix="",
    ),
    # Network errors (transient)
    PatternRule(
        trigger_re=re.compile(
            r"connectex:|dial tcp|connection refused|no route to host",
            re.I,
        ),
        category="exploration",
        summary="Transient network error — not a durable command mistake.",
        fix="",
    ),
    # Brace/JSON parsed as error
    PatternRule(
        trigger_re=re.compile(
            r"(?:^|shell_command failed: )\s*[\{\[\]\}]\s*(?:→|$)",
        ),
        category="exploration",
        summary="Parsed shell output captured as error — not a command mistake.",
        fix="",
    ),
]


# -- classifier ----------------------------------------------------------------


@dataclass
class ClassifyResult:
    op: ClassifierOp
    category: ClassifierCategory
    summary: str
    trigger: str
    fix: str
    keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "op": self.op,
            "category": self.category,
            "summary": self.summary,
            "trigger": self.trigger,
            "fix": self.fix,
        }

    def mistake_keywords(self) -> list[str]:
        kw = [f"type:{self.category}"]
        if self.keywords:
            kw.extend(self.keywords)
        tokens = _WORD.findall(self.summary.lower())
        kw.extend(t for t in tokens if len(t) >= 4 and t not in _STOP)
        return kw[:8]


def classify(cmd: str, error_text: str) -> ClassifyResult:
    """Classify a single command+error pair.

    `cmd` is the command text.
    `error_text` is the full error output.

    Returns a ClassifyResult.  If no rule fires, defaults to ``promote``
    with category ``one-off`` — better to surface a reusable candidate
    than silently drop a genuine lesson.
    """
    # Skip rules fire first — they represent cases that are NEVER worth promoting.
    # CmdRule/PatternRule hardcode op="promote" so we flip the op here.
    for rule in _SKIP_RULES:
        result = rule.match(cmd, error_text)
        if result is not None:
            result.op = "skip"
            return result

    # Promote rules
    for rule in _PROMOTE_RULES:
        result = rule.match(cmd, error_text)
        if result is not None:
            return result

    # Default: promote as one-off (the existing heuristic behavior)
    return ClassifyResult(
        op="promote",
        category="one-off",
        summary=error_text.splitlines()[0][:140] if error_text.strip() else cmd[:140],
        trigger=cmd[:120],
        fix="",
    )
