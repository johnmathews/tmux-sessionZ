#!/usr/bin/env bash
# Preview for the line under the cursor.
# Usage: preview.sh KEY
#   KEY = d:/path   list the directory (zoxide mode)
#   KEY = $id       tree of every session and its windows, with that session highlighted
# Sessions are grouped by id taken straight from tmux, never matched by pattern,
# so ids like $1 and $10 cannot be confused.
set -u
key="${1:-}"
tab=$'\t'

if [[ "$key" == d:* ]]; then
    ls -la "${key#d:}"
    exit 0
fi

bold=$'\033[1m' blue=$'\033[1;34m' dim=$'\033[2m' reset=$'\033[0m'
previous=""
tmux list-windows -a -F "#{session_id}${tab}#{session_name}${tab}#{session_windows}${tab}#{?session_attached, (attached),}${tab}#{window_index}${tab}#{window_name}${tab}#{?window_active,*,}" |
    while IFS="$tab" read -r sid sname nwin attached widx wname wactive; do
        if [[ "$sid" != "$previous" ]]; then
            colour="$bold"
            [[ "$sid" == "$key" ]] && colour="$blue"
            printf '%s%s%s %s%s window(s)%s%s\n' "$colour" "$sname" "$reset" "$dim" "$nwin" "$attached" "$reset"
            previous="$sid"
        fi
        printf '  %s: %s%s\n' "$widx" "$wname" "$wactive"
    done
