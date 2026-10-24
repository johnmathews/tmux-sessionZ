"""ctrl-r: rename the selected session."""

import re

from conftest import Picker, settle, wait_for


def _rename(picker: Picker, old: str, new: str) -> None:
    picker.select(old)
    picker.press("C-r")
    wait_for(lambda: re.search(r"(Rename|New name):", picker.screen()), what="rename prompt")
    picker.press("C-u")
    picker.type(new)
    picker.press("Enter")


def test_rename_prompt_prefills_full_name(picker: Picker) -> None:
    """F1: the prompt starts from `server X`, not its first word."""
    picker.new_session("server X")
    picker.open()
    picker.select("server X")
    picker.press("C-r")
    wait_for(
        lambda: re.search(r"(Rename|New name): server X", picker.screen()),
        what="prompt prefilled with 'server X'",
    )


def test_rename_spaced_name_spares_first_word_session(picker: Picker) -> None:
    """F1: renaming `dot-files X` must not rename `dot-files`."""
    picker.new_session("dot-files")
    picker.new_session("dot-files X")
    picker.open()
    _rename(picker, "dot-files X", "df X")
    wait_for(lambda: "df X" in picker.names(), what="'df X' to exist")
    assert "dot-files" in picker.names()
    assert "dot-files X" not in picker.names()


def test_rename_spaced_name_with_ambiguous_prefix(picker: Picker) -> None:
    """F1/F4: `server X` must not fail as an ambiguous prefix of two sessions."""
    picker.new_session("server - nwip")
    picker.new_session("server X")
    picker.open()
    _rename(picker, "server X", "srv X")
    wait_for(lambda: "srv X" in picker.names(), what="'srv X' to exist")
    assert "server - nwip" in picker.names()


def test_cursor_follows_rename_to_awkward_name(picker: Picker) -> None:
    """F7: spaces and regex characters in the new name do not lose the cursor."""
    picker.new_session("alpha")
    picker.new_session("beta")
    picker.open()
    _rename(picker, "alpha", "a.b [c]")
    wait_for(lambda: "a.b [c]" in picker.names(), what="rename to land")
    settle(picker)
    assert picker.selected() == "a.b [c]"


def test_empty_rename_keeps_name(picker: Picker) -> None:
    picker.new_session("alpha")
    picker.open()
    _rename(picker, "alpha", "")
    settle(picker)
    assert picker.names() == ["alpha", "home"]
