"""The permanent status bar label showing "X in progress..." while a
copy/move/delete/etc. is running in the background, added because the
status bar previously said nothing until an operation finished. Headless
(offscreen); uses only local temp directories - no SD card or mtools
involved.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from mtools_gui import main_window as mw
from mtools_gui.backends.local_backend import LocalBackend


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp):
    return mw.MainWindow()


def _spin(ms=800):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def test_label_is_empty_before_anything_runs(window):
    assert window._progress_label.text() == ""


def test_label_shows_description_while_one_operation_is_running(window, tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("x" * 2_000_000)  # big enough to still be "in flight" briefly
    dst = tmp_path / "dst"
    dst.mkdir()

    window.left_pane.set_backend(LocalBackend(), str(src))
    window.right_pane.set_backend(LocalBackend(), str(dst))
    entries = window.left_pane.entries_by_names(["a.txt"])

    window.transfer_service.copy(
        window.left_pane.backend, "left", str(src), entries,
        window.right_pane.backend, "right", str(dst),
    )

    assert window._progress_label.text() != ""
    assert "a.txt" in window._progress_label.text()

    _spin()
    assert window._progress_label.text() == ""


def test_label_shows_a_count_when_multiple_operations_overlap(window):
    window._on_operation_started("Copier a.txt")
    window._on_operation_started("Copier b.txt")
    assert "2" in window._progress_label.text()

    window._on_operation_succeeded("Copier a.txt", "left")
    assert "b.txt" in window._progress_label.text()

    window._on_operation_succeeded("Copier b.txt", "left")
    assert window._progress_label.text() == ""


def test_label_clears_on_failure_too(window, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))

    window._on_operation_started("Copier a.txt")
    assert window._progress_label.text() != ""

    window._on_operation_failed("Copier a.txt : boom", "Copier a.txt")
    assert window._progress_label.text() == ""
