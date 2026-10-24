"""Enter: switch to the selection, or create a session from the typed name."""

from conftest import Picker, wait_for


def test_enter_on_spaced_name_switches_to_it(picker: Picker) -> None:
    """F5: Enter on `dot-files X` must not land in `dot-files`."""
    picker.new_session("dot-files")
    picker.new_session("dot-files X")
    picker.open()
    picker.select("dot-files X")
    picker.press("Enter")
    wait_for(lambda: picker.client_session() == "dot-files X", what="switch to 'dot-files X'")


def test_enter_on_spaced_name_creates_no_session(picker: Picker) -> None:
    """F5: Enter on `server X` with no `server` session must not create one."""
    picker.new_session("server X")
    picker.open()
    picker.select("server X")
    picker.press("Enter")
    wait_for(lambda: picker.client_session() == "server X", what="switch to 'server X'")
    assert picker.names() == ["home", "server X"]


def test_typed_name_with_no_match_creates_that_session(picker: Picker) -> None:
    """F5: a new name with spaces is created verbatim, not truncated at the first space."""
    picker.new_session("alpha")
    picker.open()
    picker.type("brand new X")
    wait_for(lambda: picker.selected() is None, what="no match for the typed name")
    picker.press("Enter")
    wait_for(lambda: picker.client_session() == "brand new X", what="switch to the new session")
    assert picker.names() == ["alpha", "brand new X", "home"]


def test_escape_closes_without_switching(picker: Picker) -> None:
    picker.new_session("alpha")
    picker.open()
    picker.select("alpha")
    picker.close()
    assert picker.client_session() == "home"
