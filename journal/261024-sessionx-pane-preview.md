# sessionX preview shows the selected session's pane

> Purpose: record why the preview changed from a session tree to a pane capture, and a bug the tree had.

## 1. Change

The right-hand preview used to print a tree of every session and window, highlighting the selected one.
It barely changed as the cursor moved, so it told the user little. It now shows the selected session's
active pane (`tmux capture-pane -e -p -t <session_id>`) under a pinned one-line header (session, active
window, window count). `--preview-window right,55%,follow,~1` keeps the header fixed and scrolls to the
bottom. Trailing blank lines are stripped first, so the bottom is the prompt or latest output rather than
empty rows.

## 2. Bug in the tree it replaced (confirmed from the user's screenshot)

The tree's `while IFS=$'\t' read -r ...` loop shifted fields whenever a format field was empty, for example
the "(attached)" flag on unattached sessions. Tab is IFS whitespace, so bash merges consecutive tabs. The
symptoms were `3 window(s)1`, `nvim: *` and lines reading `:`. The earlier suite missed it because the
preview test only counted session names. The new preview parses no fields.

## 3. Evidence

- New tests in `tests/test_preview.py`: the selected session's output is shown and the other's is not; a
  200-line pane shows its last line; the header names the window; no other session names appear.
- Red against the tree preview: 3 failed, 1 passed (the window-name test passed on the tree too and stays
  as a guard). Green after: 4 passed; full suite 26 passed.
- Rendered in the harness: header pinned, lines 179–200, `TAIL-MARK` and the prompt visible.

## 4. What is deliberately not done

- No preview of a window other than the active one, and no per-pane choice. A session-level picker
  previews what switching would land on.
- Pane width is not reflowed to the preview width; long lines are cut at the preview edge.
