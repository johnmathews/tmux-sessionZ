# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

sessionZ, a tmux session picker in an fzf popup, packaged as a TPM plugin.

- `sessionz.tmux` — TPM entry; binds the picker key (`@sessionz-bind`, `@sessionz-prefix`)
- `scripts/` — the picker: `sessionz.sh` (entry), `action.sh` (every key), `list.sh` (sessions with their
  age, from `#{window_activity}`), `preview.sh`
- `tests/`, `pyproject.toml`, `uv.lock` — pytest suite (run with uv) that drives the real popup
- `docs/sessionz.md` — design, keys and test harness; superseded notes in `docs/archive/`
- `journal/` — dated development entries; point-in-time, never retro-edited
- `.github/workflows/test.yml` — CI: the suite on macOS with Homebrew tmux/fzf

## Rules that keep it sturdy

Full design: `docs/sessionz.md`. Read it before changing a binding.

- **Target by id, never by name.** List lines are `<session_id>\t<age>\t<name>`. fzf shows fields 2..,
  searches field 3 only, and actions receive field 1, so tmux gets `-t '$27'`. Names with spaces, shared prefixes or regex characters must
  never reach a `-t`.
- **One input stream.** `sessionz.sh` writes the list to a file and fzf reads only that. Cursor moves use
  `reload-sync(cat <file>)+pos(N)` with N computed from the same file. Never use `--listen`/`curl` or
  `sleep` for cursor placement.
- **No `execute()` for prompts.** Rename and new-session are fzf prompt modes driven by `action.sh`.
  `execute()` takes over the terminal, and the redraw after it overrides chained cursor actions.
- **Per-instance state only.** Mode, sort, client tty, previewed window and list files live in the
  picker's `mktemp -d` directory. Never write tmux options: two pickers on two clients must not interfere.
- **Every key except `alt-p` goes through `action.sh`**, which prints the fzf actions to run next. Free
  text (a header, the prefilled rename query) goes last, in the colon form (`change-header:<text>`), whose
  argument runs to the end of the string, so names and tmux errors need no escaping. Failed tmux calls
  that change state must be shown in the header, not swallowed.
- **Switch the right client.** The binding passes `#{client_tty}`, and every `switch-client` uses
  `-c "$client"`.
- **Brace variables next to non-ASCII text** (`${dim}──`). In a non-UTF-8 locale bash reads the first
  byte of `─` as part of the name. Count widths of non-ASCII text in characters, not bytes
  (`visible_width` in `preview.sh`).

## Tests

```bash
uv run pytest      # ~90 s; private tmux servers (-L), never your running one
uv run ruff check tests && uv run ruff format --check tests
```

Every behaviour change needs a test in `tests/` that is seen failing first. `tests/test_shellcheck.py`
lints every script and `sessionz.tmux`. Never load a full personal tmux config in a test server: plugins
such as continuum would restore and save against the real resurrect files.

## fzf behaviour worth knowing

Verified on fzf 0.74.5 / tmux 3.8. Older measurements: `docs/archive/fzf-cursor-positioning.md`.

- `start` fires before input is read, so `start:pos(N)` only works with `--sync`.
- `reload-sync(CMD)+pos(N)` works: `reload-sync` blocks until the new list, and any preceding query
  change, is applied.
- After `execute(...)`, fzf's redraw overrides chained `pos()`/`last`. This is why prompts live inside fzf.
- `capture-pane` trims trailing spaces, so match `New session:`, not `New session: `.
- Root-table tmux bindings (e.g. `bind -n C-l`) do not fire while the popup is open; keys reach fzf.
