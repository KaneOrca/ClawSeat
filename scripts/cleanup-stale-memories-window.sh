#!/usr/bin/env bash
# Close stale pre-marker iTerm memories windows after upgrading to v2 tabs mode.
#
# Usage:
#   bash scripts/cleanup-stale-memories-window.sh
#
# The pkg-C tabs path marks the live shared window with user.window_title.
# Older windows named "clawseat-memories" may not have that marker; this helper
# closes only those unmarked windows and exits 0 if iTerm is unavailable.
set -euo pipefail

if ! command -v osascript >/dev/null 2>&1; then
  printf '%s\n' 'osascript_not_available'
  exit 0
fi

if ! output="$(osascript <<'APPLESCRIPT' 2>&1
tell application "System Events"
  set itermRunning to exists process "iTerm2"
end tell

if itermRunning is false then
  return "iterm_not_running"
end if

tell application "iTerm2"
  set closedCount to 0
  repeat with w in windows
    set candidateTitle to ""
    try
      set candidateTitle to name of w as text
    end try
    if candidateTitle is "clawseat-memories" then
      set markerValue to ""
      try
        set activeTab to current tab of w
        set activeSession to current session of activeTab
        tell activeSession to set markerValue to variable named "user.window_title"
      end try
      if markerValue is "" then
        close w
        set closedCount to closedCount + 1
      end if
    end if
  end repeat
  return "closed=" & closedCount
end tell
APPLESCRIPT
)"; then
  printf 'warn: cleanup-stale-memories-window skipped: %s\n' "$output" >&2
  exit 0
fi

if [[ -n "$output" ]]; then
  printf '%s\n' "$output"
fi
