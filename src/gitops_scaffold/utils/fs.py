"""Small filesystem helpers used by generators and the CLI."""

from __future__ import annotations

from pathlib import Path


def ensure_directory(path: Path) -> Path:
    """Create ``path`` (and parents) if it doesn't already exist."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_file(path: Path, content: str, *, overwrite: bool = False) -> Path:
    """Write ``content`` to ``path``, refusing to clobber existing files by default."""
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    ensure_directory(path.parent)
    path.write_text(content)
    return path
