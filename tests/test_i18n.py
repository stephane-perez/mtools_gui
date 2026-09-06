"""i18n language detection and lookup are import-time/env-driven, so each
test that needs a specific language reloads the module with
MTOOLS_GUI_LANG set - the module-level LANGUAGE constant is otherwise
fixed for the whole process (matches how it's actually used: detected
once at app startup, never switched at runtime).
"""

import importlib
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import mtools_gui.i18n as i18n_module


def _reload_with_lang(lang: str | None):
    if lang is None:
        os.environ.pop("MTOOLS_GUI_LANG", None)
    else:
        os.environ["MTOOLS_GUI_LANG"] = lang
    return importlib.reload(i18n_module)


def test_french_override_selects_french_strings():
    mod = _reload_with_lang("fr")
    assert mod.LANGUAGE == "fr"
    assert mod._("status_ready") == "Prêt"


def test_english_override_selects_english_strings():
    mod = _reload_with_lang("en")
    assert mod.LANGUAGE == "en"
    assert mod._("status_ready") == "Ready"


def test_unknown_key_returns_the_key_itself():
    mod = _reload_with_lang("en")
    assert mod._("this_key_does_not_exist") == "this_key_does_not_exist"


def test_format_substitution():
    mod = _reload_with_lang("en")
    assert mod._("op_copy", name="foo.txt") == "Copy foo.txt"
    mod = _reload_with_lang("fr")
    assert mod._("op_copy", name="foo.txt") == "Copier foo.txt"


def test_lang_override_accepts_full_locale_like_values():
    # MTOOLS_GUI_LANG=fr_FR.UTF-8 should still mean French, not just the
    # bare "fr"/"en" codes.
    mod = _reload_with_lang("fr_FR.UTF-8")
    assert mod.LANGUAGE == "fr"


def teardown_module(module):
    # Leave the module state clean (system locale) for any test that runs
    # after this file, and restore MTOOLS_GUI_LANG's absence.
    os.environ.pop("MTOOLS_GUI_LANG", None)
    importlib.reload(i18n_module)
