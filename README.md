# mtools_gui

A two-pane file manager (Midnight/Total Commander style) for exchanging
files between the local Linux filesystem and a DOS/FAT partition on an
SD card, via [mtools](https://www.gnu.org/software/mtools/) rather than
a kernel mount.

## Installation

```bash
pipx install .
sudo "$(command -v mtools-gui-install-helper)"
```

The second command installs, once per machine:
- `/usr/local/libexec/mtools-gui-helper`: the small privileged program
  that actually runs mtools commands against the chosen device.
- `/etc/polkit-1/rules.d/49-mtools-gui.rules`: a polkit rule that lets
  the active graphical session's user run this helper (and only this
  helper) without a password.

The left pane (local files) works without this step; it's only needed
to access the right pane (SD card).

## Running the application

```bash
mtools-gui
```

## Language

The interface is in French or English depending on the system locale
(`fr_*` -> French, everything else -> English). To force a language:

```bash
MTOOLS_GUI_LANG=en mtools-gui
```

## System requirements

- `mtools` (`mcopy`, `mdir`, `mdel`, `mmd`, ...) installed (`apt install mtools`).
- `polkit`/`pkexec` (present by default on most modern desktop
  distributions).
- `lsblk` (util-linux, present by default).

## Security

See the comments in `src/mtools_gui/system_files/mtools-gui-helper`: the
helper independently validates (via `lsblk` AND `/sys/block/*/removable`)
that the target device is actually removable before any operation, and
confines any Unix path passed to `mcopy` to the user's home directory or
the usual removable-media mount roots.

## Uninstalling the privileged helper

```bash
sudo "$(command -v mtools-gui-install-helper)" --uninstall
```
