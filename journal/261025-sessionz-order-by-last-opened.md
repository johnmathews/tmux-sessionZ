# 2026-10-25 — Order by when a session was last opened

## Request

Straight after PR #9 (age and order from the last keystroke, `261025-sessionz-live-list-keystroke-age.md`),
during `/done`, John asked for the picker's order to be the order he last opened the sessions in. Given
the choice, he picked: **order by last opened, keep the age as the time since the last keystroke.**

## Evidence (tmux 3.8, private servers through the test harness)

`#{session_last_attached}` against `#{session_activity}`, step by step:

| Step | `session_last_attached` | `session_activity` |
| --- | --- | --- |
| Typing in the attached session | unchanged | moves |
| `switch-client` to a session | moves | moves |
| A second client attaches | moves | moves |
| A second client types | unchanged | moves |

So `session_last_attached` is "last opened". It is empty for a session no client has ever been on (created
with `new-session -d`, as `ctrl-a` does), which `list.sh` replaces with `#{session_created}`. On John's
running 3.6a server it is populated, including for sessions resurrect restored (confirmed with a read-only
`list-sessions`).

With one terminal the two orders almost coincide, since you can only type into the session you are on.
They part when a session is typed into from a second client: its age goes to `0s` but it keeps its place.
So the ages no longer have to run in order down the list; the docs no longer claim they do.

## Tests

`test_typing_moves_the_age_but_not_the_order` was seen failing against #9's code (the typed session sorted
first). The live tests now trigger the reorder by switching a second client to a session, so they passed
against both versions; `test_switching_to_a_session_makes_it_young` is a guard too.
`uv run pytest`: 93 passed, exit 0.

## Doc audit fixes carried in this PR

The `/done` audit of #9 (an independent agent pass) found:
- CLAUDE.md stated the tick reload condition incompletely: it left out the prompt modes, zoxide and the key sheet.
- `action.sh`'s header still said "preview timer", and its STATE_DIR list missed `window` and `preview`.
- The state lists in CLAUDE.md and the docs missed `preview`.
- `sessionz.sh` said "0.1 to 99.9" where the regex accepts anything under 100.
- §1.2 read as if `tick` only redraws the preview.
- The files table said `action.sh` handles every key, but `alt-p` does not go through it, and the table left out `hints`.

All were fixed. The audit also noted that no test covers the list holding during a prompt or with the key
sheet open.

## What is deliberately not done

- Tests for the list holding during a rename/new prompt or with the key sheet open. A reload there would
  move the cursor, which in a prompt does nothing visible (the session id lives in the mode), so the guard
  would assert little.
- A separate option to choose the sort signal. One behaviour, as asked.
