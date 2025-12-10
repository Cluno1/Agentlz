import logging
import os
import sys
from typing import Optional


class _ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m",   # Cyan
        "INFO": "\033[32m",    # Green
        "WARNING": "\033[33m", # Yellow
        "ERROR": "\033[31m",   # Red
        "CRITICAL": "\033[35m"  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, fmt: str, datefmt: Optional[str], use_color: bool, prefix: Optional[str], suffix: Optional[str]):
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.use_color = bool(use_color)
        self.prefix = prefix or ""
        self.suffix = suffix or ""

    def format(self, record: logging.LogRecord) -> str:
        orig_levelname = record.levelname
        if self.use_color:
            color = self.COLORS.get(orig_levelname, "")
            if color:
                record.levelname = f"{color}{orig_levelname}{self.RESET}"
        try:
            base = super().format(record)
        finally:
            record.levelname = orig_levelname
        if self.prefix:
            base = f"{self.prefix} {base}"
        if self.suffix:
            base = f"{base} {self.suffix}"
        return base


def setup_logging(
    level: Optional[str] = "INFO",
    name: str = "agentlz",
    enable_color: bool = True,
    prefix: Optional[str] = None,
    suffix: Optional[str] = None,
    fmt: Optional[str] = None,
    datefmt: Optional[str] = None,
) -> logging.Logger:
    lvl = getattr(logging, (level or "INFO").upper(), logging.INFO)
    logger = logging.getLogger(name)
    logger.setLevel(lvl)
    if not any(getattr(h, "_agentlz_handler", False) for h in logger.handlers):
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setLevel(lvl)
        is_tty = hasattr(handler.stream, "isatty") and handler.stream.isatty()
        no_color = os.environ.get("NO_COLOR") is not None
        force_color = os.environ.get("FORCE_COLOR") is not None
        use_color = bool(enable_color) and (force_color or (is_tty and not no_color))
        _fmt = fmt or "%(asctime)s %(levelname)s %(name)s: %(message)s"
        formatter = _ColoredFormatter(fmt=_fmt, datefmt=datefmt, use_color=use_color, prefix=prefix, suffix=suffix)
        handler.setFormatter(formatter)
        handler._agentlz_handler = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
        logger.propagate = False
    return logger