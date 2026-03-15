#!/usr/bin/env bash
# SessionX wrapper — custom keybindings and behavior enhancements.
# Runs automatically via: bind o run-shell "~/.tmux/scripts/sessionx-wrapper.sh"
# Survives plugin updates — no plugin source files are modified.
# fzf allows duplicate --bind for the same key; the last one wins.
#
# Custom bindings added by this wrapper:
#   ctrl-r  Rename session (reloads window list, cursor follows renamed session)
#   ctrl-y  Rename window (cursor follows renamed window)
#   ctrl-a  New session (prompts for name)
#   ctrl-g  New window in the selected session (prompts for name)
#   ctrl-x  Kill/close window
#   ctrl-q  Kill/close session (all its windows)
#   ctrl-t  Toggle sort: most recently active (default) ↔ alphabetical
#
# Behavior changes:
#   - Default view: reverse chronological (most recently active session first)
#   - Opens with the current window pre-selected (via --listen HTTP API)
#   - All mutations reload in chronological order
#   - Rename-session reloads the window list (not session-only list)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="/Users/john/.tmux/plugins/tmux-sessionx/scripts"
CURRENT_WINDOW=$(tmux display-message -p '#{session_name}:#{window_index}')
RENAME_TMPFILE="/tmp/sessionx-last-rename-$$"
SORT_STATE_FILE="/tmp/sessionx-sort-state"
LIST_CMD="$SCRIPT_DIR/sessionx-list-recent.sh"
REPOS_CMD="$SCRIPT_DIR/sessionx-repos.sh"

# Save original stored args
ORIG_ARGS=$(tmux show-option -gqv @sessionx-_built-args)
ORIG_OPTS=$(tmux show-option -gqv @sessionx-_built-fzf-opts)

# Restore originals on exit (so plugin updates aren't affected)
cleanup() {
    tmux set-option -g @sessionx-_built-args "$ORIG_ARGS"
    tmux set-option -g @sessionx-_built-fzf-opts "$ORIG_OPTS"
    rm -f "$RENAME_TMPFILE"
    [[ -n "$CURSOR_PID" ]] && kill "$CURSOR_PID" 2>/dev/null
}
trap cleanup EXIT

# Rebuild args array from stored value
eval "$ORIG_ARGS"

# --- 1. Default view: reverse chronological, cursor on current window ---
# Use --listen HTTP API for 100% reliable cursor positioning.
# The load:pos() approach is only ~80% reliable due to a race condition where
# load fires for the piped input before reload-sync replaces it.
# See docs/fzf-cursor-positioning.md for details.
RECENT_LIST=$("$LIST_CMD")
LINE_NUM=$(echo "$RECENT_LIST" | grep -n "^${CURRENT_WINDOW} " | head -1 | cut -d: -f1)

FZF_LISTEN_PORT=$((RANDOM % 10000 + 40000))
args+=(--listen "localhost:$FZF_LISTEN_PORT")
args+=(--bind "start:reload-sync($LIST_CMD)")

if [[ -n "$LINE_NUM" ]]; then
    TOTAL=$(echo "$RECENT_LIST" | wc -l | tr -d ' ')
    POS=$((TOTAL - LINE_NUM + 1))
    # Background: wait for fzf to start listening, then position cursor via HTTP.
    # pos() sent via HTTP is queued behind start:reload-sync (which blocks the
    # main event loop), so it always applies to the correct (reloaded) list.
    (
        for _ in $(seq 1 100); do
            if curl -s -o /dev/null --connect-timeout 0.1 "http://localhost:$FZF_LISTEN_PORT" 2>/dev/null; then
                sleep 0.1
                curl -s -X POST "http://localhost:$FZF_LISTEN_PORT" -d "pos($POS)" 2>/dev/null
                break
            fi
            sleep 0.02
        done
    ) &
    CURSOR_PID=$!
fi

# --- 2. ctrl-r: rename session ---
# execute: prompt for new name, rename, save new name to tmpfile
# reload-sync: refresh with chronological list
# transform: compute cursor position for renamed session
RENAME_EXEC="bash -c 'printf >&2 \"New name: \";read name; tmux rename-session -t {1} \"\${name}\"; echo \"\${name}\" > ${RENAME_TMPFILE};'"
args+=(--bind "ctrl-r:execute($RENAME_EXEC)+reload-sync($LIST_CMD)+transform($REPOS_CMD --session \$(cat $RENAME_TMPFILE 2>/dev/null))")

# --- 3. ctrl-y: rename window ---
WIN_RENAME_EXEC="bash -c 'printf >&2 \"New window name: \"; read name; session=\$(echo {1} | cut -d: -f1); win=\$(echo {1} | cut -d: -f2 | cut -d\" \" -f1); tmux rename-window -t \"\${session}:\${win}\" \"\${name}\"; echo \"\${session}:\${win}\" > ${RENAME_TMPFILE};'"
args+=(--bind "ctrl-y:execute($WIN_RENAME_EXEC)+reload-sync($LIST_CMD)+transform($REPOS_CMD --window \$(cat $RENAME_TMPFILE 2>/dev/null))")

# --- 4. ctrl-a: new session ---
# Uses --boost to force the new session to the top of the chronological list.
# Without this, the new session always lands at position 2 because tmux new-session -d
# creates a detached session whose session_activity is immediately stale — the current
# session (where fzf runs) continuously updates its activity and always wins position 1.
#
# Cursor positioning uses the --listen HTTP API (background curl) instead of chaining
# pos()/last/transform in the fzf action chain. Both reload-sync+transform(pos(N)) and
# reload-sync+last produced an off-by-one (cursor at position 2 instead of 1) when
# preceded by execute(). The HTTP API works because fzf processes HTTP-delivered actions
# after all rendering/redrawing is complete — same principle as initial cursor positioning.
# See docs/fzf-cursor-positioning.md for details.
NEW_SESSION_EXEC="bash -c 'printf >&2 \"New session name: \"; read name; tmux new-session -d -s \"\${name}\"; echo \"\${name}\" > ${RENAME_TMPFILE};'"
args+=(--bind "ctrl-a:execute($NEW_SESSION_EXEC)+execute-silent(echo recent > $SORT_STATE_FILE)+reload-sync($LIST_CMD --boost \$(cat $RENAME_TMPFILE 2>/dev/null))+execute-silent(bash -c 'sleep 0.1; curl -s -X POST http://localhost:$FZF_LISTEN_PORT -d last' &)")

# --- 5. ctrl-g: new window (prompts for name, creates in selected session) ---
# Creates the window in the session under the cursor, prompts for a name,
# then renames it (to override the after-new-window hook that blanks names).
# Uses tmux new-window -P to capture the new window's session:index target.
NEW_WIN_EXEC="bash -c 'printf >&2 \"New window name: \"; read name; session=\$(echo {1} | cut -d: -f1); target=\$(tmux new-window -t \"\${session}:\" -P -F \"#{session_name}:#{window_index}\"); tmux rename-window -t \"\${target}\" \"\${name}\"; echo \"\${target}\" > ${RENAME_TMPFILE};'"
args+=(--bind "ctrl-g:execute($NEW_WIN_EXEC)+execute-silent(echo recent > $SORT_STATE_FILE)+reload-sync($LIST_CMD)+transform($REPOS_CMD --window \$(cat $RENAME_TMPFILE 2>/dev/null))")

# --- 6. ctrl-x: kill window ---
KILL_WIN_EXEC='bash -c '\''session=$(echo {1} | cut -d: -f1); win=$(echo {1} | cut -d: -f2 | cut -d" " -f1); tmux kill-window -t "${session}:${win}";'\'''
args+=(--bind "ctrl-x:execute-silent($KILL_WIN_EXEC)+reload-sync($LIST_CMD)+transform($REPOS_CMD --window ${CURRENT_WINDOW})")

# --- 7. ctrl-q: kill session ---
KILL_SESSION_EXEC='bash -c '\''session=$(echo {1} | cut -d: -f1); tmux kill-session -t "${session}";'\'''
args+=(--bind "ctrl-q:execute-silent($KILL_SESSION_EXEC)+reload-sync($LIST_CMD)+transform($REPOS_CMD --window ${CURRENT_WINDOW})")

# --- 8. Override change:first → change:last ---
# Sessionx sets --bind 'change:first', but with --tac, 'first' = bottom of display.
# We want the cursor at the top (most recent) when the query changes, so override with 'last'.
args+=(--bind 'change:last')

# --- 9. ctrl-t: toggle sort (recent ↔ alphabetical) ---
echo "recent" > "$SORT_STATE_FILE"
args+=(--bind "ctrl-t:transform($SCRIPT_DIR/sessionx-sort-toggle.sh $SORT_STATE_FILE $CURRENT_WINDOW)")

# Store modified args and run sessionx
tmux set-option -g @sessionx-_built-args "$(declare -p args)"

"$PLUGIN_DIR/sessionx.sh"
