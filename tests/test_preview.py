"""The tree preview beside the list."""

from collections.abc import Callable

from conftest import Picker


def test_tree_preview_lists_each_session_once(tmux_env: Callable[..., Picker]) -> None:
    """F3: with ids past $10, `$1` must not also match `$10`-`$13`."""
    picker = tmux_env(height=80)
    names = [f"n{i:02d}" for i in range(1, 14)]
    for name in names:
        picker.new_session(name)
    picker.open()
    screen = picker.screen()
    # Each name appears once in the list and once in the preview tree.
    counts = {name: screen.count(name) for name in names}
    assert counts == {name: 2 for name in names}, screen
