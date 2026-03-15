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

### `start:reload-sync(CMD)` + `load:pos(N)` — ~80% reliable

The `load` event fires "when the input stream is complete and the initial
processing of the list is complete"
([fzf 0.36.0 changelog](https://github.com/junegunn/fzf/blob/master/CHANGELOG.md),
search "0.36.0"). When `start:reload-sync` replaces the input, `load` fires
after the reloaded data is fully processed — confirmed by the event ordering
test above (`load` appears after `start`).

**However**, when fzf receives piped input AND `start:reload-sync` replaces it,
`load` can fire for the piped input before reload-sync replaces it. This makes
`load:pos(N)` unreliable (~80% success) when the piped input has a different
order than the reloaded input — `pos(N)` applies to the wrong list. See
"Why `load:pos(N)` was unreliable" below for details.

Additional caveat: `load` fires after *every* input stream completion, not just
once. User-triggered `reload-sync` bindings (ctrl-r, ctrl-t, etc.) will
re-fire `load`, re-applying `pos($POS)` with the stale startup value.

```bash
args+=(--bind "start:reload-sync($RECENT_CMD)")
args+=(--bind "load:pos($POS)")
```

### User-triggered `reload-sync` + `transform` — mostly reliable

For bindings triggered by user interaction (ctrl-r, ctrl-t, etc.), fzf is
fully initialized. `reload-sync(CMD)+transform(SCRIPT)` works because:

1. fzf is past the startup phase; the result list is properly maintained.
2. `transform` defers action execution — its stdout is parsed as fzf actions,
   which run after the reload is fully processed.

```bash
args+=(--bind "ctrl-r:execute(...)+reload-sync(CMD)+transform(SCRIPT)")
```

Where `SCRIPT` outputs `pos(N)` after computing the correct position.

### Inline cursor positioning after state changes — unreliable

Cursor positioning via actions chained inline (`pos(N)`, `last`,
`transform(pos(N))`) is unreliable when the list or display state has changed
earlier in the same action chain. This affects two confirmed scenarios:

**1. After `execute()` (terminal takeover):**

When the chain includes `execute()` (which takes over the terminal for user
input), cursor positioning in subsequent chained actions fails:

| Chained after `execute()+reload-sync(CMD)` | Result   |
| ------------------------------------------ | -------- |
| `transform(repos.sh)` → outputs `pos(N)`  | position 2 |
| `last`                                      | position 2 |

Observed for ctrl-a (new session creation) where `--boost` places the new
session at line 1 (top of display with `--tac`). Cursor consistently lands on
position 2 (the second item).

**Cause:** After `execute()` returns control to fzf, fzf redraws the terminal.
This redraw resets or overrides cursor position set by subsequent actions in
the chain. Confirmed by the HTTP API fix working (HTTP-delivered actions are
processed after the redraw).

**Why other `execute()` operations appear unaffected:** ctrl-r (rename session)
and ctrl-y (rename window) also use `execute()` but don't exhibit the off-by-one
because renaming doesn't change list order — even if fzf resets the cursor to
its pre-execute position, that position is still correct.

**2. After `change` event (query text changes):**

Sessionx sets `change:first`, but with `--tac`, `first` = bottom of display.
Overriding with `change:last` or `change:transform(echo last)` does not
reliably position the cursor at the top — after clearing a filter query, the
cursor lands in the middle of the list instead:

| `change` binding                              | Result             |
| --------------------------------------------- | ------------------ |
| `change:last`                                  | middle of list     |
| `change:transform(echo last)`                  | middle of list     |
| `change:transform` → HTTP API `last`           | top of list ✓      |

**Cause:** Same rendering override. When the query changes, fzf re-filters and
redraws. Inline `last` runs before the redraw completes and is overridden.

**Fix for both:** Use the `--listen` HTTP API to send cursor actions after fzf
has fully settled. A background `curl` with a 100ms delay ensures the action
is processed after all rendering:

```bash
# ctrl-a: new session — send 'last' via HTTP after execute()+reload-sync
args+=(--bind "ctrl-a:execute(PROMPT)+reload-sync(LIST --boost NAME)\
+execute-silent(bash -c 'sleep 0.1; curl -s -X POST \
http://localhost:PORT -d last' &)")

# change: cursor to top when query is cleared — conditional HTTP via transform
args+=(--bind "change:transform([[ -z {q} ]] && echo \
\"execute-silent(bash -c 'sleep 0.1; curl -s -X POST \
http://localhost:PORT -d last' &)\")")
```

The `execute-silent` backgrounds a process that waits 100ms, then sends `last`
via the HTTP API. fzf processes the HTTP-delivered action after all rendering
is complete, reliably moving the cursor to the top of the display.

### `pos(N)` via `--listen` HTTP API — reliable (adopted solution)

Sending `pos(N)` via `curl -X POST localhost:PORT -d 'pos(N)'` after fzf is
running always works. This is the approach adopted for startup positioning.

**Why an HTTP API for a tmux plugin?** It looks like overkill, but every
event-based approach (`load`, `result`, `unbind`/`rebind`) fails due to the
fundamental problem: the wrapper doesn't control fzf's piped input (sessionx
does), so there are always two competing input streams and no way to guarantee
event ordering between them using fzf's built-in event system alone.

The HTTP API sidesteps this entirely — it's the only mechanism that guarantees
`pos()` runs *after* `reload-sync` completes, because `reload-sync` blocks
fzf's main event loop and HTTP-delivered actions queue behind it.

**How it works internally:** fzf is written in Go. The `--listen` HTTP server
runs in a separate goroutine. When it receives a POST with actions (e.g.,
`pos(5)`), it sends them to the main event loop's channel. If `reload-sync` is
currently blocking the main loop, the action sits in the channel until
`reload-sync` finishes and the loop resumes — at which point `pos()` applies to
the correct (reloaded) list.

**Alternative that would eliminate the need:** If sessionx were patched to pipe
the chronological list directly (or to accept a custom input command), there
would be no competing input streams and `load:pos(N)` would work reliably. The
HTTP approach exists because we chose not to modify plugin source files (so the
wrapper survives plugin updates).

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

## Current solution: `--listen` HTTP API

The `load:pos(N)` approach was only ~80% reliable due to the piped-input race
condition (see below). The current solution uses fzf's `--listen` HTTP API:

```bash
FZF_LISTEN_PORT=$((RANDOM % 10000 + 40000))
args+=(--listen "localhost:$FZF_LISTEN_PORT")
args+=(--bind "start:reload-sync($LIST_CMD)")

# Background: wait for fzf, then send pos() via HTTP
(
    for _ in $(seq 1 100); do
        if curl -s -o /dev/null --connect-timeout 0.1 \
            "http://localhost:$FZF_LISTEN_PORT" 2>/dev/null; then
            sleep 0.1
            curl -s -X POST "http://localhost:$FZF_LISTEN_PORT" \
                -d "pos($POS)" 2>/dev/null
            break
        fi
        sleep 0.02
    done
) &
```

**Why this works:** `start:reload-sync` blocks fzf's main event loop. The
HTTP-delivered `pos()` action is received by the HTTP listener goroutine and
queued in the main event channel. When `reload-sync` completes and the main
loop resumes, it dequeues `pos()` and applies it to the correct (reloaded)
list. The 100ms sleep after connection provides margin for `reload-sync` to
start blocking before we send `pos()`.

**Limitation:** Incompatible with sessionx's git-branch mode, which also uses
`--listen`. fzf only supports one `--listen` port; the last `--listen` arg
wins. If git-branch mode is enabled, its port overrides ours and the background
curl fails silently (cursor lands at default position).

### Previous solution: `load:pos(N)` (~80% reliable)

```bash
args+=(--bind "start:reload-sync($RECENT_CMD)")
args+=(--bind "load:pos($POS)")
```

### Why `load:pos(N)` was unreliable (piped-input race condition)

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
  - `--listen` (0.36.0): HTTP server for sending actions to fzf programmatically
- fzf man page (`man fzf`):
  - AVAILABLE ACTIONS: `pos(...)`, `first` (= `pos(1)`), `last` (= `pos(-1)`)
  - `--tac`: "Reverse the order of the input"
  - `reload-sync(...)`: "synchronous version of reload"
  - `--listen`: "Start HTTP server on the given address... POST a valid action to perform it"
