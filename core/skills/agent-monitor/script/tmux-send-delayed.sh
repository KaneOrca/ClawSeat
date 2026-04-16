#!/bin/bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <target> <message>" >&2
  exit 1
fi

target="$1"
shift
message="$*"

# env -u TMUX: allow running from inside a tmux session
env -u TMUX tmux send-keys -t "$target" "$message"
sleep 1
env -u TMUX tmux send-keys -t "$target" Enter
