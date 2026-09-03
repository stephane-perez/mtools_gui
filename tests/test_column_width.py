"""Auto-sizing of the Name column: it claims whatever space Modified
would otherwise stretch into (so Name - not Modified - is the widest
column, especially visible on a maximized window), capped at 75% of the
pane's width so Size/Modified never get crowded out entirely. Headless
(offscreen) - needs real widget geometry, so panes are resized
explicitly to a known size rather than relying on window manager layout.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime

import pytest
from PySide6.QtWidgets import QApplication

from mtools_gui.entry import Entry
from mtools_gui.pane_widget import MAX_NAME_COLUMN_FRACTION, NAME_COLUMN, SIZE_COLUMN, PaneWidget


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _entry(name, is_dir=False, size=0):
    return Entry(name=name, is_dir=is_dir, size=size, modified=datetime(2024, 1, 1))


def _make_pane(width=800):
    pane = PaneWidget("left")
    pane.resize(width, 400)
    pane.show()
    QApplication.processEvents()
    return pane


def test_content_width_grows_with_a_longer_filename():
    pane = _make_pane()
    pane.model.set_entries([_entry("a.txt")])
    pane._update_name_column_width()
    short_content_width = pane._name_column_content_width

    pane.model.set_entries([_entry("a_much_much_longer_filename_than_before.txt")])
    pane._update_name_column_width()
    long_content_width = pane._name_column_content_width

    assert long_content_width > short_content_width


def test_name_column_never_exceeds_75_percent_of_pane_width():
    pane = _make_pane(width=400)
    very_long_name = "x" * 300 + ".txt"
    pane.model.set_entries([_entry(very_long_name)])
    pane._update_name_column_width()

    viewport_width = pane.view.viewport().width()
    cap = int(viewport_width * MAX_NAME_COLUMN_FRACTION)
    assert pane.view.columnWidth(NAME_COLUMN) <= cap


def test_other_columns_stay_visible_even_with_a_very_long_name():
    pane = _make_pane(width=400)
    pane.model.set_entries([_entry("x" * 300 + ".txt")])
    pane._update_name_column_width()

    viewport_width = pane.view.viewport().width()
    # at least 25% of the viewport must remain for Size + Modified
    assert pane.view.columnWidth(NAME_COLUMN) <= viewport_width * MAX_NAME_COLUMN_FRACTION + 1


def test_name_column_is_the_widest_even_with_short_names_on_a_wide_window():
    # Regression: Modified used to absorb all leftover space via
    # stretchLastSection while Name only claimed its own content width,
    # so on a maximized window with short filenames Modified ended up
    # the widest column - Name must dominate instead.
    pane = _make_pane(width=1200)
    pane.model.set_entries([_entry("a.txt", size=100), _entry("b.txt", size=200)])
    pane._update_name_column_width()

    name_width = pane.view.columnWidth(NAME_COLUMN)
    size_width = pane.view.columnWidth(SIZE_COLUMN)
    modified_width = pane.view.viewport().width() - name_width - size_width  # stretched section

    assert name_width > size_width
    assert name_width > modified_width


def test_size_column_stays_compact():
    pane = _make_pane(width=1200)
    pane.model.set_entries([_entry("a.txt", size=123456), _entry("Adir", is_dir=True)])
    pane._update_name_column_width()

    viewport_width = pane.view.viewport().width()
    assert pane.view.columnWidth(SIZE_COLUMN) < viewport_width * 0.15


def test_resize_event_reapplies_the_cap():
    pane = _make_pane(width=800)
    pane.model.set_entries([_entry("x" * 300 + ".txt")])
    pane._update_name_column_width()
    wide_cap_width = pane.view.columnWidth(NAME_COLUMN)

    pane.resize(300, 400)
    QApplication.processEvents()

    viewport_width = pane.view.viewport().width()
    narrow_cap = int(viewport_width * MAX_NAME_COLUMN_FRACTION)
    assert pane.view.columnWidth(NAME_COLUMN) <= narrow_cap
    assert pane.view.columnWidth(NAME_COLUMN) < wide_cap_width
