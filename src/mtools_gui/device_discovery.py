"""Discovery of removable partitions that might be DOS-formatted (an SD
card, a USB drive, ...), so the user never has to type a raw device
path. Read-only, no root required: lsblk enumeration alone doesn't
touch the device.

Deliberately does NOT require lsblk to have already recognized the
filesystem as FAT: a non-standard DOS variant (e.g. GEMDOS on Atari
machines) typically shows up with an empty/unrecognized fstype in lsblk
even though mtools reads it fine (mtools parses the FAT structures
itself, bypassing the kernel's own detection - see NON_DOS_FSTYPES).
Requiring a kernel-recognized FAT fstype would only ever surface
partitions the desktop file manager could already mount directly,
defeating the point of this tool.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass

from .constants import NON_DOS_FSTYPES
from .i18n import _

logger = logging.getLogger(__name__)

LSBLK_COLUMNS = "NAME,PATH,FSTYPE,SIZE,RM,MOUNTPOINT,LABEL,TYPE,HOTPLUG"


@dataclass(frozen=True)
class DriveCandidate:
    path: str
    label: str
    size: str
    fstype: str
    mountpoint: str | None

    def display_name(self) -> str:
        label = self.label or _("drive_no_label")
        fstype = self.fstype or _("drive_unknown_fstype")
        return f"{self.path} - {label} - {self.size} ({fstype})"


def discover() -> list[DriveCandidate]:
    """Run lsblk and return removable, potentially-DOS partitions found on
    this system."""
    try:
        proc = subprocess.run(
            ["lsblk", "-J", "-o", LSBLK_COLUMNS],
            capture_output=True,
            text=True,
            check=True,
            env={"LC_ALL": "C", "PATH": "/usr/bin:/bin"},
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        logger.error("lsblk failed: %s", exc)
        return []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        logger.error("Unreadable lsblk output: %s", exc)
        return []
    candidates = filter_candidates(data)
    logger.debug("Candidates found: %s", [c.path for c in candidates])
    return candidates


def filter_candidates(lsblk_json: dict) -> list[DriveCandidate]:
    """Pure filtering logic, kept separate from the lsblk call so it can be
    unit-tested with captured/synthetic JSON."""
    candidates: list[DriveCandidate] = []
    for device in _iter_devices(lsblk_json.get("blockdevices", [])):
        if device.get("type") != "part":
            continue
        fstype = (device.get("fstype") or "").lower()
        if fstype in NON_DOS_FSTYPES:
            continue
        removable = device.get("rm")
        hotplug = device.get("hotplug")
        if not (removable is True or hotplug is True):
            continue
        path = device.get("path")
        if not path:
            continue
        candidates.append(
            DriveCandidate(
                path=path,
                label=device.get("label") or "",
                size=device.get("size") or "",
                fstype=fstype,
                mountpoint=device.get("mountpoint") or None,
            )
        )
    return candidates


def _iter_devices(devices: list[dict]):
    for device in devices:
        yield device
        children = device.get("children") or []
        yield from _iter_devices(children)
