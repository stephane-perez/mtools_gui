"""A multi-select delete/move/overwrite on a folder with hundreds of
entries used to dump the whole comma-joined name list into the
confirmation dialog - unusable once selection sizes got large. See
main_window._format_name_list_for_dialog.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from mtools_gui.main_window import _NAME_LIST_CHAR_LIMIT, _format_name_list_for_dialog


def test_short_list_is_left_untouched():
    names = ["a.txt", "b.txt", "c.txt"]
    assert _format_name_list_for_dialog(names) == "a.txt, b.txt, c.txt"


def test_list_under_the_character_limit_is_not_truncated():
    names = [f"file{i}.txt" for i in range(10)]
    result = _format_name_list_for_dialog(names)
    assert "..." not in result
    assert result == ", ".join(names)


def test_long_list_is_truncated_and_stays_under_the_char_budget():
    names = [f"BASEDR_{i}.DIG" for i in range(50)]
    result = _format_name_list_for_dialog(names)
    assert result.startswith("BASEDR_0.DIG")
    shown_part = result.split(", ...")[0]
    assert len(shown_part) <= _NAME_LIST_CHAR_LIMIT
    # every kept name must appear whole - no name is cut mid-string
    for name in shown_part.split(", "):
        assert name in names


def test_truncated_result_mentions_how_many_are_left_out():
    names = [f"file{i}.txt" for i in range(50)]
    result = _format_name_list_for_dialog(names)
    shown_count = len(result.split(", ...")[0].split(", "))
    remaining = len(names) - shown_count
    assert str(remaining) in result


def test_single_very_long_name_is_still_shown_whole():
    # Even if one name alone exceeds the limit, it must not be chopped
    # mid-string - there'd be nothing sensible left to show otherwise.
    long_name = "A" * (_NAME_LIST_CHAR_LIMIT + 50) + ".DIG"
    result = _format_name_list_for_dialog([long_name, "b.txt"])
    assert long_name in result
