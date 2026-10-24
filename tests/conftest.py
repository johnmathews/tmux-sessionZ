"""Harness that drives the sessionZ picker through a real tmux popup.

Two private tmux servers per test:

- *inner* hosts the sessions under test and binds F12 to the picker entry.
- *outer* has one pane running a client attached to inner, so the popup renders
  exactly as it would in a terminal. Keys go to the outer pane and the screen is
  read back with capture-pane.

Neither server touches the user's default tmux server: every command passes -L.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
TMUX = shutil.which("tmux") or "tmux"
ENTRY = (REPO / os.environ.get("SESSIONZ_ENTRY", "scripts/sessionz.sh")).resolve()

# Characters that can bound the list column on screen: popup border, preview border.
_EDGE = re.compile(r"[│┃|╭╮╰╯─]")


@dataclass
class Tmux:
    """A private tmux server addressed by socket name."""

    socket: str
    env: dict[str, str]

    def run(self, *args: str, check: bool = True) -> str:
        proc = subprocess.run(
            [TMUX, "-L", self.socket, *args],
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )
        if check and proc.returncode != 0:
            raise RuntimeError(f"tmux {' '.join(args)} failed: {proc.stderr.strip()}")
        return proc.stdout

    def kill(self) -> None:
        # tmux 3.8 leaves the socket file behind after kill-server; remove it so runs don't accumulate them.
        socket = self.run("display-message", "-p", "#{socket_path}", check=False).strip()
        self.run("kill-server", check=False)
        if socket:
            Path(socket).unlink(missing_ok=True)


@dataclass
class Picker:
    """Drives one attached client and the picker it opens."""

    inner: Tmux
    outer: Tmux
    pane: str = "outer:0.0"
    clients: list[str] = field(default_factory=list)

    # --- inner server state -------------------------------------------------

    def sessions(self) -> dict[str, str]:
        """Map of session id to session name."""
        out = self.inner.run("list-sessions", "-F", "#{session_id}\t#{session_name}", check=False)
        return dict(line.split("\t", 1) for line in out.splitlines() if line)

    def names(self) -> list[str]:
        return sorted(self.sessions().values())

    def new_session(self, name: str) -> str:
        return self.inner.run("new-session", "-d", "-s", name, "-P", "-F", "#{session_id}").strip()

    def client_session(self) -> str | None:
        """Session name this pane's client is attached to, or None if it has detached."""
        tty = self.outer.run("display", "-p", "-t", self.pane, "#{pane_tty}", check=False).strip()
        out = self.inner.run("list-clients", "-F", "#{client_tty}\t#{session_name}", check=False)
        for line in out.splitlines():
            client, _, session = line.partition("\t")
            if client == tty:
                return session
        return None

    def client_window(self) -> str | None:
        """Window name this pane's client is looking at, or None if it has detached."""
        tty = self.outer.run("display", "-p", "-t", self.pane, "#{pane_tty}", check=False).strip()
        out = self.inner.run("list-clients", "-F", "#{client_tty}\t#{window_name}", check=False)
        for line in out.splitlines():
            client, _, window = line.partition("\t")
            if client == tty:
                return window
        return None

    def attach_another(self, session: str) -> Picker:
        """A second client, in its own outer window, attached to `session`."""
        name = f"c{len(self.clients) + 2}"
        self.clients.append(name)
        self.outer.run("new-window", "-d", "-t", "outer:", "-n", name, _attach_cmd(self.inner, session))
        other = Picker(self.inner, self.outer, pane=f"outer:{name}.0")
        wait_for(lambda: other.client_session() == session, what="second client to attach")
        return other

    # --- screen -------------------------------------------------------------

    def screen(self) -> str:
        return self.outer.run("capture-pane", "-p", "-t", self.pane, check=False)

    def screen_ansi(self) -> str:
        """The screen with colours and attributes kept as escape sequences."""
        return self.outer.run("capture-pane", "-e", "-p", "-t", self.pane, check=False)

    def selected(self) -> str | None:
        """Display text of the line under the picker's cursor."""
        for line in self.screen().splitlines():
            if "▶ " in line:
                text = line.split("▶ ", 1)[1]
                return _EDGE.split(text, 1)[0].rstrip()
        return None

    def is_open(self) -> bool:
        return "Current session" in self.screen()

    # --- input --------------------------------------------------------------

    def press(self, *keys: str) -> None:
        self.outer.run("send-keys", "-t", self.pane, *keys)

    def type(self, text: str) -> None:
        self.outer.run("send-keys", "-t", self.pane, "-l", text)

    def open(self) -> None:
        self.press("F12")
        wait_for(lambda: self.is_open() and self.selected() is not None, what="picker to open")
        settle(self)

    def close(self) -> None:
        self.press("Escape")
        wait_for(lambda: not self.is_open(), what="picker to close")

    def select(self, name: str) -> None:
        """Move the cursor to the line whose display text is `name`."""
        for key in ("Up", "Down"):
            previous: str | None = None
            for _ in range(60):
                current = self.selected()
                if current == name:
                    return
                if current == previous:
                    break
                previous = current
                self.press(key)
                wait_for(
                    lambda before=current: self.selected() != before,
                    timeout=1.0,
                    what=f"cursor to move {key}",
                    soft=True,
                )
        raise AssertionError(f"could not select {name!r}; screen:\n{self.screen()}")


def wait_for(
    predicate: Callable[[], object],
    timeout: float = 5.0,
    what: str = "condition",
    soft: bool = False,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    if soft:
        return False
    raise AssertionError(f"timed out waiting for {what}")


def settle(picker: Picker, quiet: float = 0.4, timeout: float = 5.0) -> None:
    """Wait until the screen stops changing for `quiet` seconds."""
    deadline = time.monotonic() + timeout
    last = picker.screen()
    stable_since = time.monotonic()
    while time.monotonic() < deadline:
        time.sleep(0.05)
        now = picker.screen()
        if now != last:
            last, stable_since = now, time.monotonic()
        elif time.monotonic() - stable_since >= quiet:
            return


def _attach_cmd(inner: Tmux, session: str) -> str:
    return f"env -u TMUX {TMUX} -L {inner.socket} attach -t '={session}'"


def _env(tmp: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("TMUX", "FZF_"))}
    env["_ZO_DATA_DIR"] = str(tmp / "zoxide")
    (tmp / "zoxide").mkdir()
    return env


def start(tmp: Path, first_session: str = "home", width: int = 200, height: int = 50) -> Picker:
    tag = uuid.uuid4().hex[:8]
    env = _env(tmp)
    inner = Tmux(f"sxt-{tag}", env)
    outer = Tmux(f"sxt-{tag}-outer", env)

    conf = tmp / "inner.conf"
    conf.write_text(
        "\n".join(
            [
                "set -g default-shell /bin/sh",
                "set -g escape-time 0",
                "set -g status off",
                "set -g detach-on-destroy on",
                f"bind -n F12 run-shell \"'{ENTRY}' '#{{client_tty}}'\"",
                "",
            ]
        )
    )
    inner.run("-f", str(conf), "new-session", "-d", "-s", first_session)
    attach = _attach_cmd(inner, first_session)
    outer.run("-f", "/dev/null", "new-session", "-d", "-s", "outer", "-x", str(width), "-y", str(height), attach)
    outer.run("set", "-g", "status", "off")
    outer.run("set", "-g", "escape-time", "0")
    picker = Picker(inner, outer)
    wait_for(lambda: picker.client_session() == first_session, what="client to attach")
    return picker


@pytest.fixture
def tmux_env(tmp_path: Path) -> Iterator[Callable[..., Picker]]:
    """Factory: start(first_session=...) -> Picker. All servers are killed afterwards."""
    started: list[Picker] = []

    def factory(**kwargs: object) -> Picker:
        picker = start(tmp_path, **kwargs)  # type: ignore[arg-type]
        started.append(picker)
        return picker

    yield factory
    for picker in started:
        picker.outer.kill()
        picker.inner.kill()


@pytest.fixture
def picker(tmux_env: Callable[..., Picker]) -> Picker:
    return tmux_env()
