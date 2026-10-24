#!/usr/bin/env bash
# Preview for the line under the cursor.
# Usage: preview.sh KEY
#   KEY = d:/path   list the directory (zoxide mode)
#   KEY = $id       the active pane of that session, under a one-line header
#                   naming the session and its active window
# The header is pinned (--preview-window ~1) and the pane is shown from its last
# non-blank line upwards (follow), so the prompt or latest output is in view.
set -u
key="${1:-}"

if [[ "$key" == d:* ]]; then
    ls -la "${key#d:}"
    exit 0
fi
[[ "$key" == \$* ]] || exit 0

bold=$'\033[1m' dim=$'\033[2m' reset=$'\033[0m'
tmux display-message -p -t "$key" \
    "${bold}#{session_name}${reset}${dim} · #{window_index}: #{window_name} · #{session_windows} window(s)${reset}"
# Trailing blank lines would push the real content above the fold under `follow`.
tmux capture-pane -e -p -t "$key" | awk '{ line[NR] = $0 } /[^[:space:]]/ { last = NR } END { for (i = 1; i <= last; i++) print line[i] }'
