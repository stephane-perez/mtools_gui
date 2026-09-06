# mtools_gui

A two-pane file manager (Midnight/Total Commander style) for exchanging
files between the local Linux filesystem and a DOS/FAT partition on a
removable drive (an SD card, a USB drive, ...), via
[mtools](https://www.gnu.org/software/mtools/) rather than a kernel
mount.

mtools' official graphical frontend, [MToolsFM](https://mtoolsfm.sourceforge.net/),
hasn't had a release since 2008 and is hard to build on current
distributions (it depends on an obsolete GTK version) - hence this
project.

## Authorship

Every line of code in this project was written by Claude (Anthropic's
AI model), through an extended pair-programming conversation with
Stéphane Perez, who directed the design, decided every feature and fix, 
and tested each change against real hardware (an Atari SD card).

## Installation

Two ways to install, pick whichever suits you:

- **AppImage**: a single ~80 MB file (it bundles its own Python and Qt,
  so it works regardless of what's already on your system) - no
  installation, no dependencies, but a bigger download.
- **pipx**: a much smaller download, but requires Python and pipx to
  already be installed.

### AppImage (no Python/pip needed)

Download `mtools_gui-x86_64.AppImage` from the
[releases page](https://github.com/stephane-perez/mtools_gui/releases),
then:

```bash
chmod +x mtools_gui-x86_64.AppImage
./mtools_gui-x86_64.AppImage
```

Needs glibc >= 2.28 (Ubuntu 18.10+/20.04/22.04, Debian 10+, Fedora 29+,
and most distributions from the last several years). To build it
yourself: `packaging/appimage/build.sh` (needs network access, to
download a base Python AppImage and appimagetool).

### From source (pipx)

Needs Python >= 3.10 and [pipx](https://pipx.pypa.io/) (`apt install
pipx` / `dnf install pipx` / `pip install --user pipx`):

```bash
pipx install .
```

The left pane (local files) works right away; the right pane (DOS
drive) needs one extra one-time step first - either click "Install now"
when the app prompts for it on first launch, or run manually:

```bash
sudo "$(command -v mtools-gui-install-helper)"
```

This installs, once per machine:
- `/usr/local/libexec/mtools-gui-helper`: the small privileged program
  that actually runs mtools commands against the chosen device.
- `/etc/polkit-1/rules.d/49-mtools-gui.rules`: a polkit rule that lets
  the active graphical session's user run this helper (and only this
  helper) without a password.

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

- [mtools](https://www.gnu.org/software/mtools/): a collection of
  command-line tools (`mcopy`, `mdir`, `mdel`, `mmd`, ...) that read and
  write MS-DOS/FAT disks directly, without mounting them.
  - Debian/Ubuntu and derivatives: `apt install mtools`
  - Fedora/RHEL/CentOS and other RPM-based distributions: `dnf install mtools`
    (`yum install mtools` on older releases)
  - Arch Linux: `pacman -S mtools`
  - Or grab a `.deb`/`.rpm` package directly from the
    [official mtools downloads](https://www.gnu.org/software/mtools/).
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

## License

GPLv3 or later - see [LICENSE](LICENSE).
