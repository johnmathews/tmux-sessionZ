#!/usr/bin/env bash
# Print one line per tmux session: "<session_id>\t<session_name>".
# Usage: list.sh recent|alpha
#   recent  most recently active first (ties broken by name)
#   alpha   by name, case-insensitive
set -u
tab=$'\t'

case "${1:-recent}" in
alpha)
    tmux list-sessions -F "#{session_id}${tab}#{session_name}" | sort -t "$tab" -k2,2f
    ;;
*)
    tmux list-sessions -F "#{session_activity}${tab}#{session_id}${tab}#{session_name}" |
        sort -t "$tab" -k1,1nr -k3,3f | cut -f2-
    ;;
esac
