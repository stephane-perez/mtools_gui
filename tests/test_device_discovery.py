"""tests/fixtures/lsblk_sample.json is real `lsblk -J` output captured on
the development machine (internal disks, non-removable), with synthetic
removable partitions added to exercise the positive cases - no real SD
card was available to capture those parts:
  - /dev/sde1: a recognized vfat partition (the "easy" case)
  - /dev/sdg1, /dev/sdg2: fstype=null partitions, standing in for a
    GEMDOS (Atari) card that Linux's own fstype detection doesn't
    recognize but mtools reads fine - this is the case the fstype filter
    used to wrongly exclude (see device_discovery.py's module docstring).
"""

import json
from pathlib import Path

from mtools_gui.device_discovery import filter_candidates

FIXTURE = Path(__file__).parent / "fixtures" / "lsblk_sample.json"


def _load_json():
    return json.loads(FIXTURE.read_text())


def test_removable_fat_partition_is_selected():
    candidates = filter_candidates(_load_json())
    paths = [c.path for c in candidates]
    assert "/dev/sde1" in paths


def test_removable_partition_with_unrecognized_fstype_is_selected():
    # This is the GEMDOS/Atari case: lsblk has no idea what filesystem
    # this is (fstype=null) but it's still a candidate, because mtools
    # doesn't rely on the kernel's detection - it parses the FAT
    # structures itself. Excluding these defeated the point of the tool.
    candidates = filter_candidates(_load_json())
    paths = [c.path for c in candidates]
    assert "/dev/sdg1" in paths
    assert "/dev/sdg2" in paths


def test_internal_vfat_partition_is_excluded():
    # /dev/sda1 is vfat (the EFI system partition) but rm=false - must
    # never show up as a candidate DOS pane target.
    candidates = filter_candidates(_load_json())
    assert all(c.path != "/dev/sda1" for c in candidates)


def test_non_fat_removable_partition_would_be_excluded():
    data = {
        "blockdevices": [
            {
                "name": "sdz1",
                "path": "/dev/sdz1",
                "fstype": "ext4",
                "size": "1G",
                "rm": True,
                "mountpoint": None,
                "label": None,
                "type": "part",
                "hotplug": True,
            }
        ]
    }
    assert filter_candidates(data) == []


def test_removable_whole_disk_without_partition_is_excluded():
    data = {
        "blockdevices": [
            {
                "name": "sdf",
                "path": "/dev/sdf",
                "fstype": None,
                "size": "0B",
                "rm": True,
                "mountpoint": None,
                "label": None,
                "type": "disk",
                "hotplug": True,
            }
        ]
    }
    assert filter_candidates(data) == []


def test_hotplug_true_is_accepted_even_if_rm_is_missing():
    data = {
        "blockdevices": [
            {
                "name": "mmcblk0p1",
                "path": "/dev/mmcblk0p1",
                "fstype": "vfat",
                "size": "29.7G",
                "rm": None,
                "mountpoint": None,
                "label": "SDCARD",
                "type": "part",
                "hotplug": True,
            }
        ]
    }
    candidates = filter_candidates(data)
    assert [c.path for c in candidates] == ["/dev/mmcblk0p1"]


def test_display_name_includes_path_and_label():
    candidates = filter_candidates(_load_json())
    sde1 = next(c for c in candidates if c.path == "/dev/sde1")
    assert sde1.display_name().startswith("/dev/sde1")
    assert "SDCARD" in sde1.display_name()


def test_display_name_flags_unrecognized_fstype():
    candidates = filter_candidates(_load_json())
    sdg1 = next(c for c in candidates if c.path == "/dev/sdg1")
    assert "GEMDOS" in sdg1.display_name()
