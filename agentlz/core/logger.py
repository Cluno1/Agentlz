import logging
from typing import Optional


def setup_logging(level: Optional[str] = "INFO") -> logging.Logger:
    """Configure basic logging and return a package logger."""
    logging.basicConfig(
        level=getattr(logging, (level or "INFO").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return logging.getLogger("agentlz")