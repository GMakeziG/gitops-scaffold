"""The shared Jinja2 environment every generator renders through.

``StrictUndefined`` means a template referencing a variable no generator
ever populates fails loudly at render time instead of silently rendering
blank — the same "never silently guess" principle applied to the templates
themselves.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
    undefined=StrictUndefined,
)


def render_template(name: str, **context: object) -> str:
    """Renders ``templates/<name>`` with ``context``."""
    return _env.get_template(name).render(**context)
