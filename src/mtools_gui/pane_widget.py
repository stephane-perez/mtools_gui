from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .backends import Backend
from .constants import DND_MIME_TYPE
from .entry import Entry
from .entry_model import PaneTableModel, decode_dnd_payload
from .i18n import _

logger = logging.getLogger(__name__)

ROOT_PATHS = {"", "/"}

NAME_COLUMN = 0
SIZE_COLUMN = 1
MODIFIED_COLUMN = 2
# Never let the Name column crowd out Size/Modified entirely, even with
# a very long filename.
MAX_NAME_COLUMN_FRACTION = 0.75
NAME_COLUMN_PADDING = 24
MIN_NAME_COLUMN_WIDTH = 60
SIZE_COLUMN_PADDING = 16


class _DragDropTableView(QTableView):
    """QTableView with internal drag-to-copy support: dragging the current
    selection out and dropping it onto the *other* pane's view triggers
    entries_dropped(source_side, entry_names, move). Drops that don't
    carry our own DND_MIME_TYPE (e.g. from outside the app) are ignored -
    dragging external files in isn't handled yet.

    Holding ALTERNATE (Alt) while dropping moves instead of copies -
    same modifier TeraDesk/the Atari GEM desktop uses for the same
    purpose, so this matches muscle memory from that world.
    """

    entries_dropped = Signal(str, list, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.CopyAction)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(DND_MIME_TYPE):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(DND_MIME_TYPE):
            action = Qt.MoveAction if event.keyboardModifiers() & Qt.AltModifier else Qt.CopyAction
            event.setDropAction(action)
            event.accept()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        mime = event.mimeData()
        if not mime.hasFormat(DND_MIME_TYPE):
            super().dropEvent(event)
            return
        side, names = decode_dnd_payload(mime.data(DND_MIME_TYPE))
        move = bool(event.keyboardModifiers() & Qt.AltModifier)
        if names:
            self.entries_dropped.emit(side, names, move)
        event.setDropAction(Qt.MoveAction if move else Qt.CopyAction)
        event.accept()


class PaneWidget(QWidget):
    """One Commander-style pane: a path bar, an Up button and a table of
    entries. Backend-agnostic - works the same for the local pane and the
    DOS pane, they just carry a different Backend implementation.
    """

    path_changed = Signal(str)
    error = Signal(str)
    activated_file = Signal(Entry)  # double-click on a non-directory entry
    focused = Signal()

    def __init__(self, side: str, parent=None):
        super().__init__(parent)
        self.side = side
        self.backend: Backend | None = None
        self.current_path = ""

        self._name_column_content_width = MIN_NAME_COLUMN_WIDTH
        self._size_column_width = MIN_NAME_COLUMN_WIDTH
        self._modified_column_min_width = MIN_NAME_COLUMN_WIDTH

        self.model = PaneTableModel(self)
        self.model.side = side
        self.view = _DragDropTableView(self)
        self.view.setModel(self.model)
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # All three columns are sized explicitly on every refresh/resize
        # (see _apply_name_column_width) rather than relying on
        # setStretchLastSection - Qt enforces its own minimum on a
        # stretched last section (its defaultSectionSize, 100px) that
        # doesn't line up with what we reserve for Modified here, which
        # was overflowing the viewport and popping a horizontal scrollbar.
        self.view.horizontalHeader().setSortIndicatorShown(True)
        self.view.horizontalHeader().setSortIndicator(self.model.sort_column, self.model.sort_order)
        self.view.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self.view.doubleClicked.connect(self._on_double_clicked)
        self.view.installEventFilter(self)
        self.view.viewport().installEventFilter(self)

        self.path_label = QLineEdit(self)
        self.path_label.setReadOnly(True)
        self.up_button = QPushButton(_("pane_up_button"), self)
        self.up_button.clicked.connect(self.go_up)

        path_row = QHBoxLayout()
        path_row.addWidget(self.up_button)
        path_row.addWidget(self.path_label)

        layout = QVBoxLayout(self)
        layout.addLayout(path_row)
        layout.addWidget(self.view)
        self.setLayout(layout)

        self._set_enabled(False)

    def set_backend(self, backend: Backend | None, initial_path: str = "") -> None:
        self.backend = backend
        self.current_path = initial_path
        self._set_enabled(backend is not None)
        if backend is not None:
            self.refresh()
        else:
            self.model.set_entries([])
            self.path_label.setText("")
            # Even with nothing to show, Size/Modified still need at
            # least their header-text width reserved - otherwise Name
            # (falling back to Qt's stale/default widths for the other
            # two) can claim more than it should, and a real backend
            # attached later starts from a wrong layout.
            self._update_name_column_width()

    def _set_enabled(self, enabled: bool) -> None:
        self.view.setEnabled(enabled)
        self.up_button.setEnabled(enabled)

    def refresh(self) -> None:
        if self.backend is None:
            return
        logger.debug("[%s] listing %s", self.side, self.current_path or "/")
        try:
            entries = self.backend.list_dir(self.current_path)
        except Exception as exc:  # surfaced to the status bar, pane stays as-is
            logger.error("[%s] failed to list %s: %s", self.side, self.current_path or "/", exc)
            self.error.emit(str(exc))
            return
        logger.debug("[%s] found %d entries in %s", self.side, len(entries), self.current_path or "/")
        self.model.set_entries(entries)
        self._update_name_column_width()
        self.path_label.setText(self.current_path or "/")
        self.path_changed.emit(self.current_path)

    def _update_name_column_width(self) -> None:
        # Size and Modified each get a compact, content-sized minimum
        # (numbers/units and dates are naturally short); Name gets
        # whatever's left (see _apply_name_column_width). All three are
        # set explicitly - relying on Qt's setStretchLastSection for
        # Modified turned out to enforce its own ~100px minimum
        # (defaultSectionSize) regardless of what we'd reserved for it,
        # which silently overflowed the viewport and popped a horizontal
        # scrollbar.
        fm = self.view.fontMetrics()
        name_width = MIN_NAME_COLUMN_WIDTH
        size_width = fm.horizontalAdvance(self.model.headerData(SIZE_COLUMN, Qt.Horizontal)) + SIZE_COLUMN_PADDING
        modified_width = (
            fm.horizontalAdvance(self.model.headerData(MODIFIED_COLUMN, Qt.Horizontal)) + SIZE_COLUMN_PADDING
        )
        for row in range(self.model.rowCount()):
            entry = self.model.entry_at(row)
            if entry is None:
                continue
            text = f"[{entry.name}]" if entry.is_dir else entry.name
            name_width = max(name_width, fm.horizontalAdvance(text) + NAME_COLUMN_PADDING)
            size_text = self.model.data(self.model.index(row, SIZE_COLUMN)) or ""
            size_width = max(size_width, fm.horizontalAdvance(size_text) + SIZE_COLUMN_PADDING)
            modified_text = self.model.data(self.model.index(row, MODIFIED_COLUMN)) or ""
            modified_width = max(modified_width, fm.horizontalAdvance(modified_text) + SIZE_COLUMN_PADDING)
        self._name_column_content_width = name_width
        self._size_column_width = size_width
        self._modified_column_min_width = modified_width
        self._apply_name_column_width()
        # If this changes the row count enough to show/hide a vertical
        # scrollbar, the viewport resizes on its own right after this -
        # the viewport-resize event filter below catches that and
        # reapplies with the now-correct width, so no extra handling is
        # needed here even though the viewport isn't always at its final
        # size yet at this exact point (e.g. called from __init__ before
        # the window is ever shown).

    def _apply_name_column_width(self) -> None:
        viewport_width = self.view.viewport().width()
        if viewport_width <= 0:
            self.view.setColumnWidth(NAME_COLUMN, max(self._name_column_content_width, MIN_NAME_COLUMN_WIDTH))
            self.view.setColumnWidth(SIZE_COLUMN, self._size_column_width)
            self.view.setColumnWidth(MODIFIED_COLUMN, self._modified_column_min_width)
            return
        # Name claims whatever's left after Size and Modified's reserved
        # minimum - it does NOT also grow to fit its own longest-name
        # content beyond that (Qt already elides overflowing text with
        # "..." in a cell that's narrower than its content, same as any
        # other column). Letting content width push Name past the fair
        # share computed here is exactly what caused a several-pixel
        # overflow - and therefore a horizontal scrollbar - even though
        # every column already had a reasonable size: avoiding a
        # scrollbar takes priority over never eliding a long name.
        size_width = self._size_column_width
        available_for_name = viewport_width - size_width - self._modified_column_min_width
        name_width = min(available_for_name, int(viewport_width * MAX_NAME_COLUMN_FRACTION))
        name_width = max(name_width, MIN_NAME_COLUMN_WIDTH)
        # Whatever's left after Name and Size goes to Modified, so the
        # three columns exactly fill the viewport - no gap, no overflow,
        # no scrollbar, except in the genuinely-unavoidable case of a
        # viewport too narrow to fit even the minimums.
        modified_width = max(self._modified_column_min_width, viewport_width - name_width - size_width)
        self.view.setColumnWidth(NAME_COLUMN, name_width)
        self.view.setColumnWidth(SIZE_COLUMN, size_width)
        self.view.setColumnWidth(MODIFIED_COLUMN, modified_width)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Immediate best-effort pass for a snappy resize; the viewport's
        # own Resize event (caught in eventFilter) fires right after with
        # the now-settled width and corrects anything this pass got wrong.
        self._apply_name_column_width()

    def go_up(self) -> None:
        if self.backend is None or self.current_path in ROOT_PATHS:
            return
        self.current_path = self.backend.parent(self.current_path)
        self.refresh()

    def navigate_into(self, name: str) -> None:
        if self.backend is None:
            return
        self.current_path = self.backend.join(self.current_path, name)
        self.refresh()

    def _on_header_clicked(self, column: int) -> None:
        if self.model.sort_column == column:
            order = (
                Qt.DescendingOrder
                if self.model.sort_order == Qt.AscendingOrder
                else Qt.AscendingOrder
            )
        else:
            order = Qt.AscendingOrder
        self.model.set_sort(column, order)
        self.view.horizontalHeader().setSortIndicator(column, order)

    def selected_entries(self) -> list[Entry]:
        rows = {index.row() for index in self.view.selectionModel().selectedRows()}
        entries = [self.model.entry_at(row) for row in sorted(rows)]
        return [e for e in entries if e is not None]

    def entries_by_names(self, names: list[str]) -> list[Entry]:
        by_name = {e.name: e for e in (self.model.entry_at(r) for r in range(self.model.rowCount())) if e}
        return [by_name[name] for name in names if name in by_name]

    def eventFilter(self, obj, event) -> bool:
        if obj is self.view and event.type() == QEvent.FocusIn:
            self.focused.emit()
        elif obj is self.view.viewport() and event.type() == QEvent.Resize:
            # The authoritative signal that the viewport's width has
            # actually changed - unlike PaneWidget's own resizeEvent or a
            # fixed-delay timer, this can't fire with a stale size (a
            # vertical scrollbar appearing/disappearing after a
            # navigation, for instance, resizes the viewport on its own
            # schedule, independent of the outer widget).
            self._apply_name_column_width()
        return super().eventFilter(obj, event)

    def _on_double_clicked(self, index) -> None:
        entry = self.model.entry_at(index.row())
        if entry is None:
            return
        if entry.is_dir:
            self.navigate_into(entry.name)
        else:
            self.activated_file.emit(entry)
