"""Logging set-up (standard library ``logging``).

Messages go to standard error with a UTC ISO 8601 timestamp, so that they can be kept by a
scheduler. Verbosity: warnings only by default, ``-v`` for progress, ``-vv`` for details.
"""

from __future__ import annotations

import logging
import time

LOGGER_NAME = "data_automation"
FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class UtcFormatter(logging.Formatter):
    converter = time.gmtime

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802 - logging API
        return time.strftime("%Y-%m-%dT%H:%M:%S", self.converter(record.created)) + f".{int(record.msecs):03d}Z"


def configure_logging(verbosity: int = 0) -> logging.Logger:
    """Configure the package logger; repeated calls replace the previous handler."""
    level = logging.WARNING if verbosity <= 0 else logging.INFO if verbosity == 1 else logging.DEBUG
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.setFormatter(UtcFormatter(FORMAT))
    handler.setLevel(level)  # the console shows what was asked for...
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)  # ...while run logs (run.log) still receive INFO messages
    logger.propagate = False
    return logger


class LfFileHandler(logging.FileHandler):
    """File handler writing LF line endings on every system, like the other report files."""

    def _open(self):  # noqa: ANN202 - logging API
        return open(self.baseFilename, self.mode, encoding=self.encoding, errors=self.errors, newline="\n")  # noqa: SIM115
