"""preview.sh output, run directly so the line budget and colours can be checked exactly."""

import subprocess
from pathlib import Path

from conftest import REPO, Picker, settle

PREVIEW = REPO / "sessionx" / "preview.sh"
BRIGHT = "\x1b[1;95m"  # bold bright magenta, the pane-label colour


def _preview(picker: Picker, tmp_path: Path, session: str, lines: int, cols: int = 60) -> list[str]:
    """Run preview.sh for `session` on the inner server as fzf would, and return its lines."""
    socket = picker.inner.run("display-message", "-p", "#{socket_path}").strip()
    session_id = picker.inner.run("display-message", "-p", "-t", f"={session}:", "#{session_id}").strip()
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    env = dict(picker.inner.env, TMUX=f"{socket},0,0", FZF_PREVIEW_LINES=str(lines), FZF_PREVIEW_COLUMNS=str(cols))
    proc = subprocess.run(
        ["bash", str(PREVIEW), str(state), session_id], env=env, capture_output=True, text=True, check=True
    )
    return proc.stdout.splitlines()


def _split(picker: Picker, top: str, bottom: str) -> None:
    picker.new_session("split")
    picker.inner.run("split-window", "-d", "-t", "=split:")
    picker.inner.run("send-keys", "-t", "=split:.0", top, "Enter")
    picker.inner.run("send-keys", "-t", "=split:.1", bottom, "Enter")
    settle(picker, quiet=0.4)


def _sections(out: list[str]) -> list[list[str]]:
    """Body lines of each pane, split on the pane labels (header line excluded)."""
    sections: list[list[str]] = []
    for line in out[1:]:
        if "── pane " in line:
            sections.append([])
        elif sections:
            sections[-1].append(line)
    return sections


def test_header_is_only_the_window_list(picker: Picker, tmp_path: Path) -> None:
    picker.new_session("solo")
    out = _preview(picker, tmp_path, "solo", lines=20)
    assert "0: " in out[0]
    assert "window(s)" not in "\n".join(out)
    assert "solo" not in out[0]


def test_pane_labels_are_bright_and_span_the_width(picker: Picker, tmp_path: Path) -> None:
    _split(picker, "echo A", "echo B")
    out = _preview(picker, tmp_path, "split", lines=20, cols=60)
    labels = [line for line in out if "── pane " in line]
    assert len(labels) == 2
    for label in labels:
        assert label.startswith(BRIGHT), repr(label)
        visible = label.replace(BRIGHT, "").replace("\x1b[0m", "")
        assert len(visible) == 60, repr(visible)


# The harness's panes are about 12 rows each, so a 14-line preview has to cut a full pane.
LINES = 14


def test_unused_lines_go_to_the_longer_pane(picker: Picker, tmp_path: Path) -> None:
    _split(picker, "seq 1 100", "echo SHORT")
    out = _preview(picker, tmp_path, "split", lines=LINES)
    top, bottom = _sections(out)
    assert any("SHORT" in line for line in bottom)
    # Header + 2 labels + the short pane in full; everything else goes to the long pane.
    assert len(out) == LINES
    assert len(top) == LINES - 1 - 2 - len(bottom)
    assert len(top) > len(bottom)


def test_two_long_panes_share_the_lines_evenly(picker: Picker, tmp_path: Path) -> None:
    _split(picker, "seq 1 100", "seq 1 100")
    out = _preview(picker, tmp_path, "split", lines=LINES)
    top, bottom = _sections(out)
    assert len(out) == LINES
    assert abs(len(top) - len(bottom)) <= 1


def test_long_pane_fills_spare_lines_from_its_scrollback(picker: Picker, tmp_path: Path) -> None:
    """With more preview lines than the pane is tall, history above the screen fills them."""
    _split(picker, "seq 1 100", "echo SHORT")
    out = _preview(picker, tmp_path, "split", lines=40)
    top, bottom = _sections(out)
    pane_rows = int(picker.inner.run("display-message", "-p", "-t", "=split:.0", "#{pane_height}"))
    assert len(top) == 40 - 1 - 2 - len(bottom)
    assert len(top) > pane_rows


def test_single_pane_window_also_reaches_into_scrollback(picker: Picker, tmp_path: Path) -> None:
    picker.new_session("long")
    picker.inner.run("send-keys", "-t", "=long:", "seq 1 100", "Enter")
    settle(picker, quiet=0.4)
    out = _preview(picker, tmp_path, "long", lines=40)
    pane_rows = int(picker.inner.run("display-message", "-p", "-t", "=long:", "#{pane_height}"))
    assert len(out) - 1 > pane_rows
