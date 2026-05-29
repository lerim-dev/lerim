"""Structured model schemas for Working Memory compilation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkingMemoryLineDraft(BaseModel):
    """One short handoff line with exact source record IDs."""

    text: str = Field(description="Compact handoff statement without inline citations.")
    record_ids: list[str] = Field(
        description="Exact record IDs copied from the supplied records."
    )


class WorkingMemoryDraftOutput(BaseModel):
    """Short-term Working Memory model output."""

    summary: list[WorkingMemoryLineDraft] = Field(default_factory=list)
    start_here: list[WorkingMemoryLineDraft] = Field(default_factory=list)
    recent_changes: list[WorkingMemoryLineDraft] = Field(default_factory=list)
    current_context: list[WorkingMemoryLineDraft] = Field(default_factory=list)
    open_questions: list[WorkingMemoryLineDraft] = Field(default_factory=list)
