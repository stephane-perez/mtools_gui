from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import PurePosixPath

from . import Backend
from ..entry import Entry


class LocalBackend(Backend):
    """Plain Linux filesystem access - no elevated privileges involved."""

    def list_dir(self, path: str) -> list[Entry]:
        entries = []
        with os.scandir(path) as it:
            for item in it:
                try:
                    stat = item.stat(follow_symlinks=True)
                except OSError:
                    continue
                entries.append(
                    Entry(
                        name=item.name,
                        is_dir=item.is_dir(follow_symlinks=True),
                        size=0 if item.is_dir(follow_symlinks=True) else stat.st_size,
                        modified=datetime.fromtimestamp(stat.st_mtime),
                    )
                )
        return entries

    def mkdir(self, path: str, name: str) -> None:
        os.mkdir(self.join(path, name))

    def delete(self, path: str, name: str, is_dir: bool) -> None:
        target = self.join(path, name)
        if is_dir:
            shutil.rmtree(target)
        else:
            os.remove(target)

    def rename(self, path: str, old_name: str, new_name: str) -> None:
        os.rename(self.join(path, old_name), self.join(path, new_name))

    def read_text(self, path: str, name: str) -> str:
        with open(self.join(path, name), "r", errors="replace") as f:
            return f.read()

    def join(self, path: str, name: str) -> str:
        return str(PurePosixPath(path) / name)

    def parent(self, path: str) -> str:
        parent = str(PurePosixPath(path).parent)
        return parent
