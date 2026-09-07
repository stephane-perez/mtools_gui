"""Navigating into (or up from) a directory the backend can't actually
list (e.g. permission denied) used to still commit to the new path
before the listing failed - the pane kept showing the old, still-valid
listing (set_entries was never reached), so nothing on screen looked
wrong, but current_path was left pointing at a directory that doesn't
list. Double-clicking the same visible entry again then joined onto that
already-broken path instead of the real one, nesting the same name
deeper each time (".../timeshift/timeshift/timeshift/...") - reported
against a real root-owned timeshift snapshot directory. See
PaneWidget._list_and_display.

Headless (offscreen); uses only local temp directories - no SD card or
mtools involved.
"""

import os
import stat

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from mtools_gui.backends.local_backend import LocalBackend
from mtools_gui.pane_widget import PaneWidget


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_navigate_into_unreadable_dir_leaves_current_path_untouched(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("running as root ignores directory permissions")

    unreadable = tmp_path / "timeshift"
    unreadable.mkdir()
    unreadable.chmod(0)
    try:
        pane = PaneWidget("left")
        pane.set_backend(LocalBackend(), str(tmp_path))
        errors = []
        pane.error.connect(errors.append)

        pane.navigate_into("timeshift")

        assert errors  # the permission error was surfaced
        assert pane.current_path == str(tmp_path)
    finally:
        unreadable.chmod(stat.S_IRWXU)


def test_repeated_failed_navigation_does_not_nest_the_path(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("running as root ignores directory permissions")

    unreadable = tmp_path / "timeshift"
    unreadable.mkdir()
    unreadable.chmod(0)
    try:
        pane = PaneWidget("left")
        pane.set_backend(LocalBackend(), str(tmp_path))

        # Simulates the user double-clicking the same still-visible entry
        # several times in a row, as described in the bug report.
        for _ in range(3):
            pane.navigate_into("timeshift")

        assert pane.current_path == str(tmp_path)
        assert "timeshift/timeshift" not in pane.current_path
    finally:
        unreadable.chmod(stat.S_IRWXU)


def test_navigate_into_a_readable_dir_still_updates_current_path(tmp_path):
    (tmp_path / "PHOTOS").mkdir()
    pane = PaneWidget("left")
    pane.set_backend(LocalBackend(), str(tmp_path))

    pane.navigate_into("PHOTOS")

    assert pane.current_path == str(tmp_path / "PHOTOS")


def test_go_up_from_a_dir_that_becomes_unlistable_leaves_current_path_untouched(
    tmp_path, monkeypatch
):
    sub = tmp_path / "SUBDIR"
    sub.mkdir()
    pane = PaneWidget("left")
    pane.set_backend(LocalBackend(), str(sub))

    def failing_list_dir(path):
        raise PermissionError("simulated: parent became unreadable")

    monkeypatch.setattr(pane.backend, "list_dir", failing_list_dir)
    errors = []
    pane.error.connect(errors.append)

    pane.go_up()

    assert errors
    assert pane.current_path == str(sub)
