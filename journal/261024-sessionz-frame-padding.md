# sessionZ: space between the frame and the content

> Purpose: record the padding inside the bold frame.

## 1. Change

The prompt sat on the row right under the green frame, and the list's pointer and the preview's border
sat one space from its sides. The user asked for a blank row or column between them. `--padding 1` adds
one blank row at the top and bottom and one blank column on each side, inside the border and outside
the content. The padding is fixed, not an option.

## 2. Evidence

- `test_blank_space_inside_the_frame` requires the first and last rows inside the frame to be blank, and
  two spaces inside each side on every row: fzf's existing space plus the padding. It failed before the
  change (the prompt row was directly under `┏`), confirmed.
- `test_popup_border_is_bold_and_green` found the prompt rule by `┃ ──`; with the padding it is `┃  ──`,
  so the match became `┃ +──`.
- Panel size is unchanged: the padding is inside the frame, and the size tests in `tests/test_options.py`
  measure the frame.

## 3. What is deliberately not done

- No `@sessionz-padding` option. Not asked for.
