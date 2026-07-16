"""Tests for store-backed evidence verification in proposal validation and guarding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lerim.context import ContextStore
from lerim.skill_stewardship.artifacts import scan_instruction_artifact
from lerim.skill_stewardship.pipeline import guard_proposal
from lerim.skill_stewardship.schemas import AutoApplyPolicy, SkillPatch, SkillProposalDraft
from lerim.skill_stewardship.validation import validate_proposal

ORIGINAL_SKILL_TEXT = "---\nname: demo\ndescription: Demo.\n---\n\nUse evidence.\n"


def _make_record(store: ContextStore, *, title: str, body: str) -> dict[str, Any]:
    """Create a minimal durable record usable as cited evidence in tests."""
    return store.create_record(
        project_id=None,
        session_id=None,
        kind="fact",
        title=title,
        body=body,
        scope_type="workspace",
        scope_id="ws-test",
        scope_label="workspace",
    )


def _scanned_skill(tmp_path: Path) -> tuple[Path, Any]:
    """Write and scan one minimal SKILL.md fixture, returning its base and manifest."""
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(ORIGINAL_SKILL_TEXT, encoding="utf-8")
    base, manifest, _files = scan_instruction_artifact(skill)
    return base, manifest


def test_validate_proposal_rejects_nonexistent_evidence_record(tmp_path: Path) -> None:
    """A patch citing a record id that does not exist in the store fails validation."""
    base, manifest = _scanned_skill(tmp_path)
    store = ContextStore(tmp_path / "context.sqlite3")
    draft = SkillProposalDraft(
        title="Cite missing record",
        summary="Cites a record id that was never created.",
        risk_level="low",
        patches=[
            SkillPatch(
                relative_path="SKILL.md",
                change_type="modify",
                risk="low",
                rationale="Claims support from a record that does not exist.",
                evidence_record_ids=["rec_does_not_exist"],
                before_text=ORIGINAL_SKILL_TEXT,
                after_text=ORIGINAL_SKILL_TEXT + "Keep updates small.\n",
                diff_text="",
            )
        ],
    )

    result = validate_proposal(base_path=base, manifest=manifest, proposal=draft, store=store)

    assert result.ok is False
    assert any("evidence record not found" in error for error in result.errors)


def test_validate_proposal_flags_unsupported_after_text(tmp_path: Path) -> None:
    """A patch whose new text has nothing to do with its cited record fails validation."""
    base, manifest = _scanned_skill(tmp_path)
    store = ContextStore(tmp_path / "context.sqlite3")
    record = _make_record(
        store,
        title="Adopt uv for dependency management",
        body=(
            "Adopt uv and lockfile pinning for all Python dependency installs "
            "to keep environments reproducible."
        ),
    )
    unrelated_addition = (
        "\n## Deploys\n\nDeploy the frontend using blue-green Kubernetes canary "
        "rollouts with the Istio service mesh.\n"
    )
    draft = SkillProposalDraft(
        title="Add deployment guidance",
        summary="Adds unrelated deployment guidance.",
        risk_level="low",
        patches=[
            SkillPatch(
                relative_path="SKILL.md",
                change_type="modify",
                risk="low",
                rationale="Claims support from a dependency-management record.",
                evidence_record_ids=[record["record_id"]],
                before_text=ORIGINAL_SKILL_TEXT,
                after_text=ORIGINAL_SKILL_TEXT + unrelated_addition,
                diff_text="",
            )
        ],
    )

    result = validate_proposal(base_path=base, manifest=manifest, proposal=draft, store=store)

    assert result.ok is False
    assert any("not supported by cited evidence records" in error for error in result.errors)


def test_validate_proposal_accepts_supported_after_text(tmp_path: Path) -> None:
    """A patch whose new text is well supported by its cited record still passes."""
    base, manifest = _scanned_skill(tmp_path)
    store = ContextStore(tmp_path / "context.sqlite3")
    record = _make_record(
        store,
        title="Adopt tenacity for API retries",
        body=(
            "Use tenacity with exponential backoff and jitter for all outbound API "
            "retries so we survive upstream rate limits."
        ),
    )
    supported_addition = (
        "\n## Retries\n\nUse tenacity with exponential backoff and jitter when "
        "retrying API calls.\n"
    )
    draft = SkillProposalDraft(
        title="Add retry guidance",
        summary="Documents the retry approach already used in the codebase.",
        risk_level="low",
        patches=[
            SkillPatch(
                relative_path="SKILL.md",
                change_type="modify",
                risk="low",
                rationale="Supported by the tenacity retry record.",
                evidence_record_ids=[record["record_id"]],
                before_text=ORIGINAL_SKILL_TEXT,
                after_text=ORIGINAL_SKILL_TEXT + supported_addition,
                diff_text="",
            )
        ],
    )

    result = validate_proposal(base_path=base, manifest=manifest, proposal=draft, store=store)

    assert result.ok is True


def test_validate_proposal_without_store_skips_evidence_checks(tmp_path: Path) -> None:
    """Omitting store keeps validation exactly as before: no existence or support checks."""
    base, manifest = _scanned_skill(tmp_path)
    draft = SkillProposalDraft(
        title="Cite missing record",
        summary="Cites a record id that was never created.",
        risk_level="low",
        patches=[
            SkillPatch(
                relative_path="SKILL.md",
                change_type="modify",
                risk="low",
                rationale="Would fail if evidence were checked.",
                evidence_record_ids=["rec_does_not_exist"],
                before_text=ORIGINAL_SKILL_TEXT,
                after_text=ORIGINAL_SKILL_TEXT + "Keep updates small.\n",
                diff_text="",
            )
        ],
    )

    result = validate_proposal(base_path=base, manifest=manifest, proposal=draft)

    assert result.ok is True


def test_guard_proposal_rejects_nonexistent_evidence_record(tmp_path: Path) -> None:
    """The guard's upgraded evidence gate also rejects citing a record that does not exist."""
    store = ContextStore(tmp_path / "context.sqlite3")
    draft = SkillProposalDraft(
        title="Cite missing record",
        summary="Cites a record id that was never created.",
        risk_level="low",
        patches=[
            SkillPatch(
                relative_path="SKILL.md",
                change_type="modify",
                risk="low",
                rationale="Would be caught by the upgraded guard.",
                evidence_record_ids=["rec_does_not_exist"],
                after_text="Some new guidance.\n",
                diff_text="",
            )
        ],
    )

    result = guard_proposal(draft=draft, policy=AutoApplyPolicy(enabled=True), store=store)

    assert result.accepted is False
    assert result.auto_apply_eligible is False
    assert any("evidence record not found" in reason for reason in result.reasons)


def test_guard_proposal_without_store_only_checks_presence() -> None:
    """Omitting store keeps the guard's evidence gate presence-only, as before."""
    draft = SkillProposalDraft(
        title="Cite missing record",
        summary="Cites a record id that was never created.",
        risk_level="low",
        patches=[
            SkillPatch(
                relative_path="SKILL.md",
                change_type="modify",
                risk="low",
                rationale="Would fail if evidence were checked.",
                evidence_record_ids=["rec_does_not_exist"],
                after_text="Some new guidance.\n",
                diff_text="",
            )
        ],
    )

    result = guard_proposal(draft=draft, policy=AutoApplyPolicy(enabled=True))

    assert result.accepted is True
