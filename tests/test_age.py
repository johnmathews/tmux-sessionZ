"""The age column (time since a session was last typed in or switched to) and the recent sort (most recently
opened first), both kept live while the picker is open."""

import re
import subprocess
import time

import pytest
from conftest import _EDGE, REPO, Picker, settle, strip_age, wait_for

LIST = REPO / "scripts" / "list.sh"


def _list(picker: Picker, now: int | None = None) -> list[tuple[str, str, str]]:
    """Run list.sh against the inner server; return (id, age, name) with colour codes removed."""
    socket = picker.inner.run("display-message", "-p", "#{socket_path}").strip()
    env = dict(picker.inner.env, TMUX=f"{socket},0,0")
    if now is not None:
        env["SESSIONZ_NOW"] = str(now)
    out = subprocess.run(["bash", str(LIST), "recent"], env=env, capture_output=True, text=True, check=True).stdout
    rows = []
    for line in out.splitlines():
        sid, age, name = line.split("\t")
        rows.append((sid, re.sub(r"\x1b\[[0-9;]*m", "", age).strip(), name))
    return rows


def _last_input(picker: Picker, session: str) -> int:
    """The session's #{session_activity}: moved by keys typed into it, and by a client switching to it."""
    out = picker.inner.run("list-sessions", "-F", "#{session_name}\t#{session_activity}")
    return int(dict(line.split("\t") for line in out.splitlines())[session])


def _last_opened(picker: Picker, session: str) -> int:
    """When a client last switched or attached to the session (#{session_last_attached}), else its creation."""
    out = picker.inner.run("list-sessions", "-F", "#{session_name}\t#{session_last_attached}\t#{session_created}")
    rows = {
        name: int(attached or created) for name, attached, created in (line.split("\t") for line in out.splitlines())
    }
    return rows[session]


def _open_from(other: Picker, session: str) -> None:
    """Switch the client in `other`'s pane to `session`, as picking it would."""
    tty = other.outer.run("display", "-p", "-t", other.pane, "#{pane_tty}").strip()
    other.inner.run("switch-client", "-c", tty, "-t", f"={session}")
    wait_for(lambda: other.client_session() == session, what=f"the other client to open {session!r}")


def _a_second_after(when: int) -> None:
    """Wait until the clock is past `when`, so the next activity lands on a later second."""
    wait_for(lambda: int(time.time()) > when, timeout=3, what="a second to pass")


def _list_rows(picker: Picker) -> list[str]:
    """Session names in the picker's list, top to bottom."""
    rows = []
    for line in picker.screen().splitlines():
        if "┃" not in line:
            continue
        text = line.split("┃", 1)[1].replace("▶ ", "  ", 1)
        name = strip_age(_EDGE.split(text, 1)[0])
        if name and re.match(r"^\s*\d+(?:s|m|hr|d)\s", text):
            rows.append(name)
    return rows


@pytest.mark.parametrize(
    ("elapsed", "shown"),
    [
        (5, "5s"),
        (59, "59s"),
        (60, "1m"),
        (300, "5m"),
        (3599, "59m"),
        (3600, "1hr"),
        (7200, "2hr"),
        (30 * 3600, "30hr"),
        (47 * 3600, "47hr"),
        (48 * 3600, "2d"),
        (3 * 86400, "3d"),
    ],
)
def test_age_format(picker: Picker, elapsed: int, shown: str) -> None:
    picker.new_session("alpha")
    when = _last_input(picker, "alpha")
    ages = {name: age for _, age, name in _list(picker, now=when + elapsed)}
    assert ages["alpha"] == shown


def test_output_does_not_make_a_session_young(picker: Picker) -> None:
    """A detached session printing on its own keeps the age of the last time anyone typed in it."""
    picker.new_session("chatty")
    typed = _last_input(picker, "chatty")
    _a_second_after(typed + 1)
    picker.inner.run("send-keys", "-t", "=chatty:", "echo output only", "Enter")
    settle(picker, quiet=0.3)
    ages = {name: age for _, age, name in _list(picker, now=typed + 30)}
    assert ages["chatty"] == "30s"


def test_recent_sort_ignores_output(picker: Picker) -> None:
    picker.new_session("older")
    picker.new_session("newer")
    _a_second_after(_last_input(picker, "newer"))
    picker.inner.run("send-keys", "-t", "=older:", "echo wake", "Enter")
    settle(picker, quiet=0.3)
    names = [name for _, _, name in _list(picker)]
    assert names.index("newer") < names.index("older")


def test_typing_moves_the_age_but_not_the_order(picker: Picker) -> None:
    """Keys typed in a session from another client make its age young; its place follows when it was opened."""
    picker.new_session("older")
    other = picker.attach_another("older")
    _a_second_after(_last_opened(picker, "older"))
    picker.new_session("newer")
    _a_second_after(_last_input(picker, "newer"))
    other.type("x")
    wait_for(lambda: _last_input(picker, "older") > _last_input(picker, "newer"), what="the keystroke to register")
    rows = _list(picker, now=_last_input(picker, "older"))
    ages = {name: age for _, age, name in rows}
    names = [name for _, _, name in rows]
    assert ages["older"] == "0s"
    assert ages["newer"] != "0s"
    assert names.index("newer") < names.index("older")


def test_switching_to_a_session_makes_it_young(picker: Picker) -> None:
    """Guard: switching moves both the age and the place, before and after the sort used last-opened."""
    picker.new_session("visited")
    picker.new_session("newer")
    _a_second_after(_last_input(picker, "newer"))
    picker.open()
    picker.select("visited")
    picker.press("Enter")
    wait_for(lambda: picker.client_session() == "visited", what="the client to switch")
    names = [name for _, _, name in _list(picker)]
    assert names.index("visited") < names.index("newer")


def test_age_column_is_shown_left_of_each_name(picker: Picker) -> None:
    picker.new_session("alpha")
    picker.open()
    row = next(line for line in picker.screen().splitlines() if "alpha" in line)
    assert re.search(r"\b\d+(?:s|m|hr|d)\s+alpha\b", row), row


def test_search_matches_names_not_ages(picker: Picker) -> None:
    """Every age ends in s, m, hr or d; typing 's' must not match a name without an s."""
    picker.new_session("alpha")
    picker.new_session("bus")
    picker.open()
    picker.type("s")
    wait_for(lambda: picker.selected() == "bus", what="'bus' to be the match")
    settle(picker)
    rows = [strip_age(line) for line in picker.screen().splitlines()]
    assert not any(row.endswith("alpha") or " alpha " in row for row in rows), picker.screen()


def _opened_elsewhere(picker: Picker) -> Picker:
    """Sessions alpha above beta, a second client on 'spare', and the picker open on alpha."""
    picker.new_session("beta")
    picker.new_session("alpha")
    picker.new_session("spare")
    other = picker.attach_another("spare")
    picker.open()
    picker.select("alpha")
    assert _list_rows(picker).index("alpha") < _list_rows(picker).index("beta"), picker.screen()
    _a_second_after(max(_last_opened(picker, name) for name in ("alpha", "beta", "home", "spare")))
    return other


def test_open_list_reorders_live_and_the_cursor_stays_on_its_session(picker: Picker) -> None:
    """Another client opening beta moves beta to the top within the interval; alpha stays selected."""
    other = _opened_elsewhere(picker)
    _open_from(other, "beta")
    wait_for(lambda: _list_rows(picker)[:1] == ["beta"], timeout=4.0, what="beta to move to the top")
    settle(picker)
    assert picker.selected() == "alpha", picker.screen()


def test_open_list_holds_while_a_query_is_typed(picker: Picker) -> None:
    """Guard: with a query the list is filtered by match, so the live reload waits and the cursor holds."""
    other = _opened_elsewhere(picker)
    picker.type("a")
    wait_for(lambda: "home" not in _list_rows(picker), what="the query to filter out 'home'")
    picker.select("beta")
    _open_from(other, "beta")
    time.sleep(2.5)
    assert picker.selected() == "beta", picker.screen()
    assert "> a" in picker.screen()
