import logging
import sys
from contextlib import contextmanager

LOGGER_NAMES = (
    "modules.content_utils",
    "modules.cleanup_utils",
    "modules.unmatched_utils",
    "modules.safety_utils",
    "modules.folder_utils",
    "modules.encora_utils",
    "modules.api_utils",
    "organiser.safe",
)


@contextmanager
def run_logging(log_path: str = "organiser-debug.log"):
    """Configure WARNING+ stderr logging and DEBUG+ file logging for an organiser run."""
    fmt_term = logging.Formatter("\r\033[2K  ║ %(levelname)s [%(name)s] %(message)s")
    fmt_file = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    warn_handler = logging.StreamHandler(sys.stderr)
    warn_handler.setLevel(logging.WARNING)
    warn_handler.setFormatter(fmt_term)

    dbg_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    dbg_handler.setLevel(logging.DEBUG)
    dbg_handler.setFormatter(fmt_file)

    configured = []
    for name in LOGGER_NAMES:
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.addHandler(warn_handler)
        lg.addHandler(dbg_handler)
        lg.setLevel(logging.DEBUG)
        lg.propagate = False
        configured.append(lg)

    try:
        yield
    finally:
        for lg in configured:
            lg.handlers.clear()
        dbg_handler.close()
        warn_handler.close()
