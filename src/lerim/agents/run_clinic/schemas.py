"""Structured model schemas for Run Clinic diagnosis."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RunClinicFindingDraft(BaseModel):
    """One evidence-backed recurring project pattern."""

    title: str = Field(description="Short finding title.")
    pattern_type: str = Field(description="Pattern category such as context_gap, verification_gap, friction, or strength.")
    severity: str = Field(description="low, medium, or high.")
    confidence: str = Field(description="low, medium, or high.")
    summary: str = Field(description="Plain-language diagnosis grounded in supplied records.")
    why_it_matters: str = Field(description="Impact on future agent work or product quality.")
    evidence_record_ids: list[str] = Field(description="Exact record IDs copied from supplied records or versions.")


class RunClinicActionDraft(BaseModel):
    """One recommended improvement action."""

    title: str = Field(description="Short action title.")
    action_type: str = Field(description="Action class such as skill_update, context_record, eval_asset, product_ui, or workflow.")
    priority: str = Field(description="low, medium, or high.")
    summary: str = Field(description="Concrete action the user can decide to take.")
    evidence_record_ids: list[str] = Field(description="Exact record IDs copied from supplied records or versions.")


class RunClinicReportOutput(BaseModel):
    """Run Clinic structured diagnosis output."""

    headline: str = Field(description="One sentence project diagnosis.")
    readiness_score: int = Field(description="0-100 confidence/readiness score for this Clinic.")
    summary: list[str] = Field(default_factory=list)
    findings: list[RunClinicFindingDraft] = Field(default_factory=list)
    recommended_actions: list[RunClinicActionDraft] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
