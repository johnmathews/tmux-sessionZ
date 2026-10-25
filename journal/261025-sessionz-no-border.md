# sessionZ: an option to drop the popup frame

> Purpose: record the `@sessionz-border` option and what it keeps.

## 1. Change

The user asked for an option to show the popup without its border. `@sessionz-border` takes `on`
(default) or `off`; `off` passes `--border none` instead of `--border bold`. It is a separate on/off
option, matching `@sessionz-blackout`, rather than a `none` value for `@sessionz-border-color`, which
would mix whether there is a frame with what colour it is. The user chose to keep the `--padding 1`
blank row and column, and the preview's own grey border. `@sessionz-border-color` is ignored while the
frame is off. A bad value falls back to `on` and is named in the existing warning.

## 2. Evidence

- `test_border_off_removes_only_the_frame` requires no heavy box glyphs with the option off, the preview
  border still drawn, and the prompt one row up and two columns left of where it sits with the frame.
  It failed before the change (the frame was still drawn), confirmed.
- The first version expected one column, not two. With the frame off, fzf also drops the space it keeps
  beside a side border, so the prompt lands at the popup's first column plus the padding. Turning the
  padding off as well moved the prompt by two rows and three columns and failed the test, so the test
  tells "frame gone" apart from "frame and padding gone".
- `test_bad_values_fall_back_to_defaults_and_say_so` checked option names as substrings, so
  `@sessionz-border` would have passed on the strength of `@sessionz-border-color`. It now matches
  `<name> '`, as the warning prints it, and failed before the change.
- The harness found an open popup by the frame's `┏` corner. `is_open` now also accepts the list's
  pointer, so a frameless popup counts as open. A frameless popup with no matching row therefore reads as
  closed; no test opens one that way today.
- Full suite after the wrap-up review: 85 passed; ruff and shellcheck clean. The wrap-up also added
  `*.secret` to `.gitignore`.

## 3. What is deliberately not done

- No `@sessionz-border-style` with every fzf style. Not asked for.
- No frame-free open check that survives an empty match. Nothing needs it yet.
