"""tests/fixtures/mdir_sample.txt is REAL output captured with
`pkexec mtools-gui-helper mdir <device> ::/DEMOS` against an actual
GEMDOS (Atari) SD card partition - see the module docstring in
mdir_parser.py for the short-name (8.3) quirk this revealed and fixed.
"""

from pathlib import Path

from mtools_gui.mdir_parser import _normalize_short_name, parse_mdir_output

FIXTURE = Path(__file__).parent / "fixtures" / "mdir_sample.txt"
SINGLE_DIGIT_HOUR_FIXTURE = (
    Path(__file__).parent / "fixtures" / "mdir_sample_single_digit_hour.txt"
)
DIR_WITH_EXTENSION_FIXTURE = (
    Path(__file__).parent / "fixtures" / "mdir_sample_dir_with_extension.txt"
)
RAJOUNET_SUBDIR_FIXTURE = (
    Path(__file__).parent / "fixtures" / "mdir_sample_rajounet_subdir.txt"
)


def _load_entries():
    text = FIXTURE.read_text()
    return parse_mdir_output(text)


def test_parses_expected_number_of_entries():
    # mtools reports "14 files" including "." and ".." - both filtered
    # out, leaving 12.
    entries = _load_entries()
    assert len(entries) == 12


def test_dot_and_dotdot_are_filtered_out():
    names = [e.name for e in _load_entries()]
    assert "." not in names
    assert ".." not in names


def test_directory_entries_detected():
    entries = _load_entries()
    democlip = next(e for e in entries if e.name == "DEMOCLIP")
    assert democlip.is_dir is True
    assert democlip.size == 0
    assert democlip.modified.year == 2009
    assert democlip.modified.month == 3
    assert democlip.modified.day == 1
    assert democlip.modified.hour == 17
    assert democlip.modified.minute == 42


def test_long_looking_directory_name_without_extension_is_untouched():
    # e.g. "2007_09" - a single token, no embedded base/ext gap to
    # collapse, must be left exactly as mtools printed it.
    entries = _load_entries()
    entry = next(e for e in entries if e.name == "2007_09")
    assert entry.is_dir is True


def test_short_dos_name_gets_dot_reinserted_between_base_and_extension():
    # mtools prints classic 8.3 short names as two whitespace-padded
    # fields ("XTCB     PRG") since there's no long filename - this must
    # come back as a single valid mtools path component "XTCB.PRG",
    # otherwise later mcopy/mdel/mren calls using this name would fail.
    entries = _load_entries()
    entry = next(e for e in entries if e.name == "XTCB.PRG")
    assert entry.is_dir is False
    assert entry.size == 331940
    assert entry.modified.year == 2006
    assert entry.modified.month == 10
    assert entry.modified.day == 27
    assert entry.modified.hour == 20
    assert entry.modified.minute == 20

    entry2 = next(e for e in entries if e.name == "AD1.TOS")
    assert entry2.is_dir is False
    assert entry2.size == 113526


def test_header_and_summary_lines_are_ignored():
    entries = _load_entries()
    names = [e.name for e in entries]
    assert not any("Volume" in n for n in names)
    assert not any("file(s)" in n or "bytes free" in n for n in names)


def test_empty_input_returns_no_entries():
    assert parse_mdir_output("") == []


def test_normalize_short_name_joins_base_and_extension():
    assert _normalize_short_name("XTCB     PRG") == "XTCB.PRG"
    assert _normalize_short_name("AD1      TOS") == "AD1.TOS"


def test_normalize_short_name_leaves_single_token_unchanged():
    assert _normalize_short_name("DEMOCLIP") == "DEMOCLIP"
    assert _normalize_short_name("2007_09") == "2007_09"


def test_single_digit_hour_entries_are_not_dropped():
    # Regression test: mdir doesn't always zero-pad the hour (e.g. "1:52",
    # not "01:52"). The entry regex used to require exactly 2 digits for
    # the hour, silently skipping every entry whose time had a single
    # digit - in a real directory this truncated a 10-file listing down
    # to 6, since the remaining files all happened to have been written
    # in the same overnight batch (hours 0-2).
    text = SINGLE_DIGIT_HOUR_FIXTURE.read_text()
    entries = parse_mdir_output(text)
    # 12 files reported minus "." and ".." = 10
    assert len(entries) == 10
    names = {e.name for e in entries}
    assert names == {
        "EXAMPLES", "DOC", "ICONS.RSC", "CICONS.RSC", "DESKTOP.RSC",
        "TERADESK.INF", "DESKTOP.RSD", "DESKTOP.PRG", "DESKTOS.PRG",
        "README.TXT",
    }
    desktop_rsd = next(e for e in entries if e.name == "DESKTOP.RSD")
    assert desktop_rsd.modified.hour == 1
    assert desktop_rsd.modified.minute == 52


def test_directory_with_8_3_extension_is_not_dropped():
    # Regression test: a *directory* can have an 8.3 extension too (e.g.
    # "VDI_FX.68K" - an Atari convention for 68000-targeted content),
    # which packs its column tighter and leaves only a single space
    # before "<DIR>" ("VDI_FX   68K <DIR>"). The entry regex used to
    # require 2+ spaces there, silently dropping every such directory -
    # on a real card this meant 2 of 3 root-level folders vanished.
    text = DIR_WITH_EXTENSION_FIXTURE.read_text()
    entries = parse_mdir_output(text)
    names = {e.name for e in entries}
    assert names == {"RAJOUNET", "VDI_FX.68K", "TRAMIEL.68K"}
    assert all(e.is_dir for e in entries)


def test_subdirectory_full_of_dotted_directories_is_not_dropped():
    text = RAJOUNET_SUBDIR_FIXTURE.read_text()
    entries = parse_mdir_output(text)
    # 9 files reported minus "." and ".." = 7
    assert len(entries) == 7
    names = {e.name for e in entries}
    assert names == {
        "2048.68K", "DEFLATE.68K", "DOSFS.68K", "HEXEDIT.68K",
        "KKCMDFR.68K", "TRAMIEL.68K", "VDI_FX.68K",
    }
    assert all(e.is_dir for e in entries)
