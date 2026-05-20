"""Public types for the context-answerer agent."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContextAnswerResult(BaseModel):
    """Structured output for the context-answerer flow."""

    answer: str = Field(description="Answer text with record citations when available")
    supporting_record_ids: list[str] = Field(
        default_factory=list,
        description="Validated context record ids that support the answer",
    )
