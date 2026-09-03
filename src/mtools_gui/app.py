from __future__ import annotations

import logging
import os
import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    # MTOOLS_GUI_DEBUG=1 mtools-gui for verbose (DEBUG) output, e.g. the
    # exact pkexec/mtools command lines - handy when diagnosing a failed
    # or crashing DOS-side operation.
    level = logging.DEBUG if os.environ.get("MTOOLS_GUI_DEBUG") else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    _configure_logging()
    logger.info("Starting mtools_gui")
    app = QApplication(sys.argv)
    app.setApplicationName("mtools_gui")
    app.setOrganizationName("mtools_gui")
    window = MainWindow()
    window.show()
    exit_code = app.exec()
    logger.info("Closing mtools_gui (exit code %s)", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
