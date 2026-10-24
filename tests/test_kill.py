"""ctrl-q: kill the selected session."""

from conftest import Picker, settle, wait_for


def test_kill_spaced_name_spares_first_word_session(picker: Picker) -> None:
    """F1: `dot-files X` must not resolve to `dot-files`."""
    picker.new_session("dot-files")
    picker.new_session("dot-files X")
    picker.open()
    picker.select("dot-files X")
    picker.press("C-q")
    wait_for(lambda: "dot-files X" not in picker.names(), what="'dot-files X' to be killed")
    assert "dot-files" in picker.names()


def test_kill_spaced_name_with_ambiguous_prefix(picker: Picker) -> None:
    """F1/F4: `server X` must not fail as an ambiguous prefix of two sessions."""
    picker.new_session("server - nwip")
    picker.new_session("server X")
    picker.open()
    picker.select("server X")
    picker.press("C-q")
    wait_for(lambda: "server X" not in picker.names(), what="'server X' to be killed")
    assert "server - nwip" in picker.names()


def test_kill_attached_session_keeps_client_attached(picker: Picker) -> None:
    """F2: killing the session this client is on moves the client, it does not detach it."""
    picker.new_session("alpha")
    picker.open()
    picker.select("home")
    picker.press("C-q")
    wait_for(lambda: "home" not in picker.names(), what="'home' to be killed")
    assert picker.client_session() == "alpha"


def test_kill_last_session_is_refused(picker: Picker) -> None:
    """F2: with nothing to move the client to, ctrl-q refuses instead of ending the server."""
    picker.open()
    picker.press("C-q")
    settle(picker)
    assert picker.names() == ["home"]
    assert picker.client_session() == "home"
    assert "last session" in picker.screen()


def test_consecutive_kills_each_remove_the_selection(picker: Picker) -> None:
    """The Phase 1 prototype dropped a second ctrl-q; every kill must land."""
    for name in ("k1", "k2", "k3"):
        picker.new_session(name)
    picker.open()
    for name in ("k1", "k2", "k3"):
        picker.select(name)
        picker.press("C-q")
        wait_for(lambda gone=name: gone not in picker.names(), what=f"{name!r} to be killed")
        settle(picker, quiet=0.2)
    assert picker.names() == ["home"]


def test_failed_kill_is_reported(picker: Picker) -> None:
    """F4: a kill that tmux rejects shows the error instead of silently reloading."""
    picker.new_session("victim")
    picker.open()
    picker.select("victim")
    picker.inner.run("kill-session", "-t", "=victim")
    picker.press("C-q")
    wait_for(lambda: "can't find session" in picker.screen(), what="error in the picker")
