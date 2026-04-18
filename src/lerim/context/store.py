"""SQLite-backed context store for Lerim.

This module owns the canonical schema, record/session mutations, and hybrid
retrieval helpers for the DB-only context architecture.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lerim.config.logging import logger
from lerim.context.embedding import EMBEDDING_MODEL_NAME, cosine_similarity, embed_text
from lerim.context.project_identity import ProjectIdentity

SCHEMA_VERSION = "1"
ALLOWED_KINDS = ("decision", "preference", "constraint", "fact", "reference", "episode")
ALLOWED_DOMAINS = ("project", "user", "team", "external", "session")
ALLOWED_STATUSES = ("active", "archived")
ALLOWED_RELATIONS = ("supersedes", "supports", "contradicts", "related")
ALLOWED_CHANGE_KINDS = ("create", "update", "supersede", "archive", "migrate")
RRF_K = 60


def _utc_now() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    """Serialize JSON payloads with stable formatting."""
    return json.dumps(value if value is not None else {}, ensure_ascii=True, sort_keys=True)


def _parse_json(raw: str | None, default: Any) -> Any:
    """Parse JSON text safely with a default value."""
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _new_id(prefix: str) -> str:
    """Create a compact prefixed ID."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _compile_safe_fts_query(raw: str) -> str | None:
    """Compile free-form text into a conservative SQLite FTS query."""
    if not raw or not raw.strip():
        return None

    normalized_chars: list[str] = []
    for char in raw:
        normalized_chars.append(char if char.isalnum() else " ")
    normalized = "".join(normalized_chars)

    terms: list[str] = []
    seen: set[str] = set()
    for token in normalized.split():
        term = token.strip()
        if not term:
            continue
        lowered = term.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        terms.append(term)
        if len(terms) >= 8:
            break

    if not terms:
        return None
    return " OR ".join(f'"{term}"' for term in terms)


def render_content_md(kind: str, summary: str, structured: dict[str, Any]) -> str:
    """Render human-readable markdown from structured semantic content."""
    summary = (summary or "").strip()
    if kind == "decision":
        decision = str(structured.get("decision") or summary).strip()
        why = str(structured.get("why") or "").strip()
        alternatives = structured.get("alternatives") or []
        consequences = structured.get("consequences") or []
        lines = [decision]
        if why:
            lines.extend(["", f"**Why:** {why}"])
        if alternatives:
            lines.extend(["", "**Alternatives considered:**"])
            lines.extend(f"- {item}" for item in alternatives if str(item).strip())
        if consequences:
            lines.extend(["", "**Consequences:**"])
            lines.extend(f"- {item}" for item in consequences if str(item).strip())
        return "\n".join(lines).strip()

    if kind == "episode":
        user_intent = str(structured.get("user_intent") or "").strip()
        happened = str(structured.get("what_happened") or summary).strip()
        outcomes = structured.get("outcomes") or []
        lines = ["## User Intent", user_intent or "(not captured)", "", "## What Happened", happened]
        if outcomes:
            lines.extend(["", "## Outcomes"])
            lines.extend(f"- {item}" for item in outcomes if str(item).strip())
        return "\n".join(lines).strip()

    content = str(structured.get("content") or summary).strip()
    why = str(structured.get("why") or "").strip()
    how = str(structured.get("how_to_apply") or "").strip()
    lines = [content or summary]
    if why:
        lines.extend(["", f"**Why:** {why}"])
    if how:
        lines.extend(["", f"**How to apply:** {how}"])
    return "\n".join(lines).strip()


@dataclass(frozen=True)
class SearchHit:
    """Compact retrieval hit returned by hybrid search."""

    record_id: str
    project_id: str
    kind: str
    domain: str
    title: str
    summary: str
    status: str
    valid_from: str
    valid_until: str | None
    score: float
    sources: list[str]


class ContextStore:
    """Canonical global SQLite context store."""

    def __init__(self, db_path: Path | str) -> None:
        """Create a store wrapper for one SQLite database path."""
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Any:
        """Open a SQLite connection with row access and foreign keys enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        """Create all canonical tables and indexes idempotently."""
        with self.connect() as conn:
            conn.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS schema_meta (
                            key TEXT PRIMARY KEY,
                            value TEXT NOT NULL
                        );

                        CREATE TABLE IF NOT EXISTS projects (
                            project_id TEXT PRIMARY KEY,
                            project_slug TEXT NOT NULL,
                            repo_path TEXT NOT NULL UNIQUE,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        );

                        CREATE TABLE IF NOT EXISTS sessions (
                            session_id TEXT PRIMARY KEY,
                            project_id TEXT NOT NULL,
                            agent_type TEXT NOT NULL,
                            source_trace_ref TEXT NOT NULL,
                            repo_path TEXT,
                            cwd TEXT,
                            started_at TEXT,
                            model_name TEXT,
                            instructions_text TEXT,
                            prompt_text TEXT,
                            metadata_json TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            FOREIGN KEY(project_id) REFERENCES projects(project_id)
                        );

                        CREATE TABLE IF NOT EXISTS records (
                            record_id TEXT PRIMARY KEY,
                            project_id TEXT NOT NULL,
                            kind TEXT NOT NULL,
                            domain TEXT NOT NULL,
                            title TEXT NOT NULL,
                            summary TEXT NOT NULL,
                            content_md TEXT NOT NULL,
                            structured_json TEXT NOT NULL,
                            status TEXT NOT NULL,
                            confidence REAL,
                            source_session_id TEXT,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            valid_from TEXT NOT NULL,
                            valid_until TEXT,
                            FOREIGN KEY(project_id) REFERENCES projects(project_id),
                            FOREIGN KEY(source_session_id) REFERENCES sessions(session_id)
                        );

                        CREATE TABLE IF NOT EXISTS record_versions (
                            version_id TEXT PRIMARY KEY,
                            project_id TEXT NOT NULL,
                            record_id TEXT NOT NULL,
                            version_no INTEGER NOT NULL,
                            kind TEXT NOT NULL,
                            domain TEXT NOT NULL,
                            title TEXT NOT NULL,
                            summary TEXT NOT NULL,
                            content_md TEXT NOT NULL,
                            structured_json TEXT NOT NULL,
                            status TEXT NOT NULL,
                            change_kind TEXT NOT NULL,
                            change_reason TEXT,
                            changed_at TEXT NOT NULL,
                            changed_by_session_id TEXT,
                            FOREIGN KEY(project_id) REFERENCES projects(project_id),
                            FOREIGN KEY(record_id) REFERENCES records(record_id),
                            FOREIGN KEY(changed_by_session_id) REFERENCES sessions(session_id)
                        );

                        CREATE TABLE IF NOT EXISTS record_links (
                            link_id TEXT PRIMARY KEY,
                            project_id TEXT NOT NULL,
                            from_record_id TEXT NOT NULL,
                            to_record_id TEXT NOT NULL,
                            relation TEXT NOT NULL,
                            reason TEXT,
                            created_at TEXT NOT NULL,
                            created_by_session_id TEXT,
                            FOREIGN KEY(project_id) REFERENCES projects(project_id),
                            FOREIGN KEY(from_record_id) REFERENCES records(record_id),
                            FOREIGN KEY(to_record_id) REFERENCES records(record_id),
                            FOREIGN KEY(created_by_session_id) REFERENCES sessions(session_id)
                        );

                        CREATE TABLE IF NOT EXISTS evidence (
                            evidence_id TEXT PRIMARY KEY,
                            project_id TEXT NOT NULL,
                            record_id TEXT NOT NULL,
                            session_id TEXT,
                            evidence_type TEXT NOT NULL,
                            snippet TEXT,
                            source_ref TEXT,
                            metadata_json TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            FOREIGN KEY(project_id) REFERENCES projects(project_id),
                            FOREIGN KEY(record_id) REFERENCES records(record_id),
                            FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                        );

                        CREATE TABLE IF NOT EXISTS session_findings (
                            finding_id TEXT PRIMARY KEY,
                            project_id TEXT NOT NULL,
                            session_id TEXT NOT NULL,
                            theme TEXT NOT NULL,
                            durability TEXT NOT NULL,
                            kind_hint TEXT,
                            quote TEXT NOT NULL,
                            trace_ref TEXT,
                            metadata_json TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            committed_record_id TEXT,
                            FOREIGN KEY(project_id) REFERENCES projects(project_id),
                            FOREIGN KEY(session_id) REFERENCES sessions(session_id),
                            FOREIGN KEY(committed_record_id) REFERENCES records(record_id)
                        );

                        CREATE TABLE IF NOT EXISTS record_embeddings (
                            record_id TEXT PRIMARY KEY,
                            project_id TEXT NOT NULL,
                            embedding_model TEXT NOT NULL,
                            embedding_json TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            FOREIGN KEY(project_id) REFERENCES projects(project_id),
                            FOREIGN KEY(record_id) REFERENCES records(record_id)
                        );

                        CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
                            record_id UNINDEXED,
                            project_id UNINDEXED,
                            title,
                            summary,
                            content_md
                        );

                        CREATE INDEX IF NOT EXISTS idx_projects_repo_path ON projects(repo_path);
                        CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions(project_id);
                        CREATE INDEX IF NOT EXISTS idx_records_project_id ON records(project_id);
                        CREATE INDEX IF NOT EXISTS idx_records_kind ON records(kind);
                        CREATE INDEX IF NOT EXISTS idx_records_status ON records(status);
                        CREATE INDEX IF NOT EXISTS idx_links_from_record ON record_links(from_record_id);
                        CREATE INDEX IF NOT EXISTS idx_links_to_record ON record_links(to_record_id);
                        CREATE INDEX IF NOT EXISTS idx_evidence_record_id ON evidence(record_id);
                        CREATE INDEX IF NOT EXISTS idx_findings_session_id ON session_findings(session_id);
                        """
                    )
            self._validate_schema(conn)
            conn.execute(
                """
                INSERT INTO schema_meta(key, value)
                VALUES('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (SCHEMA_VERSION,),
            )

    def _validate_schema(self, conn: sqlite3.Connection) -> None:
        """Ensure the on-disk DB matches the canonical DB-only schema."""
        required_columns = {
            "projects": {"project_id", "project_slug", "repo_path"},
            "sessions": {"session_id", "project_id", "agent_type", "source_trace_ref"},
            "records": {"record_id", "project_id", "kind", "domain", "title", "summary", "content_md"},
            "record_versions": {"version_id", "project_id", "record_id", "version_no", "change_kind"},
            "record_links": {"link_id", "project_id", "from_record_id", "to_record_id", "relation"},
            "evidence": {"evidence_id", "project_id", "record_id", "evidence_type"},
            "session_findings": {"finding_id", "project_id", "session_id", "theme", "durability"},
            "record_embeddings": {"record_id", "project_id", "embedding_model", "embedding_json"},
            "records_fts": {"record_id", "project_id", "title", "summary", "content_md"},
        }

        for table_name, expected in required_columns.items():
            rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            actual = {str(row[1]) for row in rows}
            missing = expected - actual
            if missing:
                missing_list = ", ".join(sorted(missing))
                raise sqlite3.OperationalError(
                    f"context schema incompatible: table {table_name} missing columns {missing_list}"
                )

    def register_project(self, identity: ProjectIdentity) -> dict[str, Any]:
        """Upsert a project row and return the canonical project payload."""
        self.initialize()
        now = _utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO projects(project_id, project_slug, repo_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    project_slug=excluded.project_slug,
                    repo_path=excluded.repo_path,
                    updated_at=excluded.updated_at
                """,
                (
                    identity.project_id,
                    identity.project_slug,
                    str(identity.repo_path),
                    now,
                    now,
                ),
            )
        return {
            "project_id": identity.project_id,
            "project_slug": identity.project_slug,
            "repo_path": str(identity.repo_path),
        }

    def upsert_session(
        self,
        *,
        project_id: str,
        session_id: str,
        agent_type: str,
        source_trace_ref: str,
        repo_path: str | None,
        cwd: str | None,
        started_at: str | None,
        model_name: str | None,
        instructions_text: str | None,
        prompt_text: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Insert or replace a session provenance row."""
        self.initialize()
        now = _utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions(
                    session_id, project_id, agent_type, source_trace_ref, repo_path, cwd,
                    started_at, model_name, instructions_text, prompt_text, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    project_id=excluded.project_id,
                    agent_type=excluded.agent_type,
                    source_trace_ref=excluded.source_trace_ref,
                    repo_path=excluded.repo_path,
                    cwd=excluded.cwd,
                    started_at=excluded.started_at,
                    model_name=excluded.model_name,
                    instructions_text=excluded.instructions_text,
                    prompt_text=excluded.prompt_text,
                    metadata_json=excluded.metadata_json
                """,
                (
                    session_id,
                    project_id,
                    agent_type,
                    source_trace_ref,
                    repo_path,
                    cwd,
                    started_at,
                    model_name,
                    instructions_text,
                    prompt_text,
                    _json(metadata or {}),
                    now,
                ),
            )
        return {"session_id": session_id, "project_id": project_id}

    def add_session_findings(
        self,
        *,
        project_id: str,
        session_id: str,
        findings: list[dict[str, Any]],
    ) -> list[str]:
        """Persist extraction findings for one session."""
        self.initialize()
        created_ids: list[str] = []
        with self.connect() as conn:
            for finding in findings:
                finding_id = _new_id("find")
                created_ids.append(finding_id)
                conn.execute(
                    """
                    INSERT INTO session_findings(
                        finding_id, project_id, session_id, theme, durability, kind_hint, quote,
                        trace_ref, metadata_json, created_at, committed_record_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        finding_id,
                        project_id,
                        session_id,
                        str(finding.get("theme") or "").strip(),
                        str(finding.get("level") or "").strip(),
                        str(finding.get("kind_hint") or "").strip() or None,
                        str(finding.get("quote") or "").strip(),
                        str(finding.get("offset") or ""),
                        _json({"source": "note"}),
                        _utc_now(),
                    ),
                )
        return created_ids

    def fetch_record(
        self,
        record_id: str,
        *,
        project_ids: list[str] | None = None,
        include_versions: bool = False,
        include_evidence: bool = False,
        include_links: bool = False,
    ) -> dict[str, Any] | None:
        """Fetch one record plus optional related detail."""
        self.initialize()
        filter_sql, params = self._build_record_filter_sql(
            project_ids=project_ids,
            kind_filters=None,
            domain_filters=None,
            as_of=None,
            include_history=True,
        )
        with self.connect() as conn:
            row = conn.execute(
                f"SELECT * FROM records WHERE record_id = ? AND {filter_sql}",
                tuple([record_id] + params),
            ).fetchone()
            if row is None:
                return None
            payload = self._record_row_to_dict(row)
            if include_versions:
                versions = conn.execute(
                    """
                    SELECT * FROM record_versions
                    WHERE record_id = ?
                    ORDER BY version_no DESC
                    """,
                    (record_id,),
                ).fetchall()
                payload["versions"] = [dict(item) | {"structured": _parse_json(item["structured_json"], {})} for item in versions]
            if include_evidence:
                evidence = conn.execute(
                    """
                    SELECT * FROM evidence
                    WHERE record_id = ?
                    ORDER BY created_at ASC
                    """,
                    (record_id,),
                ).fetchall()
                payload["evidence"] = [dict(item) | {"metadata": _parse_json(item["metadata_json"], {})} for item in evidence]
            if include_links:
                links = conn.execute(
                    """
                    SELECT * FROM record_links
                    WHERE from_record_id = ? OR to_record_id = ?
                    ORDER BY created_at ASC
                    """,
                    (record_id, record_id),
                ).fetchall()
                payload["links"] = [dict(item) for item in links]
            return payload

    def create_record(
        self,
        *,
        project_id: str,
        session_id: str | None,
        record_id: str | None = None,
        kind: str,
        domain: str,
        title: str,
        summary: str,
        structured: dict[str, Any],
        status: str = "active",
        confidence: float | None = None,
        valid_from: str | None = None,
        valid_until: str | None = None,
        links: list[dict[str, Any]] | None = None,
        evidence: list[dict[str, Any]] | None = None,
        change_reason: str | None = None,
    ) -> dict[str, Any]:
        """Create a new canonical record and first version."""
        self._validate_record_fields(kind=kind, domain=domain, status=status)
        self.initialize()
        now = _utc_now()
        record_id = str(record_id or _new_id("rec")).strip()
        if not record_id:
            raise ValueError("record_id_required")
        self._validate_structured_payload(kind=kind, structured=structured, session_id=session_id)
        content_md = render_content_md(kind, summary, structured)
        effective_valid_from = valid_from or now
        with self.connect() as conn:
            self._ensure_episode_uniqueness(
                conn,
                project_id=project_id,
                kind=kind,
                session_id=session_id,
                exclude_record_id=None,
            )
            conn.execute(
                """
                INSERT INTO records(
                    record_id, project_id, kind, domain, title, summary, content_md,
                    structured_json, status, confidence, source_session_id,
                    created_at, updated_at, valid_from, valid_until
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    project_id,
                    kind,
                    domain,
                    title.strip(),
                    summary.strip(),
                    content_md,
                    _json(structured),
                    status,
                    confidence,
                    session_id,
                    now,
                    now,
                    effective_valid_from,
                    valid_until,
                ),
            )
            self._insert_record_version(
                conn,
                project_id=project_id,
                record_id=record_id,
                version_no=1,
                kind=kind,
                domain=domain,
                title=title,
                summary=summary,
                content_md=content_md,
                structured=structured,
                status=status,
                change_kind="create",
                change_reason=change_reason,
                changed_by_session_id=session_id,
            )
            self._upsert_embedding(conn, project_id=project_id, record_id=record_id, text=self._search_text(title, summary, content_md))
            self._upsert_fts(conn, project_id=project_id, record_id=record_id, title=title, summary=summary, content_md=content_md)
            self._insert_links(conn, project_id=project_id, session_id=session_id, from_record_id=record_id, links=links or [])
            self._insert_evidence(conn, project_id=project_id, record_id=record_id, session_id=session_id, evidence=evidence or [])
        return self.fetch_record(record_id, include_evidence=True, include_links=True) or {}

    def update_record(
        self,
        *,
        record_id: str,
        session_id: str | None,
        changes: dict[str, Any],
        change_reason: str | None = None,
        change_kind_override: str | None = None,
    ) -> dict[str, Any]:
        """Apply a partial semantic update and create a new version."""
        self.initialize()
        with self.connect() as conn:
            current = conn.execute("SELECT * FROM records WHERE record_id = ?", (record_id,)).fetchone()
            if current is None:
                raise ValueError(f"record_not_found:{record_id}")
            merged = self._record_row_to_dict(current)
            structured = dict(merged["structured"])
            if "structured" in changes and isinstance(changes["structured"], dict):
                structured.update(changes["structured"])
            kind = str(changes.get("kind") or merged["kind"])
            domain = str(changes.get("domain") or merged["domain"])
            status = str(changes.get("status") or merged["status"])
            title = str(changes.get("title") or merged["title"])
            summary = str(changes.get("summary") or merged["summary"])
            confidence = changes.get("confidence", merged.get("confidence"))
            valid_from = str(changes.get("valid_from") or merged["valid_from"])
            valid_until = changes.get("valid_until", merged.get("valid_until"))
            self._validate_record_fields(kind=kind, domain=domain, status=status)
            self._validate_structured_payload(
                kind=kind,
                structured=structured,
                session_id=merged.get("source_session_id"),
            )
            self._ensure_episode_uniqueness(
                conn,
                project_id=merged["project_id"],
                kind=kind,
                session_id=merged.get("source_session_id"),
                exclude_record_id=record_id,
            )
            content_md = render_content_md(kind, summary, structured)
            now = _utc_now()
            conn.execute(
                """
                UPDATE records
                SET kind=?, domain=?, title=?, summary=?, content_md=?, structured_json=?,
                    status=?, confidence=?, updated_at=?, valid_from=?, valid_until=?
                WHERE record_id=?
                """,
                (
                    kind,
                    domain,
                    title,
                    summary,
                    content_md,
                    _json(structured),
                    status,
                    confidence,
                    now,
                    valid_from,
                    valid_until,
                    record_id,
                ),
            )
            version_no = int(conn.execute("SELECT COALESCE(MAX(version_no), 0) FROM record_versions WHERE record_id = ?", (record_id,)).fetchone()[0]) + 1
            change_kind = change_kind_override or ("archive" if status == "archived" else "update")
            self._insert_record_version(
                conn,
                project_id=merged["project_id"],
                record_id=record_id,
                version_no=version_no,
                kind=kind,
                domain=domain,
                title=title,
                summary=summary,
                content_md=content_md,
                structured=structured,
                status=status,
                change_kind=change_kind,
                change_reason=change_reason,
                changed_by_session_id=session_id,
            )
            self._upsert_embedding(conn, project_id=merged["project_id"], record_id=record_id, text=self._search_text(title, summary, content_md))
            self._upsert_fts(conn, project_id=merged["project_id"], record_id=record_id, title=title, summary=summary, content_md=content_md)
            if isinstance(changes.get("links"), list):
                self._insert_links(conn, project_id=merged["project_id"], session_id=session_id, from_record_id=record_id, links=changes["links"])
            if isinstance(changes.get("evidence"), list):
                self._insert_evidence(conn, project_id=merged["project_id"], record_id=record_id, session_id=session_id, evidence=changes["evidence"])
        return self.fetch_record(record_id, include_evidence=True, include_links=True) or {}

    def archive_record(
        self,
        *,
        record_id: str,
        session_id: str | None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Archive an existing record."""
        return self.update_record(
            record_id=record_id,
            session_id=session_id,
            changes={"status": "archived"},
            change_reason=reason or "archive_record",
        )

    def link_records(
        self,
        *,
        project_id: str,
        from_record_id: str,
        to_record_id: str,
        relation: str,
        reason: str | None,
        session_id: str | None,
    ) -> dict[str, Any]:
        """Create one graph link between two records."""
        if relation not in ALLOWED_RELATIONS:
            raise ValueError(f"invalid_relation:{relation}")
        self.initialize()
        link_id = _new_id("link")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO record_links(
                    link_id, project_id, from_record_id, to_record_id, relation,
                    reason, created_at, created_by_session_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (link_id, project_id, from_record_id, to_record_id, relation, reason, _utc_now(), session_id),
            )
        return {
            "link_id": link_id,
            "project_id": project_id,
            "from_record_id": from_record_id,
            "to_record_id": to_record_id,
            "relation": relation,
            "reason": reason,
        }

    def supersede_record(
        self,
        *,
        record_id: str,
        session_id: str | None,
        replacement_record_id: str,
        reason: str | None = None,
        valid_until: str | None = None,
    ) -> dict[str, Any]:
        """Close one record's validity window and link it to its replacement."""
        archived = self.update_record(
            record_id=record_id,
            session_id=session_id,
            changes={"valid_until": valid_until or _utc_now()},
            change_reason=reason or "supersede_record",
            change_kind_override="supersede",
        )
        self.link_records(
            project_id=archived["project_id"],
            from_record_id=replacement_record_id,
            to_record_id=record_id,
            relation="supersedes",
            reason=reason,
            session_id=session_id,
        )
        return self.fetch_record(record_id, include_evidence=True, include_links=True) or {}

    def search(
        self,
        *,
        project_ids: list[str] | None,
        query: str,
        kind_filters: list[str] | None = None,
        domain_filters: list[str] | None = None,
        as_of: str | None = None,
        include_history: bool = False,
        limit: int = 8,
    ) -> list[SearchHit]:
        """Run hybrid search over active records with optional temporal filters."""
        self.initialize()
        semantic_rows = self._semantic_candidates(
            project_ids=project_ids,
            query=query,
            kind_filters=kind_filters,
            domain_filters=domain_filters,
            as_of=as_of,
            include_history=include_history,
            limit=max(limit * 3, 24),
        )
        lexical_rows = self._lexical_candidates(
            project_ids=project_ids,
            query=query,
            kind_filters=kind_filters,
            domain_filters=domain_filters,
            as_of=as_of,
            include_history=include_history,
            limit=max(limit * 3, 24),
        )
        combined = self._rrf_fuse(semantic_rows=semantic_rows, lexical_rows=lexical_rows)
        if not combined:
            return []
        top_ids = [record_id for record_id, _score, _sources in combined[:limit]]
        expanded_ids = self._expand_related(top_ids, limit=limit)
        if not expanded_ids:
            return []
        filter_sql, params = self._build_record_filter_sql(
            project_ids=project_ids,
            kind_filters=kind_filters,
            domain_filters=domain_filters,
            as_of=as_of,
            include_history=include_history,
        )
        with self.connect() as conn:
            placeholders = ", ".join("?" for _ in expanded_ids)
            rows = conn.execute(
                f"SELECT * FROM records WHERE record_id IN ({placeholders}) AND {filter_sql}",
                tuple(expanded_ids + params),
            ).fetchall()
            row_map = {str(row["record_id"]): row for row in rows}
        hits: list[SearchHit] = []
        for record_id, score, sources in combined:
            row = row_map.get(record_id)
            if row is None:
                continue
            hits.append(
                SearchHit(
                    record_id=record_id,
                    project_id=str(row["project_id"]),
                    kind=str(row["kind"]),
                    domain=str(row["domain"]),
                    title=str(row["title"]),
                    summary=str(row["summary"]),
                    status=str(row["status"]),
                    valid_from=str(row["valid_from"]),
                    valid_until=row["valid_until"],
                    score=score,
                    sources=sources,
                )
            )
            if len(hits) >= limit:
                break
        if len(hits) < limit:
            for record_id in expanded_ids:
                if any(hit.record_id == record_id for hit in hits):
                    continue
                row = row_map.get(record_id)
                if row is None:
                    continue
                hits.append(
                    SearchHit(
                        record_id=record_id,
                        project_id=str(row["project_id"]),
                        kind=str(row["kind"]),
                        domain=str(row["domain"]),
                        title=str(row["title"]),
                        summary=str(row["summary"]),
                        status=str(row["status"]),
                        valid_from=str(row["valid_from"]),
                        valid_until=row["valid_until"],
                        score=0.0,
                        sources=["graph"],
                    )
                )
                if len(hits) >= limit:
                    break
        return hits

    def _search_text(self, title: str, summary: str, content_md: str) -> str:
        """Build canonical text used for embeddings."""
        return "\n".join([title.strip(), summary.strip(), content_md.strip()]).strip()

    def _record_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert a record row into JSON-like data."""
        return {
            "record_id": str(row["record_id"]),
            "project_id": str(row["project_id"]),
            "kind": str(row["kind"]),
            "domain": str(row["domain"]),
            "title": str(row["title"]),
            "summary": str(row["summary"]),
            "content_md": str(row["content_md"]),
            "structured": _parse_json(row["structured_json"], {}),
            "status": str(row["status"]),
            "confidence": row["confidence"],
            "source_session_id": row["source_session_id"],
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "valid_from": str(row["valid_from"]),
            "valid_until": row["valid_until"],
        }

    def _validate_record_fields(self, *, kind: str, domain: str, status: str) -> None:
        """Validate canonical record enums."""
        if kind not in ALLOWED_KINDS:
            raise ValueError(f"invalid_kind:{kind}")
        if domain not in ALLOWED_DOMAINS:
            raise ValueError(f"invalid_domain:{domain}")
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"invalid_status:{status}")

    def _validate_structured_payload(
        self,
        *,
        kind: str,
        structured: dict[str, Any],
        session_id: str | None,
    ) -> None:
        """Validate kind-specific structured payload requirements."""
        if kind == "episode":
            if not str(session_id or "").strip():
                raise ValueError("episode_requires_session_id")
            user_intent = str(structured.get("user_intent") or "").strip()
            what_happened = str(structured.get("what_happened") or "").strip()
            if not user_intent or not what_happened:
                raise ValueError("invalid_episode_structured")
        if kind == "decision":
            decision = str(structured.get("decision") or "").strip()
            why = str(structured.get("why") or "").strip()
            if not decision or not why:
                raise ValueError("invalid_decision_structured")

    def _ensure_episode_uniqueness(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        kind: str,
        session_id: str | None,
        exclude_record_id: str | None,
    ) -> None:
        """Ensure one episode record per project session."""
        if kind != "episode" or not str(session_id or "").strip():
            return
        query = """
            SELECT record_id
            FROM records
            WHERE project_id = ? AND kind = 'episode' AND source_session_id = ?
        """
        params: list[Any] = [project_id, session_id]
        if exclude_record_id:
            query += " AND record_id != ?"
            params.append(exclude_record_id)
        row = conn.execute(query, tuple(params)).fetchone()
        if row is not None:
            raise ValueError("duplicate_episode_for_session")

    def _insert_record_version(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        record_id: str,
        version_no: int,
        kind: str,
        domain: str,
        title: str,
        summary: str,
        content_md: str,
        structured: dict[str, Any],
        status: str,
        change_kind: str,
        change_reason: str | None,
        changed_by_session_id: str | None,
    ) -> None:
        """Insert one immutable record version row."""
        if change_kind not in ALLOWED_CHANGE_KINDS:
            raise ValueError(f"invalid_change_kind:{change_kind}")
        conn.execute(
            """
            INSERT INTO record_versions(
                version_id, project_id, record_id, version_no, kind, domain, title,
                summary, content_md, structured_json, status, change_kind,
                change_reason, changed_at, changed_by_session_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _new_id("ver"),
                project_id,
                record_id,
                version_no,
                kind,
                domain,
                title,
                summary,
                content_md,
                _json(structured),
                status,
                change_kind,
                change_reason,
                _utc_now(),
                changed_by_session_id,
            ),
        )

    def _insert_links(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        session_id: str | None,
        from_record_id: str,
        links: list[dict[str, Any]],
    ) -> None:
        """Insert link rows from a normalized link list."""
        for link in links:
            target_record_id = str(link.get("target_record_id") or "").strip()
            relation = str(link.get("relation") or "").strip()
            if not target_record_id or relation not in ALLOWED_RELATIONS:
                continue
            conn.execute(
                """
                INSERT INTO record_links(
                    link_id, project_id, from_record_id, to_record_id, relation,
                    reason, created_at, created_by_session_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _new_id("link"),
                    project_id,
                    from_record_id,
                    target_record_id,
                    relation,
                    str(link.get("reason") or "").strip() or None,
                    _utc_now(),
                    session_id,
                ),
            )

    def _insert_evidence(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        record_id: str,
        session_id: str | None,
        evidence: list[dict[str, Any]],
    ) -> None:
        """Insert bounded evidence rows."""
        for item in evidence:
            evidence_type = str(item.get("evidence_type") or "").strip() or "trace_snippet"
            conn.execute(
                """
                INSERT INTO evidence(
                    evidence_id, project_id, record_id, session_id, evidence_type,
                    snippet, source_ref, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _new_id("evi"),
                    project_id,
                    record_id,
                    session_id,
                    evidence_type,
                    str(item.get("snippet") or "").strip()[:1200] or None,
                    str(item.get("source_ref") or "").strip() or None,
                    _json(item.get("metadata") or {}),
                    _utc_now(),
                ),
            )

    def _upsert_embedding(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        record_id: str,
        text: str,
    ) -> None:
        """Update derived embedding storage for one record."""
        conn.execute(
            """
            INSERT INTO record_embeddings(record_id, project_id, embedding_model, embedding_json, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(record_id) DO UPDATE SET
                project_id=excluded.project_id,
                embedding_model=excluded.embedding_model,
                embedding_json=excluded.embedding_json,
                updated_at=excluded.updated_at
            """,
            (record_id, project_id, EMBEDDING_MODEL_NAME, _json(embed_text(text)), _utc_now()),
        )

    def _upsert_fts(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        record_id: str,
        title: str,
        summary: str,
        content_md: str,
    ) -> None:
        """Refresh derived FTS storage for one record."""
        conn.execute("DELETE FROM records_fts WHERE record_id = ?", (record_id,))
        conn.execute(
            """
            INSERT INTO records_fts(record_id, project_id, title, summary, content_md)
            VALUES (?, ?, ?, ?, ?)
            """,
            (record_id, project_id, title, summary, content_md),
        )

    def _build_record_filter_sql(
        self,
        *,
        table_alias: str = "",
        project_ids: list[str] | None,
        kind_filters: list[str] | None,
        domain_filters: list[str] | None,
        as_of: str | None,
        include_history: bool,
    ) -> tuple[str, list[Any]]:
        """Build reusable SQL filter fragments for record queries."""
        prefix = f"{table_alias}." if table_alias else ""
        clauses = ["1=1"]
        params: list[Any] = []
        if project_ids:
            placeholders = ", ".join("?" for _ in project_ids)
            clauses.append(f"{prefix}project_id IN ({placeholders})")
            params.extend(project_ids)
        if kind_filters:
            placeholders = ", ".join("?" for _ in kind_filters)
            clauses.append(f"{prefix}kind IN ({placeholders})")
            params.extend(kind_filters)
        if domain_filters:
            placeholders = ", ".join("?" for _ in domain_filters)
            clauses.append(f"{prefix}domain IN ({placeholders})")
            params.extend(domain_filters)
        if not include_history:
            clauses.append(f"{prefix}status = 'active'")
        if as_of:
            clauses.append(f"{prefix}valid_from <= ?")
            clauses.append(f"({prefix}valid_until IS NULL OR {prefix}valid_until >= ?)")
            params.extend([as_of, as_of])
        return " AND ".join(clauses), params

    def _semantic_candidates(
        self,
        *,
        project_ids: list[str] | None,
        query: str,
        kind_filters: list[str] | None,
        domain_filters: list[str] | None,
        as_of: str | None,
        include_history: bool,
        limit: int,
    ) -> list[tuple[str, float]]:
        """Return ranked semantic candidates from local embeddings."""
        query_vec = embed_text(query)
        filter_sql, params = self._build_record_filter_sql(
            table_alias="records",
            project_ids=project_ids,
            kind_filters=kind_filters,
            domain_filters=domain_filters,
            as_of=as_of,
            include_history=include_history,
        )
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT records.record_id, record_embeddings.embedding_json
                FROM records
                JOIN record_embeddings ON record_embeddings.record_id = records.record_id
                WHERE {filter_sql}
                """,
                tuple(params),
            ).fetchall()
        scored: list[tuple[str, float]] = []
        for row in rows:
            vector = _parse_json(row["embedding_json"], [])
            if not vector:
                continue
            scored.append((str(row["record_id"]), cosine_similarity(query_vec, vector)))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]

    def _lexical_candidates(
        self,
        *,
        project_ids: list[str] | None,
        query: str,
        kind_filters: list[str] | None,
        domain_filters: list[str] | None,
        as_of: str | None,
        include_history: bool,
        limit: int,
    ) -> list[tuple[str, float]]:
        """Return ranked lexical candidates from SQLite FTS."""
        compiled_query = _compile_safe_fts_query(query)
        if not compiled_query:
            return []
        filter_sql, params = self._build_record_filter_sql(
            table_alias="records",
            project_ids=project_ids,
            kind_filters=kind_filters,
            domain_filters=domain_filters,
            as_of=as_of,
            include_history=include_history,
        )
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT records.record_id, bm25(records_fts) AS rank_score
                FROM records_fts
                JOIN records ON records.record_id = records_fts.record_id
                WHERE records_fts MATCH ? AND {filter_sql}
                ORDER BY rank_score ASC
                LIMIT ?
                """,
                tuple([compiled_query] + params + [limit]),
            ).fetchall()
        return [(str(row["record_id"]), float(row["rank_score"])) for row in rows]

    def _rrf_fuse(
        self,
        *,
        semantic_rows: list[tuple[str, float]],
        lexical_rows: list[tuple[str, float]],
    ) -> list[tuple[str, float, list[str]]]:
        """Fuse ranked lists with Reciprocal Rank Fusion."""
        scores: dict[str, float] = {}
        sources: dict[str, set[str]] = {}
        for rank, (record_id, _score) in enumerate(semantic_rows, start=1):
            scores[record_id] = scores.get(record_id, 0.0) + 1.0 / (RRF_K + rank)
            sources.setdefault(record_id, set()).add("semantic")
        for rank, (record_id, _score) in enumerate(lexical_rows, start=1):
            scores[record_id] = scores.get(record_id, 0.0) + 1.0 / (RRF_K + rank)
            sources.setdefault(record_id, set()).add("fts")
        combined = [
            (record_id, score, sorted(sources.get(record_id, set())))
            for record_id, score in scores.items()
        ]
        combined.sort(key=lambda item: item[1], reverse=True)
        return combined

    def _expand_related(self, record_ids: list[str], *, limit: int) -> list[str]:
        """Expand one graph hop from the top-ranked records."""
        if not record_ids:
            return []
        ordered = list(record_ids)
        seen = set(ordered)
        placeholders = ", ".join("?" for _ in record_ids)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT from_record_id, to_record_id
                FROM record_links
                WHERE from_record_id IN ({placeholders}) OR to_record_id IN ({placeholders})
                ORDER BY created_at ASC
                """,
                tuple(record_ids + record_ids),
            ).fetchall()
        for row in rows:
            for candidate in (str(row["from_record_id"]), str(row["to_record_id"])):
                if candidate in seen:
                    continue
                seen.add(candidate)
                ordered.append(candidate)
                if len(ordered) >= max(limit * 2, limit):
                    return ordered
        return ordered


if __name__ == "__main__":
    """Run a small end-to-end smoke check for schema and record creation."""
    import tempfile

    from lerim.context.project_identity import resolve_project_identity

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "context.sqlite3"
        store = ContextStore(db_path)
        identity = resolve_project_identity(Path.cwd())
        store.register_project(identity)
        store.upsert_session(
            project_id=identity.project_id,
            session_id="sess_demo",
            agent_type="codex",
            source_trace_ref="/tmp/trace.jsonl",
            repo_path=str(identity.repo_path),
            cwd=str(identity.repo_path),
            started_at=None,
            model_name="demo",
            instructions_text=None,
            prompt_text=None,
            metadata={},
        )
        record = store.create_record(
            project_id=identity.project_id,
            session_id="sess_demo",
            kind="decision",
            domain="project",
            title="Use one global DB",
            summary="Canonical context store lives in ~/.lerim/context.sqlite3.",
            structured={"decision": "Use one global DB", "why": "One source of truth."},
        )
        assert record["record_id"]
        hits = store.search(project_ids=[identity.project_id], query="global sqlite db", limit=4)
        assert hits
        print("context store: self-test passed")
