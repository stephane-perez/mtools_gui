"""mtools_client's batch functions build the pkexec/helper argv for a whole
file list in one call - see transfer_service and dos_backend for why this
matters (avoids one pkexec+helper+mtools round-trip per file). subprocess.run
is mocked throughout; no real device involved.
"""

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from mtools_gui import mtools_client
from mtools_gui.backends.dos_backend import DosBackend


def _capture_argv(monkeypatch):
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(mtools_client.subprocess, "run", fake_run)
    return captured


def test_copy_many_unix_to_dos_lists_every_source_before_the_target_dir(monkeypatch):
    captured = _capture_argv(monkeypatch)
    mtools_client.copy_many_unix_to_dos("/dev/sde1", ["/a.txt", "/b.txt"], "::/DEST")
    assert captured["argv"][-3:] == ["/a.txt", "/b.txt", "::/DEST"]


def test_copy_many_dos_to_unix_lists_every_source_before_the_target_dir(monkeypatch):
    captured = _capture_argv(monkeypatch)
    mtools_client.copy_many_dos_to_unix("/dev/sde1", ["::/a.txt", "::/b.txt"], "/home/user/dst")
    assert captured["argv"][-3:] == ["::/a.txt", "::/b.txt", "/home/user/dst"]


def test_delete_many_passes_every_path_in_one_call(monkeypatch):
    captured = _capture_argv(monkeypatch)
    mtools_client.delete_many("/dev/sde1", ["::/a.txt", "::/b.txt", "::/c.txt"])
    assert captured["argv"][-3:] == ["::/a.txt", "::/b.txt", "::/c.txt"]


def test_delete_recursive_many_passes_every_path_in_one_call(monkeypatch):
    captured = _capture_argv(monkeypatch)
    mtools_client.delete_recursive_many("/dev/sde1", ["::/DIR1", "::/DIR2"])
    assert captured["argv"][-2:] == ["::/DIR1", "::/DIR2"]


def test_move_within_dos_many_lists_every_source_before_the_target_dir(monkeypatch):
    captured = _capture_argv(monkeypatch)
    mtools_client.move_within_dos_many("/dev/sde1", ["::/a.txt", "::/b.txt"], "::/DEST")
    assert captured["argv"][-3:] == ["::/a.txt", "::/b.txt", "::/DEST"]


# -- DosBackend.delete_many: files and directories need different binaries --


def test_delete_many_splits_files_and_directories_into_separate_calls(monkeypatch):
    from mtools_gui.entry import Entry
    from datetime import datetime

    def _entry(name, is_dir):
        return Entry(name=name, is_dir=is_dir, size=0, modified=datetime(2024, 1, 1))

    backend = DosBackend("/dev/sde1")
    file_calls = []
    dir_calls = []
    monkeypatch.setattr(
        mtools_client, "delete_many", lambda device, paths: file_calls.append(paths)
    )
    monkeypatch.setattr(
        mtools_client, "delete_recursive_many", lambda device, paths: dir_calls.append(paths)
    )

    entries = [_entry("A.DIG", False), _entry("B.DIG", False), _entry("SUBDIR", True)]
    backend.delete_many("/DIR", entries)

    assert file_calls == [["::/DIR/A.DIG", "::/DIR/B.DIG"]]
    assert dir_calls == [["::/DIR/SUBDIR"]]


def test_delete_many_skips_the_mdel_call_when_only_directories_are_selected(monkeypatch):
    from mtools_gui.entry import Entry
    from datetime import datetime

    def _entry(name, is_dir):
        return Entry(name=name, is_dir=is_dir, size=0, modified=datetime(2024, 1, 1))

    backend = DosBackend("/dev/sde1")
    file_calls = []
    dir_calls = []
    monkeypatch.setattr(
        mtools_client, "delete_many", lambda device, paths: file_calls.append(paths)
    )
    monkeypatch.setattr(
        mtools_client, "delete_recursive_many", lambda device, paths: dir_calls.append(paths)
    )

    backend.delete_many("/DIR", [_entry("SUBDIR", True)])

    assert file_calls == []
    assert dir_calls == [["::/DIR/SUBDIR"]]
