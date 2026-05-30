"""Deterministic validation for proposed instruction artifact patches."""

from __future__ import annotations

from pathlib import Path

import yaml

from lerim.skill_stewardship.schemas import ArtifactManifest, SkillProposalDraft, ValidationResult


def validate_proposal(
    *,
    base_path: Path,
    manifest: ArtifactManifest,
    proposal: SkillProposalDraft,
) -> ValidationResult:
    """Validate proposal shape, paths, frontmatter, and artifact constraints."""
    checks: list[str] = []
    errors: list[str] = []
    base = base_path.resolve()
    changed_files = {patch.relative_path for patch in proposal.patches}
    if not proposal.patches:
        return ValidationResult(ok=True, checks=["abstained_no_patch"], errors=[])
    checks.append("has_patch")
    for patch in proposal.patches:
        _validate_patch_path(base, patch.relative_path, errors)
        if not patch.evidence_record_ids:
            errors.append(f"{patch.relative_path}: missing evidence_record_ids")
        if patch.change_type == "create" and not _new_file_allowed(manifest, patch.relative_path):
            errors.append(f"{patch.relative_path}: new file is not allowed for {manifest.target_type}")
        if patch.relative_path == manifest.entry_file:
            if str(patch.before_text or "").startswith("---\n") and not patch.after_text.startswith("---\n"):
                errors.append(f"{manifest.entry_file}: must preserve existing YAML frontmatter")
            _validate_entry_text(manifest, patch.after_text, errors)
    if len(changed_files) <= 3:
        checks.append("bounded_changed_files")
    else:
        errors.append("proposal changes too many files for one review")
    return ValidationResult(ok=not errors, checks=checks, errors=errors)


def _validate_patch_path(base: Path, relative_path: str, errors: list[str]) -> None:
    """Reject absolute paths and path traversal."""
    path = Path(relative_path)
    if path.is_absolute():
        errors.append(f"{relative_path}: absolute paths are not allowed")
        return
    resolved = (base / path).resolve()
    if base != resolved and base not in resolved.parents:
        errors.append(f"{relative_path}: path escapes target")


def _validate_entry_text(manifest: ArtifactManifest, text: str, errors: list[str]) -> None:
    """Check required frontmatter for entry-file edits."""
    if not manifest.required_frontmatter:
        return
    if not text.startswith("---\n"):
        errors.append(f"{manifest.entry_file}: missing YAML frontmatter")
        return
    end = text.find("\n---", 4)
    if end < 0:
        errors.append(f"{manifest.entry_file}: unterminated YAML frontmatter")
        return
    parsed = yaml.safe_load(text[4:end]) or {}
    if not isinstance(parsed, dict):
        errors.append(f"{manifest.entry_file}: frontmatter must be a mapping")
        return
    for key in manifest.required_frontmatter:
        if not str(parsed.get(key) or "").strip():
            errors.append(f"{manifest.entry_file}: missing required frontmatter field {key}")


def _new_file_allowed(manifest: ArtifactManifest, relative_path: str) -> bool:
    """Return whether a target type supports creating this file."""
    first = Path(relative_path).parts[0] if Path(relative_path).parts else ""
    if manifest.target_type in {"codex_skill", "claude_skill", "agent_skill"}:
        return first in {"references", "reference", "examples"}
    if manifest.target_type == "cline_rules":
        return relative_path.endswith((".md", ".txt"))
    if manifest.target_type == "gemini_context":
        return relative_path.endswith((".md", ".txt"))
    return relative_path in manifest.instruction_files
