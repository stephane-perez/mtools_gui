# mtools_gui

Gestionnaire de fichiers a deux volets (facon Midnight/Total Commander) pour
echanger des fichiers entre le systeme de fichiers Linux local et une
partition DOS/FAT presente sur une carte SD, via [mtools](https://www.gnu.org/software/mtools/)
plutot que par un montage noyau.

## Installation

```bash
pipx install .
sudo "$(command -v mtools-gui-install-helper)"
```

La seconde commande installe, une seule fois par machine :
- `/usr/local/libexec/mtools-gui-helper` : le petit programme privilegie
  qui execute reellement les commandes mtools sur le peripherique choisi.
- `/etc/polkit-1/rules.d/49-mtools-gui.rules` : une regle polkit qui
  autorise l'utilisateur de la session graphique active a lancer ce
  helper (et uniquement lui) sans mot de passe.

Le volet gauche (fichiers locaux) fonctionne sans cette etape ; elle n'est
necessaire que pour acceder au volet droit (carte SD).

## Lancer l'application

```bash
mtools-gui
```

## Langue

L'interface est en francais ou en anglais selon la locale systeme
(`fr_*` -> francais, tout le reste -> anglais). Pour forcer une langue :

```bash
MTOOLS_GUI_LANG=en mtools-gui
```

## Prerequis systeme

- `mtools` (`mcopy`, `mdir`, `mdel`, `mmd`, ...) installe (`apt install mtools`).
- `polkit`/`pkexec` (present par defaut sur la plupart des distributions
  de bureau modernes).
- `lsblk` (util-linux, present par defaut).

## Securite

Voir les commentaires dans `src/mtools_gui/system_files/mtools-gui-helper` :
le helper valide independamment (via `lsblk` ET `/sys/block/*/removable`)
que le peripherique cible est bien amovible avant toute operation, et
confine tout chemin Unix passe a `mcopy` au dossier personnel de
l'utilisateur ou aux racines de montage amovible usuelles.

## Desinstaller le helper privilegie

```bash
sudo "$(command -v mtools-gui-install-helper)" --uninstall
```
# mtools_gui
