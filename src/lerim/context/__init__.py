"""Public context-store API for Lerim's DB-only architecture."""

from lerim.context.embedding import EMBEDDING_DIMS, EMBEDDING_MODEL_NAME, embed_text
from lerim.context.project_identity import ProjectIdentity, resolve_project_identity
from lerim.context.store import (
    ALLOWED_DOMAINS,
    ALLOWED_KINDS,
    ALLOWED_RELATIONS,
    ContextStore,
    SearchHit,
    render_content_md,
)

__all__ = [
    "ALLOWED_DOMAINS",
    "ALLOWED_KINDS",
    "ALLOWED_RELATIONS",
    "ContextStore",
    "EMBEDDING_DIMS",
    "EMBEDDING_MODEL_NAME",
    "ProjectIdentity",
    "SearchHit",
    "embed_text",
    "render_content_md",
    "resolve_project_identity",
]
