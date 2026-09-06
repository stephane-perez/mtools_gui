"""Parsing of ``mdir`` output. Pure functions, no subprocess/IO here so this
stays trivially testable without a real device.

Verified against real output captured from a GEMDOS (Atari) SD card - see
tests/fixtures/mdir_sample.txt. Two quirks that real capture revealed:

- Classic short (8.3) GEMDOS entries have no long filename, so mdir
  prints the base and extension as two whitespace-padded fields instead
  of "BASE.EXT" (e.g. ``XTCB     PRG``, not ``XTCB.PRG``). Since a short
  DOS name can never legally contain a space, any remaining internal
  whitespace in a captured name is unambiguously that base/extension
  gap, never part of the filename - see _normalize_short_name below. (A
  card with real VFAT long filenames containing spaces would need a
  different heuristic, but that doesn't arise for GEMDOS media.)
- A *directory* can have an 8.3 extension too (e.g. ``VDI_FX.68K``,
  seemingly an Atari convention for 68000-targeted content), which packs
  its column tighter and can leave only a single space before ``<DIR>``
  (``VDI_FX   68K <DIR>``). The entry regex originally required 2+
  spaces before the size/<DIR> field on the assumption columns were
  always generously padded - real data proved that wrong, so it now
  accepts a single space there too.
- A *VFAT long filename* (one that doesn't fit 8.3) is listed with an
  extra trailing column: the usual short-name/size/date/time fields,
  then 2+ spaces, then the real long name (e.g.
  ``VID_20~1 MP4  192031009 2026-09-06  22:43  VID_20200713_220831.mp4``).
  Entries like this used to be silently dropped: the old regex was
  anchored to end right after the time field, so a line with anything
  after it simply never matched - the file existed on the card (mdir run
  directly proved it) but never appeared in the GUI. When present, that
  trailing long name is the real filename and takes priority over the
  truncated 8.3 alias.
"""

from __future__ import annotations

import re
from datetime import datetime

from .entry import Entry

_SKIP_PREFIXES = (
    "Volume in drive",
    "Volume Serial Number",
    "Directory for",
)

_ENTRY_RE = re.compile(
    r"^(?P<name>.+?)\s+(?P<meta><DIR>|[\d,]+)\s+"
    r"(?P<date>\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4})\s+"
    r"(?P<time>\d{1,2}:\d{2})"
    r"(?:\s{2,}(?P<longname>\S.*))?\s*$"
)

_SUMMARY_RE = re.compile(r"^\s*\d+\s+file\(s\)|^\s*\d+\s+bytes free\s*$")

_SHORT_NAME_RE = re.compile(r"^(\S{1,8})\s+(\S{1,3})$")


def _normalize_short_name(name: str) -> str:
    match = _SHORT_NAME_RE.match(name)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    return name


def parse_mdir_output(text: str) -> list[Entry]:
    entries: list[Entry] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(_SKIP_PREFIXES) or _SUMMARY_RE.match(stripped):
            continue
        match = _ENTRY_RE.match(stripped)
        if not match:
            continue
        longname = match.group("longname")
        name = longname.strip() if longname else _normalize_short_name(match.group("name").strip())
        if name in (".", ".."):
            continue
        is_dir = match.group("meta") == "<DIR>"
        size = 0 if is_dir else int(match.group("meta").replace(",", ""))
        modified = _parse_datetime(match.group("date"), match.group("time"))
        entries.append(Entry(name=name, is_dir=is_dir, size=size, modified=modified))
    return entries


def _parse_datetime(date_str: str, time_str: str) -> datetime | None:
    fmt = "%Y-%m-%d" if "-" in date_str and date_str.index("-") == 4 else "%m-%d-%Y"
    try:
        return datetime.strptime(f"{date_str} {time_str}", f"{fmt} %H:%M")
    except ValueError:
        return None
