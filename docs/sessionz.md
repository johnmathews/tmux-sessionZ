# sessionZ design

> Purpose: how sessionZ works, why it is built this way, and how to test it. Read this before changing
> any binding.

**Status:** active. **Last updated:** 2026-10-24. **Last verified:** 2026-10-24 (`uv run pytest`, 74 passed).

## 1. What it is

The picker key (`prefix o` by default) opens an fzf popup listing every tmux session, the one with the
most recent output first, with the cursor on the current session. sessionZ began in October 2026 as a rewrite of a local
wrapper around [`omerxx/tmux-sessionx`](https://github.com/omerxx/tmux-sessionx). It shares that
plugin's idea and none of its code. The evaluation that led to the rewrite is in
`journal/261024-sessionx-rewrite.md`.

### 1.1 Keys

| Key | Action |
| --- | --- |
| `enter` | Switch to the selected session, on the window being previewed. With no match, switch to the session named exactly as typed, or create it in the client's current directory |
| `esc` | Close the key sheet, leave a prompt/zoxide mode, or close the picker |
| `ctrl-r` | Rename the selected session; the prompt starts from its full name. An empty name cancels |
| `ctrl-a` | New session (stays in the picker, cursor on it). An empty name cancels |
| `ctrl-q` | Kill the selected session. Clients on it move to the most recent other session first; the last session cannot be killed |
| `ctrl-t` | Toggle sort: most recent output ↔ A-Z |
| `ctrl-f` | Toggle the list to zoxide directories; `enter` on one switches to the session named after the directory, or creates it there |
| `←` / `→`, `ctrl-h` / `ctrl-l` | Preview the previous / next window of the selected session (in a prompt or zoxide mode: move the text cursor) |
| `?` | Show / hide the key sheet in the preview pane, in two columns when it is wide enough (in a prompt mode: types `?`) |
| `alt-p` | Show / hide the preview |
| `ctrl-u` / `ctrl-d` | Scroll the preview (in a prompt mode: clear line / delete char) |

Failed tmux actions show their error in the header instead of failing silently.

### 1.2 The preview

The right-hand pane shows one window of the selected session as it looks now. A pinned header line lists
every window (`index: name`, or the running command when unnamed), with the previewed window in reverse
video and the active one starred. `←`/`→` step through the windows and wrap at the ends. Another session
always opens on its active window.

A window with several panes shows them stacked in index order, each under a full-width
`── pane N: command ───` rule. Stacking keeps every pane readable at the preview's width, so a
side-by-side split is shown one pane above the other. The preview's height is shared by water-filling:
a pane short enough to fit is shown in full, and the remaining lines go to the longer panes, which reach
back into their scrollback to use them. Each pane ends at its last non-blank line, so the prompt or latest
output is in view.

### 1.3 The age column

Left of each name is the time since the session last printed anything, in any of its windows: `30s`,
`5m`, `2hr`, `30hr`, `3d`. Hours run to 48 before switching to days. The value is the newest
`#{window_activity}` among the session's windows, which tmux updates whenever a pane writes output.
`#{session_activity}` is not used, because it only changes when a client attaches or types; it cannot show
that a detached session just finished something. The "recent" sort uses the same value, so the ages run
down the list in order. A program that keeps redrawing (a clock, a spinner, `htop`) keeps its session at
a few seconds old. Search matches names only (`--nth 2`), never ages.

### 1.4 Look

The list takes a quarter of the popup's width and the preview the rest (`--preview-window right,75%`):
session names are short and the preview is what is read. Zoxide mode widens the list to 45%
(`change-preview-window(55%)`) because paths are long, and leaving it restores 75%. Both keep a preview
that `alt-p` has hidden hidden.

The prompt sits at the top (`--layout reverse`). Under it are a short header (`? keys · Sort: recent`) and
a blank row, then the list. The selected row is highlighted across its full width (`--highlight-line`).
The gutter is blank (`--gutter ' '`, `gutter:-1`); fzf otherwise draws a `▌` beside every unselected row.
fzf's match counter is hidden (`--info hidden`).

The popup's outer frame is drawn with heavy lines (`--border bold`, `┏━┓┃┗┛`) in the accent, so the
picker stands out from the pane it covers. The frame has no label, so it is unbroken on all four sides;
the tmux status bar already names the current session, and the cursor opens on it. The preview border, the rule under the prompt and the scrollbar stay grey (colour 59, fzf's default), so the
outer frame is the only accented edge.

The accent is green `#5fff00`, colour 82 of the 256-colour palette. It is the green of the author's tmux
status bar. The outer frame, the selection, the header's `?` and the pane rules use it. In the key sheet,
key names are bright magenta and section titles bright cyan. Colours are fixed in the scripts.

## 2. Design

### 2.1 Identity is the tmux id

Every list line is `<key>\t<age>\t<display>`: `$27\t 2hr\tdot-files X` for a session,
`d:/path\t    \t/path` for a directory. fzf shows fields 2 onwards (`--with-nth '2..'`) and searches only
the display (`--nth 2`, counted within the shown fields). Every action receives field 1. Actions call
`tmux -t '$27'`, which is exact. Names never become targets, so spaces, shared prefixes
(`server X` / `server - nwip`) and regex characters cannot pick the wrong session. The old wrapper used
names and fzf's `{1}`, which is the first *word* of the line. It killed `dot-files` when `dot-files X` was
selected.

### 2.2 One input stream, fzf-native cursor

`sessionz.sh` writes the list to a file and feeds that one stream to fzf with `--sync`, so
`start:pos(N)` lands on the current session at open. Mutations rewrite the file and emit
`reload-sync(cat <file>)` followed by `pos(N)`, computed from the same file. `reload-sync` blocks until the
reload, and any query change before it, is applied, so the `pos()` after it is not overwritten. No
`--listen`, `curl` or `sleep` is involved. The old design needed them because the plugin piped its own
list and the wrapper replaced it, giving two competing streams.

### 2.3 Prompts inside fzf

Rename and new-session switch fzf into a prompt mode (`change-prompt`, `disable-search`, the query as the
name). No `execute()` takes over the terminal, so there is no post-redraw cursor loss to work around.

### 2.4 One helper, per-instance state

fzf calls `action.sh <state-dir> <verb> [field1] [query]` for every bound key except `alt-p`, which is a
plain `toggle-preview`. That gives one place that decides what a key means in each mode: `?` opens the key
sheet in the list but types `?` in a prompt, so `?` cannot be typed into the search. `esc` closes the key
sheet before it closes anything else. The helper performs the tmux call and prints the fzf actions to run
next (`transform`).

The current mode (`sessions`, `zoxide`, `rename:<id>`, `new`), sort order, client tty, previewed window
and list files live in a `mktemp -d` directory. One picker instance owns it, and it is removed on exit.
Nothing is written to tmux options, so two pickers on two clients cannot interfere.

### 2.5 Files

| File | Role |
| --- | --- |
| `sessionz.tmux` | TPM entry: binds `@sessionz-bind` (default `o`), in the prefix table unless `@sessionz-prefix` is `off` |
| `scripts/sessionz.sh` | Picker entry; called by `run-shell` with `#{client_tty}` |
| `scripts/action.sh` | Every key's behaviour |
| `scripts/list.sh` | `id\tage\tname` lines, `recent` (newest output first) or `alpha`. `SESSIONZ_NOW` overrides the clock for tests |
| `scripts/preview.sh` | Window list and pane contents (`capture-pane -e`, with history), the key sheet, or a directory listing in zoxide mode. `--window` reports which window is previewed |

Tested with fzf 0.74.5 (`--tmux`, `--with-shell`, `transform`, `--gutter`), tmux 3.8 and bash 5. zoxide is
optional.

## 3. Tests

```bash
uv run pytest            # ~90 s; private tmux servers (-L), never your running one
```

Each test starts two private servers (`tmux -L sxt-<random>`). The *inner* one holds the sessions under
test and binds F12 to the picker. The *outer* one has a pane running a client attached to the inner
server, so the popup renders as it would in a terminal. The test sends keys to that pane and reads it back
with `capture-pane`; `screen_ansi()` keeps the colours. Helpers live in `tests/conftest.py`: `open`,
`select`, `press`, `names`, `client_session`, `client_window`, and `attach_another` for a second client.

- `tests/test_preview_layout.py` runs `preview.sh` directly, with a fixed `FZF_PREVIEW_LINES`/`COLUMNS`, to
  check the line budget and escape codes exactly.
- `tests/test_tpm.py` loads `sessionz.tmux` and opens the picker through the key it binds.
- `tests/test_shellcheck.py` lints every script and the TPM entry.
- `SESSIONZ_ENTRY=<path>` points the suite at another entry script.

Before the rewrite, the same cases were run against the old wrapper (17 failed, 6 passed); see the journal.
CI runs the suite on `macos-latest` with Homebrew's tmux and fzf (`.github/workflows/test.yml`).
