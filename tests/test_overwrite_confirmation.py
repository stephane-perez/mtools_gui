"""Copying/moving onto an existing same-named destination entry used to
silently nest instead of replacing it (mcopy/mmove, and shutil.copytree
without dirs_exist_ok, copy the source *inside* an existing destination
directory rather than replacing it - e.g. copying folder PHOTOS onto an
already-present PHOTOS produced PHOTOS/PHOTOS/* nested alongside PHOTOS's old
contents). Now: the destination is checked for conflicts, the user is
asked to confirm, and on confirmation every conflicting destination entry is
renamed to a backup name before the copy/move runs (not deleted outright -
see _with_replace_many's docstring: a rename-then-restore-on-failure means a
copy that fails partway through doesn't cost the user their original).
Headless (offscreen); the end-to-end test uses only local temp
directories - no SD card or mtools involved.
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


# -- TransferService._with_replace_many --------------------------------------


def _fake_backend(calls):
    return SimpleNamespace(
        rename=lambda directory, old, new: calls.append(("rename", directory, old, new)),
        delete=lambda directory, name, is_dir: calls.append(("delete", directory, name, is_dir)),
    )


def test_with_replace_renames_existing_entry_out_of_the_way_first():
    calls = []
    existing = _entry("PHOTOS", is_dir=True)
    dst_backend = _fake_backend(calls)

    wrapped = TransferService._with_replace_many(
        lambda: calls.append(("copy",)), dst_backend, "/dest_dir", [existing]
    )
    wrapped()

    assert calls == [
        ("rename", "/dest_dir", "PHOTOS", ".mtools_gui_bak_PHOTOS"),
        ("copy",),
        ("delete", "/dest_dir", ".mtools_gui_bak_PHOTOS", True),
    ]


def test_with_replace_renames_every_conflicting_entry_for_a_batch():
    calls = []
    existing_a = _entry("PHOTOS", is_dir=True)
    existing_b = _entry("VIDEOS", is_dir=True)
    dst_backend = _fake_backend(calls)

    wrapped = TransferService._with_replace_many(
        lambda: calls.append(("copy",)), dst_backend, "/dest_dir", [existing_a, existing_b]
    )
    wrapped()

    assert calls == [
        ("rename", "/dest_dir", "PHOTOS", ".mtools_gui_bak_PHOTOS"),
        ("rename", "/dest_dir", "VIDEOS", ".mtools_gui_bak_VIDEOS"),
        ("copy",),
        ("delete", "/dest_dir", ".mtools_gui_bak_PHOTOS", True),
        ("delete", "/dest_dir", ".mtools_gui_bak_VIDEOS", True),
    ]


def test_with_replace_restores_the_backup_if_the_copy_fails():
    calls = []
    existing = _entry("PHOTOS", is_dir=True)
    dst_backend = _fake_backend(calls)

    def failing_copy():
        raise OSError("card was pulled mid-copy")

    wrapped = TransferService._with_replace_many(failing_copy, dst_backend, "/dest_dir", [existing])

    with pytest.raises(OSError, match="card was pulled"):
        wrapped()

    # the failed attempt is cleaned up, then the original is restored -
    # the user still has their original PHOTOS, not nothing
    assert calls == [
        ("rename", "/dest_dir", "PHOTOS", ".mtools_gui_bak_PHOTOS"),
        ("delete", "/dest_dir", "PHOTOS", True),
        ("rename", "/dest_dir", ".mtools_gui_bak_PHOTOS", "PHOTOS"),
    ]


def test_with_replace_is_noop_when_nothing_to_replace():
    calls = []
    wrapped = TransferService._with_replace_many(lambda: calls.append("copy"), None, "/x", [])
    wrapped()
    assert calls == ["copy"]


def test_replace_end_to_end_survives_a_failed_copy(tmp_path):
    # A LocalBackend<->LocalBackend rehearsal of the rollback: the
    # destination's original content must still be there after a copy
    # that fails partway through, not vanished.
    src_dir = tmp_path / "src"
    (src_dir / "PHOTOS").mkdir(parents=True)
    (src_dir / "PHOTOS" / "f1.txt").write_text("from source")

    dst_dir = tmp_path / "dst"
    (dst_dir / "PHOTOS").mkdir(parents=True)
    (dst_dir / "PHOTOS" / "existing.txt").write_text("precious original data")

    backend = LocalBackend()
    existing = _entry("PHOTOS", is_dir=True)

    def failing_copy():
        raise OSError("simulated failure partway through the copy")

    wrapped = TransferService._with_replace_many(failing_copy, backend, str(dst_dir), [existing])

    with pytest.raises(OSError):
        wrapped()

    assert (dst_dir / "PHOTOS" / "existing.txt").read_text() == "precious original data"


# -- main_window._transfer_entries: conflict detection + confirmation -------


@pytest.fixture(autouse=True)
def no_real_dialogs(monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))


@pytest.fixture
def window(qapp):
    return mw.MainWindow()


def test_conflict_detected_asks_confirmation_and_passes_replacements(window, monkeypatch):
    src = window.left_pane
    dst = window.right_pane

    existing = _entry("PHOTOS", is_dir=True)
    monkeypatch.setattr(dst, "backend", SimpleNamespace(list_dir=lambda path: [existing]))

    captured = {}
    monkeypatch.setattr(
        window.transfer_service,
        "copy",
        lambda *a, **k: captured.update(kwargs=k),
    )
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))

    window._transfer_entries(src, dst, [_entry("PHOTOS", is_dir=True)], move=False)

    assert captured["kwargs"]["replacements"] == {"PHOTOS": existing}


def test_conflict_declined_cancels_the_whole_transfer(window, monkeypatch):
    src = window.left_pane
    dst = window.right_pane
    monkeypatch.setattr(
        dst, "backend", SimpleNamespace(list_dir=lambda path: [_entry("PHOTOS", is_dir=True)])
    )
    called = []
    monkeypatch.setattr(window.transfer_service, "copy", lambda *a, **k: called.append(True))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))

    window._transfer_entries(src, dst, [_entry("PHOTOS", is_dir=True)], move=False)

    assert called == []


def test_no_conflict_does_not_prompt_and_passes_empty_replacements(window, monkeypatch):
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
    assert captured["kwargs"]["replacements"] == {}


# -- End-to-end: reproduces the exact PHOTOS nesting bug with local dirs -----


def test_copying_a_folder_onto_an_existing_one_replaces_instead_of_nesting(
    window, monkeypatch, tmp_path
):
    src_dir = tmp_path / "src"
    (src_dir / "PHOTOS").mkdir(parents=True)
    (src_dir / "PHOTOS" / "f1.txt").write_text("from source")
    (src_dir / "PHOTOS" / "f2.txt").write_text("from source")

    dst_dir = tmp_path / "dst"
    (dst_dir / "PHOTOS").mkdir(parents=True)
    (dst_dir / "PHOTOS" / "existing.txt").write_text("pre-existing local file")

    window.left_pane.set_backend(LocalBackend(), str(src_dir))
    window.right_pane.set_backend(LocalBackend(), str(dst_dir))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))

    entries = window.left_pane.entries_by_names(["PHOTOS"])
    window._transfer_entries(window.left_pane, window.right_pane, entries, move=False)

    # let the background QRunnable finish
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(500, loop.quit)
    loop.exec()

    result = {p.name for p in (dst_dir / "PHOTOS").iterdir()}
    # must be replaced (f1.txt, f2.txt only) - not nested (PHOTOS/PHOTOS/...)
    # and not merged with the stale existing.txt
    assert result == {"f1.txt", "f2.txt"}
    assert not (dst_dir / "PHOTOS" / "PHOTOS").exists()
