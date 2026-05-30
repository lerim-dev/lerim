"""Tests for instruction artifact scanning."""

from __future__ import annotations

from pathlib import Path

from lerim.skill_stewardship.artifacts import scan_instruction_artifact


def test_scans_codex_skill_manifest(tmp_path: Path) -> None:
    """Codex-style skills expose SKILL.md plus standard support files."""
    skill = tmp_path / ".agents" / "skills" / "clean-code"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: clean-code\ndescription: Keep code simple.\n---\n\nUse small functions.\n",
        encoding="utf-8",
    )
    (skill / "references" / "simplification.md").write_text("Avoid pass-through wrappers.\n", encoding="utf-8")

    base, manifest, files = scan_instruction_artifact(skill)

    assert base == skill
    assert manifest.target_type == "codex_skill"
    assert manifest.entry_file == "SKILL.md"
    assert "name" in manifest.required_frontmatter
    assert {item.relative_path for item in files} == {"SKILL.md", "references/simplification.md"}


def test_scans_plain_agents_file(tmp_path: Path) -> None:
    """A standalone AGENTS.md is treated as a plain instruction target."""
    path = tmp_path / "AGENTS.md"
    path.write_text("# Project Instructions\n\nRun tests before finishing.\n", encoding="utf-8")

    base, manifest, files = scan_instruction_artifact(path)

    assert base == tmp_path
    assert manifest.target_type == "agents_md"
    assert manifest.entry_file == "AGENTS.md"
    assert files[0].relative_path == "AGENTS.md"

