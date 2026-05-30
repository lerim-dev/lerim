"""Apply approved instruction proposal patches with snapshots."""

from __future__ import annotations

import hashlib
from pathlib import Path

from lerim.skill_stewardship.repository import SkillStewardshipRepository, utc_now
from lerim.skill_stewardship.schemas import SkillProposal, SkillProposalDraft


def apply_proposal(
    *,
    repository: SkillStewardshipRepository,
    proposal: SkillProposal,
    applied_by: str,
) -> SkillProposal:
    """Apply a persisted proposal after review or auto-apply guard approval."""
    target = repository.get_target(proposal.target_id)
    base = Path(target.path).expanduser().resolve()
    if base.is_file():
        base = base.parent
    draft = SkillProposalDraft.model_validate(proposal.patch_json)
    snapshot_root = _snapshot_root(repository.context_store.db_path.parent, proposal.proposal_id)
    for patch in draft.patches:
        target_file = _safe_child(base, patch.relative_path)
        before_hash = _hash_text(target_file.read_text(encoding="utf-8", errors="replace")) if target_file.exists() else None
        snapshot_path = None
        if target_file.exists():
            snapshot_path = str(_write_snapshot(snapshot_root, patch.relative_path, target_file))
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(patch.after_text, encoding="utf-8")
        after_hash = _hash_text(patch.after_text)
        repository.save_applied_version(
            target_id=target.target_id,
            proposal_id=proposal.proposal_id,
            relative_path=patch.relative_path,
            before_hash=before_hash,
            after_hash=after_hash,
            snapshot_path=snapshot_path,
            applied_by=applied_by,
        )
    return repository.set_proposal_status(proposal.proposal_id, "applied")


def _snapshot_root(base: Path, proposal_id: str) -> Path:
    """Return the snapshot directory for one proposal application."""
    return base / "skill-snapshots" / proposal_id / utc_now().replace(":", "-")


def _write_snapshot(snapshot_root: Path, relative_path: str, target_file: Path) -> Path:
    """Copy one before-file into the snapshot folder."""
    snapshot_path = _safe_child(snapshot_root, relative_path)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_bytes(target_file.read_bytes())
    return snapshot_path


def _safe_child(base: Path, relative_path: str) -> Path:
    """Resolve a child path and reject traversal outside base."""
    resolved = (base / relative_path).resolve()
    if base != resolved and base not in resolved.parents:
        raise ValueError(f"path escapes instruction target: {relative_path}")
    return resolved


def _hash_text(text: str) -> str:
    """Hash file text for version metadata."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
