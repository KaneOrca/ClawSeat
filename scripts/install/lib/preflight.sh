#!/usr/bin/env bash
# shellcheck shell=bash
# Loaded by scripts/install.sh. Resolve this file with BASH_SOURCE so
# callers may source install.sh from any current working directory.
_CLAWSEAT_INSTALL_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

resolve_python_candidate() {
  local candidate="$1"
  if [[ "$candidate" == */* ]]; then
    [[ -x "$candidate" ]] || return 1
    printf '%s\n' "$candidate"
    return 0
  fi
  command -v "$candidate" 2>/dev/null || return 1
}

python_candidate_version() {
  local candidate="$1"
  "$candidate" -c 'import sys; print(".".join(str(part) for part in sys.version_info[:3]))' 2>/dev/null
}

python_version_supported() {
  local version="$1"
  local major="" minor="" patch=""
  IFS=. read -r major minor patch <<<"$version"
  [[ "$major" =~ ^[0-9]+$ && "$minor" =~ ^[0-9]+$ ]] || return 1
  (( major > 3 || (major == 3 && minor >= 11) ))
}

resolve_supported_python_bin() {
  local resolved="" version="" detail="" candidate=""
  local -a attempted=()
  local -a candidates=(
    "python3.13"
    "python3.12"
    "python3.11"
    "/opt/homebrew/bin/python3.13"
    "/opt/homebrew/bin/python3.12"
    "/opt/homebrew/bin/python3.11"
    "/usr/local/bin/python3.13"
    "/usr/local/bin/python3.12"
    "/usr/local/bin/python3.11"
    "python3"
    "python"
  )

  if [[ -n "$PYTHON_BIN_WAS_SET" && -n "$PYTHON_BIN_OVERRIDE" ]]; then
    resolved="$(resolve_python_candidate "$PYTHON_BIN_OVERRIDE" || true)"
    if [[ -z "$resolved" ]]; then
      die 2 INVALID_PYTHON_BIN \
        "PYTHON_BIN=$PYTHON_BIN_OVERRIDE was provided, but that executable was not found. ClawSeat install requires Python >= 3.11 before preflight can import. Try: PYTHON_BIN=/opt/homebrew/bin/python3.12 bash scripts/install.sh --provider 1"
    fi
    version="$(python_candidate_version "$resolved" || true)"
    if [[ -n "$version" ]] && python_version_supported "$version"; then
      PYTHON_BIN="$resolved"
      PYTHON_BIN_VERSION="$version"
      PYTHON_BIN_RESOLUTION="explicit"
      export PYTHON_BIN
      return 0
    fi
    detail="version probe failed"
    [[ -n "$version" ]] && detail="Python $version"
    die 2 INVALID_PYTHON_BIN \
      "PYTHON_BIN=$PYTHON_BIN_OVERRIDE resolves to $resolved ($detail), but ClawSeat install requires Python >= 3.11 before preflight can import. Try: PYTHON_BIN=/opt/homebrew/bin/python3.12 bash scripts/install.sh --provider 1"
  fi

  for candidate in "${candidates[@]}"; do
    resolved="$(resolve_python_candidate "$candidate" || true)"
    [[ -n "$resolved" ]] || continue
    version="$(python_candidate_version "$resolved" || true)"
    if [[ -n "$version" ]]; then
      attempted+=("$resolved=$version")
      if python_version_supported "$version"; then
        PYTHON_BIN="$resolved"
        PYTHON_BIN_VERSION="$version"
        PYTHON_BIN_RESOLUTION="auto"
        export PYTHON_BIN
        return 0
      fi
    fi
  done

  local attempted_summary="none"
  if [[ ${#attempted[@]} -gt 0 ]]; then
    attempted_summary="$(printf '%s' "${attempted[0]}")"
    local idx=1
    while (( idx < ${#attempted[@]} )); do
      attempted_summary+=", ${attempted[$idx]}"
      ((idx += 1))
    done
  fi
  die 2 MISSING_PYTHON311 \
    "No supported Python >= 3.11 found for ClawSeat install before preflight import. Detected: $attempted_summary. Install/use python3.11+ or run: PYTHON_BIN=/opt/homebrew/bin/python3.12 bash scripts/install.sh --provider 1"
}


ensure_host_deps() {
  note "Step 1: preflight"
  if [[ "$FORCE_REINSTALL" != "1" && -f "$STATUS_FILE" ]] && grep -q '^phase=ready$' "$STATUS_FILE"; then
    # Round-8: even on the "already installed" fast-path, honor the
    # auto-patrol default. If the operator rerun without
    # --enable-auto-patrol but an existing LaunchAgent is still firing
    # (from a pre-Round-8 install), tear it down; otherwise the ghost
    # plist keeps injecting stale payloads even though install.sh
    # itself exited early and never reached Step 6.
    if [[ "$ENABLE_AUTO_PATROL" != "1" ]]; then
      uninstall_primary_patrol_plist_if_present
    fi
    printf 'Project %s already installed (phase=ready) at %s.\n' "$PROJECT" "$STATUS_FILE"
    printf 'Use --reinstall or --force to rebuild.\n'
    exit 0
  fi
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] %q %q --project %q --phase bootstrap\n' \
      "$PYTHON_BIN" "$REPO_ROOT/core/preflight.py" "$PROJECT"
    return 0
  fi

  local pf_out="" pf_rc=0
  if pf_out="$("$PYTHON_BIN" "$REPO_ROOT/core/preflight.py" --project "$PROJECT" --phase bootstrap 2>&1)"; then
    pf_rc=0
  else
    pf_rc=$?
  fi
  printf '%s\n' "$pf_out"
  if [[ $pf_rc -ne 0 ]]; then
    if [[ "$pf_out" == *"HARD_BLOCKED"* ]]; then
      die 10 PREFLIGHT_FAILED "preflight 检测到 HARD_BLOCKED 项。按上面 fix_command 修复后重跑 install.sh。"
    fi
    die 10 PREFLIGHT_FAILED "preflight failed. 按上面的输出修复后重跑 install.sh。"
  fi
  echo "OK: preflight"
}

ensure_python_tomllib_fallback() {
  note "Step 2.5: ensure Python tomllib fallback"
  if "$PYTHON_BIN" -c 'import tomllib' >/dev/null 2>&1; then
    return 0
  fi
  if "$PYTHON_BIN" -c 'import tomli' >/dev/null 2>&1; then
    return 0
  fi
  "$PYTHON_BIN" -m pip install --user --quiet tomli >/dev/null 2>&1 || true
}

scan_machine() {
  note "Step 2: environment scan"
  run "$PYTHON_BIN" "$SCAN_SCRIPT" --output "$MEMORY_ROOT"
  [[ "$DRY_RUN" == "1" ]] && { printf '[dry-run] verify %s\n' "$MEMORY_ROOT/machine/{credentials,network,openclaw,github,current_context}.json"; return; }
  local name
  for name in credentials network openclaw github current_context; do
    [[ -f "$MEMORY_ROOT/machine/$name.json" ]] || die 2 ENV_SCAN_INCOMPLETE "missing memory artifact: $MEMORY_ROOT/machine/$name.json"
  done
}

run_legacy_path_migration() {
  [[ -f "$MIGRATE_ANCESTOR_PATHS_SCRIPT" ]] || return 0
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] %q %q --project %q\n' "$PYTHON_BIN" "$MIGRATE_ANCESTOR_PATHS_SCRIPT" "$PROJECT"
    return 0
  fi
  "$PYTHON_BIN" "$MIGRATE_ANCESTOR_PATHS_SCRIPT" --project "$PROJECT" \
    || warn "legacy path migration failed (non-fatal); run $MIGRATE_ANCESTOR_PATHS_SCRIPT --project $PROJECT"
}

reconcile_seat_liveness_state() {
  note "Step 1.5: reconcile seat liveness state"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] %q %q --project %q\n' "$PYTHON_BIN" "$RECONCILE_SEAT_STATES_SCRIPT" "$PROJECT"
    return 0
  fi
  [[ -f "$RECONCILE_SEAT_STATES_SCRIPT" ]] || { warn "state.db reconcile skipped (missing $RECONCILE_SEAT_STATES_SCRIPT)"; return 0; }
  "$PYTHON_BIN" "$RECONCILE_SEAT_STATES_SCRIPT" --project "$PROJECT" \
    || warn "state.db reconcile skipped (non-fatal)"
}
