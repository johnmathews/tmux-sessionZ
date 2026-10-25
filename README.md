# sessionZ

A tmux session picker in an fzf popup. You can switch, create, rename and kill sessions, and preview
every window and pane of a session before you jump to it.

- **Names can contain spaces.** Every action targets the session's tmux id, never its name. Picking
  `dot-files X` can never touch `dot-files`.
- **The preview is live.** It shows the selected session's windows. `←`/`→` step through them, a window
  with several panes shows every pane, and `enter` lands on the window you are looking at.
- **You can see how stale each session is.** Left of each name is the time since the session last
  printed anything (`30s`, `5m`, `2hr`, `3d`), and the list is sorted by it.
- **Errors show up.** A failed tmux action shows its error in the picker. Killing the session you are on
  moves you to another one first, instead of detaching you.
- **Keys are one `?` away.** `?` opens a key sheet in the preview pane.

## Install

Requires tmux ≥ 3.3, [fzf](https://github.com/junegunn/fzf) (tested with 0.74.5) and bash.
[zoxide](https://github.com/ajeetdsouza/zoxide) is optional and powers `ctrl-f`.

With [TPM](https://github.com/tmux-plugins/tpm), add to `~/.tmux.conf`:

```tmux
set -g @plugin 'johnmathews/tmux-sessionZ'
```

then press `prefix I` to install. The picker opens with `prefix o`.

### Options

```tmux
set -g @sessionz-bind 'o'                # key that opens the picker (default: o)
set -g @sessionz-prefix 'on'             # 'off' binds the key without the prefix
set -g @sessionz-width '75%'             # popup width (default: 75%)
set -g @sessionz-height '75%'            # popup height (default: 75%)
set -g @sessionz-list-width '25%'        # session list's share of the popup; the preview gets the rest
set -g @sessionz-border 'on'             # 'off' draws the popup without its frame
set -g @sessionz-border-color '82'       # frame colour: 0-255, '#rrggbb' or a name like 'bright-green'
set -g @sessionz-blackout 'off'          # 'on' hides everything behind the picker
set -g @sessionz-preview-interval '1'    # seconds between preview redraws; 'off' or '0': only on cursor moves
```

The last seven are read each time the picker opens, so a change needs no reload. A bad value falls back to
its default and is named in a tmux message.

## Keys

| Key | Action |
| --- | --- |
| `enter` | Switch to the session, on the previewed window; with no match, switch to or create the session named exactly as typed |
| `esc` | Close the key sheet, a prompt, or the picker |
| `ctrl-r` | Rename (the prompt starts from the full current name; empty cancels) |
| `ctrl-a` | New session; the picker stays open on it. Empty name cancels |
| `ctrl-q` | Kill session. Clients on it move to the most recent other session; the last session is refused |
| `ctrl-t` | Toggle sort: most recent output ↔ A-Z |
| `ctrl-f` | Toggle to zoxide directories; `enter` switches to the session named after the directory, or creates it there |
| `←` / `→`, `ctrl-h` / `ctrl-l` | Preview the previous / next window of the selected session |
| `?` | Show / hide the key sheet |
| `alt-p` | Show / hide the preview |
| `ctrl-u` / `ctrl-d` | Scroll the preview |

## Development

```bash
uv run pytest
```

The suite drives the real popup on private tmux servers (`tmux -L sxt-*`), never the one you are using.
It needs tmux, fzf, uv and shellcheck; the zoxide tests skip without zoxide. Design notes are in
[docs/sessionz.md](docs/sessionz.md), and dated development notes are in `journal/`.

## Origin

sessionZ started as a fix-up of a wrapper around
[omerxx/tmux-sessionx](https://github.com/omerxx/tmux-sessionx). The fix-up became a rewrite: it keeps
the idea and shares no code.

## License

MIT
