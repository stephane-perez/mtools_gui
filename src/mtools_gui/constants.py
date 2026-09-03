HELPER_INSTALL_PATH = "/usr/local/libexec/mtools-gui-helper"
POLKIT_RULES_INSTALL_PATH = "/etc/polkit-1/rules.d/49-mtools-gui.rules"

HELPER_SOURCE_NAME = "mtools-gui-helper"
POLKIT_RULES_SOURCE_NAME = "49-mtools-gui.rules"

# Operations the privileged helper accepts, in the order the GUI is most
# likely to need them. Kept in sync with system_files/mtools-gui-helper.
ALLOWED_OPS = (
    "mdir",
    "mcopy",
    "mdel",
    "mdeltree",
    "mmd",
    "mmove",
    "mren",
    "mattrib",
    "mrd",
    "mtype",
)

FAT_FSTYPES = frozenset({"vfat", "fat", "fat12", "fat16", "fat32", "msdos"})

# Filesystems the Linux kernel positively identifies as *not* FAT-like.
# Partitions with one of these fstypes are never shown as DOS-pane
# candidates. Everything else - including an empty/unrecognized fstype,
# which is exactly what a GEMDOS (Atari) partition looks like to lsblk -
# is left in: mtools reads the FAT structures itself, independently of
# the kernel's own filesystem detection, so it can succeed even where
# Linux reports nothing usable.
NON_DOS_FSTYPES = frozenset(
    {
        "ext2", "ext3", "ext4",
        "btrfs", "xfs", "jfs", "reiserfs", "f2fs",
        "ntfs", "hfs", "hfsplus", "apfs",
        "swap", "iso9660", "udf",
        "zfs_member", "linux_raid_member", "lvm2_member", "crypto_luks",
    }
)

INSTALL_HELPER_COMMAND = 'sudo "$(command -v mtools-gui-install-helper)"'

# Custom drag-and-drop payload: "<source side>\n<entry name>\n<entry name>...",
# UTF-8 encoded. Internal to this app - a drag never needs to leave the
# process, so this stays deliberately simple rather than trying to look
# like a real file:// URI list (DOS-side paths aren't real filesystem
# paths anyway).
DND_MIME_TYPE = "application/x-mtools-gui-entries"
