#!/usr/bin/env bash
# Print one line per tmux session: "<session_id>\t<age>\t<session_name>".
# Usage: list.sh recent|alpha
#   recent  most recently used first (ties broken by name)
#   alpha   by name, case-insensitive
# <age> is the time since the session was last used: since a key was last typed
# into it from a client, or a client last switched to it (#{session_activity}).
# Output does not count, so a pane printing on its own does not make its session
# young. Shown as 30s, 5m, 2hr, 30hr, 3d: hours run up to 48 before switching to
# days. It is right-aligned to 4 columns and dimmed.
# SESSIONZ_NOW overrides the current time (seconds since the epoch) for tests.
set -u
tab=$'\t'
now=${SESSIONZ_NOW:-$(date +%s)}

tmux list-sessions -F "#{session_activity}${tab}#{session_id}${tab}#{session_name}" |
    awk -F "$tab" -v OFS="$tab" -v now="$now" -v dim=$'\033[2m' -v reset=$'\033[0m' '
    function age(s) {
        if (s < 0) s = 0
        if (s < 60) return s "s"
        if (s < 3600) return int(s / 60) "m"
        if (s < 48 * 3600) return int(s / 3600) "hr"
        return int(s / 86400) "d"
    }
    { printf "%s\t%s\t%s%4s%s\t%s\n", $1, $2, dim, age(now - $1), reset, $3 }
' | if [[ "${1:-recent}" == alpha ]]; then
    sort -t "$tab" -k4,4f
else
    sort -t "$tab" -k1,1nr -k4,4f
fi | cut -f2-
