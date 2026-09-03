from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QAbstractTableModel, QMimeData, QModelIndex, Qt

from .constants import DND_MIME_TYPE
from .entry import Entry
from .i18n import _

COLUMNS = (_("column_name"), _("column_size"), _("column_modified"))

# One sort key function per column, applied within each is_dir group (see
# _resort). SIZE_COLUMN is special-cased there: every directory reports
# size=0 (we never compute a recursive folder size), so sorting
# directories by size would just leave them in whatever order they
# happened to be in before - falls back to name instead, same as Windows
# Explorer/GNOME Files do for the size column.
SIZE_COLUMN = 1
_SORT_KEYS = (
    lambda e: e.name.lower(),
    lambda e: e.size,
    lambda e: e.modified or datetime.min,
)


class PaneTableModel(QAbstractTableModel):
    """Table model shared by both panes; only the backing entries differ."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: list[Entry] = []
        # Set by PaneWidget right after construction ("left"/"right") -
        # embedded in drag payloads so a drop handler on the other pane
        # knows which pane the dragged entries came from.
        self.side = ""
        # Default: sort by name, ascending. Persists across refreshes and
        # navigation - set_entries() re-applies it every time.
        self.sort_column = 0
        self.sort_order = Qt.AscendingOrder

    def set_entries(self, entries: list[Entry]) -> None:
        self.beginResetModel()
        self._entries = list(entries)
        self._resort()
        self.endResetModel()

    def set_sort(self, column: int, order) -> None:
        self.sort_column = column
        self.sort_order = order
        self.layoutAboutToBeChanged.emit()
        self._resort()
        self.layoutChanged.emit()

    def _resort(self) -> None:
        column = self.sort_column if self.sort_column < len(_SORT_KEYS) else 0
        key_fn = _SORT_KEYS[column]
        name_fn = _SORT_KEYS[0]
        descending = self.sort_order == Qt.DescendingOrder

        # Sorted as two separate homogeneous-key lists rather than one
        # combined sort: the size column's key is an int for files but
        # falls back to a str (name) for directories, and Python can't
        # compare str to int - splitting first sidesteps that entirely,
        # on top of being what we want anyway (dirs always first).
        dirs = [e for e in self._entries if e.is_dir]
        files = [e for e in self._entries if not e.is_dir]
        if column == SIZE_COLUMN:
            # Size is meaningless for a directory (always 0, never
            # computed recursively) - always alphabetical, regardless of
            # the chosen order. Toggling asc/desc on the Size column must
            # only affect the files, not silently reverse the folders too.
            dirs.sort(key=name_fn)
        else:
            dirs.sort(key=key_fn, reverse=descending)
        files.sort(key=key_fn, reverse=descending)
        self._entries = dirs + files

    def entry_at(self, row: int) -> Entry | None:
        if 0 <= row < len(self._entries):
            return self._entries[row]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._entries)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMNS[section]
        return None

    def flags(self, index: QModelIndex):
        default = super().flags(index)
        return default | Qt.ItemIsDragEnabled if index.isValid() else default

    def mimeTypes(self) -> list[str]:
        return [DND_MIME_TYPE]

    def mimeData(self, indexes) -> QMimeData:
        rows = sorted({index.row() for index in indexes})
        names = [self._entries[row].name for row in rows if 0 <= row < len(self._entries)]
        mime = QMimeData()
        payload = "\n".join([self.side, *names])
        mime.setData(DND_MIME_TYPE, payload.encode("utf-8"))
        return mime

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        entry = self._entries[index.row()]
        column = index.column()
        if column == 0:
            return f"[{entry.name}]" if entry.is_dir else entry.name
        if column == 1:
            return "" if entry.is_dir else _format_size(entry.size)
        if column == 2:
            return entry.modified.strftime("%Y-%m-%d %H:%M") if entry.modified else ""
        return None


def decode_dnd_payload(data: bytes) -> tuple[str, list[str]]:
    """Pure inverse of PaneTableModel.mimeData's encoding - kept separate
    so the drop side's parsing is testable without a real drag event."""
    text = bytes(data).decode("utf-8")
    side, *names = text.split("\n")
    return side, names


def _format_size(size: int) -> str:
    units = (_("size_bytes"), _("size_kb"), _("size_mb"), _("size_gb"))
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.0f} {unit}" if unit == units[0] else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} {units[-1]}"
