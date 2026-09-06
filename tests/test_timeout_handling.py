"""A wedged/disconnected DOS device must surface as a clear timeout error
rather than hanging the privileged helper (root, via pkexec) or the
client forever. Covers both sides of the contract:
  - mtools_client._run_helper: subprocess.run itself times out (the
    helper process is stuck and pkexec/the OS never returns).
  - the helper's own subprocess.run (calling mdir/mcopy/...) times out,
    which it reports as exit code 4 - the client must recognize that
    code too, not just its own local timeout.
No real device or SD card involved - subprocess.run is mocked throughout.
"""

import importlib.util
import subprocess
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace

import pytest

from mtools_gui import mtools_client
from mtools_gui.mtools_client import MtoolsTimeoutError

HELPER_PATH = (
    Path(__file__).parent.parent
    / "src"
    / "mtools_gui"
    / "system_files"
    / "mtools-gui-helper"
)


def _load_helper_module():
    loader = SourceFileLoader("mtools_gui_helper_timeout", str(HELPER_PATH))
    spec = importlib.util.spec_from_loader("mtools_gui_helper_timeout", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def helper():
    return _load_helper_module()


# -- client side: mtools_client._run_helper ----------------------------------


def test_run_helper_raises_on_subprocess_timeout(monkeypatch):
    def fake_run(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout"))

    monkeypatch.setattr(mtools_client.subprocess, "run", fake_run)

    with pytest.raises(MtoolsTimeoutError):
        mtools_client._run_helper("mdir", "/dev/sde1", ["::"])


def test_run_helper_uses_the_longer_timeout_for_mcopy(monkeypatch):
    captured = {}

    def fake_run(argv, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout"))

    monkeypatch.setattr(mtools_client.subprocess, "run", fake_run)

    with pytest.raises(MtoolsTimeoutError):
        mtools_client._run_helper("mcopy", "/dev/sde1", ["a", "::b"])

    assert captured["timeout"] == mtools_client.HELPER_COPY_TIMEOUT_SECONDS


def test_run_helper_uses_the_short_timeout_for_metadata_ops(monkeypatch):
    captured = {}

    def fake_run(argv, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout"))

    monkeypatch.setattr(mtools_client.subprocess, "run", fake_run)

    with pytest.raises(MtoolsTimeoutError):
        mtools_client._run_helper("mdir", "/dev/sde1", ["::"])

    assert captured["timeout"] == mtools_client.HELPER_TIMEOUT_SECONDS


def test_run_helper_raises_on_helper_side_timeout_exit_code(monkeypatch):
    # The helper itself caught a TimeoutExpired around mdir/mcopy/... and
    # reported it as exit code 4 - the client must translate that the
    # same way as its own local subprocess timeout, not as a generic
    # command failure.
    monkeypatch.setattr(
        mtools_client.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=4, stdout="", stderr="TIMEOUT_ERROR: ..."),
    )

    with pytest.raises(MtoolsTimeoutError):
        mtools_client._run_helper("mdir", "/dev/sde1", ["::"])


# -- helper side: main()'s own subprocess.run to mdir/mcopy/... -------------


def test_helper_main_reports_exit_code_4_on_timeout(helper, monkeypatch):
    monkeypatch.setattr(helper, "validate_device", lambda d: d)
    monkeypatch.setattr(helper, "validate_args", lambda op, args, **kwargs: args)

    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(cmd=command, timeout=kwargs.get("timeout"))

    monkeypatch.setattr(helper.subprocess, "run", fake_run)

    code = helper.main(["mtools-gui-helper", "mdir", "/dev/sde1", "::"])

    assert code == 4


def test_helper_lsblk_row_raises_validation_error_on_timeout(helper, monkeypatch):
    def fake_run(*a, **k):
        raise subprocess.TimeoutExpired(cmd=a[0], timeout=k.get("timeout"))

    monkeypatch.setattr(helper.subprocess, "run", fake_run)

    with pytest.raises(helper.ValidationError):
        helper._lsblk_row("/dev/sde1")
