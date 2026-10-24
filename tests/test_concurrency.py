"""Two pickers open at once, on two clients."""

from conftest import Picker, settle, wait_for


def test_overlapping_pickers_leave_no_global_state(picker: Picker) -> None:
    """F6: closing in open order must not leave one picker's bindings in tmux options."""
    picker.new_session("other")
    second = picker.attach_another("other")
    before = picker.inner.run("show-options", "-g")
    picker.open()
    second.open()
    picker.close()
    second.close()
    settle(picker)
    assert picker.inner.run("show-options", "-g") == before


def test_sort_toggle_is_per_picker(picker: Picker) -> None:
    """F12: ctrl-t in one picker must not flip the other's sort order."""
    picker.new_session("other")
    second = picker.attach_another("other")
    picker.open()
    second.open()
    picker.press("C-t")
    wait_for(lambda: "Sort: A-Z" in picker.screen(), what="first picker to sort A-Z")
    second.press("C-t")
    wait_for(lambda: "Sort: A-Z" in second.screen(), what="second picker to sort A-Z")
