# Test servers leaked when start() failed

## 1. Problem

On 2026-11-04 three private tmux servers were found still running on John's Mac: `sxt-6f264062` and
`sxt-6f264062-outer` (one test's inner and outer pair), plus `sz-probe-22938`, which no test creates and
was probably started by hand while debugging. They had been up since about 2026-10-25. That cost more
than memory. tmux-continuum only autosaves while it sees a single tmux server, so when the dotfiles
config was reloaded it dropped its save hook, and John's sessions were not saved from 2026-10-25 to
2026-11-04. The dotfiles journal (`261104-tmux-mouse-clipboard-kitty.md`) has that side of the story.

Cause: `start()` in `tests/conftest.py` creates both servers and then waits for the client to attach.
If that wait timed out, or anything else in `start()` raised, the exception left before the `tmux_env`
fixture could record the picker. Teardown only kills servers it has recorded, so the pair stayed up.

## 2. Change

- `start()` kills both servers itself if anything after their creation raises (`except BaseException`,
  so Ctrl-C is covered), then re-raises.
- The fixture's teardown kills the inner server even if killing the outer one raises.
- New `tests/test_harness.py`: it makes the attach wait time out and checks that neither socket still
  answers. It failed before the change (both servers alive) and passes after it. The test kills both
  sockets in a `finally`, so its own red run leaks nothing.

## 3. Verification

Full suite: 96 passed in 137 s; ruff check and format clean. `pgrep -lf sxt-` found nothing afterwards,
and the live server's continuum hook was still present (`grep -c continuum_save` printed 1).

## 4. Not done

- **Sweeping every `sxt-*` server at session start or end.** Another session can be running the suite at
  the same time, and a sweep would kill its servers mid-test. Servers from a pytest that is SIGKILLed
  can still leak; `docs/sessionz.md` §3 says how to find and stop them.
