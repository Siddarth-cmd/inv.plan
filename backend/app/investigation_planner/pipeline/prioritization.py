"""
Prioritization Stage.

Scores and sorts investigation questions by priority.
Priority considers: severity of linked red flags, evidence availability, 
investigation impact, and dependency implications.
"""
from __future__ import annotations

from typing import List

from ..config.taxonomy import Priority
from ..schemas.question import InvestigationQuestion

_PRIORITY_ORDER = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}


def prioritize_questions(questions: List[InvestigationQuestion]) -> List[InvestigationQuestion]:
    """Stage 9 – Sort questions by priority (HIGH → MEDIUM → LOW)."""
    return sorted(questions, key=lambda q: _PRIORITY_ORDER.get(q.priority, 3))
