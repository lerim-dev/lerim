"""Deterministic validation for proposed instruction artifact patches."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

import yaml

from lerim.context import ContextStore
from lerim.skill_stewardship.schemas import ArtifactManifest, SkillPatch, SkillProposalDraft, ValidationResult

_MEANINGFUL_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_STOPWORDS = {
    "this", "that", "with", "from", "have", "will", "your", "their",
    "these", "those", "into", "when", "than", "then", "also", "such",
    "each", "more", "most", "some", "only", "just", "must", "should",
    "would", "could", "about", "which", "while", "where", "there",
    "been", "being", "does", "done", "make", "made", "used", "using",
    "text", "file", "files",
}
_QUOTE_PHRASE_SIZE = 4
_SUPPORT_OVERLAP_THRESHOLD = 0.25


def validate_proposal(
    *,
    base_path: Path,
    manifest: ArtifactManifest,
    proposal: SkillProposalDraft,
    store: ContextStore | None = None,
) -> ValidationResult:
    """Validate proposal shape, paths, frontmatter, artifact, and evidence constraints.

    ``store`` is optional and backward compatible: when omitted, validation behaves
    exactly as before. When provided, each patch's cited evidence records must exist
    and the patch's newly introduced text must show meaningful support from them.
    """
    checks: list[str] = []
    errors: list[str] = []
    base = base_path.resolve()
    changed_files: set[str] = set()
    instruction_files = set(manifest.instruction_files or [manifest.entry_file])
    if not proposal.patches:
        return ValidationResult(ok=True, checks=["abstained_no_patch"], errors=[])
    checks.append("has_patch")
    for patch in proposal.patches:
        if patch.relative_path in changed_files:
            errors.append(f"{patch.relative_path}: duplicate patch path")
            continue
        changed_files.add(patch.relative_path)
        _validate_patch_path(base, patch.relative_path, errors)
        target_file = (base / patch.relative_path).resolve()
        if not path_belongs_to_manifest(manifest, patch.relative_path, change_type=patch.change_type):
            errors.append(f"{patch.relative_path}: path is not part of the registered instruction artifact")
        if target_file.exists() and patch.change_type == "create":
            errors.append(f"{patch.relative_path}: create patch targets an existing file")
        if not target_file.exists():
            if patch.change_type != "create":
                errors.append(f"{patch.relative_path}: missing file must use create change_type")
            if not _new_file_allowed(manifest, patch.relative_path):
                errors.append(f"{patch.relative_path}: new file is not allowed for {manifest.target_type}")
        if not patch.evidence_record_ids:
            errors.append(f"{patch.relative_path}: missing evidence_record_ids")
        elif store is not None:
            errors.extend(patch_evidence_errors(store=store, patch=patch))
        if patch.relative_path == manifest.entry_file:
            if frontmatter_block(str(patch.before_text or "")) and not frontmatter_block(patch.after_text):
                errors.append(f"{manifest.entry_file}: must preserve existing YAML frontmatter")
            _validate_entry_text(manifest, patch.after_text, errors)
        if patch.relative_path in instruction_files:
            _validate_instruction_body(patch.relative_path, patch.after_text, errors)
    if len(changed_files) <= 3:
        checks.append("bounded_changed_files")
    else:
        errors.append("proposal changes too many files for one review")
    if store is not None:
        checks.append("evidence_checked")
    return ValidationResult(ok=not errors, checks=checks, errors=errors)


def patch_evidence_errors(*, store: ContextStore, patch: SkillPatch) -> list[str]:
    """Return evidence problems for one patch: missing records or unsupported text.

    Each cited record id is looked up with ``store.fetch_record``. A missing record
    is reported directly. When at least one cited record exists, the patch's newly
    introduced text (the diff for a modify patch, the whole file for a create patch)
    must share a meaningful token or quoted phrase with the cited records' combined
    text; otherwise the patch is reported as unsupported. Callers that also want a
    bare "no evidence cited" error should check ``patch.evidence_record_ids`` first,
    since this function assumes there is at least one id to look up.
    """
    problems: list[str] = []
    evidence_texts: list[str] = []
    for record_id in patch.evidence_record_ids:
        record = store.fetch_record(record_id)
        if record is None:
            problems.append(f"{patch.relative_path}: evidence record not found: {record_id}")
            continue
        evidence_texts.append(_record_text(record))
    if not evidence_texts:
        return problems
    new_text = _patch_new_text(patch)
    if not _text_supported_by_evidence(new_text, "\n".join(evidence_texts)):
        problems.append(f"{patch.relative_path}: after_text is not supported by cited evidence records")
    return problems


def _record_text(record: dict[str, object]) -> str:
    """Flatten one fetched record's narrative fields into a single text blob."""
    fields = (
        "title",
        "body",
        "decision",
        "why",
        "alternatives",
        "consequences",
        "user_intent",
        "what_happened",
        "outcomes",
    )
    return "\n".join(str(record.get(field) or "") for field in fields)


def _patch_new_text(patch: SkillPatch) -> str:
    """Return the text a patch newly introduces, for evidence-support checks."""
    before = patch.before_text or ""
    if patch.change_type == "create" or not before.strip():
        return patch.after_text
    return _added_lines(before, patch.after_text)


def _added_lines(before: str, after: str) -> str:
    """Return only the lines a modify patch adds or changes, via a line-level diff."""
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    matcher = SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    added = [
        after_lines[index]
        for tag, _i1, _i2, j1, j2 in matcher.get_opcodes()
        if tag in {"insert", "replace"}
        for index in range(j1, j2)
    ]
    return "\n".join(added)


def _text_supported_by_evidence(text: str, evidence_text: str) -> bool:
    """Return whether text shares a meaningful quote or enough tokens with evidence_text."""
    candidate_tokens = _meaningful_tokens(text)
    if not candidate_tokens:
        return True
    evidence_tokens = _meaningful_tokens(evidence_text)
    if not evidence_tokens:
        return False
    if _quote_phrases(text) & _quote_phrases(evidence_text):
        return True
    overlap = candidate_tokens & evidence_tokens
    return len(overlap) / len(candidate_tokens) >= _SUPPORT_OVERLAP_THRESHOLD


def _meaningful_tokens(text: str) -> set[str]:
    """Return lowercase content words of length 4+, with common stopwords removed."""
    tokens = {match.group(0).lower() for match in _MEANINGFUL_TOKEN.finditer(text)}
    return {token for token in tokens if len(token) >= 4 and token not in _STOPWORDS}


def _quote_phrases(text: str) -> set[str]:
    """Return normalized 4-word phrases from text for verbatim quote-overlap checks."""
    words = [match.group(0).lower() for match in _MEANINGFUL_TOKEN.finditer(text)]
    if len(words) < _QUOTE_PHRASE_SIZE:
        return set()
    return {
        " ".join(words[index : index + _QUOTE_PHRASE_SIZE])
        for index in range(len(words) - _QUOTE_PHRASE_SIZE + 1)
    }


def frontmatter_block(text: str) -> str | None:
    """Return the complete YAML frontmatter block from text when present."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end < 0:
        return None
    return text[: end + 4]


def _validate_patch_path(base: Path, relative_path: str, errors: list[str]) -> None:
    """Reject absolute paths and path traversal."""
    path = Path(relative_path)
    if path.is_absolute():
        errors.append(f"{relative_path}: absolute paths are not allowed")
        return
    if any(part in {"", ".", ".."} for part in path.parts):
        errors.append(f"{relative_path}: relative path components are not allowed")
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


def _validate_instruction_body(relative_path: str, text: str, errors: list[str]) -> None:
    """Require instruction files to retain human-readable guidance."""
    body = text
    frontmatter = frontmatter_block(text)
    if frontmatter:
        body = text[len(frontmatter):]
    if not body.strip():
        errors.append(f"{relative_path}: instruction body cannot be empty")


def _new_file_allowed(manifest: ArtifactManifest, relative_path: str) -> bool:
    """Return whether a target type supports creating this file."""
    first = Path(relative_path).parts[0] if Path(relative_path).parts else ""
    if manifest.target_type in {"codex_skill", "claude_skill", "agent_skill"}:
        return first in {"references", "reference", "examples"}
    return False


def path_belongs_to_manifest(manifest: ArtifactManifest, relative_path: str, *, change_type: str) -> bool:
    """Return whether a patch path is inside the scanned artifact surface."""
    tracked = {
        manifest.entry_file,
        *manifest.instruction_files,
        *manifest.supporting_files,
    }
    if relative_path in tracked:
        return True
    return change_type == "create" and _new_file_allowed(manifest, relative_path)
