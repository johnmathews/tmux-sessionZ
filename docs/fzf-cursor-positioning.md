# Cursor positioning in fzf with `reload-sync`

How to reliably set the cursor position when using fzf's `reload-sync` to
replace the input list at startup. Documented while implementing the "open
sessionx with current window pre-selected" feature.

Environment: fzf 0.67.0, tmux 3.6a, bash 5.3.9, macOS.

## The problem

The sessionx wrapper replaces fzf's default input (session names) with a
chronological window list via `start:reload-sync(CMD)`. After reload, we need
`pos(N)` to move the cursor to the currently focused tmux window.

Naively chaining `start:reload-sync(CMD)+pos(N)` does not work.

## fzf event lifecycle

fzf's `start` event fires before input is available. From the
[fzf 0.53.0 changelog](https://github.com/junegunn/fzf/blob/master/CHANGELOG.md)
(search "0.53.0"):

> "Since fzf consumes the input asynchronously, the input list is not
> available in most cases."

Empirical event ordering (tested via `execute-silent(echo EVENT >> log)`):

```
start            ← fires first, before any input is read
start-done       ← after reload-sync completes
load             ← after the input stream is fully processed
result           ← after filtering; fires multiple times
result
result
result
```

Source: tested by binding `execute-silent(echo EVENT >> FILE)` to `start`,
`load`, and `result`, with `reload-sync` in `start`. Verified on fzf 0.67.0.

## What doesn't work and why

### `start:reload-sync(CMD)+pos(N)` — fails

`pos()` runs immediately after `reload-sync` returns, but fzf hasn't indexed
the new result list yet. The cursor silently stays at position 0.

Reference: fzf 0.53.0 changelog, `start` event description.

### `start:reload-sync(CMD)` + `result:pos(N)+unbind(result)` — fails

The `result` event fires when "filtering for the current query is complete."
The problem: fzf processes the initial piped input concurrently with the
`start` event's action chain. By the time `reload-sync` finishes, `result`
has already fired for the initial (pre-reload) input, applied `pos(N)` to the
wrong list (e.g., 10 sessions instead of 25 windows), and `unbind(result)` has
removed the handler. When the reloaded data produces a new result, there's no
handler left.

Verified by observing `pos(24)` clamping to `pos(10)` on the initial 10-item
session list, producing `position=9` — consistent with `pos` clamping to the
list length.

### `start:unbind(result)+reload-sync(CMD)+rebind(result)` + `result:pos(N)+unbind(result)` — fails

Attempted to suppress the premature `result` by unbinding it before
`reload-sync` and rebinding after. Still produced wrong positions. The
`rebind` may re-fire a queued result from the initial input, or internal fzf
event dispatching doesn't guarantee the ordering we need.

## What works

### `start:reload-sync(CMD)` + `load:pos(N)` — reliable

The `load` event fires "when the input stream is complete and the initial
processing of the list is done"
([fzf 0.49.0 changelog](https://github.com/junegunn/fzf/blob/master/CHANGELOG.md),
search "0.49.0"). When `start:reload-sync` replaces the input, `load` fires
after the reloaded data is fully processed — confirmed by the event ordering
test above (`load` appears after `start-done`).

`load` fires exactly once, so no `unbind` is needed.

```bash
args+=(--bind "start:reload-sync($RECENT_CMD)")
args+=(--bind "load:pos($POS)")
```

### User-triggered `reload-sync` + `transform` — reliable

For bindings triggered by user interaction (ctrl-r, ctrl-t, etc.), fzf is
fully initialized. `reload-sync(CMD)+transform(SCRIPT)` works because:

1. fzf is past the startup phase; the result list is properly maintained.
2. `transform` defers action execution — its stdout is parsed as fzf actions,
   which run after the reload is fully processed.

```bash
args+=(--bind "ctrl-r:execute(...)+reload-sync(CMD)+transform(SCRIPT)")
```

Where `SCRIPT` outputs `pos(N)` after computing the correct position.

### `pos(N)` via `--listen` HTTP API — reliable

Sending `pos(N)` via `curl -X POST localhost:PORT -d 'pos(N)'` after fzf is
running always works. Not practical for startup positioning, but useful for
debugging.

## pos() semantics with `--tac`

The sessionx setup uses `--tac` (reverse input) + `--layout=default`
(prompt at bottom, list grows upward).

- `pos(1)` = first item after `--tac` = last item of original input
- `pos(N)` counts from the first displayed item (nearest to prompt in default
  layout)
- To select original line `L` from a list of `T` items: `pos(T - L + 1)`

Verified via fzf's `--listen` HTTP API:

```
Input: line1-AAA, line2-BBB, line3-CCC, line4-DDD, line5-EEE
Flags: --tac --layout=default

pos(1) → position=0 → line5-EEE  (last original, first after tac)
pos(2) → position=1 → line4-DDD
pos(3) → position=2 → line3-CCC
pos(5) → position=4 → line1-AAA  (first original, last after tac)
```

## Current solution (90% reliable)

```bash
RECENT_CMD='tmux list-sessions -F "#{session_activity} #{session_name}" \
  | sort -rn | while read _ts sess; do \
  tmux list-windows -t "$sess" \
    -F "#{session_name}:#{window_index} #{window_name}"; done'

RECENT_LIST=$(eval "$RECENT_CMD")
LINE_NUM=$(echo "$RECENT_LIST" | grep -n "^${CURRENT_WINDOW} " | head -1 | cut -d: -f1)

args+=(--bind "start:reload-sync($RECENT_CMD)")
if [[ -n "$LINE_NUM" ]]; then
    TOTAL=$(echo "$RECENT_LIST" | wc -l | tr -d ' ')
    POS=$((TOTAL - LINE_NUM + 1))
    args+=(--bind "load:pos($POS)")
fi
```

The remaining ~10% failure rate is likely a timing edge case where `load`
fires before the reloaded result list is fully indexed, similar to the `start`
event issue but less frequent. A possible mitigation would be to also bind
`result:pos(N)+unbind(result)` as a fallback, accepting that it may
occasionally position on the pre-reload list.

## References

- fzf CHANGELOG.md: https://github.com/junegunn/fzf/blob/master/CHANGELOG.md
  - `start` event (0.53.0): "the input list is not available in most cases"
  - `load` event (0.49.0): fires when input stream is complete
  - `result` event (0.49.0): fires when filtering is complete
  - `pos()` action (0.36.0): move cursor to numeric position
  - `reload-sync` (0.36.0): synchronous input replacement
  - `--track` with `--tac` warning (0.39.0): "not recommended"
- fzf man page (`man fzf`):
  - AVAILABLE ACTIONS: `pos(...)`, `first` (= `pos(1)`), `last` (= `pos(-1)`)
  - `--tac`: "Reverse the order of the input"
  - `reload-sync(...)`: "synchronous version of reload"
