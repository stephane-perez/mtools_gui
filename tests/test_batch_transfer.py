"""A multi-select copy/move/delete used to submit one operation per entry,
each paying the full cost of a fresh pkexec+polkit round-trip, a new helper
Python interpreter, a fresh lsblk device re-validation and mtools re-parsing
the FAT tables from scratch - roughly a second of overhead per file, however
small the file. mcopy/mmove/mdel/mdeltree all natively accept a whole list of
source files in a single invocation, so TransferService now batches an
entire selection into one backend call instead of one per entry.

These tests verify the batching itself - that exactly one call reaches the
(mocked) backend regardless of how many entries were selected - not the
underlying mtools plumbing, which test_helper_validation.py and
test_timeout_handling.py already cover. No real SD card or subprocess call
involved: DosBackend's own batch methods are monkeypatched out.
"""

import os
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from mtools_gui.backends.dos_backend import DosBackend
from mtools_gui.backends.local_backend import LocalBackend
from mtools_gui.entry import Entry
from mtools_gui.transfer_service import TransferService


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _entry(name, is_dir=False):
    return Entry(name=name, is_dir=is_dir, size=0, modified=datetime(2024, 1, 1))


def _run_and_wait(service, method_name, *args, **kwargs):
    getattr(service, method_name)(*args, **kwargs)
    loop = QEventLoop()
    QTimer.singleShot(300, loop.quit)
    loop.exec()


def test_copy_within_dos_batches_multiple_entries_into_one_call(monkeypatch):
    service = TransferService()
    backend = DosBackend("/dev/sde1")
    calls = []
    monkeypatch.setattr(
        backend, "copy_within_many", lambda names, src, dst: calls.append((names, src, dst))
    )

    entries = [_entry("A.DIG"), _entry("B.DIG"), _entry("C.DIG")]
    _run_and_wait(service, "copy", backend, "left", "/SRC", entries, backend, "left", "/DST")

    assert calls == [(["A.DIG", "B.DIG", "C.DIG"], "/SRC", "/DST")]


def test_copy_local_to_dos_batches_into_one_mcopy_call(monkeypatch):
    service = TransferService()
    dos = DosBackend("/dev/sde1")
    local = LocalBackend()
    calls = []
    monkeypatch.setattr(
        dos, "copy_in_many", lambda paths, dst_dir: calls.append((paths, dst_dir))
    )

    entries = [_entry("a.txt"), _entry("b.txt")]
    _run_and_wait(service, "copy", local, "left", "/home/user/src", entries, dos, "right", "/DST")

    assert calls == [(["/home/user/src/a.txt", "/home/user/src/b.txt"], "/DST")]


def test_copy_dos_to_local_batches_into_one_mcopy_call(monkeypatch):
    service = TransferService()
    dos = DosBackend("/dev/sde1")
    local = LocalBackend()
    calls = []
    monkeypatch.setattr(
        dos, "copy_out_many", lambda src_dir, names, dst: calls.append((src_dir, names, dst))
    )

    entries = [_entry("a.txt"), _entry("b.txt")]
    _run_and_wait(service, "copy", dos, "left", "/SRC", entries, local, "right", "/home/user/dst")

    assert calls == [("/SRC", ["a.txt", "b.txt"], "/home/user/dst")]


def test_delete_on_dos_backend_batches_every_entry_into_one_call(monkeypatch):
    service = TransferService()
    dos = DosBackend("/dev/sde1")
    calls = []
    monkeypatch.setattr(
        dos, "delete_many", lambda directory, entries: calls.append((directory, list(entries)))
    )

    entries = [_entry("A.DIG"), _entry("B.DIG"), _entry("SUBDIR", is_dir=True)]
    _run_and_wait(service, "delete", dos, "left", "/DIR", entries)

    assert len(calls) == 1
    directory, passed_entries = calls[0]
    assert directory == "/DIR"
    assert {e.name for e in passed_entries} == {"A.DIG", "B.DIG", "SUBDIR"}


def test_move_across_boundary_batches_both_the_copy_and_the_source_delete(monkeypatch):
    service = TransferService()
    dos = DosBackend("/dev/sde1")
    local = LocalBackend()

    copy_calls = []
    delete_calls = []
    monkeypatch.setattr(
        dos, "copy_out_many", lambda src_dir, names, dst: copy_calls.append((src_dir, names, dst))
    )
    monkeypatch.setattr(
        dos, "delete_many", lambda directory, entries: delete_calls.append((directory, list(entries)))
    )

    entries = [_entry("a.txt"), _entry("b.txt")]
    _run_and_wait(service, "move", dos, "left", "/SRC", entries, local, "right", "/home/user/dst")

    assert copy_calls == [("/SRC", ["a.txt", "b.txt"], "/home/user/dst")]
    assert len(delete_calls) == 1
    assert delete_calls[0][0] == "/SRC"
    assert {e.name for e in delete_calls[0][1]} == {"a.txt", "b.txt"}


def test_move_within_dos_batches_multiple_entries_into_one_mmove_call(monkeypatch):
    service = TransferService()
    backend = DosBackend("/dev/sde1")
    calls = []
    monkeypatch.setattr(
        backend, "move_within_many", lambda names, src, dst: calls.append((names, src, dst))
    )

    entries = [_entry("A.DIG"), _entry("B.DIG")]
    _run_and_wait(service, "move", backend, "left", "/SRC", entries, backend, "left", "/DST")

    assert calls == [(["A.DIG", "B.DIG"], "/SRC", "/DST")]


def test_single_entry_description_still_names_the_file(monkeypatch, qapp):
    service = TransferService()
    dos = DosBackend("/dev/sde1")
    monkeypatch.setattr(dos, "copy_within_many", lambda *a, **k: None)

    seen = []
    service.operation_started.connect(seen.append)
    _run_and_wait(service, "copy", dos, "left", "/SRC", [_entry("A.DIG")], dos, "left", "/DST")

    assert seen == ["Copier A.DIG"] or seen == ["Copy A.DIG"]


def test_many_entries_description_reports_a_count(monkeypatch, qapp):
    service = TransferService()
    dos = DosBackend("/dev/sde1")
    monkeypatch.setattr(dos, "copy_within_many", lambda *a, **k: None)

    seen = []
    service.operation_started.connect(seen.append)
    entries = [_entry(f"F{i}.DIG") for i in range(5)]
    _run_and_wait(service, "copy", dos, "left", "/SRC", entries, dos, "left", "/DST")

    assert seen and "5" in seen[0]
