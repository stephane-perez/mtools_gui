from __future__ import annotations

from abc import ABC, abstractmethod

from ..entry import Entry


class Backend(ABC):
    """Common operations a pane needs, regardless of whether it's the local
    filesystem or a DOS partition reached through mtools."""

    @abstractmethod
    def list_dir(self, path: str) -> list[Entry]: ...

    @abstractmethod
    def mkdir(self, path: str, name: str) -> None: ...

    @abstractmethod
    def delete(self, path: str, name: str, is_dir: bool) -> None: ...

    @abstractmethod
    def rename(self, path: str, old_name: str, new_name: str) -> None: ...

    @abstractmethod
    def read_text(self, path: str, name: str) -> str: ...

    @abstractmethod
    def join(self, path: str, name: str) -> str: ...

    @abstractmethod
    def parent(self, path: str) -> str: ...
