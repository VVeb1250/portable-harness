#!/usr/bin/env bash
# Cross-OS smoke for the bundle's prebuilt-binary CLIs.
#
# Downloads each vendor's prebuilt release asset for the CURRENT runner OS/arch,
# extracts it, runs --version, then a no-network behavioral probe. Proves the
# PORTABLE artifact actually runs on this OS — the empirical gate that promotes
# quality-gate + api-quality from `candidate` to `ready` (docs/CATALOG-DEEP-VET).
#
# Driven by three env vars set per matrix row in bundle-smoke.yml:
#   RUST_TRIPLE  cargo-dist triple   (e.g. x86_64-unknown-linux-gnu)
#   GO_OSARCH    goreleaser os_arch  (e.g. linux_amd64)
#   EXT          archive extension   (tar.gz on unix, zip on windows)
#
# Pinned versions = the exact release tags whose assets were confirmed present
# (gh release view, 2026-06-26). Bump here + in paw/registry/sets.json together.
set -euo pipefail

: "${RUST_TRIPLE:?need RUST_TRIPLE}"
: "${GO_OSARCH:?need GO_OSARCH}"
: "${EXT:?need EXT}"

PREK_TAG=v0.4.5
ACTIONLINT_TAG=v1.7.12
ACTIONLINT_VER=1.7.12
HURL_TAG=8.0.1
LYCHEE_TAG=lychee-v0.24.2

work="$(mktemp -d)"
cd "$work"

dl() { # repo tag asset
  gh release download "$2" --repo "$1" --pattern "$3" --dir "$work" --clobber
}

# tar.gz via tar (auto-detects gzip on GNU+bsd). zip (Windows only) via unzip if
# present, else PowerShell Expand-Archive — GNU tar (local Git Bash) cannot read
# zip, so don't rely on bsdtar being the runner default.
extract() {
  case "$1" in
    *.zip)
      if command -v unzip >/dev/null 2>&1; then
        unzip -oq "$1"
      else
        powershell -NoProfile -NonInteractive -Command \
          "Expand-Archive -LiteralPath '$1' -DestinationPath '.' -Force"
      fi ;;
    *) tar -xf "$1" ;;
  esac
}

locate() { # binary base-name -> first matching executable path
  find "$work" -type f \( -name "$1" -o -name "$1.exe" \) | head -1
}

run() { local p="$1"; shift; chmod +x "$p" 2>/dev/null || true; "$p" "$@"; }

fail() { echo "::error::$1"; exit 1; }

# --- prek (Rust single-binary pre-commit-compatible hook manager) ------------
echo "::group::prek $PREK_TAG"
asset="prek-${RUST_TRIPLE}.${EXT}"
dl j178/prek "$PREK_TAG" "$asset"
extract "$asset"
PREK="$(locate prek)"; [ -n "$PREK" ] || fail "prek binary not found in $asset"
run "$PREK" --version
echo "::endgroup::"

# --- actionlint (static GitHub Actions checker) ------------------------------
echo "::group::actionlint $ACTIONLINT_TAG"
asset="actionlint_${ACTIONLINT_VER}_${GO_OSARCH}.${EXT}"
dl rhysd/actionlint "$ACTIONLINT_TAG" "$asset"
extract "$asset"
AL="$(locate actionlint)"; [ -n "$AL" ] || fail "actionlint binary not found in $asset"
run "$AL" -version
# behavioral probe: it MUST flag a deliberately broken workflow (needs a ghost job)
mkdir -p probe/.github/workflows
cat > probe/.github/workflows/broken.yml <<'YML'
on: push
jobs:
  build:
    needs: ghost-job-that-does-not-exist
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
YML
if run "$AL" -no-color probe/.github/workflows/broken.yml; then
  fail "actionlint did not flag a broken workflow (exit 0)"
fi
echo "actionlint correctly flagged the broken workflow"
echo "::endgroup::"

# --- lychee (link checker) ---------------------------------------------------
echo "::group::lychee $LYCHEE_TAG"
asset="lychee-${RUST_TRIPLE}.${EXT}"
dl lycheeverse/lychee "$LYCHEE_TAG" "$asset"
extract "$asset"
LY="$(locate lychee)"; [ -n "$LY" ] || fail "lychee binary not found in $asset"
run "$LY" --version
# behavioral probe (offline = filesystem only, no network): a valid local link resolves
printf '# present\n' > present.md
printf '[local](./present.md)\n' > here.md
run "$LY" --offline --no-progress here.md
echo "::endgroup::"

# --- hurl (HTTP contract test runner) ----------------------------------------
echo "::group::hurl $HURL_TAG"
asset="hurl-${HURL_TAG}-${RUST_TRIPLE}.${EXT}"
dl Orange-OpenSource/hurl "$HURL_TAG" "$asset"
extract "$asset"
HURL="$(locate hurl)"; [ -n "$HURL" ] || fail "hurl binary not found in $asset"
run "$HURL" --version
echo "::endgroup::"

echo "All bundle CLIs ran on ${RUST_TRIPLE}."
