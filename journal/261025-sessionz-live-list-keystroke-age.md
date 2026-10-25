# 2026-10-25 — Live list, and the age is the last keystroke

## Request

After the live preview (`261025-sessionz-live-preview.md`), John asked whether it affected the ordering
or the age column. It did neither: the timer only ran `refresh-preview`, so ages and order were frozen at
open. He then asked for the list to update live too, and for the age to measure the time since a command
was last entered rather than since a pane last printed.

## What "command entered" can mean in tmux

Three signals were on the table. John chose the last keystroke.

1. **OSC 133 shell marks.** tmux 3.8 records `#{pane_command_start_time}` (and end time, status,
   duration) when the shell sends `\033]133;C\033\\` before each command. Verified on a private 3.8
   server: emitting the marks by hand set the start and end times. Two things block it today. John's
   running tmux server is 3.6a (started 4 Oct; the binary is 3.8), so the formats are not there until
   tmux restarts. And his zsh sends no OSC 133 inside tmux (every pane showed an empty value). It would
   also miss typing into a long-running `claude` or `nvim`.
2. **The last keystroke, `#{session_activity}`.** Works on 3.6a with no setup. Chosen.
3. Both, with keystrokes as the fallback. The most logic, for a hook that does not exist yet.

## What moves `#{session_activity}` (tmux 3.8, probed with the test harness)

- Keys typed into the session from an attached client: yes.
- Output, including output from server-side `send-keys`: no.
- `switch-client` to the session: yes.
- Keys typed into the picker popup: no. The key that opens it (F12 in tests) does.

So the session you are on does not sit at `0s` while you browse the picker. Switching to a session
counts as using it, which suits "most recently used" ordering.

## Keeping the cursor on its session through a reload

- `track-current+reload-sync(...)` with `--id-nth 1` keeps the cursor on the item through a reordering
  reload. But the tracking lingers: after clearing a query the cursor stayed on the tracked item instead of
  resetting to the top, as it does without the tick.
- Chaining `+untrack-current` fixes the lingering but also cancels the tracking before the reload lands:
  the cursor stayed at the same index and landed on another session.
- So `tick` uses the project's existing rule: rewrite the list file, then `reload-sync(cat file)+pos(N)`,
  with N the focused session's line in that file. `pos(N)` counts matches, so while a query is typed (or
  a rename/new prompt is open) the list is not reloaded and only the preview redraws.
- Any reload re-runs the preview (counted with a preview command that appends to a log: an identical
  list, a changed age and a reorder each caused one run). So the reload branch prints no
  `refresh-preview`; that would render twice.

## Tests

Seen failing against the old code: `test_output_does_not_make_a_session_young`,
`test_recent_sort_ignores_output`, `test_open_list_reorders_live_and_the_cursor_stays_on_its_session`,
and `test_age_format[60-1m]` (the old age moved with the shell's first prompt). Guards that passed before:
`test_typing_in_a_session_makes_it_young` (typing also prints), `test_switching_to_a_session_makes_it_young`,
`test_open_list_holds_while_a_query_is_typed`.

## Not done

- OSC 133 command times. They become possible after a tmux server restart onto 3.8 plus a zsh hook, if
  keystrokes turn out too coarse.
- Reloading the list while a query is typed: it needs a cursor that follows by id, which `pos(N)` cannot
  give for a filtered list, and tracking (above) changes how typing moves the cursor.
