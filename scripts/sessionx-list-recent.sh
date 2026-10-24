#!/usr/bin/env bash
# Output tmux sessions (or windows) in reverse-chronological order.
# Respects @sessionx-window-mode: 'on' lists windows, 'off' lists sessions only.
# Used by sessionx-wrapper.sh for reload-sync and position computation.
#
# Usage: sessionx-list-recent.sh [--boost SESSION_NAME]
#   --boost: force SESSION_NAME to the top of the list regardless of activity.
#            Needed for newly created sessions — tmux new-session -d creates a
#            detached session whose session_activity is immediately stale because
#            the current session (where fzf runs) continuously updates its own
#            activity. Without --boost, new sessions always appear at position 2.

BOOST=""
if [[ "$1" == "--boost" ]]; then
    BOOST="$2"
fi

WINDOW_MODE=$(tmux show-option -gqv @sessionx-window-mode)

if [[ "$WINDOW_MODE" == "on" ]]; then
    # Window mode: list all windows grouped by session
    if [[ -n "$BOOST" ]]; then
        tmux list-windows -t "$BOOST" -F "#{session_name}:#{window_index} #{window_name}" 2>/dev/null
    fi
    tmux list-sessions -F "#{session_activity} #{session_name}" | sort -rn | while read _ts sess; do
        [[ "$sess" == "$BOOST" ]] && continue
        tmux list-windows -t "$sess" -F "#{session_name}:#{window_index} #{window_name}"
    done
else
    # Session-only mode: list session names
    if [[ -n "$BOOST" ]]; then
        echo "$BOOST"
    fi
    tmux list-sessions -F "#{session_activity} #{session_name}" | sort -rn | while read _ts sess; do
        [[ "$sess" == "$BOOST" ]] && continue
        echo "$sess"
    done
fi
