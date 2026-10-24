# sessionZ: an age column and a recency sort based on output

> Purpose: record the age column and why it measures pane output, not session activity.

## 1. Change

Each row now starts with the time since the session last printed anything in any window: `30s`, `5m`,
`2hr`, `30hr`, `3d`. Hours run to 48 before switching to days, following the user's examples. The age is
dimmed and right-aligned to four columns. List lines are now `id\tage\tname`. fzf shows fields `2..` and
searches field 2 of that (the name) with `--nth 2`, so a query like `s` never matches an age. Zoxide lines
gained a blank age field to keep the same shape. The "recent" sort now uses the same value, so ages run
in order down the list.

## 2. Decision: window_activity, not session_activity

The user named both as acceptable. Probed on a throwaway server (confirmed):

- After `echo hi` was sent to a detached session, its `window_activity` moved to the moment it ran, and
  moved again when delayed output printed 3 s later.
- Its `session_activity` did not move at all. It changes only on client attach or input.

So `session_activity` cannot show that a background session finished something, which is the point of the
column. The newest `window_activity` across the session's windows is used. A continuously redrawing
program keeps its session looking a few seconds old; that limit is documented.

## 3. Evidence

- `tests/test_age.py` has 15 cases:
  - the format at 11 boundaries, through `SESSIONZ_NOW`;
  - the newest output in any window, with the output in a second window of a detached session;
  - the recency sort following the age;
  - the column rendered left of the name in the popup;
  - search matching names only.
- Red before: 14 failed. The search case passed as a guard, because with no ages on screen there was
  nothing to mis-match.
- After: all pass; full suite 70 passed (pytest exit 0), ruff and shellcheck clean.
- Rendered in the harness: `1s beta x` on top after output in `beta x`, the others at `3s`; A-Z sort
  keeps the ages.

## 4. What is deliberately not done

- No "last command" via shell hooks (e.g. zsh `preexec` writing a pane option). That would ignore output
  from long-running programs and needs per-shell setup; output time needs none.
