# sessionX picker

> Purpose: how the session picker in `sessionx/` works, why it is built this way, and how to test it.
> Read this before changing any binding.

**Status:** active. **Last updated:** 2026-10-24. **Last verified:** 2026-10-24 (`uv run pytest`, 31 passed).

## 1. What it is

`prefix o` opens an fzf popup listing every tmux session, most recently active first, with the cursor on
the current session and, on the right, one window of the selected session as it looks right now. Two
pinned header lines name the session and its window count, then list every window (`index: name`, or the
running command when unnamed). The previewed window is highlighted and the active one starred. `←`/`→`
step through the windows, wrapping at the ends; another session always opens on its active window. The
pane is scrolled to its last non-blank line, so the prompt or latest output is in view. The prompt sits at the top
(`--layout reverse`), so the most recent session is directly under it. It replaced a wrapper around the
`omerxx/tmux-sessionx` plugin in October 2026. The evaluation that led to the rewrite is summarised in
`journal/261024-sessionx-rewrite.md`.

| Key | Action |
| --- | --- |
| `enter` | Switch to the selected session. With no match, switch to the session named exactly as typed, or create it in the client's current directory |
| `esc` | Close, or leave the rename/new/zoxide mode |
| `ctrl-r` | Rename the selected session; the prompt starts from its full name. An empty name cancels |
| `ctrl-a` | New session (stays in the picker, cursor on it). An empty name cancels |
| `ctrl-q` | Kill the selected session. Clients on it move to the most recent other session first; the last session cannot be killed |
| `ctrl-t` | Toggle sort: recent ↔ A-Z |
| `ctrl-f` | Toggle the list to zoxide directories; `enter` on one switches to the session named after the directory, or creates it there |
| `←` / `→` | Preview the previous / next window of the selected session (in a prompt or zoxide mode: move the text cursor) |
| `?` | Toggle the preview (in a prompt mode: types `?`) |
| `ctrl-u` / `ctrl-d` | Scroll the preview (in a prompt mode: clear line / delete char) |

Failed tmux actions show their error in the header instead of failing silently.

## 2. Design

### 2.1 Identity is the tmux id

Every list line is `<key>\t<display>`: `$27\tdot-files X` for a session, `d:/path\t/path` for a directory.
fzf shows only field 2 (`--with-nth 2`) and every action receives field 1. Actions call `tmux -t '$27'`,
which is exact. Names never become targets, so spaces, shared prefixes (`server X` / `server - nwip`) and
regex characters cannot pick the wrong session. The old wrapper used names and fzf's `{1}` (the first
*word*), which killed `dot-files` when `dot-files X` was selected.

### 2.2 One input stream, fzf-native cursor

`sessionx.sh` writes the list to a file and feeds that one stream to fzf with `--sync`, so
`start:pos(N)` lands on the current session at open. Mutations rewrite the file and emit
`reload-sync(cat <file>)` followed by `pos(N)` computed from the same file. `reload-sync` blocks until the
reload (and any query change before it) is applied, so the `pos()` after it is not overwritten. No
`--listen`, `curl` or `sleep` is involved. The old design needed them because the
plugin piped its own list and the wrapper replaced it, giving two competing streams.

### 2.3 Prompts inside fzf

Rename and new-session switch fzf into a prompt mode (`change-prompt`, `disable-search`, the query as the
name). No `execute()` takes over the terminal, so there is no post-redraw cursor loss to work around.

### 2.4 One helper, per-instance state

fzf calls `action.sh <state-dir> <verb> [field1] [query]` for every bound key, so one place decides what a
key means in each mode (`?` toggles the preview in the list but types `?` in a prompt; `?` therefore
cannot be typed into the search). The
helper performs the tmux call and prints the fzf actions to run next (`transform`). The current mode
(`sessions`, `zoxide`, `rename:<id>`, `new`), sort order, client tty and list files live in a
`mktemp -d` directory owned by one picker instance and removed on exit. Nothing is written to tmux
options, so two pickers on two clients cannot interfere.

### 2.5 Files

| File | Role |
| --- | --- |
| `sessionx/sessionx.sh` | Entry point; called by `run-shell` with `#{client_tty}` |
| `sessionx/action.sh` | Every key's behaviour |
| `sessionx/list.sh` | `id\tname` lines, `recent` or `alpha` |
| `sessionx/preview.sh` | One window of the session (`capture-pane -e`) under the window list, or a directory listing in zoxide mode. `--window` reports which window is previewed |

Binding in `~/.tmux.conf.local`:

```tmux
bind o run-shell "~/.tmux/sessionx/sessionx.sh '#{client_tty}'"
```

Tested with fzf 0.74.5 (`--tmux`, `--with-shell`, `transform`), tmux 3.8 and bash. zoxide is optional.

## 3. Tests

```bash
uv run pytest            # ~65 s; private tmux servers (-L), never your running one
```

Each test starts two private servers (`tmux -L sxt-<random>`). The *inner* one holds the sessions under
test and binds F12 to the picker. The *outer* one has a pane running a client attached to the inner
server, so the popup renders as it would in a terminal. The test sends keys to that pane and reads it back
with `capture-pane`. Helpers live in `tests/conftest.py` (`open`, `select`, `press`, `names`,
`client_session`, `attach_another` for a second client).

`SESSIONX_ENTRY=<path>` runs the suite against another entry script. That is how the old wrapper was shown
to fail every finding-tagged case before the rewrite: check out `scripts/` from commit `4be4389`, then run
`SESSIONX_ENTRY=scripts/sessionx-wrapper.sh uv run pytest` (17 failed, 6 passed). That run also needs the
plugin at `~/.tmux/plugins/tmux-sessionx`, which TPM clean removes once the `@plugin` line is gone. `tests/test_shellcheck.py` lints every script beside
the entry.
