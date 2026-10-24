#!/usr/bin/env bash
# sessionX: switch, create, rename and kill tmux sessions from an fzf popup.
# Bind with: bind o run-shell "~/.tmux/sessionx/sessionx.sh '#{client_tty}'"
# Design, keys and tests: docs/sessionx.md
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
client="${1:-}"
[[ -n "$client" ]] || client=$(tmux display-message -p '#{client_tty}')

state=$(mktemp -d "${TMPDIR:-/tmp}/sessionx.XXXXXX") || exit 0
trap 'rm -rf "$state"' EXIT
printf '%s\n' "$client" >"$state/client"
printf 'sessions\n' >"$state/mode"
printf 'recent\n' >"$state/sort"
"$DIR/list.sh" recent >"$state/list"

current=$(tmux display-message -p -c "$client" '#{session_id}')
current_name=$(tmux display-message -p -c "$client" '#{session_name}')
line=$(awk -F'\t' -v id="$current" '$1 == id { print NR; exit }' "$state/list")
act="$(printf %q "$DIR/action.sh") $(printf %q "$state")"

fzf --tmux center,75%,75% \
    --with-shell 'bash -c' \
    --layout reverse --sync \
    --delimiter '\t' --with-nth 2 \
    --border rounded --border-label " Current session: \"$current_name\" " \
    --prompt '> ' --pointer '▶' \
    --ansi --info hidden --highlight-line \
    --color 'bg+:82,fg+:black:bold,hl+:black:bold:underline,pointer:black,gutter:-1' \
    --header "$("$DIR/action.sh" "$state" hints)" \
    --preview "$(printf %q "$DIR/preview.sh") $(printf %q "$state") {1}" --preview-window 'right,55%,follow,~1' \
    --bind "start:pos(${line:-1})" \
    --bind "enter:transform($act enter {1} {q})" \
    --bind "esc:transform($act esc)" \
    --bind "ctrl-q:transform($act kill {1})" \
    --bind "ctrl-r:transform($act rename {1})" \
    --bind "ctrl-a:transform($act new)" \
    --bind "ctrl-t:transform($act sort {1})" \
    --bind "ctrl-f:transform($act zoxide)" \
    --bind "?:transform($act '?')" \
    --bind "alt-p:toggle-preview" \
    --bind "ctrl-u:transform($act ctrl-u)" \
    --bind "ctrl-d:transform($act ctrl-d)" \
    --bind "right:transform($act win-next {1})" \
    --bind "left:transform($act win-prev {1})" \
    --bind "ctrl-l:transform($act win-next {1})" \
    --bind "ctrl-h:transform($act win-prev {1})" \
    <"$state/list" >/dev/null

# run-shell reports a non-zero exit in the pane; aborting the picker is not an error.
exit 0
