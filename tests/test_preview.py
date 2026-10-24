"""The preview beside the list shows the selected session's active pane."""

from collections.abc import Callable

from conftest import Picker, settle, wait_for


def _say(picker: Picker, session: str, command: str) -> None:
    """Run a shell command in the session's active pane and wait for it to finish."""
    picker.inner.run("send-keys", "-t", f"={session}:", command, "Enter")
    settle(picker, quiet=0.3)


def test_preview_shows_active_pane_of_selected_session(picker: Picker) -> None:
    picker.new_session("alpha")
    picker.new_session("beta")
    _say(picker, "alpha", "echo ALPHA-MARK")
    _say(picker, "beta", "echo BETA-MARK")
    picker.open()
    picker.select("alpha")
    wait_for(lambda: "ALPHA-MARK" in picker.screen(), what="alpha's pane in the preview")
    assert "BETA-MARK" not in picker.screen()
    picker.select("beta")
    wait_for(lambda: "BETA-MARK" in picker.screen(), what="beta's pane in the preview")
    assert "ALPHA-MARK" not in picker.screen()


def test_preview_follows_the_bottom_of_a_full_pane(picker: Picker) -> None:
    """A pane taller than the preview shows its last lines, where the prompt is."""
    picker.new_session("busy")
    _say(picker, "busy", "seq 1 200; echo TAIL-MARK")
    picker.open()
    picker.select("busy")
    wait_for(lambda: "TAIL-MARK" in picker.screen(), what="the last line of 'busy' in the preview")


def test_preview_names_session_and_window(picker: Picker) -> None:
    picker.new_session("alpha")
    picker.inner.run("rename-window", "-t", "=alpha:", "editor pane")
    picker.open()
    picker.select("alpha")
    wait_for(lambda: "editor pane" in picker.screen(), what="window name in the preview header")


def test_preview_lists_no_other_sessions(tmux_env: Callable[..., Picker]) -> None:
    """F3: no session appears twice; ids past $10 caused ghosts in the old tree preview."""
    picker = tmux_env(height=80)
    names = [f"n{i:02d}" for i in range(1, 14)]
    for name in names:
        picker.new_session(name)
    picker.open()
    picker.select("n05")
    settle(picker)
    screen = picker.screen()
    counts = {name: screen.count(name) for name in names}
    # Each name once in the list; the selected one also once in the preview header.
    assert counts == {name: 2 if name == "n05" else 1 for name in names}, screen
