"""Column sorting (PaneTableModel.set_sort / _resort) and the
click-on-header wiring in PaneWidget. Headless (offscreen) since it
needs a real QApplication for the model/view.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from mtools_gui.entry import Entry
from mtools_gui.entry_model import PaneTableModel
from mtools_gui.pane_widget import PaneWidget


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _entry(name, is_dir=False, size=0, modified=None):
    return Entry(name=name, is_dir=is_dir, size=size, modified=modified or datetime(2024, 1, 1))


def test_default_sort_is_name_ascending_dirs_first():
    model = PaneTableModel()
    model.set_entries(
        [
            _entry("banana.txt"),
            _entry("Zdir", is_dir=True),
            _entry("apple.txt"),
            _entry("Adir", is_dir=True),
        ]
    )
    names = [model.entry_at(r).name for r in range(model.rowCount())]
    # dirs first (alphabetical among themselves), then files (alphabetical)
    assert names == ["Adir", "Zdir", "apple.txt", "banana.txt"]


def test_sort_by_name_descending():
    model = PaneTableModel()
    model.set_entries([_entry("a.txt"), _entry("c.txt"), _entry("b.txt")])
    model.set_sort(0, Qt.DescendingOrder)
    names = [model.entry_at(r).name for r in range(model.rowCount())]
    assert names == ["c.txt", "b.txt", "a.txt"]


def test_sort_by_size_ascending_keeps_directories_grouped_by_name():
    model = PaneTableModel()
    model.set_entries(
        [
            _entry("big.txt", size=300),
            _entry("Zdir", is_dir=True),
            _entry("small.txt", size=10),
            _entry("Adir", is_dir=True),
        ]
    )
    model.set_sort(1, Qt.AscendingOrder)
    names = [model.entry_at(r).name for r in range(model.rowCount())]
    # directories always report size=0 (never computed) - falls back to
    # name among themselves rather than an arbitrary/stale order
    assert names == ["Adir", "Zdir", "small.txt", "big.txt"]


def test_sort_by_size_descending_does_not_reverse_directory_order():
    # Regression: toggling the Size column to descending must only
    # reverse the files - directories have no size, so flipping their
    # alphabetical order too ("Zdir" before "Adir") made no sense.
    model = PaneTableModel()
    model.set_entries(
        [
            _entry("big.txt", size=300),
            _entry("Zdir", is_dir=True),
            _entry("small.txt", size=10),
            _entry("Adir", is_dir=True),
        ]
    )
    model.set_sort(1, Qt.DescendingOrder)
    names = [model.entry_at(r).name for r in range(model.rowCount())]
    assert names == ["Adir", "Zdir", "big.txt", "small.txt"]


def test_sort_by_modified_date():
    model = PaneTableModel()
    old = datetime(2020, 1, 1)
    new = datetime(2024, 1, 1)
    model.set_entries([_entry("a.txt", modified=new), _entry("b.txt", modified=old)])
    model.set_sort(2, Qt.AscendingOrder)
    names = [model.entry_at(r).name for r in range(model.rowCount())]
    assert names == ["b.txt", "a.txt"]


def test_sort_persists_across_set_entries_calls():
    model = PaneTableModel()
    model.set_entries([_entry("a.txt"), _entry("b.txt")])
    model.set_sort(0, Qt.DescendingOrder)
    # simulate navigating to a different directory - refresh calls
    # set_entries() again, the sort choice must survive it
    model.set_entries([_entry("x.txt"), _entry("y.txt")])
    names = [model.entry_at(r).name for r in range(model.rowCount())]
    assert names == ["y.txt", "x.txt"]


def test_click_same_column_toggles_order():
    pane = PaneWidget("left")
    pane.model.set_entries([_entry("a.txt"), _entry("b.txt")])
    assert pane.model.sort_order == Qt.AscendingOrder

    pane.view.horizontalHeader().sectionClicked.emit(0)
    assert pane.model.sort_column == 0
    assert pane.model.sort_order == Qt.DescendingOrder

    pane.view.horizontalHeader().sectionClicked.emit(0)
    assert pane.model.sort_order == Qt.AscendingOrder


def test_click_different_column_resets_to_ascending():
    pane = PaneWidget("left")
    pane.model.set_entries([_entry("a.txt", size=5), _entry("b.txt", size=1)])

    pane.view.horizontalHeader().sectionClicked.emit(0)  # -> descending on name
    assert pane.model.sort_order == Qt.DescendingOrder

    pane.view.horizontalHeader().sectionClicked.emit(1)  # switch to size column
    assert pane.model.sort_column == 1
    assert pane.model.sort_order == Qt.AscendingOrder
