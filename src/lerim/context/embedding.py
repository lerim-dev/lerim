"""Deterministic embedding helpers for Lerim hybrid retrieval.

The retrieval contract needs a semantic-style ranking signal in addition to
SQLite FTS. This module provides a deterministic local embedding function so
the context store can build and test ranked retrieval without introducing a
second service dependency.
"""

from __future__ import annotations

import hashlib
import math
import re


EMBEDDING_MODEL_NAME = "lerim-hash-v1"
EMBEDDING_DIMS = 96
_TOKEN_RE = re.compile(r"[a-z0-9_./:-]{2,}", re.IGNORECASE)


def _tokens(text: str) -> list[str]:
    """Extract normalized tokens from free text."""
    return [token.lower() for token in _TOKEN_RE.findall(text or "")]


def embed_text(text: str, *, dims: int = EMBEDDING_DIMS) -> list[float]:
    """Build a deterministic dense vector from text."""
    vector = [0.0] * dims
    for token in _tokens(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:2], "big") % dims
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        weight = 1.0 + min(len(token), 16) / 16.0
        vector[bucket] += sign * weight

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Return cosine similarity for same-length vectors."""
    if len(left) != len(right) or not left or not right:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))


if __name__ == "__main__":
    """Run a tiny embedding smoke check."""
    a = embed_text("use postgres for billing joins")
    b = embed_text("postgres decision for relational billing queries")
    c = embed_text("how to plant tomatoes in spring")
    assert cosine_similarity(a, b) > cosine_similarity(a, c)
    print("embedding helpers: self-test passed")
