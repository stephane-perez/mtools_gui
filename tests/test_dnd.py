"""Drag-and-drop payload encode/decode, and the model/pane glue around it.
Runs headless (QT_QPA_PLATFORM=offscreen) since it needs a real QApplication
for QMimeData/PaneTableModel but no actual display.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime

import pytest
from PySide6.QtWidgets import QApplication

from mtools_gui.constants import DND_MIME_TYPE
from mtools_gui.entry import Entry
from mtools_gui.entry_model import PaneTableModel, decode_dnd_payload


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _entry(name, is_dir=False):
    return Entry(name=name, is_dir=is_dir, size=0, modified=datetime(2024, 1, 1))


def test_decode_dnd_payload_splits_side_and_names():
    payload = "left\nfoo.txt\nSUBDIR".encode("utf-8")
    side, names = decode_dnd_payload(payload)
    assert side == "left"
    assert names == ["foo.txt", "SUBDIR"]


def test_decode_dnd_payload_handles_no_names():
    side, names = decode_dnd_payload("right".encode("utf-8"))
    assert side == "right"
    assert names == []


def test_model_mime_data_encodes_side_and_selected_entries():
    model = PaneTableModel()
    model.side = "left"
    model.set_entries([_entry("b.txt"), _entry("a.txt"), _entry("SUBDIR", is_dir=True)])

    # after sorting: SUBDIR (dir first), a.txt, b.txt
    indexes = [model.index(0, 0), model.index(2, 0)]  # SUBDIR and b.txt
    mime = model.mimeData(indexes)

    assert mime.hasFormat(DND_MIME_TYPE)
    side, names = decode_dnd_payload(mime.data(DND_MIME_TYPE))
    assert side == "left"
    assert names == ["SUBDIR", "b.txt"]


def test_model_mime_types_advertises_custom_format():
    model = PaneTableModel()
    assert model.mimeTypes() == [DND_MIME_TYPE]


def test_pane_widget_resolves_dropped_names_to_entries():
    from mtools_gui.pane_widget import PaneWidget

    pane = PaneWidget("left")
    pane.model.set_entries([_entry("b.txt"), _entry("a.txt"), _entry("SUBDIR", is_dir=True)])

    entries = pane.entries_by_names(["SUBDIR", "b.txt"])

    assert [e.name for e in entries] == ["SUBDIR", "b.txt"]


def test_pane_widget_ignores_unknown_dropped_names():
    from mtools_gui.pane_widget import PaneWidget

    pane = PaneWidget("left")
    pane.model.set_entries([_entry("a.txt")])

    entries = pane.entries_by_names(["a.txt", "ghost.txt"])

    assert [e.name for e in entries] == ["a.txt"]
