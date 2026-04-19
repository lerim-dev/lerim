"""Tests for cloud shipper pull functions."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lerim.cloud.shipper import (
    _ShipperState,
    _normalize_cloud_kind,
    _pull_records,
    _typed_fields_from_cloud_record,
    _upsert_pulled_record,
)
from lerim.context import ContextStore, resolve_project_identity
from tests.helpers import make_config


class TestNormalizeCloudKind:
    """Tests for _normalize_cloud_kind."""

    def test_canonical_kinds_pass_through(self):
        for kind in (
            "decision",
            "preference",
            "constraint",
            "fact",
            "reference",
            "episode",
        ):
            assert _normalize_cloud_kind(kind) == kind

    def test_project_maps_to_fact(self):
        assert _normalize_cloud_kind("project") == "fact"

    def test_learning_maps_to_fact(self):
        assert _normalize_cloud_kind("learning") == "fact"

    def test_feedback_maps_to_fact(self):
        assert _normalize_cloud_kind("feedback") == "fact"

    def test_implementation_maps_to_fact(self):
        assert _normalize_cloud_kind("implementation") == "fact"

    def test_unknown_kind_maps_to_fact(self):
        assert _normalize_cloud_kind("custom_type") == "fact"

    def test_none_maps_to_fact(self):
        assert _normalize_cloud_kind(None) == "fact"

    def test_case_insensitive(self):
        assert _normalize_cloud_kind("Decision") == "decision"
        assert _normalize_cloud_kind("FACT") == "fact"

    def test_whitespace_stripped(self):
        assert _normalize_cloud_kind("  decision  ") == "decision"


class TestTypedFieldsFromCloudRecord:
    """Tests for _typed_fields_from_cloud_record."""

    def test_decision_kind(self):
        record = {"title": "Use typed tools", "body": "No raw SQL"}
        result = _typed_fields_from_cloud_record(record, kind="decision")
        assert result["decision"] == "Use typed tools"
        assert result["why"] == "No raw SQL"

    def test_episode_kind(self):
        record = {"description": "fix bug", "body": "Fixed the importer bug"}
        result = _typed_fields_from_cloud_record(record, kind="episode")
        assert result["user_intent"] == "fix bug"
        assert result["what_happened"] == "Fixed the importer bug"

    def test_fact_kind_returns_empty(self):
        record = {"title": "X depends on Y", "body": "some body"}
        result = _typed_fields_from_cloud_record(record, kind="fact")
        assert result == {}

    def test_decision_uses_name_fallback(self):
        record = {"name": "Named decision", "description": "desc"}
        result = _typed_fields_from_cloud_record(record, kind="decision")
        assert result["decision"] == "Named decision"

    def test_episode_description_fallback(self):
        record = {"description": "user intent here"}
        result = _typed_fields_from_cloud_record(record, kind="episode")
        assert result["user_intent"] == "user intent here"
        assert result["what_happened"] == "user intent here"


class TestUpsertPulledRecord:
    """Tests for _upsert_pulled_record."""

    def test_skips_empty_record_id(self, tmp_path):
        result = _upsert_pulled_record(
            context_db_path=tmp_path / "ctx.sqlite3",
            project_name="proj",
            project_path=tmp_path,
            record={"record_id": ""},
        )
        assert result is False

    def test_creates_new_record(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "lerim.config.project_scope.git_root_for",
            lambda _p=None: tmp_path,
        )
        ctx_db = tmp_path / "context.sqlite3"
        result = _upsert_pulled_record(
            context_db_path=ctx_db,
            project_name="proj",
            project_path=tmp_path,
            record={
                "record_id": "cloud-rec-1",
                "record_kind": "decision",
                "title": "Cloud Decision",
                "body": "Use typed tools",
                "status": "active",
                "cloud_edited_at": "2026-04-01T12:00:00Z",
            },
        )
        assert result is True
        store = ContextStore(ctx_db)
        with store.connect() as conn:
            row = conn.execute(
                "SELECT title, kind FROM records WHERE record_id = ?",
                ("cloud-rec-1",),
            ).fetchone()
        assert row is not None
        assert row["title"] == "Cloud Decision"

    def test_updates_existing_record(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "lerim.config.project_scope.git_root_for",
            lambda _p=None: tmp_path,
        )
        ctx_db = tmp_path / "context.sqlite3"
        _upsert_pulled_record(
            context_db_path=ctx_db,
            project_name="proj",
            project_path=tmp_path,
            record={
                "record_id": "cloud-rec-2",
                "record_kind": "fact",
                "title": "Original Title",
                "body": "Original body",
                "status": "active",
                "cloud_edited_at": "2026-04-01T12:00:00Z",
            },
        )
        result = _upsert_pulled_record(
            context_db_path=ctx_db,
            project_name="proj",
            project_path=tmp_path,
            record={
                "record_id": "cloud-rec-2",
                "record_kind": "fact",
                "title": "Updated Title",
                "body": "Updated body",
                "status": "active",
                "cloud_edited_at": "2026-04-02T12:00:00Z",
            },
        )
        assert result is True
        store = ContextStore(ctx_db)
        with store.connect() as conn:
            row = conn.execute(
                "SELECT title FROM records WHERE record_id = ?",
                ("cloud-rec-2",),
            ).fetchone()
        assert row["title"] == "Updated Title"


class TestPullRecords:
    """Tests for _pull_records."""

    def test_returns_zero_not_configured(self, tmp_path):
        cfg = make_config(tmp_path)
        state = _ShipperState()
        result = asyncio.run(_pull_records("https://api.test", "tok", cfg, state))
        assert result == 0

    def test_no_data_returns_zero(self, tmp_path):
        proj_dir = tmp_path / "proj"
        proj_dir.mkdir()
        cfg = replace(make_config(tmp_path), projects={"proj": str(proj_dir)})
        state = _ShipperState()

        async def mock_to_thread(fn, *args, **kwargs):
            return None

        with patch("lerim.cloud.shipper.asyncio.to_thread", side_effect=mock_to_thread):
            pulled = asyncio.run(_pull_records("https://api.test", "tok", cfg, state))
        assert pulled == 0

    def test_empty_records_returns_zero(self, tmp_path):
        proj_dir = tmp_path / "proj"
        proj_dir.mkdir()
        cfg = replace(make_config(tmp_path), projects={"proj": str(proj_dir)})
        state = _ShipperState()

        async def mock_to_thread(fn, *args, **kwargs):
            return {"records": []}

        with patch("lerim.cloud.shipper.asyncio.to_thread", side_effect=mock_to_thread):
            pulled = asyncio.run(_pull_records("https://api.test", "tok", cfg, state))
        assert pulled == 0
