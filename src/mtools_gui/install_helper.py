"""Console-script that installs (or removes) the privileged helper and its
polkit rule. Must be run as root, once, after `pipx install .` - pipx
itself cannot write outside its isolated venv, so it can never place
files under /etc/polkit-1 or /usr/local/libexec on its own.

Usage:
    sudo "$(command -v mtools-gui-install-helper)"
    sudo "$(command -v mtools-gui-install-helper)" --uninstall
"""

from __future__ import annotations

import argparse
import importlib.resources
import os
import shutil
import sys

from .constants import (
    HELPER_INSTALL_PATH,
    HELPER_SOURCE_NAME,
    POLKIT_RULES_INSTALL_PATH,
    POLKIT_RULES_SOURCE_NAME,
)
from .i18n import _

# Note: `sudo` typically resets LANG/LC_* (env_reset) unless a sudoers
# admin has explicitly kept them, so this may print English even on a
# French system when run via `sudo mtools-gui-install-helper` - a minor,
# low-stakes inconsistency with the main GUI (which is never run via
# sudo and always sees the real user locale).


def _require_root() -> None:
    if os.geteuid() != 0:
        print(_("install_need_root"), file=sys.stderr)
        sys.exit(1)


def _install() -> None:
    system_files = importlib.resources.files("mtools_gui") / "system_files"

    helper_src = system_files / HELPER_SOURCE_NAME
    os.makedirs(os.path.dirname(HELPER_INSTALL_PATH), exist_ok=True)
    with importlib.resources.as_file(helper_src) as helper_path:
        shutil.copyfile(helper_path, HELPER_INSTALL_PATH)
    os.chmod(HELPER_INSTALL_PATH, 0o755)
    os.chown(HELPER_INSTALL_PATH, 0, 0)
    print(_("install_installed", path=HELPER_INSTALL_PATH))

    rules_src = system_files / POLKIT_RULES_SOURCE_NAME
    os.makedirs(os.path.dirname(POLKIT_RULES_INSTALL_PATH), exist_ok=True)
    with importlib.resources.as_file(rules_src) as rules_path:
        shutil.copyfile(rules_path, POLKIT_RULES_INSTALL_PATH)
    os.chmod(POLKIT_RULES_INSTALL_PATH, 0o644)
    os.chown(POLKIT_RULES_INSTALL_PATH, 0, 0)
    print(_("install_installed", path=POLKIT_RULES_INSTALL_PATH))

    print(_("install_verify_hint", helper_path=HELPER_INSTALL_PATH))


def _uninstall() -> None:
    for path in (HELPER_INSTALL_PATH, POLKIT_RULES_INSTALL_PATH):
        if os.path.exists(path):
            os.remove(path)
            print(_("install_removed", path=path))
        else:
            print(_("install_already_absent", path=path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Retire le helper privilegie et la regle polkit au lieu de les installer.",
    )
    args = parser.parse_args()

    _require_root()
    if args.uninstall:
        _uninstall()
    else:
        _install()


if __name__ == "__main__":
    main()
