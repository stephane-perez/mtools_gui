"""Lightweight i18n: a single dict of {key: {"fr": ..., "en": ...}} and a
lookup function that picks the string for the detected locale.

Deliberately not using Qt's tr()/.ts/.qm toolchain (pyside6-lupdate,
lrelease) - that's the "correct" scalable approach for a large app with
many translators, but is overkill for the few dozen short strings here
and would add a separate build step. This keeps every string reviewable
as plain Python with no external tooling.

Only user-facing UI text goes through _() - log messages stay as
plain French for the developer reading them in the console, regardless
of the UI language (see main_window.py, pane_widget.py, etc.).
"""

from __future__ import annotations

import os

from PySide6.QtCore import QLocale


def _detect_language() -> str:
    # MTOOLS_GUI_LANG lets a user (or a test) force the language without
    # changing their whole system locale.
    override = os.environ.get("MTOOLS_GUI_LANG")
    if override:
        return "fr" if override.lower().startswith("fr") else "en"
    name = QLocale.system().name()  # e.g. "fr_FR", "en_US"
    return "fr" if name.lower().startswith("fr") else "en"


LANGUAGE = _detect_language()

_STRINGS: dict[str, dict[str, str]] = {
    "window_title": {
        "fr": "mtools_gui - echange Linux / lecteur DOS",
        "en": "mtools_gui - exchange files between Linux and a DOS drive",
    },
    "status_ready": {"fr": "Pret", "en": "Ready"},
    "toolbar_refresh": {"fr": "Rafraichir (F5)", "en": "Refresh (F5)"},
    "toolbar_copy": {"fr": "Copier (Ctrl+C)", "en": "Copy (Ctrl+C)"},
    "toolbar_move": {"fr": "Deplacer", "en": "Move"},
    "toolbar_move_tooltip": {
        "fr": "Deplacer (ou Alt+glisser-deposer)",
        "en": "Move (or Alt+drag-and-drop)",
    },
    "toolbar_rename": {"fr": "Renommer (F2)", "en": "Rename (F2)"},
    "toolbar_delete": {"fr": "Supprimer (Suppr)", "en": "Delete (Del)"},
    "toolbar_mkdir": {"fr": "Nouveau dossier (Ctrl+N)", "en": "New folder (Ctrl+N)"},
    "toolbar_about": {"fr": "A propos", "en": "About"},
    "drive_label": {"fr": "Lecteur DOS :", "en": "DOS drive:"},
    "drive_refresh_button": {"fr": "Rafraichir lecteurs", "en": "Refresh drives"},
    "drive_placeholder": {"fr": "(choisir un lecteur)", "en": "(choose a drive)"},
    "drive_unknown_fstype": {
        "fr": "type inconnu - probablement DOS",
        "en": "unknown type - probably DOS",
    },
    "drive_no_label": {"fr": "(sans nom)", "en": "(no label)"},
    "pane_up_button": {"fr": "Remonter", "en": "Up"},
    "column_name": {"fr": "Nom", "en": "Name"},
    "column_size": {"fr": "Taille", "en": "Size"},
    "column_modified": {"fr": "Modifie", "en": "Modified"},
    "size_bytes": {"fr": "o", "en": "B"},
    "size_kb": {"fr": "Ko", "en": "KB"},
    "size_mb": {"fr": "Mo", "en": "MB"},
    "size_gb": {"fr": "Go", "en": "GB"},
    "confirm_delete_title": {"fr": "Confirmer la suppression", "en": "Confirm delete"},
    "confirm_delete_text": {"fr": "Supprimer : {names} ?", "en": "Delete: {names}?"},
    "confirm_move_title": {"fr": "Confirmer le deplacement", "en": "Confirm move"},
    "confirm_move_text": {
        "fr": "Deplacer vers {side} : {names} ?",
        "en": "Move to {side}: {names}?",
    },
    "status_choose_drive": {
        "fr": "Choisissez d'abord un lecteur DOS",
        "en": "Choose a DOS drive first",
    },
    "status_select_one_to_rename": {
        "fr": "Selectionnez un seul element a renommer",
        "en": "Select exactly one item to rename",
    },
    "status_op_done": {"fr": "{description} : termine", "en": "{description}: done"},
    "op_copy": {"fr": "Copier {name}", "en": "Copy {name}"},
    "op_move": {"fr": "Deplacer {name}", "en": "Move {name}"},
    "op_delete": {"fr": "Supprimer {name}", "en": "Delete {name}"},
    "op_mkdir": {"fr": "Nouveau dossier {name}", "en": "New folder {name}"},
    "op_rename": {"fr": "Renommer {name}", "en": "Rename {name}"},
    "dialog_new_folder_title": {"fr": "Nouveau dossier", "en": "New folder"},
    "dialog_new_folder_label": {"fr": "Nom du dossier :", "en": "Folder name:"},
    "dialog_rename_title": {"fr": "Renommer", "en": "Rename"},
    "dialog_rename_label": {"fr": "Nouveau nom :", "en": "New name:"},
    "dialog_error_title": {"fr": "Erreur", "en": "Error"},
    "dialog_install_required_title": {
        "fr": "Installation requise",
        "en": "Installation required",
    },
    "dialog_install_required_text": {
        "fr": (
            "Le helper privilegie n'est pas encore installe.\n\n"
            "Cliquez sur \"Installer maintenant\" (demandera votre mot de "
            "passe), ou lancez une fois manuellement dans un terminal :\n"
            "  {command}\n\n"
            "Le volet gauche (fichiers locaux) fonctionne deja sans cela."
        ),
        "en": (
            "The privileged helper isn't installed yet.\n\n"
            "Click \"Install now\" (will ask for your password), or run "
            "this once manually in a terminal:\n"
            "  {command}\n\n"
            "The left pane (local files) already works without it."
        ),
    },
    "install_now_button": {"fr": "Installer maintenant", "en": "Install now"},
    "install_later_button": {"fr": "Plus tard", "en": "Later"},
    "install_success_title": {"fr": "Installation reussie", "en": "Installation succeeded"},
    "install_success_text": {
        "fr": "Le helper privilegie est maintenant installe.",
        "en": "The privileged helper is now installed.",
    },
    "install_auth_cancelled": {
        "fr": "Installation annulee (authentification refusee).",
        "en": "Installation cancelled (authentication refused).",
    },
    "install_failed_text": {
        "fr": "Echec de l'installation : {error}",
        "en": "Installation failed: {error}",
    },
    "about_title": {"fr": "A propos de mtools_gui", "en": "About mtools_gui"},
    "about_text": {
        "fr": (
            "<b>mtools_gui</b><br>"
            "Version {version}<br>"
            "Auteur : Stephane Perez<br><br>"
            "Gestionnaire de fichiers a deux volets pour echanger des "
            "fichiers entre Linux et une partition DOS sur un lecteur "
            "amovible, via mtools."
        ),
        "en": (
            "<b>mtools_gui</b><br>"
            "Version {version}<br>"
            "Author: Stephane Perez<br><br>"
            "Two-pane file manager for exchanging files between Linux "
            "and a DOS partition on a removable drive, via mtools."
        ),
    },
    "err_helper_not_installed": {
        "fr": "Le helper privilegie n'est pas installe. Lancez une fois : {command}",
        "en": "The privileged helper isn't installed. Run this once: {command}",
    },
    "err_auth_dismissed": {
        "fr": "Authentification refusee ou annulee.",
        "en": "Authentication refused or dismissed.",
    },
    "err_validation_default": {
        "fr": "Operation rejetee par le helper.",
        "en": "Operation rejected by the helper.",
    },
    "err_usage_default": {"fr": "Erreur d'usage du helper.", "en": "Helper usage error."},
    "err_command_default": {
        "fr": "Echec de la commande {op}.",
        "en": "Command {op} failed.",
    },
    "err_pkexec_not_found": {
        "fr": "pkexec introuvable sur ce systeme.",
        "en": "pkexec not found on this system.",
    },
    "op_unexpected_error": {
        "fr": "Erreur inattendue : {error}",
        "en": "Unexpected error: {error}",
    },
    "op_failed_combined": {"fr": "{description} : {msg}", "en": "{description}: {msg}"},
    "err_unknown_pane_combination": {
        "fr": "Combinaison de volets inconnue",
        "en": "Unknown pane combination",
    },
    "err_unknown_pane_combination_move": {
        "fr": "Combinaison de volets inconnue pour un deplacement croise",
        "en": "Unknown pane combination for a cross-side move",
    },
    "view_dialog_read_error": {
        "fr": "Lecture de {name} : {error}",
        "en": "Reading {name}: {error}",
    },
    "install_need_root": {
        "fr": (
            "Ce programme doit etre execute en root, par exemple :\n"
            '  sudo "$(command -v mtools-gui-install-helper)"'
        ),
        "en": (
            "This program must be run as root, e.g.:\n"
            '  sudo "$(command -v mtools-gui-install-helper)"'
        ),
    },
    "install_installed": {"fr": "Installe : {path}", "en": "Installed: {path}"},
    "install_removed": {"fr": "Supprime : {path}", "en": "Removed: {path}"},
    "install_already_absent": {"fr": "Deja absent : {path}", "en": "Already absent: {path}"},
    "install_verify_hint": {
        "fr": (
            "\nVerification recommandee (depuis un terminal de la session active) :\n"
            "  pkexec {helper_path} mdir /dev/sdX1 ::\n"
            "ne devrait demander aucun mot de passe."
        ),
        "en": (
            "\nRecommended check (from a terminal in the active session):\n"
            "  pkexec {helper_path} mdir /dev/sdX1 ::\n"
            "should not ask for a password."
        ),
    },
}


def _(key: str, **kwargs) -> str:
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(LANGUAGE) or entry.get("fr") or key
    return text.format(**kwargs) if kwargs else text
