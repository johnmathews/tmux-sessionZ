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
