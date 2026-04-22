#!/usr/bin/env bash
# test_v05_install.sh — v0.5 install smoke harness
# Run: bash tests/smoke/test_v05_install.sh
# Exit 0 only if all checks PASS.

set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$REPO"

FAILED=0

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1  ←  $2"; FAILED=1; }

# ── Check 1: Scripts exist + executable ──────────────────────────────

if [[ -x "$REPO/scripts/env_scan.py" ]]; then
  pass "env_scan.py exists and executable"
else
  fail "env_scan.py exists and executable" "not found or not executable"
fi

if [[ -x "$REPO/scripts/launch_ancestor.sh" ]]; then
  pass "launch_ancestor.sh exists and executable"
else
  fail "launch_ancestor.sh exists and executable" "not found or not executable"
fi

# ── Check 2: --help contract ─────────────────────────────────────────

help_out=$("$REPO/scripts/launch_ancestor.sh" --help 2>&1 || true)
if echo "$help_out" | grep -q "Usage"; then
  pass "--help contains Usage block"
else
  fail "--help contains Usage block" "missing 'Usage'"
fi

for flag in --tool --auth-mode --provider; do
  if echo "$help_out" | grep -qe "$flag"; then
    pass "--help mentions $flag"
  else
    fail "--help mentions $flag" "not found in help output"
  fi
done

for code in 0 2 3 4; do
  if echo "$help_out" | grep -qe "$code"; then
    pass "--help documents exit code $code"
  else
    fail "--help documents exit code $code" "not found"
  fi
done

# ── Check 3: Missing-flag exit 2 ─────────────────────────────────────

# The script should exit 2 when --tool is missing, and output MISSING_FLAG
set +e
missing_out=$("$REPO/scripts/launch_ancestor.sh" --project install 2>&1)
missing_rc=$?
set -e

if [[ $missing_rc -eq 2 ]] && echo "$missing_out" | grep -q "MISSING_FLAG"; then
  pass "missing --tool exits 2 with MISSING_FLAG"
else
  fail "missing --tool exits 2 with MISSING_FLAG" "rc=$missing_rc, out=$missing_out"
fi

# ── Check 4: Missing-credential exit 3 ────────────────────────────────

# Use bogus HOME so no credentials are found.
set +e
creds_out=$(HOME=/nonexistent \
  ANTHROPIC_API_KEY="" \
  "$REPO/scripts/launch_ancestor.sh" \
    --project install \
    --tool claude \
    --auth-mode oauth \
    --provider anthropic 2>&1)
creds_rc=$?
set -e

if [[ $creds_rc -eq 3 ]] && echo "$creds_out" | grep -q "MISSING_CREDENTIAL"; then
  pass "missing credential exits 3 with MISSING_CREDENTIAL"
else
  fail "missing credential exits 3 with MISSING_CREDENTIAL" "rc=$creds_rc, out=$creds_out"
fi

# ── Check 5: env_scan JSON contract ────────────────────────────────────

envscan_tmp=$(mktemp)
cleanup() { rm -f "$envscan_tmp"; }
trap cleanup EXIT

if "$REPO/scripts/env_scan.py" --output "$envscan_tmp" 2>/dev/null; then
  if [[ -s "$envscan_tmp" ]] && python3 -c "import json; json.load(open('$envscan_tmp'))" 2>/dev/null; then
    pass "env_scan.py writes valid JSON"

    # Check required keys
    for key in auth_methods runtimes providers; do
      if python3 -c "import json; d=json.load(open('$envscan_tmp')); assert '$key' in d" 2>/dev/null; then
        pass "env_scan JSON contains '$key'"
      else
        fail "env_scan JSON contains '$key'" "key not found"
      fi
    done
  else
    fail "env_scan.py writes valid JSON" "not valid JSON or empty"
  fi
else
  fail "env_scan.py writes valid JSON" "script failed"
fi

# ── Check 6: Grep-proof INSTALL.md ──────────────────────────────────

deprecated_pattern="install_entrypoint|install_wizard|cs_init|--non-interactive|6-phase"
if grep -E "$deprecated_pattern" "$REPO/docs/INSTALL.md" >/dev/null 2>&1; then
  fail "INSTALL.md has no deprecated term hits" "found deprecated terms"
else
  pass "INSTALL.md has no deprecated term hits"
fi

launch_hits=$(grep -c "launch_ancestor" "$REPO/docs/INSTALL.md" 2>/dev/null || echo 0)
if [[ "$launch_hits" -ge 1 ]]; then
  pass "INSTALL.md mentions launch_ancestor ($launch_hits hits)"
else
  fail "INSTALL.md mentions launch_ancestor" "no hits"
fi

ancestor_hits=$(grep -c "ancestor" "$REPO/docs/INSTALL.md" 2>/dev/null || echo 0)
if [[ "$ancestor_hits" -ge 5 ]]; then
  pass "INSTALL.md mentions ancestor ($ancestor_hits hits)"
else
  fail "INSTALL.md mentions ancestor" "only $ancestor_hits hits (need ≥5)"
fi

# ── Check 7: SKILL.md contract ──────────────────────────────────────

skill_file="$REPO/core/skills/clawseat-install/SKILL.md"
if [[ -f "$skill_file" ]]; then
  # Find lines with deprecated terms, check surrounding context
  while IFS= read -r line; do
    lineno="${line%%:*}"
    before=$((lineno > 1 ? lineno - 1 : 1))
    after=$((lineno + 1))
    context=$(sed -n "${before},${after}p" "$skill_file" 2>/dev/null || true)
    if ! echo "$context" | grep -qiE "not|removed|legacy|do not run|do NOT run|avoid"; then
      fail "SKILL.md deprecated hit at line $lineno is in negative context" "positive instruction found"
    else
      pass "SKILL.md deprecated hit at line $lineno is in negative context"
    fi
  done < <(grep -n "install_entrypoint\|install_wizard\|cs_init" "$skill_file" 2>/dev/null || true)
else
  fail "SKILL.md exists" "file not found at $skill_file"
fi

# ── Summary ──────────────────────────────────────────────────────────

echo ""
if [[ $FAILED -eq 0 ]]; then
  echo "All smoke checks PASSED"
  exit 0
else
  echo "Some smoke checks FAILED"
  exit 1
fi
