#!/usr/bin/env bash
# sessionZ: switch, create, rename and kill tmux sessions from an fzf popup.
# Bound by sessionz.tmux: run-shell "<plugin>/scripts/sessionz.sh '#{client_tty}'"
# Design, keys and tests: docs/sessionz.md
set -u
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
client="${1:-}"
[[ -n "$client" ]] || client=$(tmux display-message -p '#{client_tty}')

state=$(mktemp -d "${TMPDIR:-/tmp}/sessionz.XXXXXX") || exit 0
trap 'rm -rf "$state"' EXIT
printf '%s\n' "$client" >"$state/client"
printf 'sessions\n' >"$state/mode"
printf 'recent\n' >"$state/sort"
"$DIR/list.sh" recent >"$state/list"

current=$(tmux display-message -p -c "$client" '#{session_id}')
line=$(awk -F'\t' -v id="$current" '$1 == id { print NR; exit }' "$state/list")
act="$(printf %q "$DIR/action.sh") $(printf %q "$state")"

# User options from tmux.conf, read on every open so a change needs no reload. The separator is not
# whitespace, so read keeps empty (unset) fields in place.
sep=$'\x1f'
IFS="$sep" read -r width height list_width border border_color blackout < <(tmux display-message -p -c "$client" \
    "#{@sessionz-width}$sep#{@sessionz-height}$sep#{@sessionz-list-width}$sep#{@sessionz-border}$sep#{@sessionz-border-color}$sep#{@sessionz-blackout}")

# option VAR NAME DEFAULT REGEX: keep VAR if it matches REGEX; otherwise use DEFAULT, noting a bad value.
ignored=""
option() {
    local value="${!1}"
    if [[ -n "$value" && ! "$value" =~ $4 ]]; then
        ignored+="${ignored:+, }$2 '$value'"
        value=""
    fi
    printf -v "$1" '%s' "${value:-$3}"
}
option width @sessionz-width 75 '^([1-9][0-9]?|100)%?$'
option height @sessionz-height 75 '^([1-9][0-9]?|100)%?$'
option list_width @sessionz-list-width 25 '^[1-9][0-9]?%?$'
option border @sessionz-border on '^(on|off)$'
option border_color @sessionz-border-color 82 \
    '^(-1|[0-9]{1,2}|1[0-9]{2}|2[0-4][0-9]|25[0-5]|#[0-9a-fA-F]{6}|(bright-)?(black|red|green|yellow|blue|magenta|cyan|white))$'
option blackout @sessionz-blackout off '^(on|off)$'
# ## is a literal # in a tmux message, which would otherwise read it as a format.
[[ -n "$ignored" ]] && tmux display-message -c "$client" "sessionZ: ignored ${ignored//#/##}; using the defaults"
width=${width%\%} height=${height%\%} list_width=${list_width%\%}
preview=$((100 - list_width))
printf '%s\n' "$preview" >"$state/preview"

# half N: half of what N% leaves of 100%, as a percentage (12.5%).
half() {
    local n=$((100 - $1)) rest=""
    ((n % 2)) && rest=.5
    printf '%d%s%%' $((n / 2)) "$rest"
}
if [[ "$blackout" == on ]]; then
    # Cover the whole client and draw the panel inside a margin, so nothing behind it shows.
    popup=(--tmux "center,100%,100%" --margin "$(half "$height"),$(half "$width")")
else
    popup=(--tmux "center,$width%,$height%")
fi
# The frame is fzf's own: fzf --tmux opens the popup without a tmux border. The padding stays either way.
frame=bold
[[ "$border" == off ]] && frame=none

fzf "${popup[@]}" \
    --with-shell 'bash -c' \
    --layout reverse --sync \
    --delimiter '\t' --with-nth '2..' --nth 2 \
    --border "$frame" --padding 1 \
    --prompt '> ' --pointer '▶' \
    --ansi --info hidden --highlight-line --gutter ' ' \
    --color "border:$border_color,preview-border:59,separator:59,scrollbar:59,bg+:82,fg+:black:bold,hl+:black:bold:underline,pointer:black,gutter:-1" \
    --header "$("$DIR/action.sh" "$state" hints)" \
    --preview "$(printf %q "$DIR/preview.sh") $(printf %q "$state") {1}" --preview-window "right,$preview%,follow,~1" \
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
