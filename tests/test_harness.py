"""The harness itself: a test that fails while starting must not leave tmux servers running."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

import conftest
import pytest
from conftest import TMUX, Tmux


def _alive(socket: str) -> bool:
    proc = subprocess.run([TMUX, "-L", socket, "list-sessions"], capture_output=True, text=True, check=False)
    return proc.returncode == 0


def test_a_start_that_times_out_kills_both_servers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A fixed tag, so the test knows which sockets start() is about to create.
    fixed = uuid.uuid4()
    tag = fixed.hex[:8]
    sockets = (f"sxt-{tag}", f"sxt-{tag}-outer")
    monkeypatch.setattr(conftest.uuid, "uuid4", lambda: fixed)

    def attach_times_out(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("timed out waiting for client to attach")

    # Both servers exist by the time start() waits for the client, so this is the failure that leaked them.
    monkeypatch.setattr(conftest, "wait_for", attach_times_out)
    try:
        with pytest.raises(AssertionError, match="client to attach"):
            conftest.start(tmp_path)
        assert [s for s in sockets if _alive(s)] == []
    finally:
        # Never leak from this test either, whatever start() did.
        for socket in sockets:
            Tmux(socket, {}).kill()
