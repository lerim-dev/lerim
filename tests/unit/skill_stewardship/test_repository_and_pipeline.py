"""Tests for skill stewardship persistence and deterministic guards."""

from __future__ import annotations

from pathlib import Path

from lerim.context import ContextStore
from lerim.skill_stewardship.artifacts import scan_instruction_artifact
from lerim.skill_stewardship.pipeline import guard_proposal, hydrate_patch_text
from lerim.skill_stewardship.repository import SkillStewardshipRepository
from lerim.skill_stewardship.schemas import AutoApplyPolicy, SkillPatch, SkillProposalDraft
from lerim.skill_stewardship.validation import validate_proposal


def test_repository_registers_target_and_files(tmp_path: Path) -> None:
    """Target registration persists a manifest and tracked files."""
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\nname: demo\ndescription: Demo.\n---\n\nUse evidence.\n", encoding="utf-8")
    base, manifest, files = scan_instruction_artifact(skill)
    repository = SkillStewardshipRepository(ContextStore(tmp_path / "context.sqlite3"))

    target = repository.upsert_target(
        name="demo",
        path=base,
        description="Improve demo",
        manifest=manifest,
        files=files,
    )

    assert repository.get_target(target.target_id).name == "demo"
    assert repository.target_files(target.target_id)[0].relative_path == "SKILL.md"


def test_guard_allows_low_risk_auto_apply_with_evidence() -> None:
    """Low-risk bounded edits can become auto-apply eligible when policy allows it."""
    draft = SkillProposalDraft(
        title="Add simplification guard",
        summary="Adds one reusable simplification reminder.",
        risk_level="low",
        patches=[
            SkillPatch(
                relative_path="references/simplification.md",
                change_type="create",
                risk="low",
                rationale="Supported by repeated records.",
                evidence_record_ids=["rec_123"],
                after_text="Avoid pass-through wrappers that only call one function.\n",
                diff_text="",
            )
        ],
    )

    result = guard_proposal(draft=draft, policy=AutoApplyPolicy(enabled=True))

    assert result.accepted is True
    assert result.auto_apply_eligible is True


def test_guard_blocks_missing_evidence() -> None:
    """A patch without record evidence stays out of the review path."""
    draft = SkillProposalDraft(
        title="Unsupported change",
        summary="No evidence.",
        risk_level="low",
        patches=[
            SkillPatch(
                relative_path="SKILL.md",
                change_type="modify",
                risk="low",
                rationale="Unsupported.",
                evidence_record_ids=[],
                after_text="text",
                diff_text="",
            )
        ],
    )

    result = guard_proposal(draft=draft, policy=AutoApplyPolicy(enabled=True))

    assert result.accepted is False
    assert result.auto_apply_eligible is False


def test_validation_rejects_frontmatter_removal(tmp_path: Path) -> None:
    """Entry file edits must preserve existing YAML frontmatter."""
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\nname: demo\ndescription: Demo.\n---\n\n# Demo\n", encoding="utf-8")
    base, manifest, _files = scan_instruction_artifact(skill)
    draft = SkillProposalDraft(
        title="Bad edit",
        summary="Drops metadata.",
        risk_level="low",
        patches=[
            SkillPatch(
                relative_path="SKILL.md",
                change_type="modify",
                risk="low",
                rationale="Bad.",
                evidence_record_ids=["rec_1"],
                before_text="---\nname: demo\ndescription: Demo.\n---\n\n# Demo\n",
                after_text="# Demo\n\nUpdated.\n",
                diff_text="",
            )
        ],
    )

    result = validate_proposal(base_path=base, manifest=manifest, proposal=draft)

    assert result.ok is False
    assert any("frontmatter" in error for error in result.errors)


def test_hydrate_patch_text_recomputes_before_text_and_diff(tmp_path: Path) -> None:
    """Edited proposals get fresh file content and unified diffs before validation."""
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("Use simple code.\n", encoding="utf-8")
    draft = SkillProposalDraft(
        title="Add wrapper guidance",
        summary="Adds wrapper review guidance.",
        risk_level="low",
        patches=[
            SkillPatch(
                relative_path="SKILL.md",
                change_type="modify",
                risk="low",
                rationale="Supported by record.",
                evidence_record_ids=["rec_1"],
                after_text="Use simple code.\nRemove wrappers that only forward.\n",
                diff_text="stale",
            )
        ],
    )

    hydrated = hydrate_patch_text(base=skill, draft=draft)

    assert hydrated.patches[0].before_text == "Use simple code.\n"
    assert "--- a/SKILL.md" in hydrated.patches[0].diff_text
    assert "+Remove wrappers that only forward." in hydrated.patches[0].diff_text
