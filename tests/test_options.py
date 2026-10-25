"""User options read from tmux.conf each time the picker opens: size, list width, border, blackout."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import Picker, wait_for

# The test terminal is 200x50 with no status lines, so percentages map to whole cells.
COLS, ROWS = 200, 50


def _frame(picker: Picker) -> tuple[int, int]:
    """Width and height of the popup frame, corners included."""
    lines = picker.screen().splitlines()
    top = next(i for i, line in enumerate(lines) if "┏" in line)
    bottom = next(i for i, line in enumerate(lines) if "┗" in line)
    return lines[top].index("┓") - lines[top].index("┏") + 1, bottom - top + 1


def _set(picker: Picker, **options: str) -> None:
    for name, value in options.items():
        picker.inner.run("set", "-g", f"@sessionz-{name.replace('_', '-')}", value)


def test_default_size_is_three_quarters(picker: Picker) -> None:
    picker.open()
    width, height = _frame(picker)
    assert abs(width - 0.75 * COLS) <= 2 and abs(height - 0.75 * ROWS) <= 2, (width, height)


@pytest.mark.parametrize("blackout", ["off", "on"])
def test_width_and_height(picker: Picker, blackout: str) -> None:
    _set(picker, width="80%", height="60%", blackout=blackout)
    picker.open()
    width, height = _frame(picker)
    assert abs(width - 0.8 * COLS) <= 2 and abs(height - 0.6 * ROWS) <= 2, (width, height)


@pytest.mark.parametrize("value", ["40%", "40"])
def test_list_width(picker: Picker, value: str) -> None:
    _set(picker, list_width=value)
    picker.open()
    share = picker.list_share()
    assert share is not None and 0.37 <= share <= 0.43, share


def test_border_colour(picker: Picker) -> None:
    _set(picker, border_color="#ff0000")
    picker.open()
    top = next(line for line in picker.screen_ansi().splitlines() if "┏" in line)
    assert re.search(r"\x1b\[(?:[0-9;]*;)?38;2;255;0;0[;m]", top[: top.index("┏")]), top


def _content_origin(picker: Picker) -> tuple[int, int]:
    """Row and column of the prompt, the top-left of fzf's content. The preview's top edge shares its row."""
    lines = picker.screen().splitlines()
    row = next(i for i, line in enumerate(lines) if "╭" in line)
    return row, lines[row].index("> ")


def test_border_off_removes_only_the_frame(picker: Picker) -> None:
    """No popup frame; the preview's own border and the padding inside the frame stay."""
    picker.open()
    framed = _content_origin(picker)
    picker.close()
    _set(picker, border="off")
    picker.open()
    screen = picker.screen()
    assert not re.search(r"[┏┓┗┛┃━]", screen), screen
    assert "╭" in screen, screen
    # The frame goes, and with it the space fzf keeps beside a side border; the padding stays. So the
    # content moves one row up and two columns left. Dropping the padding too would make it 2 and 3.
    assert _content_origin(picker) == (framed[0] - 1, framed[1] - 2), screen


def test_blackout_hides_what_is_behind_the_popup(picker: Picker) -> None:
    picker.inner.run("send-keys", "-t", "=home:", "clear; echo BACKGROUND-MARK", "Enter")
    wait_for(lambda: "BACKGROUND-MARK" in picker.screen(), what="mark behind the popup")
    _set(picker, blackout="on")
    picker.open()
    lines = picker.screen().splitlines()
    top = next(i for i, line in enumerate(lines) if "┏" in line)
    assert top > 0 and not any(line.strip() for line in lines[:top]), lines[:top]
    picker.close()
    _set(picker, blackout="off")
    picker.open()
    lines = picker.screen().splitlines()
    top = next(i for i, line in enumerate(lines) if "┏" in line)
    assert any("BACKGROUND-MARK" in line for line in lines[:top]), lines[:top]


def test_bad_values_fall_back_to_defaults_and_say_so(picker: Picker) -> None:
    _set(
        picker,
        width="huge",
        list_width="0%",
        border="none",
        border_color="chartreuse",
        blackout="maybe",
        preview_interval="fast",
    )
    picker.open()
    width, _ = _frame(picker)  # the frame is drawn: a bad @sessionz-border means on
    assert abs(width - 0.75 * COLS) <= 2, width
    share = picker.list_share()
    assert share is not None and 0.2 <= share <= 0.3, share
    log = picker.inner.run("show-messages")
    warning = next((line for line in log.splitlines() if "sessionZ: ignored" in line), "")
    names = (
        "@sessionz-width",
        "@sessionz-list-width",
        "@sessionz-border",
        "@sessionz-border-color",
        "@sessionz-blackout",
        "@sessionz-preview-interval",
    )
    for name in names:
        assert f"{name} '" in warning, (name, log)


@pytest.mark.skipif(shutil.which("zoxide") is None, reason="zoxide not installed")
def test_zoxide_never_narrows_a_wide_list(picker: Picker, tmp_path: Path) -> None:
    """Zoxide mode widens the list to at least 45%; a list already wider keeps its width."""
    subprocess.run(["zoxide", "add", str(tmp_path)], env=picker.inner.env, check=True)
    _set(picker, list_width="60%")
    picker.open()
    picker.press("C-f")
    wait_for(lambda: "zoxide>" in picker.screen(), what="zoxide mode")
    share = picker.list_share()
    assert share is not None and 0.57 <= share <= 0.63, share
