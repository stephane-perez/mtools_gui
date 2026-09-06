"""Two operations targeting the same DOS device must never run
concurrently (mtools/FAT was never designed for concurrent writers to
the same volume) - a fast double-submit (multi-select copy, or a delete
landing while a copy is still running) used to be able to do exactly
that. Local<->Local operations are deliberately NOT serialized against
each other (see TransferService._with_device_lock's docstring) - only
real threads and a synthetic DosBackend-like object are used here, no
real mtools call or SD card involved.
"""

import threading
import time
from datetime import datetime
from types import SimpleNamespace

from mtools_gui.backends.dos_backend import DosBackend
from mtools_gui.transfer_service import TransferService


def _make_service():
    # Real QObject construction needs a QApplication in some PySide6
    # setups for signal machinery - side-step that entirely here since
    # this test only exercises the plain-Python locking helpers, not Qt
    # signal emission.
    return TransferService.__new__(TransferService)


def _dos_backend(device: str) -> DosBackend:
    return DosBackend(device)


def test_two_operations_on_the_same_device_never_overlap():
    service = _make_service()
    service._device_locks = {}
    service._device_locks_guard = threading.Lock()

    backend = _dos_backend("/dev/sde1")
    concurrent_count = 0
    max_concurrent = 0
    lock = threading.Lock()

    def slow_op():
        nonlocal concurrent_count, max_concurrent
        with lock:
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
        time.sleep(0.05)
        with lock:
            concurrent_count -= 1

    wrapped = service._with_device_lock(slow_op, backend)
    threads = [threading.Thread(target=wrapped) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert max_concurrent == 1


def test_operations_on_different_devices_run_concurrently():
    service = _make_service()
    service._device_locks = {}
    service._device_locks_guard = threading.Lock()

    concurrent_count = 0
    max_concurrent = 0
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    def slow_op():
        nonlocal concurrent_count, max_concurrent
        barrier.wait(timeout=2)  # force both to be mid-flight at once
        with lock:
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
        time.sleep(0.05)
        with lock:
            concurrent_count -= 1

    wrapped_a = service._with_device_lock(slow_op, _dos_backend("/dev/sde1"))
    wrapped_b = service._with_device_lock(slow_op, _dos_backend("/dev/sdf1"))
    t_a = threading.Thread(target=wrapped_a)
    t_b = threading.Thread(target=wrapped_b)
    t_a.start()
    t_b.start()
    t_a.join()
    t_b.join()

    assert max_concurrent == 2


def test_local_backend_is_not_serialized():
    service = _make_service()
    service._device_locks = {}
    service._device_locks_guard = threading.Lock()

    local_backend = SimpleNamespace()  # not a DosBackend instance
    wrapped = service._with_device_lock(lambda: None, local_backend)

    # No lock should even be created for a non-DosBackend.
    wrapped()
    assert service._device_locks == {}


def test_copy_between_two_different_dos_devices_locks_both():
    service = _make_service()
    service._device_locks = {}
    service._device_locks_guard = threading.Lock()

    src = _dos_backend("/dev/sdb1")
    dst = _dos_backend("/dev/sdc1")
    wrapped = service._with_device_lock(lambda: None, src, dst)
    wrapped()

    assert set(service._device_locks) == {"/dev/sdb1", "/dev/sdc1"}
