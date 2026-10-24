#!/usr/bin/env bash
# TPM entry point: TPM runs every *.tmux file in the plugin root when tmux loads.
# Binds the sessionZ picker. Options (set before TPM runs, in .tmux.conf):
#   @sessionz-bind    key to bind (default: o)
#   @sessionz-prefix  on: the key follows the prefix (default); off: bind it directly
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

option() {
    local value
    value=$(tmux show-option -gqv "$1")
    printf '%s' "${value:-$2}"
}

key=$(option @sessionz-bind o)
table=prefix
[[ "$(option @sessionz-prefix on)" == off ]] && table=root

# The client tty lets the picker switch and kill on behalf of exactly the client that opened it.
tmux bind-key -T "$table" "$key" run-shell "'$CURRENT_DIR/scripts/sessionz.sh' '#{client_tty}'"
