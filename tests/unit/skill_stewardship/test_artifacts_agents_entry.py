"""Tests for AGENTS.md entry-caliber treatment when co-located with SKILL.md."""

from __future__ import annotations

from pathlib import Path

from lerim.skill_stewardship.artifacts import scan_instruction_artifact


def test_agents_md_gets_entry_role_alongside_skill_md(tmp_path: Path) -> None:
    """A directory with both SKILL.md and AGENTS.md treats both as entry-caliber."""
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo.\n---\n\nUse small updates.\n",
        encoding="utf-8",
    )
    (skill / "AGENTS.md").write_text(
        "# Agent Notes\n\nFollow local conventions.\n",
        encoding="utf-8",
    )

    _base, manifest, files = scan_instruction_artifact(skill)

    entry_paths = {item.relative_path for item in files if item.file_role == "entry"}
    assert entry_paths == {"SKILL.md", "AGENTS.md"}
    # The singular manifest entry pointer stays SKILL.md; only per-file role is upgraded.
    assert manifest.entry_file == "SKILL.md"
    assert "AGENTS.md" in manifest.instruction_files


def test_agents_md_alone_keeps_existing_single_entry_behavior(tmp_path: Path) -> None:
    """A directory with only AGENTS.md keeps its existing single-entry behavior."""
    only_agents = tmp_path / "only-agents"
    only_agents.mkdir()
    (only_agents / "AGENTS.md").write_text(
        "# Project Instructions\n\nRun tests.\n",
        encoding="utf-8",
    )

    _base, manifest, files = scan_instruction_artifact(only_agents)

    entry_paths = {item.relative_path for item in files if item.file_role == "entry"}
    assert entry_paths == {"AGENTS.md"}
    assert manifest.entry_file == "AGENTS.md"


def test_skill_md_alone_keeps_existing_single_entry_behavior(tmp_path: Path) -> None:
    """A directory with only SKILL.md keeps its existing single-entry behavior."""
    skill_only = tmp_path / "skill-only"
    skill_only.mkdir()
    (skill_only / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo.\n---\n\nUse small updates.\n",
        encoding="utf-8",
    )

    _base, manifest, files = scan_instruction_artifact(skill_only)

    entry_paths = {item.relative_path for item in files if item.file_role == "entry"}
    assert entry_paths == {"SKILL.md"}
    assert manifest.entry_file == "SKILL.md"


def test_agents_md_in_different_directory_is_not_entry_caliber(tmp_path: Path) -> None:
    """An AGENTS.md that is not a direct sibling of SKILL.md is not promoted."""
    skill = tmp_path / "skill"
    references = skill / "references"
    references.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo.\n---\n\nUse small updates.\n",
        encoding="utf-8",
    )
    (references / "AGENTS.md").write_text(
        "# Nested notes\n\nNot a sibling entry file.\n",
        encoding="utf-8",
    )

    _base, manifest, files = scan_instruction_artifact(skill)

    entry_paths = {item.relative_path for item in files if item.file_role == "entry"}
    assert entry_paths == {"SKILL.md"}
    assert manifest.entry_file == "SKILL.md"
