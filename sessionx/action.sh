#!/usr/bin/env bash
# Behaviour of every picker key. fzf runs this through `transform`, so whatever
# it prints is the list of fzf actions to run next.
#
# Usage: action.sh STATE_DIR VERB [KEY] [QUERY]
#   STATE_DIR  per-picker directory made by sessionx.sh (mode, sort, client, list files)
#   KEY        field 1 of the focused line: a session id ($27) or d:/path
#   QUERY      the current query, which is the name being typed in prompt modes
#
# Modes (STATE_DIR/mode): sessions | zoxide | new | rename:<session_id>
# Free text (headers, the prefilled rename query) is always printed last, in the
# colon form (change-header:..., change-query:...), whose argument runs to the
# end of the string, so names and tmux error text need no escaping.
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
state="$1"
verb="$2"
key="${3:-}"
key="${key%$'\t'}"
query="${4:-}"
mode=$(<"$state/mode")
sort=$(<"$state/sort")
client=$(<"$state/client")
list="$state/list"
tab=$'\t'

hints() {
    local order=recent
    [[ "$sort" == alpha ]] && order=A-Z
    printf 'Sort: %s · enter switch · ^r rename · ^a new · ^q kill · ^t sort · ^f zoxide · ? preview' "$order"
}

set_mode() { printf '%s\n' "$1" >"$state/mode"; }

prompting() { [[ "$mode" == rename:* || "$mode" == new ]]; }

# Rewrite the session list file in the current sort order.
refresh() { "$DIR/list.sh" "$sort" >"$list"; }

# 1-based line of an id in the list file, or nothing.
line_of() { awk -F"$tab" -v id="$1" '$1 == id { print NR; exit }' "$list"; }

# Id of the session whose name is exactly $1, or nothing.
id_by_name() {
    tmux list-sessions -F "#{session_id}${tab}#{session_name}" |
        awk -F"$tab" -v name="$1" '$2 == name { print $1; exit }'
}

# First line of a (possibly multi-line) tmux error, safe to put in a header.
first_line() { head -n 1 <<<"$1"; }

# New detached session named $1 in directory $2; prints its id, or the error on failure.
create_session() { tmux new-session -d -s "$1" -c "$2" -P -F '#{session_id}' 2>&1; }

# Leave a prompt or zoxide mode: back to the session list, cursor on session $1.
# reload-sync blocks until the list (and the cleared query) is applied, so the
# pos() that follows lands on the reloaded list rather than being overwritten.
to_sessions() {
    local focus="$1" line=""
    set_mode sessions
    refresh
    [[ -n "$focus" ]] && line=$(line_of "$focus")
    printf 'change-prompt(> )+enable-search+clear-query+reload-sync(cat %q)' "$list"
    [[ -n "$line" ]] && printf '+pos(%s)' "$line"
    printf '+change-header:%s' "${2:-$(hints)}"
}

# Print an error in the header and stop.
fail() {
    printf 'change-header:⚠ %s' "$(first_line "$1")"
    exit 0
}

# Switch the client to session $1 and, if given, its window $2.
switch_to() {
    local err
    err=$(tmux switch-client -c "$client" -t "$1" 2>&1) || fail "$err"
    if [[ -n "${2:-}" ]]; then
        err=$(tmux select-window -t "$2" 2>&1) || fail "$err"
    fi
    printf 'abort'
}

client_path() { tmux display-message -p -c "$client" '#{pane_current_path}'; }

case "$verb" in
hints)
    hints
    ;;

enter)
    case "$mode" in
    rename:*)
        id="${mode#rename:}"
        if [[ -n "$query" ]]; then
            err=$(tmux rename-session -t "$id" -- "$query" 2>&1) ||
                { to_sessions "$id" "⚠ $(first_line "$err")"; exit 0; }
        fi
        to_sessions "$id"
        ;;
    new)
        [[ -n "$query" ]] || { to_sessions ""; exit 0; }
        id=$(create_session "$query" "$(client_path)") || { to_sessions "" "⚠ $(first_line "$id")"; exit 0; }
        to_sessions "$id"
        ;;
    zoxide)
        [[ "$key" == d:* ]] || exit 0
        path="${key#d:}"
        name=$(basename "$path")
        id=$(id_by_name "$name")
        if [[ -z "$id" ]]; then
            id=$(create_session "$name" "$path") || fail "$id"
        fi
        switch_to "$id"
        ;;
    *)
        if [[ "$key" == \$* ]]; then
            # Land on the window being previewed (the active one unless ←/→ chose another).
            switch_to "$key" "$("$DIR/preview.sh" "$state" --window "$key")"
        elif [[ -n "$query" ]]; then
            # Nothing matched the typed text: it is the name of a new session, verbatim.
            id=$(id_by_name "$query")
            if [[ -z "$id" ]]; then
                id=$(create_session "$query" "$(client_path)") || fail "$id"
            fi
            switch_to "$id"
        fi
        ;;
    esac
    ;;

esc)
    case "$mode" in
    rename:*) to_sessions "${mode#rename:}" ;;
    new | zoxide) to_sessions "" ;;
    *) printf 'abort' ;;
    esac
    ;;

kill)
    [[ "$mode" == sessions && "$key" == \$* ]] || exit 0
    err=$(tmux has-session -t "$key" 2>&1) || fail "$err"
    [[ $(tmux list-sessions | wc -l) -gt 1 ]] || fail "can't kill the last session"
    # Move every client on the doomed session to the most recent other one first;
    # with detach-on-destroy on, killing it under them would detach them.
    fallback=$("$DIR/list.sh" recent | awk -F"$tab" -v id="$key" '$1 != id { print $1; exit }')
    # Refuse rather than kill if any client cannot be moved: it would be detached.
    while IFS= read -r tty; do
        [[ -n "$tty" ]] || continue
        err=$(tmux switch-client -c "$tty" -t "$fallback" 2>&1) || fail "$err"
    done < <(tmux list-clients -t "$key" -F '#{client_tty}' 2>/dev/null)
    err=$(tmux kill-session -t "$key" 2>&1) || fail "$err"
    refresh
    # Keep the cursor at the same row, clamped to the shrunken result list.
    line="${FZF_POS:-1}"
    last=$((${FZF_MATCH_COUNT:-1} - 1))
    ((line > last)) && line=$last
    ((line < 1)) && line=1
    printf 'reload-sync(cat %q)+pos(%s)+change-header:%s' "$list" "$line" "$(hints)"
    ;;

rename)
    [[ "$mode" == sessions && "$key" == \$* ]] || exit 0
    name=$(tmux display-message -p -t "$key" '#{session_name}' 2>&1) || fail "$name"
    set_mode "rename:$key"
    printf 'change-prompt(Rename: )+disable-search+change-header(enter rename · esc cancel)+change-query:%s' "$name"
    ;;

new)
    [[ "$mode" == sessions ]] || exit 0
    set_mode new
    printf 'change-prompt(New session: )+disable-search+clear-query+change-header:enter create · esc cancel'
    ;;

sort)
    [[ "$mode" == sessions ]] || exit 0
    if [[ "$sort" == recent ]]; then sort=alpha; else sort=recent; fi
    printf '%s\n' "$sort" >"$state/sort"
    to_sessions "$key"
    ;;

zoxide)
    case "$mode" in
    sessions)
        command -v zoxide >/dev/null || fail "zoxide is not installed"
        zoxide query -l | awk -v t="$tab" '{ print "d:" $0 t $0 }' >"$state/dirs"
        set_mode zoxide
        printf 'change-prompt(zoxide> )+clear-query+reload-sync(cat %q)+change-header:enter open · ^f/esc back' "$state/dirs"
        ;;
    zoxide) to_sessions "" ;;
    esac
    ;;

# Left/right (and ctrl-h/ctrl-l): move the text cursor in a prompt or zoxide mode; otherwise cycle the
# preview through the focused session's windows, wrapping at either end.
win-next | win-prev)
    if prompting || [[ "$mode" == zoxide ]]; then
        if [[ "$verb" == win-next ]]; then printf 'forward-char'; else printf 'backward-char'; fi
        exit 0
    fi
    [[ "$key" == \$* ]] || exit 0
    step=1
    [[ "$verb" == win-prev ]] && step=-1
    current=$("$DIR/preview.sh" "$state" --window "$key")
    next=$(tmux list-windows -t "$key" -F '#{window_id}' | awk -v cur="$current" -v step="$step" '
        { w[NR] = $0; if ($0 == cur) i = NR }
        END { j = i + step; if (j < 1) j = NR; if (j > NR) j = 1; print w[j] }')
    printf '%s\t%s\n' "$key" "$next" >"$state/window"
    printf 'refresh-preview'
    ;;

# Keys that type text in a prompt mode and drive the preview otherwise.
'?')
    if prompting; then printf 'put(?)'; else printf 'toggle-preview'; fi
    ;;
ctrl-u)
    if prompting; then printf 'unix-line-discard'; else printf 'preview-half-page-up'; fi
    ;;
ctrl-d)
    if prompting; then printf 'delete-char'; else printf 'preview-half-page-down'; fi
    ;;
esac
