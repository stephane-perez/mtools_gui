"""conftest.py's autouse _pretend_helper_is_installed fixture is what
stops every test constructing a real MainWindow() (test_overwrite_
confirmation.py, test_progress_indicator.py, test_install_button.py)
from hanging on a real, unmocked QMessageBox.exec() when the privileged
helper isn't actually installed on whatever machine runs the tests -
confirmed against a real ~28-minute hang on a fresh GitHub Actions
runner, where the helper was never installed. Locally this went
unnoticed because the developer's own machine happens to have it
installed for real hardware testing. This locks in the fixture's own
masking behavior directly, rather than relying on it only being
exercised incidentally by those other tests.
"""

import os

from mtools_gui.constants import HELPER_INSTALL_PATH


def test_helper_install_path_reports_as_existing_during_tests():
    # Holds regardless of whether the real file is actually present on
    # the machine running the tests - that's the whole point.
    assert os.path.exists(HELPER_INSTALL_PATH) is True


def test_unrelated_paths_are_unaffected_by_the_stub():
    assert os.path.exists("/definitely/does/not/exist/xyz") is False
