#!/bin/bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <target> <message>" >&2
  exit 1
fi

target="$1"
shift
message="$*"

tmux send-keys -t "$target" "$message"
sleep 1
tmux send-keys -t "$target" Enter
