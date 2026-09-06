"""Runs copy/move (and other potentially slow) backend operations off the
UI thread, and dispatches to the right mechanism depending on which pair
of backends (local filesystem vs. DOS-via-mtools) is involved.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from .backends import Backend
from .backends.dos_backend import DosBackend
from .backends.local_backend import LocalBackend
from .entry import Entry
from .i18n import _
from .mtools_client import MtoolsClientError


class _WorkerSignals(QObject):
    succeeded = Signal()
    failed = Signal(str)


class _CallableTask(QRunnable):
    def __init__(self, func):
        super().__init__()
        self.func = func
        self.signals = _WorkerSignals()

    def run(self):
        try:
            self.func()
        except (MtoolsClientError, OSError) as exc:
            self.signals.failed.emit(str(exc))
        except Exception as exc:  # unexpected - still surface it, don't crash the UI
            self.signals.failed.emit(_("op_unexpected_error", error=exc))
        else:
            self.signals.succeeded.emit()


class TransferService(QObject):
    """Emits operation_succeeded/operation_failed; the GUI decides what to
    refresh from the `sides` hint it passed in when submitting."""

    operation_started = Signal(str)  # description
    operation_succeeded = Signal(str, str)  # description, sides ("left", "right" or "left,right")
    operation_failed = Signal(str, str)  # full_message, description

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        # PySide6/Shiboken gotcha: QThreadPool.start() hands the QRunnable's
        # C++ object to the pool, but nothing keeps the *Python* wrapper
        # alive while the worker thread runs it. If our own refcount on
        # `task` drops to zero (which it does almost immediately once
        # _submit() returns, since no other Python reference to it existed)
        # while the pool is still executing run() on a background thread,
        # the wrapper can be garbage-collected out from under Qt - this was
        # observed to segfault / corrupt the heap ("free(): invalid
        # pointer") specifically on slower operations (e.g. copying a
        # folder with many files), which give more time for the race to
        # hit. Keeping an explicit Python reference for the task's full
        # lifetime closes that race.
        self._active_tasks: list[_CallableTask] = []

    def _submit(self, description: str, sides: str, func) -> None:
        task = _CallableTask(func)
        task.setAutoDelete(False)
        self._active_tasks.append(task)

        def _release() -> None:
            if task in self._active_tasks:
                self._active_tasks.remove(task)

        def _on_succeeded() -> None:
            _release()
            self.operation_succeeded.emit(description, sides)

        def _on_failed(msg: str) -> None:
            _release()
            self.operation_failed.emit(
                _("op_failed_combined", description=description, msg=msg), description
            )

        task.signals.succeeded.connect(_on_succeeded)
        task.signals.failed.connect(_on_failed)
        self.operation_started.emit(description)
        self._pool.start(task)

    def copy(
        self,
        src_backend: Backend,
        src_side: str,
        src_dir: str,
        entry: Entry,
        dst_backend: Backend,
        dst_side: str,
        dst_dir: str,
        replace: Entry | None = None,
    ) -> None:
        description = _("op_copy", name=entry.name)
        sides = dst_side if src_side == dst_side else f"{src_side},{dst_side}"

        if isinstance(src_backend, LocalBackend) and isinstance(dst_backend, LocalBackend):
            import shutil

            src_path = src_backend.join(src_dir, entry.name)
            dst_path = dst_backend.join(dst_dir, entry.name)
            func = (
                (lambda: shutil.copytree(src_path, dst_path))
                if entry.is_dir
                else (lambda: shutil.copy2(src_path, dst_path))
            )
        elif isinstance(src_backend, DosBackend) and isinstance(dst_backend, DosBackend):
            func = lambda: src_backend.copy_within(src_dir, entry.name, dst_dir)
        elif isinstance(src_backend, LocalBackend) and isinstance(dst_backend, DosBackend):
            src_path = src_backend.join(src_dir, entry.name)
            func = lambda: dst_backend.copy_in(src_path, dst_dir, entry.name)
        elif isinstance(src_backend, DosBackend) and isinstance(dst_backend, LocalBackend):
            dst_path = dst_backend.join(dst_dir, entry.name)
            func = lambda: src_backend.copy_out(src_dir, entry.name, dst_path)
        else:
            raise TypeError(_("err_unknown_pane_combination"))

        func = self._with_replace(func, dst_backend, dst_dir, replace)
        self._submit(description, sides, func)

    def move(
        self,
        src_backend: Backend,
        src_side: str,
        src_dir: str,
        entry: Entry,
        dst_backend: Backend,
        dst_side: str,
        dst_dir: str,
        replace: Entry | None = None,
    ) -> None:
        description = _("op_move", name=entry.name)
        sides = dst_side if src_side == dst_side else f"{src_side},{dst_side}"

        if isinstance(src_backend, LocalBackend) and isinstance(dst_backend, LocalBackend):
            import shutil

            src_path = src_backend.join(src_dir, entry.name)
            dst_path = dst_backend.join(dst_dir, entry.name)
            func = lambda: shutil.move(src_path, dst_path)
        elif isinstance(src_backend, DosBackend) and isinstance(dst_backend, DosBackend):
            func = lambda: src_backend.move_within(src_dir, entry.name, dst_dir)
        else:
            # Moving across the Linux/DOS boundary: mmove can't cross it
            # (see man mmove), so this is copy-then-delete-source.
            def func():
                self._blocking_copy(
                    src_backend, src_dir, entry, dst_backend, dst_dir
                )
                src_backend.delete(src_dir, entry.name, entry.is_dir)

        func = self._with_replace(func, dst_backend, dst_dir, replace)
        self._submit(description, sides, func)

    @staticmethod
    def _with_replace(func, dst_backend: Backend, dst_dir: str, replace: Entry | None):
        """Wrap func so an existing same-named destination entry is
        deleted first. mcopy/mmove (and shutil.copytree without
        dirs_exist_ok) treat an *existing* destination directory as "copy
        source inside it" rather than "replace it" - e.g. copying a
        folder ANKHA onto an already-present ANKHA silently produced
        ANKHA/ANKHA/* nested alongside ANKHA's old contents instead of
        replacing them. Deleting the destination first guarantees a
        clean copy/move regardless of backend."""
        if replace is None:
            return func

        def wrapped():
            dst_backend.delete(dst_dir, replace.name, replace.is_dir)
            func()

        return wrapped

    def delete(self, backend: Backend, side: str, directory: str, entry: Entry) -> None:
        self._submit(
            _("op_delete", name=entry.name),
            side,
            lambda: backend.delete(directory, entry.name, entry.is_dir),
        )

    def mkdir(self, backend: Backend, side: str, directory: str, name: str) -> None:
        self._submit(_("op_mkdir", name=name), side, lambda: backend.mkdir(directory, name))

    def rename(self, backend: Backend, side: str, directory: str, old_name: str, new_name: str) -> None:
        self._submit(
            _("op_rename", name=old_name),
            side,
            lambda: backend.rename(directory, old_name, new_name),
        )

    @staticmethod
    def _blocking_copy(
        src_backend: Backend,
        src_dir: str,
        entry: Entry,
        dst_backend: Backend,
        dst_dir: str,
    ) -> None:
        """Used internally for the copy step of a cross-boundary move -
        runs synchronously since it's already inside a worker thread."""
        if isinstance(src_backend, LocalBackend) and isinstance(dst_backend, DosBackend):
            src_path = src_backend.join(src_dir, entry.name)
            dst_backend.copy_in(src_path, dst_dir, entry.name)
        elif isinstance(src_backend, DosBackend) and isinstance(dst_backend, LocalBackend):
            dst_path = dst_backend.join(dst_dir, entry.name)
            src_backend.copy_out(src_dir, entry.name, dst_path)
        else:
            raise TypeError(_("err_unknown_pane_combination_move"))
