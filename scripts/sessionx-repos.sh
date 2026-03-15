#!/usr/bin/env bash
# Compute fzf pos() for a target in the chronological window list.
# Usage:
#   sessionx-repos.sh --session NAME [--boost SESSION]
#   sessionx-repos.sh --window SESS:IDX [--boost SESSION]
# Outputs: pos(N) action string, or empty if target not found.
# Used by sessionx-wrapper.sh in fzf transform bindings.
# --boost is passed through to sessionx-list-recent.sh (see that script for details).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="$1"
TARGET="$2"
BOOST_ARGS=""
if [[ "$3" == "--boost" ]]; then
    BOOST_ARGS="--boost $4"
fi

[[ -z "$TARGET" ]] && exit 0

list=$("$SCRIPT_DIR/sessionx-list-recent.sh" $BOOST_ARGS)
total=$(echo "$list" | wc -l | tr -d ' ')

case "$MODE" in
    --session) linenum=$(echo "$list" | grep -n "^${TARGET}:" | head -1 | cut -d: -f1) ;;
    --window)  linenum=$(echo "$list" | grep -n "^${TARGET} " | head -1 | cut -d: -f1) ;;
    *)         exit 1 ;;
esac

if [[ -n "$linenum" ]]; then
    echo "pos($((total - linenum + 1)))"
fi
