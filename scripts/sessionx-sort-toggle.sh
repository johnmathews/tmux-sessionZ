#!/usr/bin/env bash
# Toggle sessionx sort order between chronological and alphabetical.
# Outputs fzf action string (reload-sync + change-header + pos).
# Usage: sessionx-sort-toggle.sh STATE_FILE CURRENT_WINDOW

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_FILE="$1"
CURRENT_WINDOW="$2"

LIST_CMD="$SCRIPT_DIR/sessionx-list-recent.sh"
ALPHA_CMD="tmux list-windows -a -F '#{session_name}:#{window_index} #{window_name}'"

compute_pos() {
    local list="$1"
    local total linenum
    total=$(echo "$list" | wc -l | tr -d ' ')
    linenum=$(echo "$list" | grep -n "^${CURRENT_WINDOW} " | head -1 | cut -d: -f1)
    if [[ -n "$linenum" ]]; then
        echo "$((total - linenum + 1))"
    else
        echo "1"
    fi
}

if [[ -f "$STATE_FILE" ]] && [[ "$(cat "$STATE_FILE")" == "recent" ]]; then
    echo "alpha" > "$STATE_FILE"
    list=$(eval "$ALPHA_CMD")
    pos=$(compute_pos "$list")
    echo "reload-sync($ALPHA_CMD)+change-header(Sort: A-Z)+pos($pos)"
else
    echo "recent" > "$STATE_FILE"
    list=$("$LIST_CMD")
    pos=$(compute_pos "$list")
    echo "reload-sync($LIST_CMD)+change-header(Sort: recent)+pos($pos)"
fi
