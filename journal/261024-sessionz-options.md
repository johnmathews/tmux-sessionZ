# sessionZ: options for size, list width, border colour and blackout

> Purpose: record the five new tmux options, how blackout works, and how bad values are handled.

## 1. Change

The user asked to set, from `~/.tmux.conf.local`, the popup's size (they want 80% width), the list
column's share, the frame colour, and whether the background behind the picker is blacked out.
`scripts/sessionz.sh` now reads `@sessionz-width`, `@sessionz-height`, `@sessionz-list-width`,
`@sessionz-border-color` and `@sessionz-blackout` in one `display-message` call on every open. The
defaults are the look as it was (75%, 75%, 25%, 82, off), and `test_default_size_is_three_quarters`
guards that.

Reading on open, rather than in `sessionz.tmux` at load time, means a `set -g` takes effect on the next
`prefix o` with no reload. Reading options does not break the "never write tmux options" rule.

## 2. Decision: blackout is a full-screen popup with a margin

tmux popups have no dimming or backdrop setting. A probe on a private server showed the alternative
works (confirmed): `fzf --tmux center,100%,100% --margin 12.5%,10%` draws the same 80%-wide panel, and a
marker printed in the pane behind it did not show outside the frame. The margin is half of what the
configured width and height leave, so the panel is the same size with blackout on or off (tested both
ways). The backdrop is the terminal's background colour, not pure black.

## 3. Decision: bad values fall back, loudly

A malformed value (`huge`, `0%`, `chartreuse`, `maybe`) is replaced by its default, and one tmux message
lists every ignored option, so a typo never stops the picker opening. `#` in the message is doubled
because tmux reads messages as formats. The first draft of the test passed before any warning code
existed: tmux's message log already held the option names from the `set` commands. It now requires
the picker's own `sessionZ: ignored` line, and failed until the warning was written.

## 4. Zoxide mode with a configured list width

Zoxide mode used to set the preview to 55%. It now uses the smaller of 55% and the configured preview
width, so the list is at least 45% for paths and a list configured wider than that is not narrowed.
`sessionz.sh` writes the preview width to the picker's state directory for `action.sh` to read.

## 5. What is deliberately not done

- The selection highlight stays colour 82; only the frame colour is an option, as asked.
- No pure-black backdrop: fzf cannot paint its margin, and the popup's style is fzf's to set.
- Sizes are percentages only, not absolute cell counts, to keep validation and blackout's margin simple.
