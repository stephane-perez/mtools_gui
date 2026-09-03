"""The Entry dataclass lives on its own, separate from entry_model.py's
Qt-based PaneTableModel, so pure logic (mdir_parser, backends) never has
to pull in PySide6 just to describe a file/directory listing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Entry:
    """A single file or directory listed in a pane."""

    name: str
    is_dir: bool
    size: int  # bytes; 0 for directories
    modified: datetime | None
