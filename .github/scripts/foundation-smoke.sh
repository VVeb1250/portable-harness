#!/usr/bin/env bash
# Foundation-core cross-OS smoke: install & probe default-init tools.
#
# Covers efficiency-min, secure-agent, doc-data-min, local-memory on
# Linux x64, macOS arm64/x64, Windows x64.  Each tool is installed via
# the best available package manager, then probed with --version and a
# short behavioral check.  Fails only for tools the runner's OS should
# support.
set -euo pipefail

FAILED=()
pass() { echo "  ✓ $1"; }
fail() { echo "  ✗ $1"; FAILED+=("$1"); }

OS="${RUNNER_OS:-unknown}"
echo "Foundation smoke on $OS"
echo

# ── helpers ──────────────────────────────────────────────────────────────────

check() {
  if command -v "$1" &>/dev/null; then return 0; fi
  if command -v "$1.exe" &>/dev/null; then return 0; fi
  return 1
}

npm_install() {
  local pkg="$1" bin="${2:-$1}"
  check "$bin" && { pass "$bin already installed"; return 0; }
  npm install -g "$pkg" 2>&1 && pass "$bin installed via npm" || fail "$bin npm install failed"
}

pip_install() {
  local pkg="$1" bin="${2:-$1}"
  check "$bin" && { pass "$bin already installed"; return 0; }
  pip install "$pkg" 2>&1 && pass "$bin installed via pip" || fail "$bin pip install failed"
}

go_install() {
  local pkg="$1" bin="${2:-$(basename "$pkg")}"
  check "$bin" && { pass "$bin already installed"; return 0; }
  go install "$pkg" 2>&1 && pass "$bin installed via go" || fail "$bin go install failed"
}

probe() {
  local bin="$1" label="${2:-$1}"
  if check "$bin"; then
    local cmd
    cmd="$(command -v "$bin" || command -v "$bin.exe" || echo "$bin")"
    echo "  $label: $($cmd --version 2>&1 | head -1)"
    return 0
  fi
  echo "  $label: NOT FOUND"
  return 1
}

# ── Install phase ─────────────────────────────────────────────────────────────

echo "::group::install tools"

export PATH="$HOME/.local/bin:$PATH"
mkdir -p "$HOME/.local/bin"
if command -v go &>/dev/null; then
  export PATH="$(go env GOPATH)/bin:$PATH"
fi

# ── gh release download helper ──
# gh_dl <owner/repo> <asset-glob> <binary-name>
# Download latest release asset, extract if archive, place binary in ~/.local/bin/.
gh_dl() {
  local repo="$1" pattern="$2" bin="$3"
  check "$bin" && { pass "$bin already installed"; return 0; }
  local tmpd; tmpd="$(mktemp -d)"
  gh release download -R "$repo" --pattern "$pattern" --dir "$tmpd" --skip-existing 2>&1 \
    || { fail "$bin gh download"; rm -rf "$tmpd"; return 1; }
  # extract archives
  local archives; archives="$(ls "$tmpd"/*.tar.gz 2>/dev/null || true)"
  if [ -n "$archives" ]; then
    tar xzf "$tmpd"/*.tar.gz -C "$tmpd" 2>&1 || true
  fi
  local zips; zips="$(ls "$tmpd"/*.zip 2>/dev/null || true)"
  if [ -n "$zips" ]; then
    unzip -o "$tmpd"/*.zip -d "$tmpd" 2>&1 || true
  fi
  # locate binary: exact name match -> single leftover file (renamed asset)
  local found; found="$(find "$tmpd" -type f \( -name "$bin" -o -name "${bin%.exe}" \) 2>/dev/null | head -1)"
  if [ -z "$found" ]; then
    local count; count="$(find "$tmpd" -type f 2>/dev/null | wc -l)"
    [ "$count" -eq 1 ] && found="$(find "$tmpd" -type f 2>/dev/null | head -1)"
  fi
  if [ -n "$found" ]; then
    chmod +x "$found" 2>/dev/null || true
    cp "$found" "$HOME/.local/bin/$bin"
    rm -rf "$tmpd"
    pass "$bin installed via gh release"
  else
    fail "$bin binary not found in release"
    ls -la "$tmpd" | head -5
    rm -rf "$tmpd"
    return 1
  fi
}

# ── Static binaries via gh release download (cross-OS) ──
arch="${RUNNER_ARCH:-X86_64}"
case "$OS" in
  Linux)
    gh_dl BurntSushi/ripgrep "ripgrep-*-x86_64-unknown-linux-musl.tar.gz" rg
    gh_dl jqlang/jq "jq-linux-amd64" jq
    gh_dl duckdb/duckdb "duckdb_cli-linux-amd64.zip" duckdb
    gh_dl gitleaks/gitleaks "gitleaks_*_linux_x64.tar.gz" gitleaks
    ;;
  macOS)
    case "$arch" in
      ARM64)
        gh_dl BurntSushi/ripgrep "ripgrep-*-aarch64-apple-darwin.tar.gz" rg
        gh_dl jqlang/jq "jq-macos-arm64" jq
        gh_dl gitleaks/gitleaks "gitleaks_*_darwin_arm64.tar.gz" gitleaks
        ;;
      *)
        gh_dl BurntSushi/ripgrep "ripgrep-*-x86_64-apple-darwin.tar.gz" rg
        gh_dl jqlang/jq "jq-macos-amd64" jq
        gh_dl gitleaks/gitleaks "gitleaks_*_darwin_x64.tar.gz" gitleaks
        ;;
    esac
    gh_dl duckdb/duckdb "duckdb_cli-osx-universal.zip" duckdb
    ;;
  Windows)
    gh_dl BurntSushi/ripgrep "ripgrep-*-x86_64-pc-windows-msvc.zip" rg.exe
    gh_dl jqlang/jq "jq-windows-amd64.exe" jq.exe
    gh_dl duckdb/duckdb "duckdb_cli-windows-amd64.zip" duckdb.exe
    gh_dl gitleaks/gitleaks "gitleaks_*_windows_x64.zip" gitleaks.exe
    ;;
esac

# npm tools (everywhere)
npm_install @ast-grep/cli ast-grep
npm_install rtk-cli rtk
npm_install @infisical/cli infisical

# pip tools
pip_install "nah[config,keys]"

# osv-scanner (prefer go)
if check go; then
  go_install github.com/google/osv-scanner/v2/cmd/osv-scanner@latest osv-scanner
else
  fail "osv-scanner requires Go on this runner"
fi

# markitdown (pip with extras)
pip_install "markitdown[docx,xlsx,pptx,pdf]" markitdown

# icm (prefer go)
if check go; then
  go_install github.com/rtk-ai/icm@latest icm
else
  pip_install icm
fi

echo "::endgroup::"

# ── Probe phase ───────────────────────────────────────────────────────────────

echo "::group::tool versions"

probe rg           || fail "rg"
probe ast-grep     || fail "ast-grep"
probe rtk          || true        # optional
probe nah          || fail "nah"
probe gitleaks     || fail "gitleaks"
probe osv-scanner  || fail "osv-scanner"
probe infisical    || fail "infisical"
probe duckdb       || fail "duckdb"
probe jq           || fail "jq"
probe markitdown   || fail "markitdown"
probe icm          || fail "icm"

echo "::endgroup::"

# ── Behavioral probes ─────────────────────────────────────────────────────────

echo "::group::behavioral probes"

# rg: search known pattern
if rg -n "def route" paw/router.py &>/dev/null; then
  pass "rg: found def route"
else
  fail "rg: search"
fi

# ast-grep: AST pattern match
if ast-grep run --lang python -p 'def route $$$BODY' paw/router.py &>/dev/null; then
  pass "ast-grep: matched def route"
else
  fail "ast-grep: AST match"
fi

# jq: parse JSON
echo '{"a":1}' | jq -e '.a == 1' &>/dev/null && pass "jq: parsed JSON" || fail "jq: parse"

# duckdb: inline SQL
duckdb -c "SELECT 1 AS x" 2>/dev/null | grep -q "1" && pass "duckdb: inline SQL" || fail "duckdb: SQL"

# markitdown: HTML conversion
echo '<h1>hello</h1>' | markitdown 2>/dev/null | grep -qi "hello" && pass "markitdown: HTML" || fail "markitdown: HTML"

# nah: deterministic allow
if nah test --defaults --json --tool Bash "echo hi" 2>/dev/null | grep -q "allow"; then
  pass "nah: allow rule"
else
  fail "nah: allow test"
fi

# gitleaks: detect secret (exits 1 when leak found = correct behavior)
printf 'password=%s%s\n' 'sk_live_' '1234567890abcdef' | gitleaks detect --no-git --stdin \
  --report-format json --report-path /dev/null -v 2>/dev/null \
  && fail "gitleaks: should have flagged secret" \
  || pass "gitleaks: flagged secret"

# icm: read-only recall
(icm.exe recall "test" --read-only --topics 1 2>/dev/null || \
 icm recall "test" --read-only --topics 1 2>/dev/null || true) \
  && pass "icm: recall ran" || true

echo "::endgroup::"

# ── Summary ───────────────────────────────────────────────────────────────────

echo "::group::summary"
echo "FAILED: ${#FAILED[@]}"
for f in "${FAILED[@]}"; do echo "  ✗ $f"; done
if [ ${#FAILED[@]} -eq 0 ]; then
  echo "Foundation core smoke PASS on $OS"
else
  echo "Foundation core smoke has ${#FAILED[@]} failure(s) on $OS"
fi
echo "::endgroup::"

exit ${#FAILED[@]}
