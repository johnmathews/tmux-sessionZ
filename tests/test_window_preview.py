"""Left/right cycle the preview through the selected session's windows."""

import re

from conftest import Picker, settle, wait_for


def _multi(picker: Picker) -> None:
    """Session 'multi' with windows first/second/third; 'first' stays active."""
    picker.new_session("multi")
    picker.inner.run("rename-window", "-t", "=multi:0", "first")
    for name in ("second", "third"):
        picker.inner.run("new-window", "-d", "-t", "=multi:", "-n", name)
    for name in ("first", "second", "third"):
        picker.inner.run("send-keys", "-t", f"=multi:{name}", f"echo {name.upper()}-MARK", "Enter")
    settle(picker, quiet=0.3)


def _showing(picker: Picker, mark: str) -> bool:
    screen = picker.screen()
    others = {"FIRST-MARK", "SECOND-MARK", "THIRD-MARK"} - {mark}
    return mark in screen and not any(other in screen for other in others)


def test_preview_starts_on_the_active_window(picker: Picker) -> None:
    _multi(picker)
    picker.open()
    picker.select("multi")
    wait_for(lambda: _showing(picker, "FIRST-MARK"), what="active window 'first' in the preview")


def test_right_and_left_cycle_through_windows_and_wrap(picker: Picker) -> None:
    _multi(picker)
    picker.open()
    picker.select("multi")
    wait_for(lambda: _showing(picker, "FIRST-MARK"), what="'first'")
    picker.press("Right")
    wait_for(lambda: _showing(picker, "SECOND-MARK"), what="'second' after Right")
    picker.press("Right")
    wait_for(lambda: _showing(picker, "THIRD-MARK"), what="'third' after Right")
    picker.press("Right")
    wait_for(lambda: _showing(picker, "FIRST-MARK"), what="wrap to 'first' after Right")
    picker.press("Left")
    wait_for(lambda: _showing(picker, "THIRD-MARK"), what="wrap to 'third' after Left")
    assert picker.selected() == "multi"
    assert picker.client_session() == "home"


def test_header_lists_every_window(picker: Picker) -> None:
    _multi(picker)
    picker.open()
    picker.select("multi")
    wait_for(
        lambda: re.search(r"0: ?first.*1: ?second.*2: ?third", picker.screen()),
        what="all three windows in the preview header",
    )


def test_other_session_previews_its_own_active_window(picker: Picker) -> None:
    _multi(picker)
    picker.new_session("solo")
    picker.inner.run("send-keys", "-t", "=solo:", "echo SOLO-MARK", "Enter")
    settle(picker, quiet=0.3)
    picker.open()
    picker.select("multi")
    picker.press("Right")
    wait_for(lambda: _showing(picker, "SECOND-MARK"), what="'second'")
    picker.select("solo")
    wait_for(lambda: "SOLO-MARK" in picker.screen(), what="solo's pane")
    assert "SECOND-MARK" not in picker.screen()


def test_arrows_still_move_the_cursor_in_a_name_prompt(picker: Picker) -> None:
    picker.open()
    picker.press("C-a")
    wait_for(lambda: re.search(r"New session( name)?:", picker.screen()), what="new-session prompt")
    picker.type("ab")
    picker.press("Left")
    picker.type("X")
    picker.press("Enter")
    wait_for(lambda: "aXb" in picker.names(), what="session 'aXb'")


def test_enter_switches_to_the_previewed_window(picker: Picker) -> None:
    _multi(picker)
    picker.open()
    picker.select("multi")
    picker.press("Right")
    wait_for(lambda: _showing(picker, "SECOND-MARK"), what="'second'")
    picker.press("Enter")
    wait_for(lambda: picker.client_session() == "multi", what="switch to 'multi'")
    wait_for(lambda: picker.client_window() == "second", what="window 'second' selected")


def test_enter_without_arrows_keeps_the_active_window(picker: Picker) -> None:
    _multi(picker)
    picker.open()
    picker.select("multi")
    picker.press("Enter")
    wait_for(lambda: picker.client_session() == "multi", what="switch to 'multi'")
    assert picker.client_window() == "first"


def test_ctrl_l_and_ctrl_h_cycle_like_the_arrows(picker: Picker) -> None:
    _multi(picker)
    picker.open()
    picker.select("multi")
    picker.press("C-l")
    wait_for(lambda: _showing(picker, "SECOND-MARK"), what="'second' after ctrl-l")
    picker.press("C-h")
    wait_for(lambda: _showing(picker, "FIRST-MARK"), what="'first' after ctrl-h")


def _split(picker: Picker, top: str, bottom: str) -> None:
    """Session 'split' whose only window has two panes running the given commands."""
    picker.new_session("split")
    picker.inner.run("split-window", "-d", "-t", "=split:")
    picker.inner.run("send-keys", "-t", "=split:.0", top, "Enter")
    picker.inner.run("send-keys", "-t", "=split:.1", bottom, "Enter")
    settle(picker, quiet=0.3)


def test_preview_shows_every_pane_of_the_window(picker: Picker) -> None:
    _split(picker, "echo PANE-ZERO", "echo PANE-ONE")
    picker.open()
    picker.select("split")
    wait_for(
        lambda: "PANE-ZERO" in picker.screen() and "PANE-ONE" in picker.screen(),
        what="both panes in the preview",
    )


def test_each_pane_shows_its_latest_output(picker: Picker) -> None:
    """Both panes' last lines fit, even when each pane holds more than the preview."""
    _split(picker, "seq 1 100; echo ZERO-END", "seq 1 100; echo ONE-END")
    picker.open()
    picker.select("split")
    wait_for(
        lambda: "ZERO-END" in picker.screen() and "ONE-END" in picker.screen(),
        what="the last line of both panes",
    )
