"""Unprivileged-side client: builds `pkexec <helper> <op> <device> [args]`
calls and translates the helper's exit-code/stdout contract (see
system_files/mtools-gui-helper) into typed results/exceptions.
"""

from __future__ import annotations

import logging
import subprocess

from .constants import HELPER_INSTALL_PATH, INSTALL_HELPER_COMMAND
from .i18n import _
from .mdir_parser import parse_mdir_output
from .entry import Entry

logger = logging.getLogger(__name__)


class MtoolsClientError(Exception):
    """Base class for all errors raised by this module."""


class HelperNotInstalledError(MtoolsClientError):
    def __init__(self):
        super().__init__(_("err_helper_not_installed", command=INSTALL_HELPER_COMMAND))


class AuthDismissedError(MtoolsClientError):
    def __init__(self):
        super().__init__(_("err_auth_dismissed"))


class ValidationError(MtoolsClientError):
    pass


class MtoolsCommandError(MtoolsClientError):
    pass


def _run_helper(op: str, device: str, args: list[str]) -> str:
    argv = ["pkexec", HELPER_INSTALL_PATH, op, device, *args]
    logger.debug("Helper call: %s", " ".join(argv))
    try:
        proc = subprocess.run(argv, capture_output=True, text=True)
    except FileNotFoundError as exc:
        logger.error("pkexec not found")
        raise MtoolsClientError(_("err_pkexec_not_found")) from exc

    if proc.returncode == 0:
        if proc.stderr.strip():
            # mtools sometimes prints a non-fatal warning to stderr even
            # on success (e.g. a BPB geometry mismatch on some GEMDOS
            # media) - log it, don't treat it as a failure.
            logger.debug("%s (device=%s): mtools warning: %s", op, device, proc.stderr.strip())
        return proc.stdout

    logger.debug(
        "%s (device=%s) failed: code=%s stderr=%s", op, device, proc.returncode, proc.stderr.strip()
    )
    if proc.returncode == 126:
        raise AuthDismissedError()
    if proc.returncode == 127:
        raise HelperNotInstalledError()
    if proc.returncode == 2:
        raise ValidationError(proc.stderr.strip() or _("err_validation_default"))
    if proc.returncode == 3:
        raise MtoolsClientError(proc.stderr.strip() or _("err_usage_default"))
    raise MtoolsCommandError(proc.stderr.strip() or _("err_command_default", op=op))


def list_dir(device: str, dos_path: str) -> list[Entry]:
    output = _run_helper("mdir", device, [dos_path])
    return parse_mdir_output(output)


def copy_unix_to_dos(device: str, unix_path: str, dos_path: str) -> None:
    _run_helper("mcopy", device, [unix_path, dos_path])


def copy_dos_to_unix(device: str, dos_path: str, unix_path: str) -> None:
    _run_helper("mcopy", device, [dos_path, unix_path])


def delete(device: str, dos_path: str) -> None:
    _run_helper("mdel", device, [dos_path])


def delete_recursive(device: str, dos_path: str) -> None:
    _run_helper("mdeltree", device, [dos_path])


def mkdir(device: str, dos_path: str) -> None:
    _run_helper("mmd", device, [dos_path])


def rmdir(device: str, dos_path: str) -> None:
    _run_helper("mrd", device, [dos_path])


def rename(device: str, old_dos_path: str, new_dos_path: str) -> None:
    _run_helper("mren", device, [old_dos_path, new_dos_path])


def move(device: str, src_dos_path: str, dst_dos_path: str) -> None:
    _run_helper("mmove", device, [src_dos_path, dst_dos_path])


def copy_within_dos(device: str, src_dos_path: str, dst_dos_path: str) -> None:
    _run_helper("mcopy", device, [src_dos_path, dst_dos_path])


def read_text(device: str, dos_path: str) -> str:
    return _run_helper("mtype", device, [dos_path])
