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
#   ctrl-g  New window in the selected session
#   ctrl-x  Kill/close window
#   ctrl-q  Kill/close session (all its windows)
#   ctrl-t  Toggle sort: most recently active (default) ↔ alphabetical
#
# Behavior changes:
#   - Default view: reverse chronological (most recently active session first)
#   - Opens with the current window pre-selected
#   - Rename-session reloads the window list (not session-only list)

PLUGIN_DIR="/Users/john/.tmux/plugins/tmux-sessionx/scripts"
CURRENT_WINDOW=$(tmux display-message -p '#{session_name}:#{window_index}')
RENAME_TMPFILE="/tmp/sessionx-last-rename-$$"

# Save original stored args
ORIG_ARGS=$(tmux show-option -gqv @sessionx-_built-args)
ORIG_OPTS=$(tmux show-option -gqv @sessionx-_built-fzf-opts)

# Restore originals on exit (so plugin updates aren't affected)
cleanup() {
    tmux set-option -g @sessionx-_built-args "$ORIG_ARGS"
    tmux set-option -g @sessionx-_built-fzf-opts "$ORIG_OPTS"
    rm -f "$RENAME_TMPFILE"
}
trap cleanup EXIT

# Rebuild args array from stored value
eval "$ORIG_ARGS"

# --- 1. Default view: reverse chronological, cursor on current window ---
# Generate the chronological list at script time so pos() is pre-computed (no race).
# The reload-sync at start replaces sessionx's default alphabetical input.
#
# pos() does NOT work in fzf's 'start' event — the input list isn't available yet
# (fzf 0.53 changelog: "the input list is not available in most cases"). Nor can we
# use 'result' — it fires for the initial piped input before reload-sync replaces it.
# The 'load' event fires once after the input stream (including reload) is fully
# processed, making it reliable for cursor positioning.
RECENT_CMD='tmux list-sessions -F "#{session_activity} #{session_name}" | sort -rn | while read _ts sess; do tmux list-windows -t "$sess" -F "#{session_name}:#{window_index} #{window_name}"; done'
RECENT_LIST=$(eval "$RECENT_CMD")
LINE_NUM=$(echo "$RECENT_LIST" | grep -n "^${CURRENT_WINDOW} " | head -1 | cut -d: -f1)
args+=(--bind "start:reload-sync($RECENT_CMD)")
if [[ -n "$LINE_NUM" ]]; then
    TOTAL=$(echo "$RECENT_LIST" | wc -l | tr -d ' ')
    POS=$((TOTAL - LINE_NUM + 1))
    args+=(--bind "load:pos($POS)")
fi

# --- 2. Override ctrl-r rename-session ---
# execute: prompt for new name, rename, save new name to tmpfile
# reload-sync: refresh list with window view (waits for completion)
# transform: calculate new cursor position and emit pos() action
RENAME_EXEC="bash -c 'printf >&2 \"New name: \";read name; tmux rename-session -t {1} \"\${name}\"; echo \"\${name}\" > ${RENAME_TMPFILE};'"
RENAME_RELOAD='bash -c '\''tmux list-windows -a -F "#{session_name}:#{window_index} #{window_name}";'\'''
RENAME_REPOS="bash -c 'name=\$(cat ${RENAME_TMPFILE} 2>/dev/null); list=\$(tmux list-windows -a -F \"#{session_name}:#{window_index} #{window_name}\"); total=\$(echo \"\$list\" | wc -l | tr -d \" \"); linenum=\$(echo \"\$list\" | grep -n \"^\${name}:\" | head -1 | cut -d: -f1); if [ -n \"\$linenum\" ]; then pos=\$((total - linenum + 1)); echo \"pos(\$pos)\"; fi;'"
args+=(--bind "ctrl-r:execute($RENAME_EXEC)+reload-sync($RENAME_RELOAD)+transform($RENAME_REPOS)")

# --- Helper: reposition cursor to current window after any reload ---
REPOS_CURRENT="bash -c 'list=\$(tmux list-windows -a -F \"#{session_name}:#{window_index} #{window_name}\"); total=\$(echo \"\$list\" | wc -l | tr -d \" \"); linenum=\$(echo \"\$list\" | grep -n \"^${CURRENT_WINDOW} \" | head -1 | cut -d: -f1); if [ -n \"\$linenum\" ]; then pos=\$((total - linenum + 1)); echo \"pos(\$pos)\"; fi;'"

# --- 3. Add ctrl-a to create new session, ctrl-g to create new window ---
NEW_SESSION_EXEC="bash -c 'printf >&2 \"New session name: \"; read name; tmux new-session -d -s \"\${name}\"; echo \"\${name}\" > ${RENAME_TMPFILE};'"
NEW_SESSION_RELOAD='bash -c '\''printf " \n"; tmux list-windows -a -F "#{session_name}:#{window_index} #{window_name}";'\'''
NEW_SESSION_REPOS="bash -c 'name=\$(cat ${RENAME_TMPFILE} 2>/dev/null); list=\$(tmux list-windows -a -F \"#{session_name}:#{window_index} #{window_name}\"); total=\$(echo \"\$list\" | wc -l | tr -d \" \"); linenum=\$(echo \"\$list\" | grep -n \"^\${name}:\" | head -1 | cut -d: -f1); if [ -n \"\$linenum\" ]; then pos=\$((total - linenum + 1)); echo \"pos(\$pos)\"; fi;'"
args+=(--bind "ctrl-a:execute($NEW_SESSION_EXEC)+reload-sync($NEW_SESSION_RELOAD)+transform($NEW_SESSION_REPOS)")

NEW_WIN_EXEC='bash -c '\''session=$(echo {1} | cut -d: -f1); tmux new-window -t "${session}:";'\'''
NEW_WIN_RELOAD='bash -c '\''tmux list-windows -a -F "#{session_name}:#{window_index} #{window_name}";'\'''
args+=(--bind "ctrl-g:execute-silent($NEW_WIN_EXEC)+reload-sync($NEW_WIN_RELOAD)+transform($REPOS_CURRENT)")

# --- 4. Add ctrl-x to kill window, ctrl-q to kill session ---
KILL_WIN_EXEC='bash -c '\''session=$(echo {1} | cut -d: -f1); win=$(echo {1} | cut -d: -f2 | cut -d" " -f1); tmux kill-window -t "${session}:${win}";'\'''
KILL_WIN_RELOAD='bash -c '\''tmux list-windows -a -F "#{session_name}:#{window_index} #{window_name}";'\'''
args+=(--bind "ctrl-x:execute-silent($KILL_WIN_EXEC)+reload-sync($KILL_WIN_RELOAD)+transform($REPOS_CURRENT)")

KILL_SESSION_EXEC='bash -c '\''session=$(echo {1} | cut -d: -f1); tmux kill-session -t "${session}";'\'''
KILL_SESSION_RELOAD='bash -c '\''tmux list-windows -a -F "#{session_name}:#{window_index} #{window_name}";'\'''
args+=(--bind "ctrl-q:execute-silent($KILL_SESSION_EXEC)+reload-sync($KILL_SESSION_RELOAD)+transform($REPOS_CURRENT)")

# --- 5. Add ctrl-y to rename windows ---
# Same pattern: rename, save new name, reload, reposition
WIN_RENAME_EXEC="bash -c 'printf >&2 \"New window name: \"; read name; session=\$(echo {1} | cut -d: -f1); win=\$(echo {1} | cut -d: -f2 | cut -d\" \" -f1); tmux rename-window -t \"\${session}:\${win}\" \"\${name}\"; echo \"\${session}:\${win}\" > ${RENAME_TMPFILE};'"
WIN_RENAME_RELOAD='bash -c '\''tmux list-windows -a -F "#{session_name}:#{window_index} #{window_name}";'\'''
WIN_RENAME_REPOS="bash -c 'target=\$(cat ${RENAME_TMPFILE} 2>/dev/null); list=\$(tmux list-windows -a -F \"#{session_name}:#{window_index} #{window_name}\"); total=\$(echo \"\$list\" | wc -l | tr -d \" \"); linenum=\$(echo \"\$list\" | grep -n \"^\${target} \" | head -1 | cut -d: -f1); if [ -n \"\$linenum\" ]; then pos=\$((total - linenum + 1)); echo \"pos(\$pos)\"; fi;'"
args+=(--bind "ctrl-y:execute($WIN_RENAME_EXEC)+reload-sync($WIN_RENAME_RELOAD)+transform($WIN_RENAME_REPOS)")

# --- 6. Add ctrl-t to toggle sort order (recent ↔ alphabetical) ---
# Default is recent (set by section 1). ctrl-t toggles to alphabetical and back.
# Pre-compute the alphabetical pos at script time (same approach as section 1).
SORT_STATE_FILE="/tmp/sessionx-sort-state"
ALPHA_CMD='tmux list-windows -a -F "#{session_name}:#{window_index} #{window_name}"'
ALPHA_LIST=$(eval "$ALPHA_CMD")
ALPHA_LINE=$(echo "$ALPHA_LIST" | grep -n "^${CURRENT_WINDOW} " | head -1 | cut -d: -f1)
ALPHA_TOTAL=$(echo "$ALPHA_LIST" | wc -l | tr -d ' ')
if [[ -n "$ALPHA_LINE" ]]; then
    ALPHA_POS=$((ALPHA_TOTAL - ALPHA_LINE + 1))
else
    ALPHA_POS=1
fi
# Re-use RECENT_LIST/POS from section 1 for the toggle back to recent
RECENT_POS=${POS:-1}
# Toggle: flip state, reload with the other sort, position cursor (pre-computed)
SORT_TOGGLE="bash -c 'if [ -f ${SORT_STATE_FILE} ] && [ \"\$(cat ${SORT_STATE_FILE})\" = \"recent\" ]; then echo alpha > ${SORT_STATE_FILE}; echo \"reload-sync(${ALPHA_CMD})+change-header(Sort: A-Z)+pos(${ALPHA_POS})\"; else echo recent > ${SORT_STATE_FILE}; echo \"reload-sync(${RECENT_CMD})+change-header(Sort: recent)+pos(${RECENT_POS})\"; fi;'"
args+=(--bind "ctrl-t:transform($SORT_TOGGLE)")
# Initialize sort state to recent (matches the default view from section 1)
echo "recent" > "$SORT_STATE_FILE"

# Store modified args and run sessionx
tmux set-option -g @sessionx-_built-args "$(declare -p args)"

"$PLUGIN_DIR/sessionx.sh"
