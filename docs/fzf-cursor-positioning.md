# Cursor positioning in fzf with `reload-sync`

How to reliably set the cursor position when using fzf's `reload-sync` to
replace the input list at startup. Documented while implementing the "open
sessionx with current window pre-selected" feature.

Environment: fzf 0.67.0 (Homebrew), tmux 3.6a, bash 5.3.9 (Homebrew;
system bash is 3.2.57), zsh 5.9, macOS (Darwin 25.3.0).
tmux-sessionx: commit 301ce31 (no tagged releases).

## The problem

The sessionx wrapper replaces fzf's default input (session names) with a
chronological window list via `start:reload-sync(CMD)`. After reload, we need
`pos(N)` to move the cursor to the currently focused tmux window.

Naively chaining `start:reload-sync(CMD)+pos(N)` does not work.

## fzf event lifecycle

fzf's `start` event fires before input is available. From the
[fzf 0.36.0 changelog](https://github.com/junegunn/fzf/blob/master/CHANGELOG.md)
(search "0.36.0") and the fzf man page:

> "Since fzf consumes the input stream asynchronously, the input list is
> not available unless you use `--sync`."

Empirical event ordering (tested via `execute-silent(echo EVENT >> log)`):

```
start            ← fires first, before any input is read
load             ← after the input stream is fully processed
result           ← after filtering; fires multiple times
result
result
result
```

Source: tested by binding `execute-silent(echo EVENT >> FILE)` to `start`,
`load`, and `result`, with `reload-sync` in `start`. Verified on fzf 0.67.0.

Note: there is no `start-done` event in fzf. The `start` event fires once
at startup; `load` fires when the input stream (including any
`start:reload-sync` replacement) is fully processed.

## What doesn't work and why

### `start:reload-sync(CMD)+pos(N)` — fails

`pos()` runs immediately after `reload-sync` returns, but fzf hasn't indexed
the new result list yet. The cursor silently stays at position 0.

Reference: fzf 0.36.0 changelog, `start` event description.

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
event dispatching doesn't guarantee the ordering we need. (`unbind` was
introduced in fzf 0.27.1, `rebind` in 0.30.0.)

## What works

### `start:reload-sync(CMD)` + `load:pos(N)` — reliable

The `load` event fires "when the input stream is complete and the initial
processing of the list is complete"
([fzf 0.36.0 changelog](https://github.com/junegunn/fzf/blob/master/CHANGELOG.md),
search "0.36.0"). When `start:reload-sync` replaces the input, `load` fires
after the reloaded data is fully processed — confirmed by the event ordering
test above (`load` appears after `start`).

Caveat: `load` fires after *every* input stream completion, not just once.
User-triggered `reload-sync` bindings (ctrl-r, ctrl-t, etc.) will re-fire
`load`, re-applying `pos($POS)` with the stale startup value. In practice
this is harmless if those bindings also set cursor position via `transform`
(which runs after `reload-sync` but before `load` re-fires), though the
`load` handler may briefly flicker the cursor. If this becomes a problem,
`unbind(load)` can be chained after the initial `load:pos(N)` fires.

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

## Current solution

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

The position is pre-computed at script time (before fzf launches) to avoid
races between the reload command and position calculation.

### Known issue: piped-input race condition

The sessionx plugin pipes an **alphabetical** window list into fzf via stdin.
The wrapper's `start:reload-sync` replaces it with a **chronological** list.
`POS` is pre-computed for the chronological order.

`load` can fire for the piped (alphabetical) input before `reload-sync`
replaces it. When that happens, `pos(POS)` applies to the wrong list — e.g.,
`pos(24)` selects `dev-lyrics:1` instead of `server:2`. The two lists
contain identical items but in different orders:
- Alphabetical (sessionx `input()`): `tmux list-windows -a -F ...`
- Chronological (wrapper `RECENT_CMD`): sessions sorted by `session_activity`,
  windows listed per session

Approaches tried and failed:
- `start:unbind(load)+reload-sync(CMD)+rebind(load)` + `load:pos(N)+unbind(load)`
  — still unreliable (~70% success); fzf event dispatching doesn't guarantee
  the ordering needed
- `load:reload-sync(CMD)+transform(echo pos(N))+unbind(load)` — cursor always
  lands on last item; `transform` output doesn't defer long enough for fzf to
  index the reloaded list

The `--listen` HTTP API (post-start `curl`) remains the only confirmed 100%
reliable method for startup positioning, but adds complexity (port selection,
background process, cleanup).

## References

- fzf CHANGELOG.md: https://github.com/junegunn/fzf/blob/master/CHANGELOG.md
  - `start` event (0.36.0): "the input list is not available unless you use `--sync`"
  - `load` event (0.36.0): fires when input stream is complete
  - `result` event (0.46.0): fires when filtering is complete
  - `pos()` action (0.36.0): move cursor to numeric position
  - `reload-sync` (0.36.0): synchronous input replacement
  - `transform` (0.45.0): conditionally perform actions based on script output
  - `unbind` (0.27.1) / `rebind` (0.30.0): dynamic binding management
  - `--track` with `--tac` warning (0.39.0): "not recommended"
- fzf man page (`man fzf`):
  - AVAILABLE ACTIONS: `pos(...)`, `first` (= `pos(1)`), `last` (= `pos(-1)`)
  - `--tac`: "Reverse the order of the input"
  - `reload-sync(...)`: "synchronous version of reload"
