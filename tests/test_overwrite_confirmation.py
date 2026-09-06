"""Copying/moving onto an existing same-named destination entry used to
silently nest instead of replacing it (mcopy/mmove, and shutil.copytree
without dirs_exist_ok, copy the source *inside* an existing destination
directory rather than replacing it - e.g. copying folder ANKHA onto an
already-present ANKHA produced ANKHA/ANKHA/* nested alongside ANKHA's old
contents). Now: the destination is checked for conflicts, the user is
asked to confirm, and on confirmation the existing destination entry is
deleted before the copy/move runs. Headless (offscreen); the end-to-end
test uses only local temp directories - no SD card or mtools involved.
"""

import os
from datetime import datetime
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from mtools_gui import main_window as mw
from mtools_gui.backends.local_backend import LocalBackend
from mtools_gui.entry import Entry
from mtools_gui.transfer_service import TransferService


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _entry(name, is_dir=False):
    return Entry(name=name, is_dir=is_dir, size=0, modified=datetime(2024, 1, 1))


# -- TransferService._with_replace -------------------------------------------


def test_with_replace_deletes_destination_before_copying():
    calls = []
    existing = _entry("ANKHA", is_dir=True)
    dst_backend = SimpleNamespace(delete=lambda *a: calls.append(("delete", a)))

    wrapped = TransferService._with_replace(
        lambda: calls.append(("copy",)), dst_backend, "/dest_dir", existing
    )
    wrapped()

    assert calls == [("delete", ("/dest_dir", "ANKHA", True)), ("copy",)]


def test_with_replace_is_noop_when_nothing_to_replace():
    calls = []
    wrapped = TransferService._with_replace(lambda: calls.append("copy"), None, "/x", None)
    wrapped()
    assert calls == ["copy"]


# -- main_window._transfer_entries: conflict detection + confirmation -------


@pytest.fixture(autouse=True)
def no_real_dialogs(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))


@pytest.fixture
def window(qapp):
    return mw.MainWindow()


def test_conflict_detected_asks_confirmation_and_passes_replace(window, monkeypatch):
    src = window.left_pane
    dst = window.right_pane

    existing = _entry("ANKHA", is_dir=True)
    monkeypatch.setattr(dst, "backend", SimpleNamespace(list_dir=lambda path: [existing]))

    captured = {}
    monkeypatch.setattr(
        window.transfer_service,
        "copy",
        lambda *a, **k: captured.update(kwargs=k),
    )
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))

    window._transfer_entries(src, dst, [_entry("ANKHA", is_dir=True)], move=False)

    assert captured["kwargs"]["replace"] is existing


def test_conflict_declined_cancels_the_whole_transfer(window, monkeypatch):
    src = window.left_pane
    dst = window.right_pane
    monkeypatch.setattr(
        dst, "backend", SimpleNamespace(list_dir=lambda path: [_entry("ANKHA", is_dir=True)])
    )
    called = []
    monkeypatch.setattr(window.transfer_service, "copy", lambda *a, **k: called.append(True))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))

    window._transfer_entries(src, dst, [_entry("ANKHA", is_dir=True)], move=False)

    assert called == []


def test_no_conflict_does_not_prompt_and_passes_replace_none(window, monkeypatch):
    src = window.left_pane
    dst = window.right_pane
    monkeypatch.setattr(dst, "backend", SimpleNamespace(list_dir=lambda path: []))

    asked = []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: asked.append(True) or QMessageBox.Yes))
    captured = {}
    monkeypatch.setattr(
        window.transfer_service, "copy", lambda *a, **k: captured.update(kwargs=k)
    )

    window._transfer_entries(src, dst, [_entry("newfile.txt")], move=False)

    assert asked == []
    assert captured["kwargs"]["replace"] is None


# -- End-to-end: reproduces the exact ANKHA nesting bug with local dirs -----


def test_copying_a_folder_onto_an_existing_one_replaces_instead_of_nesting(
    window, monkeypatch, tmp_path
):
    src_dir = tmp_path / "src"
    (src_dir / "ANKHA").mkdir(parents=True)
    (src_dir / "ANKHA" / "f1.txt").write_text("from source")
    (src_dir / "ANKHA" / "f2.txt").write_text("from source")

    dst_dir = tmp_path / "dst"
    (dst_dir / "ANKHA").mkdir(parents=True)
    (dst_dir / "ANKHA" / "existing.txt").write_text("pre-existing local file")

    window.left_pane.set_backend(LocalBackend(), str(src_dir))
    window.right_pane.set_backend(LocalBackend(), str(dst_dir))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))

    entries = window.left_pane.entries_by_names(["ANKHA"])
    window._transfer_entries(window.left_pane, window.right_pane, entries, move=False)

    # let the background QRunnable finish
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(500, loop.quit)
    loop.exec()

    result = {p.name for p in (dst_dir / "ANKHA").iterdir()}
    # must be replaced (f1.txt, f2.txt only) - not nested (ANKHA/ANKHA/...)
    # and not merged with the stale existing.txt
    assert result == {"f1.txt", "f2.txt"}
    assert not (dst_dir / "ANKHA" / "ANKHA").exists()
