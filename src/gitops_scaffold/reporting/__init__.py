"""Human-readable rendering of analysis results.

This is the layer behind the "confidence report" the ``analyze`` and
``generate`` commands print: a checklist-style summary plus an overall
confidence percentage.
"""

from __future__ import annotations

from gitops_scaffold.reporting.report import Reporter

__all__ = ["Reporter"]
