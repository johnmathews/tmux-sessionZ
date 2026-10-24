"""Where the cursor lands on open and after creating a session."""

import re

from conftest import Picker, settle, wait_for


def test_open_lands_on_current_session_every_time(picker: Picker) -> None:
    for name in ("alpha", "beta", "gamma", "delta"):
        picker.new_session(name)
    for _ in range(20):
        picker.open()
        assert picker.selected() == "home"
        picker.close()


def test_new_session_is_created_and_selected(picker: Picker) -> None:
    picker.new_session("alpha")
    picker.open()
    picker.press("C-a")
    wait_for(lambda: re.search(r"New session( name)?:", picker.screen()), what="new-session prompt")
    picker.type("fresh one")
    picker.press("Enter")
    wait_for(lambda: "fresh one" in picker.names(), what="'fresh one' to exist")
    settle(picker)
    assert picker.selected() == "fresh one"
    assert picker.client_session() == "home"
