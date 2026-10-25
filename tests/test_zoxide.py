"""ctrl-f: open a session in a zoxide directory."""

import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import Picker, settle, wait_for

pytestmark = pytest.mark.skipif(shutil.which("zoxide") is None, reason="zoxide not installed")


@pytest.fixture
def short_dir() -> Iterator[Path]:
    """pytest's tmp_path is too long to fit untruncated in the list column."""
    path = Path(tempfile.mkdtemp(prefix="sxz-", dir="/tmp")).resolve()
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.mark.parametrize("dirname", ["proj-one", "proj two"])
def test_directory_opens_a_session_rooted_there(picker: Picker, short_dir: Path, dirname: str) -> None:
    target = short_dir / dirname
    target.mkdir()
    subprocess.run(["zoxide", "add", str(target)], env=picker.inner.env, check=True)
    picker.open()
    picker.press("C-f")
    wait_for(lambda: dirname in picker.screen(), what="zoxide directories to list")
    picker.select(str(target))
    picker.press("Enter")
    wait_for(lambda: picker.client_session() == dirname, what=f"switch to {dirname!r}")
    paths = dict(
        line.split("\t", 1)
        for line in picker.inner.run("list-sessions", "-F", "#{session_name}\t#{session_path}").splitlines()
    )
    assert Path(paths[dirname]).resolve() == target


def test_directory_list_is_wider_than_the_session_list(picker: Picker, short_dir: Path) -> None:
    """Paths are longer than session names: zoxide mode gives the list 45%, leaving it gives back 25%."""
    subprocess.run(["zoxide", "add", str(short_dir)], env=picker.inner.env, check=True)
    picker.open()
    picker.press("C-f")
    wait_for(lambda: "zoxide>" in picker.screen(), what="zoxide mode")
    wait_for(lambda: 0.4 <= (picker.list_share() or 0) <= 0.5, what="the list to widen")
    picker.press("Escape")
    wait_for(lambda: "zoxide>" not in picker.screen(), what="session mode")
    wait_for(lambda: 0.2 <= (picker.list_share() or 0) <= 0.3, what="the list to narrow")


def test_zoxide_mode_keeps_a_hidden_preview_hidden(picker: Picker, short_dir: Path) -> None:
    subprocess.run(["zoxide", "add", str(short_dir)], env=picker.inner.env, check=True)
    picker.open()
    picker.press("M-p")
    wait_for(lambda: picker.list_share() is None, what="preview hidden")
    picker.press("C-f")
    wait_for(lambda: "zoxide>" in picker.screen(), what="zoxide mode")
    assert picker.list_share() is None
    picker.press("Escape")
    wait_for(lambda: "zoxide>" not in picker.screen(), what="session mode")
    assert picker.list_share() is None


def test_live_preview_keeps_a_scrolled_listing_where_it_is(picker: Picker, short_dir: Path) -> None:
    """The timer does not refresh a directory listing, so ctrl-u holds.

    A refresh would put the view back at the bottom (follow), even for an identical listing. A session
    preview is cut to the preview's height and never scrolls, so only session previews are refreshed.
    """
    for i in range(200):
        (short_dir / f"file-{i:03d}").touch()
    subprocess.run(["zoxide", "add", str(short_dir)], env=picker.inner.env, check=True)
    picker.open()
    picker.press("C-f")
    wait_for(lambda: str(short_dir) in picker.screen(), what="zoxide directories to list")
    picker.select(str(short_dir))
    wait_for(lambda: "file-199" in picker.screen(), what="the end of the listing in the preview")
    settle(picker)
    bottom = picker.screen()
    picker.press("C-u")
    wait_for(lambda: picker.screen() != bottom, what="the preview to scroll up")
    scrolled = picker.screen()
    time.sleep(2.5)
    assert picker.screen() == scrolled
