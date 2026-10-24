# sessionX picker

> Purpose: how the session picker in `sessionx/` works, why it is built this way, and how to test it.
> Read this before changing any binding.

**Status:** active. **Last updated:** 2026-10-24. **Last verified:** 2026-10-24 (`uv run pytest`, 51 passed).

## 1. What it is

`prefix o` opens an fzf popup listing every tmux session, most recently active first, with the cursor on
the current session and, on the right, one window of the selected session as it looks right now. A
pinned header line lists every window (`index: name`, or the running command when unnamed); the
previewed window is highlighted and the active one starred. `←`/`→`
(or `ctrl-h`/`ctrl-l`) step through the windows, wrapping at the ends; another session always opens on its
active window, and `enter` lands on whichever window is previewed. A window with several panes shows them
stacked in index order, each under a full-width `── pane N: command ───` rule in the accent green.
The preview's height is shared by water-filling: a pane short enough to fit is shown in full, and the
remaining lines go to the longer panes, which reach back into their scrollback to use them. Stacking
keeps every pane readable at the preview's width; a side-by-side split is therefore shown one pane above
the other. Each pane ends at its last non-blank line, so the prompt or latest output is in view. The prompt sits at the top
(`--layout reverse`). Under it, a short header (`? keys · Sort: recent`) and a blank row, then the list
with the most recent session first. The selected row is highlighted across its full width in
the accent green (`--highlight-line`, `bg+:82`); the gutter is blank (`--gutter ' '`, `gutter:-1`): fzf otherwise draws a `▌` beside every unselected row.
The accent is the tmux status bar's green, `#5fff00` (`tmux_conf_theme_colour_11`), which is colour 82
of the 256-colour palette; key names, pane rules and the selection use it, section titles use bright cyan. fzf's match counter is hidden (`--info hidden`). It replaced a wrapper around the
`omerxx/tmux-sessionx` plugin in October 2026. The evaluation that led to the rewrite is summarised in
`journal/261024-sessionx-rewrite.md`.

| Key | Action |
| --- | --- |
| `enter` | Switch to the selected session, on the window being previewed. With no match, switch to the session named exactly as typed, or create it in the client's current directory |
| `esc` | Close, or leave the rename/new/zoxide mode |
| `ctrl-r` | Rename the selected session; the prompt starts from its full name. An empty name cancels |
| `ctrl-a` | New session (stays in the picker, cursor on it). An empty name cancels |
| `ctrl-q` | Kill the selected session. Clients on it move to the most recent other session first; the last session cannot be killed |
| `ctrl-t` | Toggle sort: recent ↔ A-Z |
| `ctrl-f` | Toggle the list to zoxide directories; `enter` on one switches to the session named after the directory, or creates it there |
| `←` / `→`, `ctrl-h` / `ctrl-l` | Preview the previous / next window of the selected session (in a prompt or zoxide mode: move the text cursor) |
| `?` | Show / hide the key sheet in the preview pane, in two columns when it is wide enough (in a prompt mode: types `?`) |
| `alt-p` | Show / hide the preview |
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

fzf calls `action.sh <state-dir> <verb> [field1] [query]` for every bound key except `alt-p` (a plain
`toggle-preview`), so one place decides what a key means in each mode (`?` opens the key sheet in the
list but types `?` in a prompt; `?` therefore cannot be typed into the search). `esc` closes the key sheet
before it closes anything else. The
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
| `sessionx/preview.sh` | One window of the session (`capture-pane -e`, with history) under the window list, or a directory listing in zoxide mode. `--window` reports which window is previewed. `tests/test_preview_layout.py` runs it directly to check the line budget |

Binding in `~/.tmux.conf.local`:

```tmux
bind o run-shell "~/.tmux/sessionx/sessionx.sh '#{client_tty}'"
```

Tested with fzf 0.74.5 (`--tmux`, `--with-shell`, `transform`), tmux 3.8 and bash. zoxide is optional.

## 3. Tests

```bash
uv run pytest            # ~90 s; private tmux servers (-L), never your running one
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
