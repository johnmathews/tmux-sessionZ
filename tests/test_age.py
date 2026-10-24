"""The age column: time since each session last printed anything, newest first."""

import re
import subprocess
import time

import pytest
from conftest import REPO, Picker, settle, strip_age, wait_for

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


def _last_output(picker: Picker, session: str) -> int:
    out = picker.inner.run("list-windows", "-t", f"={session}", "-F", "#{window_activity}")
    return max(int(v) for v in out.split())


def _quiet(picker: Picker, session: str) -> int:
    """Wait until the session has printed nothing for over a second; return its last output time.

    A new session's shell prints its prompt shortly after starting. On a slow machine that lands after the
    test's first read, moving the activity time by a second (seen in CI as 299 s shown as 4m, not 5m).
    """
    previous = _last_output(picker, session)
    stable_since = time.monotonic()
    while time.monotonic() - stable_since < 1.2:
        time.sleep(0.1)
        current = _last_output(picker, session)
        if current != previous:
            previous, stable_since = current, time.monotonic()
    return previous


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
    when = _quiet(picker, "alpha")
    ages = {name: age for _, age, name in _list(picker, now=when + elapsed)}
    assert ages["alpha"] == shown


def test_age_is_the_newest_output_in_any_window(picker: Picker) -> None:
    """Output in a second window, in a session nobody is attached to, makes the session young."""
    picker.new_session("multi")
    picker.inner.run("new-window", "-d", "-t", "=multi:")
    first = _last_output(picker, "multi")
    wait_for(lambda: int(time.time()) > first + 1, timeout=4, what="a second to pass")
    picker.inner.run("send-keys", "-t", "=multi:1", "echo late", "Enter")
    settle(picker, quiet=0.3)
    newest = _last_output(picker, "multi")
    assert newest > first
    ages = {name: age for _, age, name in _list(picker, now=newest + 10)}
    assert ages["multi"] == "10s"


def test_recent_sort_follows_the_age(picker: Picker) -> None:
    picker.new_session("older")
    picker.new_session("newer")
    wait_for(lambda: int(time.time()) > _last_output(picker, "newer") + 1, timeout=4, what="a tick")
    picker.inner.run("send-keys", "-t", "=older:", "echo wake", "Enter")
    settle(picker, quiet=0.3)
    names = [name for _, _, name in _list(picker)]
    assert names.index("older") < names.index("newer")


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
