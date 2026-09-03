from __future__ import annotations

from pathlib import PurePosixPath

from . import Backend
from .. import mtools_client
from ..entry import Entry

ROOT = "/"


class DosBackend(Backend):
    """DOS/FAT partition access through mtools, via the privileged helper.

    Paths are kept as posix-style strings relative to the DOS drive root
    (e.g. "/", "/SUBDIR"); they're translated to mtools' "::"-prefixed
    syntax only at the point of calling mtools_client.
    """

    def __init__(self, device: str):
        self.device = device

    def _dos_arg(self, path: str) -> str:
        return "::" if path in ("", ROOT) else f"::{path}"

    def list_dir(self, path: str) -> list[Entry]:
        return mtools_client.list_dir(self.device, self._dos_arg(path))

    def mkdir(self, path: str, name: str) -> None:
        mtools_client.mkdir(self.device, self._dos_arg(self.join(path, name)))

    def delete(self, path: str, name: str, is_dir: bool) -> None:
        target = self._dos_arg(self.join(path, name))
        if is_dir:
            mtools_client.delete_recursive(self.device, target)
        else:
            mtools_client.delete(self.device, target)

    def rename(self, path: str, old_name: str, new_name: str) -> None:
        mtools_client.rename(
            self.device,
            self._dos_arg(self.join(path, old_name)),
            self._dos_arg(self.join(path, new_name)),
        )

    def read_text(self, path: str, name: str) -> str:
        return mtools_client.read_text(self.device, self._dos_arg(self.join(path, name)))

    def join(self, path: str, name: str) -> str:
        return str(PurePosixPath(path or ROOT) / name)

    def parent(self, path: str) -> str:
        parent = str(PurePosixPath(path or ROOT).parent)
        return parent

    def copy_in(self, unix_source: str, dest_dir: str, dest_name: str) -> None:
        """Copy a file from the local filesystem onto the DOS partition."""
        mtools_client.copy_unix_to_dos(
            self.device, unix_source, self._dos_arg(self.join(dest_dir, dest_name))
        )

    def copy_out(self, source_dir: str, source_name: str, unix_dest: str) -> None:
        """Copy a file from the DOS partition to the local filesystem."""
        mtools_client.copy_dos_to_unix(
            self.device, self._dos_arg(self.join(source_dir, source_name)), unix_dest
        )

    def move_within(self, src_dir: str, name: str, dst_dir: str) -> None:
        mtools_client.move(
            self.device,
            self._dos_arg(self.join(src_dir, name)),
            self._dos_arg(self.join(dst_dir, name)),
        )

    def copy_within(self, src_dir: str, name: str, dst_dir: str) -> None:
        mtools_client.copy_within_dos(
            self.device,
            self._dos_arg(self.join(src_dir, name)),
            self._dos_arg(self.join(dst_dir, name)),
        )
