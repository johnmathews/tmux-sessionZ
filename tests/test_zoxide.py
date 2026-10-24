"""ctrl-f: open a session in a zoxide directory."""

import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from conftest import Picker, wait_for

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
    path = picker.inner.run("display", "-p", "-t", f"={dirname}", "#{session_path}").strip()
    assert Path(path).resolve() == target
