# sessionZ: a preview that redraws while the picker is open

> Purpose: record how the live preview works, and the two designs measured and dropped on the way.

## 1. Change

The user wanted to see whether a terminal in a session is changing by looking only at the preview.
`@sessionz-preview-interval` (default `1`, `0.1`–`99.9` seconds, `off` or `0` to disable) binds fzf's
`every(N)` event to `transform(action.sh tick)`. `tick` prints `refresh-preview` in sessions and prompt
modes and nothing in zoxide mode or while the key sheet is open. `preview.sh` is unchanged.

## 2. Designs tried

1. **A looping preview** (`preview.sh` printing CSI 2 J and a new frame each second, as `fzf --man`
   suggests). It worked, but fzf draws a spinner in the preview's top-right corner for as long as a preview
   command runs. Two captures 150 ms apart differed only in that glyph. Confirmed. `--preview-window
   noinfo` did not hide it. The screen never settled, so every test's `settle()` timed out: opening went
   from under a second to 5.16 s. Dropped and reverted.
2. **`every(1):refresh-preview`.** No spinner: 60 captures 50 ms apart over 3 s were identical. But a
   refresh puts a scrolled preview back at the bottom under `follow`, even when the output is identical.
   Confirmed with a 200-file zoxide listing: `ctrl-u` held with the timer off and was undone within 1.8 s
   with it on.
3. **`every(N):transform(action.sh tick)`**, refreshing only session previews. A session preview is cut to
   the preview's height and never scrolls, so the refresh costs it nothing. Confirmed: `ctrl-u` with the
   timer off did not change a session preview.

## 3. Evidence

- `test_preview_updates_while_the_picker_is_open`: output typed into a previewed session shows within 4 s
  with no key pressed. It failed on the one-shot preview, confirmed.
- `test_live_preview_keeps_a_scrolled_listing_where_it_is` (zoxide mode) failed with design 2 and passes
  with design 3, confirmed.
- `test_preview_interval_off_keeps_it_still` and `test_live_preview_leaves_a_hidden_preview_hidden` guard
  the off switch and `alt-p`. Both would pass on the old code; they are guards, not red-first tests.
- The bad-values test gains `@sessionz-preview-interval 'fast'`, named in the warning. It failed before the
  option existed, confirmed.
- fzf 0.74.5 parsed `every(N)` for `1`, `0.5`, `.5`, `0.1`, `2.5`, `99` and `99.9`, and rejected `fast`.
- Cost: one `preview.sh` render measured about 29 ms for a one-pane window and 78 ms for four panes, 20 runs
  each on a private server. `test_cursor.py`'s slowest test took 17.7 s on `main` and 18.0 s with the timer.
- Full suite: 89 passed, before and after the wrap-up review. The review's docs audit caught the zoxide
  test's docstring describing design 2 ("redraws identically") instead of design 3, and three descriptions
  of `action.sh` as handling only keys; all corrected.

## 4. What is deliberately not done

- No marker for what changed between redraws. Not asked for.
- No refresh of the zoxide listing or key sheet; neither changes on its own, and a refresh would undo
  scrolling.
- An earlier session-pane scroll test was dropped: its premise was false (a session preview cannot
  scroll), and the first probe that seemed to show "scroll kept" proved nothing.
