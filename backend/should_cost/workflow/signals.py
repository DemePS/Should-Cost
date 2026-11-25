"""NeedsInputSignal lives in its own module (not in engine.py) so step modules
(workflow/steps/*.py) can raise it without importing engine.py, which itself imports
those step modules — avoiding a circular import.
"""

from __future__ import annotations

from should_cost.models.job import NeedsInputReason


class NeedsInputSignal(Exception):
    def __init__(self, reason: NeedsInputReason, question: str, context: str | None = None) -> None:
        super().__init__(question)
        self.reason = reason
        self.question = question
        self.context = context
