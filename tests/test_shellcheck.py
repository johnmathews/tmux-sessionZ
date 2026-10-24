"""Every picker script passes shellcheck."""

import shutil
import subprocess

import pytest
from conftest import ENTRY


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck not installed")
def test_picker_scripts_pass_shellcheck() -> None:
    scripts = sorted(ENTRY.parent.glob("*.sh"))
    assert scripts, f"no scripts next to {ENTRY}"
    proc = subprocess.run(["shellcheck", *map(str, scripts)], check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout
