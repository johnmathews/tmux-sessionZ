"""How the list column looks: highlighted selection, spacing, header, and the key sheet."""

import re

from conftest import Picker, settle, strip_age, wait_for

# The accent is the status bar's green, #5fff00 = 256-colour palette 82. tmux may
# re-encode it as 48;5;82 or as RGB. fzf's default theme already gives the current
# line a faint grey background, so any-background is not enough.
GREEN_BG = re.compile(r"\x1b\[(?:[0-9;]*;)?48;(?:5;82|2;95;255;0)[;m]")
PINK = re.compile(r"\x1b\[(?:[0-9;]*;)?(?:35|95|45|105|[34]8;5;(?:5|13))[;m]")


def _left(line: str) -> str:
    """The list column of a popup line: text between the popup border and the preview border."""
    inner = line.split("│", 1)[1] if "│" in line else line
    return re.split(r"[│╭╰]", inner, maxsplit=1)[0].strip()


def test_selected_row_has_a_background_colour(picker: Picker) -> None:
    picker.new_session("alpha")
    picker.open()
    selected = [line for line in picker.screen_ansi().splitlines() if "▶" in line]
    assert selected and GREEN_BG.search(selected[0]), selected


def test_pink_only_on_key_sheet_keys_and_no_coloured_gutter(picker: Picker) -> None:
    """Green is the accent; the key sheet's key names alone are hot pink (bright magenta)."""
    for name in ("alpha", "beta"):
        picker.new_session(name)
    picker.open()
    screen = picker.screen_ansi()
    assert not PINK.search(screen), [line for line in screen.splitlines() if PINK.search(line)][:2]
    unselected = [line for line in screen.splitlines() if "▶" not in line and ("alpha" in line or "beta" in line)]
    assert unselected and not any(GREEN_BG.search(line) for line in unselected), unselected
    picker.press("?")
    wait_for(lambda: "kill session" in picker.screen(), what="key sheet")
    sheet = picker.screen_ansi().splitlines()
    for key in ("ctrl-q", "ctrl-r", "enter"):
        line = next(line for line in sheet if key in line)
        before_key = line[: line.index(key)]
        assert PINK.search(before_key), (key, line)
    for title in ("Sessions", "Preview"):
        line = next(line for line in sheet if title in line)
        assert not PINK.search(line[: line.index(title)]), (title, line)


def test_no_match_counter(picker: Picker) -> None:
    picker.new_session("alpha")
    picker.open()
    counters = [line for line in picker.screen().splitlines() if re.search(r"\b\d+/\d+\b", _left(line))]
    assert not counters, counters


def test_blank_row_above_the_list(picker: Picker) -> None:
    for name in ("alpha", "beta"):
        picker.new_session(name)
    picker.open()
    lines = picker.screen().splitlines()
    names = {"alpha", "beta", "home"}
    first = min(i for i, line in enumerate(lines) if strip_age(_left(line).lstrip("▶▌ ")) in names)
    assert _left(lines[first - 1]) == "", lines[first - 1]


def test_header_is_short_and_points_at_the_key_sheet(picker: Picker) -> None:
    picker.open()
    screen = picker.screen()
    assert "? keys" in screen
    assert "^r rename" not in screen


def test_question_mark_shows_the_key_sheet_and_toggles_back(picker: Picker) -> None:
    picker.new_session("alpha")
    picker.inner.run("send-keys", "-t", "=alpha:", "echo PREVIEW-MARK", "Enter")
    settle(picker, quiet=0.3)
    picker.open()
    picker.select("alpha")
    wait_for(lambda: "PREVIEW-MARK" in picker.screen(), what="pane preview")
    picker.press("?")
    wait_for(lambda: "kill session" in picker.screen(), what="key sheet")
    screen = picker.screen()
    for key in ("ctrl-r", "ctrl-a", "ctrl-q", "ctrl-t", "ctrl-f", "enter", "esc"):
        assert key in screen, key
    assert "PREVIEW-MARK" not in screen
    picker.press("?")
    wait_for(lambda: "PREVIEW-MARK" in picker.screen(), what="pane preview back")


def test_escape_closes_the_key_sheet_not_the_picker(picker: Picker) -> None:
    picker.open()
    picker.press("?")
    wait_for(lambda: "kill session" in picker.screen(), what="key sheet")
    picker.press("Escape")
    wait_for(lambda: "kill session" not in picker.screen(), what="key sheet to close")
    assert picker.is_open()


def test_alt_p_toggles_the_preview(picker: Picker) -> None:
    picker.new_session("alpha")
    picker.inner.run("send-keys", "-t", "=alpha:", "echo PREVIEW-MARK", "Enter")
    settle(picker, quiet=0.3)
    picker.open()
    picker.select("alpha")
    wait_for(lambda: "PREVIEW-MARK" in picker.screen(), what="pane preview")
    picker.press("M-p")
    wait_for(lambda: "PREVIEW-MARK" not in picker.screen(), what="preview hidden")
    picker.press("M-p")
    wait_for(lambda: "PREVIEW-MARK" in picker.screen(), what="preview shown again")


def test_no_gutter_bar_beside_unselected_rows(picker: Picker) -> None:
    """fzf draws a gutter glyph (▌) left of every unselected row; it must be blank."""
    for name in ("alpha", "beta"):
        picker.new_session(name)
    picker.open()
    rows = [line for line in picker.screen().splitlines() if "▶" not in line and re.search(r"\b(alpha|beta)\b", line)]
    assert len(rows) == 2, rows
    assert not any("▌" in row for row in rows), rows
