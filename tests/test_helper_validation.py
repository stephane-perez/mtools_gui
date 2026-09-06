"""system_files/mtools-gui-helper is a standalone script (filename has
dashes, not importable as a normal module, and deliberately not part of
the mtools_gui package's import path since it must stay independent of
the app's venv) - load it via importlib so its pure validation functions
can be unit-tested without root or a real device.
"""

import importlib.util
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace

import pytest

HELPER_PATH = (
    Path(__file__).parent.parent
    / "src"
    / "mtools_gui"
    / "system_files"
    / "mtools-gui-helper"
)


def _load_helper_module():
    # The helper has no .py extension (it's installed standalone, run
    # directly by pkexec) so the loader must be given explicitly - plain
    # spec_from_file_location can't infer one from the filename alone.
    loader = SourceFileLoader("mtools_gui_helper", str(HELPER_PATH))
    spec = importlib.util.spec_from_loader("mtools_gui_helper", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def helper():
    return _load_helper_module()


# -- is_removable -----------------------------------------------------------


def test_is_removable_true_when_both_checks_agree(helper):
    row = {"rm": True, "pkname": "sde"}
    assert helper.is_removable(row, sysfs_read_fn=lambda pk: True) is True


def test_is_removable_false_when_lsblk_disagrees(helper):
    row = {"rm": False, "pkname": "sda"}
    assert helper.is_removable(row, sysfs_read_fn=lambda pk: True) is False


def test_is_removable_false_when_sysfs_disagrees(helper):
    # Two independent checks must both agree - if lsblk says removable but
    # sysfs doesn't, that mismatch must NOT be trusted.
    row = {"rm": True, "pkname": "sda"}
    assert helper.is_removable(row, sysfs_read_fn=lambda pk: False) is False


# -- is_allowed_unix_path -----------------------------------------------------


def test_path_under_home_is_allowed(helper, tmp_path):
    home = tmp_path / "home" / "testuser"
    home.mkdir(parents=True)
    target = home / "file.txt"
    target.write_text("x")
    assert helper.is_allowed_unix_path(str(target), str(home)) is True


def test_path_outside_home_and_media_roots_is_rejected(helper, tmp_path):
    home = tmp_path / "home" / "testuser"
    home.mkdir(parents=True)
    outside = tmp_path / "etc" / "shadow"
    outside.parent.mkdir(parents=True)
    outside.write_text("secret")
    assert helper.is_allowed_unix_path(str(outside), str(home)) is False


def test_path_under_extra_root_is_allowed(helper, tmp_path):
    media_root = tmp_path / "media" / "testuser"
    media_root.mkdir(parents=True)
    target = media_root / "card" / "file.txt"
    target.parent.mkdir(parents=True)
    target.write_text("x")
    assert (
        helper.is_allowed_unix_path(str(target), home_dir=None, extra_roots=(str(media_root),))
        is True
    )


# -- _extra_allowed_roots -----------------------------------------------------


def test_extra_allowed_roots_scopes_media_to_the_given_username(helper):
    roots = helper._extra_allowed_roots("testuser")
    assert "/media/testuser" in roots
    assert "/run/media/testuser" in roots
    assert "/mnt" in roots


def test_extra_allowed_roots_excludes_another_users_media(helper):
    roots = helper._extra_allowed_roots("testuser")
    assert helper.is_allowed_unix_path("/media/otheruser/SDCARD", None, roots) is False
    assert helper.is_allowed_unix_path("/media/testuser/SDCARD", None, roots) is True


def test_extra_allowed_roots_without_username_still_allows_mnt(helper):
    roots = helper._extra_allowed_roots(None)
    assert roots == ("/mnt",)


# -- validate_args -----------------------------------------------------------


def test_non_mcopy_op_rejects_unix_path(helper):
    with pytest.raises(helper.ValidationError):
        helper.validate_args("mdir", ["/etc/shadow"], home_dir="/home/testuser")


def test_non_mcopy_op_accepts_dos_path(helper):
    result = helper.validate_args("mdir", ["::/SUBDIR"], home_dir="/home/testuser")
    assert result == ["::/SUBDIR"]


def test_mcopy_rejects_path_outside_allowed_roots(helper, tmp_path):
    outside = tmp_path / "etc" / "shadow"
    outside.parent.mkdir(parents=True)
    outside.write_text("secret")
    with pytest.raises(helper.ValidationError):
        helper.validate_args("mcopy", [str(outside), "::stolen.txt"], home_dir=str(tmp_path / "home"))


def test_mcopy_accepts_path_under_home(helper, tmp_path):
    home = tmp_path / "home" / "testuser"
    home.mkdir(parents=True)
    source = home / "photo.jpg"
    source.write_text("data")
    result = helper.validate_args("mcopy", [str(source), "::photo.jpg"], home_dir=str(home))
    assert result[0] == str(source.resolve())
    assert result[1] == "::photo.jpg"


def test_unrecognised_flag_argument_is_rejected(helper):
    with pytest.raises(helper.ValidationError):
        helper.validate_args("mcopy", ["-s", "::x"], home_dir="/home/testuser")


# -- validate_device (subprocess mocked) --------------------------------------


def test_validate_device_rejects_non_removable(helper, monkeypatch):
    lsblk_output = json.dumps(
        {
            "blockdevices": [
                {"type": "part", "pkname": "sda", "rm": False, "fstype": "vfat", "mountpoint": None}
            ]
        }
    )
    monkeypatch.setattr(
        helper.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=lsblk_output, stderr=""),
    )
    monkeypatch.setattr(helper, "_sysfs_removable", lambda pk: False)
    with pytest.raises(helper.ValidationError):
        helper.validate_device("/dev/sda1")


def test_validate_device_rejects_already_mounted(helper, monkeypatch):
    lsblk_output = json.dumps(
        {
            "blockdevices": [
                {
                    "type": "part",
                    "pkname": "sde",
                    "rm": True,
                    "fstype": "vfat",
                    "mountpoint": "/media/testuser/SDCARD",
                }
            ]
        }
    )
    monkeypatch.setattr(
        helper.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=lsblk_output, stderr=""),
    )
    monkeypatch.setattr(helper, "_sysfs_removable", lambda pk: True)
    with pytest.raises(helper.ValidationError):
        helper.validate_device("/dev/sde1")


def test_validate_device_accepts_removable_unmounted_fat_partition(helper, monkeypatch):
    lsblk_output = json.dumps(
        {
            "blockdevices": [
                {
                    "type": "part",
                    "pkname": "sde",
                    "rm": True,
                    "fstype": "vfat",
                    "mountpoint": None,
                }
            ]
        }
    )
    monkeypatch.setattr(
        helper.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=lsblk_output, stderr=""),
    )
    monkeypatch.setattr(helper, "_sysfs_removable", lambda pk: True)
    assert helper.validate_device("/dev/sde1") == "/dev/sde1"


def test_validate_device_accepts_unrecognized_fstype_gemdos_case(helper, monkeypatch):
    # A GEMDOS (Atari) partition: lsblk has no idea what filesystem this
    # is (fstype=null), but that must NOT be rejected - only a fstype the
    # kernel positively identifies as non-DOS should be.
    lsblk_output = json.dumps(
        {
            "blockdevices": [
                {
                    "type": "part",
                    "pkname": "sde",
                    "rm": True,
                    "fstype": None,
                    "mountpoint": None,
                }
            ]
        }
    )
    monkeypatch.setattr(
        helper.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=lsblk_output, stderr=""),
    )
    monkeypatch.setattr(helper, "_sysfs_removable", lambda pk: True)
    assert helper.validate_device("/dev/sde3") == "/dev/sde3"


def test_validate_device_rejects_known_non_dos_fstype(helper, monkeypatch):
    lsblk_output = json.dumps(
        {
            "blockdevices": [
                {
                    "type": "part",
                    "pkname": "sde",
                    "rm": True,
                    "fstype": "ext4",
                    "mountpoint": None,
                }
            ]
        }
    )
    monkeypatch.setattr(
        helper.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=lsblk_output, stderr=""),
    )
    monkeypatch.setattr(helper, "_sysfs_removable", lambda pk: True)
    with pytest.raises(helper.ValidationError):
        helper.validate_device("/dev/sde1")


# -- ownership handback (DOS -> local copies must not stay root-owned) ------


def test_invoking_identity_none_without_pkexec_uid(helper, monkeypatch):
    monkeypatch.delenv("PKEXEC_UID", raising=False)
    assert helper._invoking_identity() is None


def test_invoking_identity_resolves_uid_and_gid(helper, monkeypatch):
    monkeypatch.setenv("PKEXEC_UID", "1000")
    monkeypatch.setattr(
        helper.pwd, "getpwuid", lambda uid: SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_dir="/home/testuser")
    )
    assert helper._invoking_identity() == (1000, 1000)


def test_chown_recursive_covers_every_file_and_subdir(helper, tmp_path, monkeypatch):
    root = tmp_path / "copied_folder"
    (root / "sub").mkdir(parents=True)
    (root / "a.txt").write_text("x")
    (root / "sub" / "b.txt").write_text("y")

    chowned = []
    monkeypatch.setattr(helper.os, "chown", lambda path, uid, gid, **kw: chowned.append(path))

    helper._chown_recursive(str(root), 1000, 1000)

    assert str(root) in chowned
    assert str(root / "a.txt") in chowned
    assert str(root / "sub") in chowned
    assert str(root / "sub" / "b.txt") in chowned


def test_chown_recursive_tolerates_a_missing_path(helper):
    # Must not raise even if the path vanished or chown is refused -
    # ownership handback is best-effort, never fatal to the operation
    # that already succeeded.
    helper._chown_recursive("/nonexistent/path/xyz", 1000, 1000)


def test_hand_back_ownership_only_touches_unix_side_paths(helper, tmp_path, monkeypatch):
    dest = tmp_path / "DEMOS"
    dest.mkdir()
    (dest / "file.txt").write_text("x")

    monkeypatch.setattr(helper, "_invoking_identity", lambda: (1000, 1000))
    chowned = []
    monkeypatch.setattr(helper, "_chown_recursive", lambda path, uid, gid: chowned.append(path))

    helper._hand_back_ownership(
        "mcopy", ["::/DEMOS", str(dest)], home_dir=str(tmp_path), extra_roots=()
    )

    assert chowned == [str(dest)]


def test_hand_back_ownership_skips_a_path_that_no_longer_validates(helper, tmp_path, monkeypatch):
    # Re-validation immediately before chown is the TOCTOU-shrinking check
    # from the security review: if the path no longer resolves under an
    # allowed root (home dir or scoped media root), skip the chown rather
    # than trusting the validation done before mcopy ran.
    dest = tmp_path / "DEMOS"
    dest.mkdir()

    monkeypatch.setattr(helper, "_invoking_identity", lambda: (1000, 1000))
    chowned = []
    monkeypatch.setattr(helper, "_chown_recursive", lambda path, uid, gid: chowned.append(path))

    helper._hand_back_ownership(
        "mcopy", ["::/DEMOS", str(dest)], home_dir=None, extra_roots=()
    )

    assert chowned == []


def test_hand_back_ownership_is_noop_for_non_mcopy_ops(helper, monkeypatch):
    calls = []
    monkeypatch.setattr(helper, "_invoking_identity", lambda: (1000, 1000))
    monkeypatch.setattr(helper, "_chown_recursive", lambda *a: calls.append(a))
    helper._hand_back_ownership("mdir", ["::/DEMOS"])
    assert calls == []


def test_hand_back_ownership_is_noop_without_pkexec_identity(helper, tmp_path, monkeypatch):
    dest = tmp_path / "file.txt"
    dest.write_text("x")
    monkeypatch.setattr(helper, "_invoking_identity", lambda: None)
    calls = []
    monkeypatch.setattr(helper, "_chown_recursive", lambda *a: calls.append(a))
    helper._hand_back_ownership("mcopy", [str(dest)])
    assert calls == []


# -- mcopy must recurse into subdirectories (-s) -----------------------------


def _stub_validated_device(helper, monkeypatch, device="/dev/sde1"):
    monkeypatch.setattr(helper, "validate_device", lambda d: device)


def test_mcopy_command_includes_recursive_flag(helper, monkeypatch, tmp_path):
    _stub_validated_device(helper, monkeypatch)
    monkeypatch.setattr(helper, "validate_args", lambda op, args, **kwargs: args)
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(helper.subprocess, "run", fake_run)
    monkeypatch.setattr(helper, "_hand_back_ownership", lambda *a, **k: None)

    helper.main(["mtools-gui-helper", "mcopy", "/dev/sde1", "::/DEMOS", str(tmp_path)])

    assert captured["command"] == ["/usr/bin/mcopy", "-i", "/dev/sde1", "-s", "::/DEMOS", str(tmp_path)]


def test_non_mcopy_command_has_no_recursive_flag(helper, monkeypatch):
    _stub_validated_device(helper, monkeypatch)
    monkeypatch.setattr(helper, "validate_args", lambda op, args, **kwargs: args)
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(helper.subprocess, "run", fake_run)

    helper.main(["mtools-gui-helper", "mdir", "/dev/sde1", "::/DEMOS"])

    assert captured["command"] == ["/usr/bin/mdir", "-i", "/dev/sde1", "::/DEMOS"]
