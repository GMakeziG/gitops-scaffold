"""Rich-backed logging configuration."""

from __future__ import annotations

import logging

from rich.logging import RichHandler


def configure_logging(verbose: bool = False) -> None:
    """Configure the root logger to render through Rich.

    Idempotent-ish for CLI purposes: intended to be called once at startup.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
        force=True,
    )
