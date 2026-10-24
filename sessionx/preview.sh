#!/usr/bin/env bash
# Preview for the line under the cursor.
# Usage: preview.sh STATE_DIR KEY            render the preview
#        preview.sh STATE_DIR --window KEY   print the window id being previewed
#   KEY = d:/path   list the directory (zoxide mode)
#   KEY = $id       one window of that session under a one-line header listing
#                   every window (previewed one highlighted, active one starred).
#                   A window with several panes shows them stacked in index order,
#                   each under a bright full-width label, sharing the preview height
#                   so that short panes show in full and long ones get the rest.
# The previewed window is the session's active window unless left/right chose
# another: action.sh records that as "<session_id>\t<window_id>" in
# STATE_DIR/window, and it only applies while that session is the one shown.
# The header is pinned (--preview-window ~1) and the pane is shown from its last
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

rev=$'\033[7m' label=$'\033[1;95m' reset=$'\033[0m'
win=$(previewed_window "$key")
# Header: one segment per window, rendered by tmux itself (unnamed windows show
# their command); the previewed window in reverse video, the active one starred.
tmux list-windows -t "$key" -F "#{?#{==:#{window_id},$win},$rev,}#{window_index}: #{?window_name,#{window_name},#{pane_current_command}}#{?window_active,*,}$reset" |
    awk '{ printf "%s%s", (NR > 1 ? "   " : ""), $0 } END { print "" }'

# Pane $1's screen plus up to $2 lines of history above it, without trailing
# blank lines (which would otherwise push the real content above the fold under
# `follow`). History lets a long pane fill more of the preview than its height.
capture() {
    tmux capture-pane -e -p -S "-$2" -t "$1" |
        awk '{ line[NR] = $0 } /[^[:space:]]/ { last = NR } END { for (i = 1; i <= last; i++) print line[i] }'
}

ids=()
titles=()
while IFS= read -r pane; do
    ids+=("${pane%% *}")
    titles+=("${pane#* }")
done < <(tmux list-panes -t "$win" -F "#{pane_id} pane #{pane_index}: #{pane_current_command}#{?pane_active,*,}")
count=${#ids[@]}
lines=${FZF_PREVIEW_LINES:-40}
if ((count == 1)); then
    capture "$win" "$lines" | tail -n "$((lines - 1))"
    exit 0
fi

bodies=()
lengths=()
for id in "${ids[@]}"; do
    body=$(capture "$id" "$lines")
    bodies+=("$body")
    if [[ -n "$body" ]]; then lengths+=("$(printf '%s\n' "$body" | wc -l)"); else lengths+=(0); fi
done

# Lines below the header, minus one label per pane, shared out by water-filling:
# each round splits what is left evenly among the panes that still have more to
# show, so a short pane keeps all its lines and the rest go to the longer ones.
budget=$((lines - 1 - count))
alloc=()
for ((i = 0; i < count; i++)); do alloc+=(0); done
while ((budget > 0)); do
    wanting=0
    for ((i = 0; i < count; i++)); do ((alloc[i] < lengths[i])) && wanting=$((wanting + 1)); done
    ((wanting == 0)) && break
    share=$((budget / wanting))
    ((share < 1)) && share=1
    for ((i = 0; i < count && budget > 0; i++)); do
        need=$((lengths[i] - alloc[i]))
        ((need <= 0)) && continue
        give=$share
        ((give > need)) && give=$need
        ((give > budget)) && give=$budget
        alloc[i]=$((alloc[i] + give))
        budget=$((budget - give))
    done
done

# Labels are full-width rules in a bright colour so pane boundaries stand out.
width=${FZF_PREVIEW_COLUMNS:-80}
for ((i = 0; i < count; i++)); do
    text="── ${titles[i]} "
    fill=$((width - ${#text}))
    ((fill < 0)) && fill=0
    printf '%s%s%s%s\n' "$label" "$text" "$(printf '%*s' "$fill" '' | sed 's/ /─/g')" "$reset"
    ((alloc[i] > 0)) && printf '%s\n' "${bodies[i]}" | tail -n "${alloc[i]}"
done
exit 0
