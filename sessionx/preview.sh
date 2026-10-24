#!/usr/bin/env bash
# Preview for the line under the cursor.
# Usage: preview.sh STATE_DIR KEY            render the preview
#        preview.sh STATE_DIR --window KEY   print the window id being previewed
#   KEY = d:/path   list the directory (zoxide mode)
#   KEY = $id       one window of that session (its active pane) under a two-line
#                   header: the session, then every window with the previewed one
#                   highlighted and the active one starred
# The previewed window is the session's active window unless left/right chose
# another: action.sh records that as "<session_id>\t<window_id>" in
# STATE_DIR/window, and it only applies while that session is the one shown.
# The header is pinned (--preview-window ~2) and the pane is shown from its last
# non-blank line upwards (follow), so the prompt or latest output is in view.
set -u
state="$1"
shift

# Window id to preview for session $1.
previewed_window() {
    local session="$1" chosen="" wid
    if [[ -f "$state/window" ]]; then
        IFS=$'\t' read -r chosen_session chosen <"$state/window"
        [[ "$chosen_session" == "$session" ]] || chosen=""
    fi
    if [[ -n "$chosen" ]]; then
        # The chosen window may have been closed since.
        wid=$(tmux list-windows -t "$session" -F '#{window_id}' | grep -Fx -- "$chosen")
        [[ -n "$wid" ]] && { printf '%s\n' "$wid"; return; }
    fi
    tmux display-message -p -t "$session" '#{window_id}'
}

if [[ "${1:-}" == --window ]]; then
    previewed_window "$2"
    exit 0
fi

key="${1:-}"
if [[ "$key" == d:* ]]; then
    ls -la "${key#d:}"
    exit 0
fi
[[ "$key" == \$* ]] || exit 0

bold=$'\033[1m' dim=$'\033[2m' rev=$'\033[7m' reset=$'\033[0m'
win=$(previewed_window "$key")
count=$(tmux display-message -p -t "$key" '#{session_windows}')
hint=""
((count > 1)) && hint=" · ←/→ windows"
printf '%s%s%s%s · %s window(s)%s%s\n' "$bold" "$(tmux display-message -p -t "$key" '#{session_name}')" \
    "$reset" "$dim" "$count" "$hint" "$reset"
# One segment per window, rendered by tmux itself (unnamed windows show their command).
tmux list-windows -t "$key" -F "#{?#{==:#{window_id},$win},$rev,}#{window_index}: #{?window_name,#{window_name},#{pane_current_command}}#{?window_active,*,}$reset" |
    awk '{ printf "%s%s", (NR > 1 ? "   " : ""), $0 } END { print "" }'
# Trailing blank lines would push the real content above the fold under `follow`.
tmux capture-pane -e -p -t "$win" | awk '{ line[NR] = $0 } /[^[:space:]]/ { last = NR } END { for (i = 1; i <= last; i++) print line[i] }'
