# sessionX accent colour: magenta to the status bar's green

> Purpose: record the accent colour change and where the colour comes from.

## 1. Change

Every bright magenta in the picker is now the tmux status bar's green, `#5fff00`
(`tmux_conf_theme_colour_11` in `.tmux.conf.local`). That colour is exactly entry 82 of the 256-colour
palette, so the picker uses `82` (`bg+:82` in fzf, `\033[1;38;5;82m` in the scripts) and matches the
status bar. It applies to the selected row, the `?` in the header, the key names in the key sheet and
the pane rules in the preview. The teal (bright cyan) section titles are unchanged.

The pink bar down the left of the list was fzf's gutter, which inherits `bg+` by default. It is now
`gutter:-1` (terminal default) rather than green.

## 2. Evidence

- `tests/test_look.py`: the selection test now requires the green background. A new test fails on any
  magenta foreground or background anywhere on screen with the key sheet open, and on any green
  background on unselected rows (the gutter). `tests/test_preview_layout.py` pins the label escape.
- Red before: 3 failed. After: 50 passed (pytest exit 0), ruff and shellcheck clean.

## 3. What is deliberately not done

- The colour is not read from the tmux theme at runtime; changing `tmux_conf_theme_colour_11` will not
  change the picker.
