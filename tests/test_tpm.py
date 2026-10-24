"""sessionz.tmux, the file TPM runs on load, binds the picker key."""

from conftest import REPO, Picker, wait_for

ENTRY_FILE = REPO / "sessionz.tmux"


def _load(picker: Picker) -> None:
    picker.inner.run("run-shell", str(ENTRY_FILE))


def _binding(picker: Picker, table: str, key: str) -> str:
    return picker.inner.run("list-keys", "-T", table, key, check=False)


def test_default_binding_is_prefix_o(picker: Picker) -> None:
    _load(picker)
    bound = _binding(picker, "prefix", "o")
    assert "scripts/sessionz.sh" in bound and "#{client_tty}" in bound, bound


def test_bind_option_changes_the_key(picker: Picker) -> None:
    picker.inner.run("set", "-g", "@sessionz-bind", "C-s")
    _load(picker)
    assert "scripts/sessionz.sh" in _binding(picker, "prefix", "C-s")


def test_prefix_off_binds_in_the_root_table(picker: Picker) -> None:
    picker.inner.run("set", "-g", "@sessionz-bind", "F11")
    picker.inner.run("set", "-g", "@sessionz-prefix", "off")
    _load(picker)
    assert "scripts/sessionz.sh" in _binding(picker, "root", "F11")


def test_key_bound_by_the_plugin_opens_the_picker(picker: Picker) -> None:
    """End to end through the TPM entry file rather than the harness's own F12 binding."""
    picker.inner.run("set", "-g", "@sessionz-bind", "F11")
    picker.inner.run("set", "-g", "@sessionz-prefix", "off")
    _load(picker)
    picker.press("F11")
    wait_for(lambda: picker.is_open() and picker.selected() == "home", what="picker opened by F11")
