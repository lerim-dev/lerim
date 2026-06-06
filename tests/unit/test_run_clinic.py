"""Unit tests for project Run Clinic artifacts."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lerim.agents.run_clinic.pipeline import sanitize_report, validate_clinic_output
from lerim.context import ContextStore, resolve_project_identity
from lerim.run_clinic import (
    RUN_CLINIC_FILENAME,
    RUN_CLINIC_REPORT_FILENAME,
    RunClinicData,
    load_run_clinic_data,
    run_clinic_paths,
    run_clinic_status,
    run_clinic_status_to_dict,
)
from lerim.server.runtime import LerimRuntime
from tests.helpers import make_config, run_cli, write_test_config


@pytest.fixture
def mock_embeddings(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Patch embeddings so context writes remain local and deterministic."""
    provider = MagicMock()
    provider.embedding_dims = 384
    provider.model_id = "test-model"
    provider.embed_document.return_value = [0.1] * 384
    provider.embed_query.return_value = [0.1] * 384
    monkeypatch.setattr("lerim.context.store.get_embedding_provider", lambda: provider)
    return provider


def _register_seeded_project(store: ContextStore, repo: Path) -> str:
    """Register a project plus one source session and return project_id."""
    identity = resolve_project_identity(repo)
    store.register_project(identity)
    store.upsert_session(
        project_id=identity.project_id,
        session_id="sess_run_clinic",
        agent_type="test",
        source_trace_ref="trace.jsonl",
        repo_path=str(identity.repo_path),
        cwd=str(identity.repo_path),
        started_at="2026-04-30T00:00:00+00:00",
        model_name="test-model",
        instructions_text=None,
        prompt_text=None,
        metadata={},
    )
    return identity.project_id


def test_run_clinic_paths_use_diagnostic_artifact_names(tmp_path):
    """Run Clinic writes markdown and JSON report artifacts."""
    cfg = make_config(tmp_path / ".lerim")
    paths = run_clinic_paths(cfg, "proj_demo")

    assert paths.current_file.name == RUN_CLINIC_FILENAME
    assert paths.current_report.name == RUN_CLINIC_REPORT_FILENAME
    assert paths.current_manifest.name == "RUN_CLINIC.manifest.json"


def test_load_run_clinic_data_reports_active_and_historical_totals(
    tmp_path,
    mock_embeddings,
) -> None:
    """Clinic samples current active records while exposing archived totals."""
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = make_config(tmp_path / ".lerim")
    store = ContextStore(cfg.context_db_path)
    project_id = _register_seeded_project(store, repo)
    active = store.create_record(
        project_id=project_id,
        session_id="sess_run_clinic",
        kind="constraint",
        title="Active memory",
        body="This record should be sampled by Clinic.",
    )
    archived = store.create_record(
        project_id=project_id,
        session_id="sess_run_clinic",
        kind="fact",
        title="Archived memory",
        body="This record should stay visible only in historical totals.",
        status="archived",
    )

    data = load_run_clinic_data(
        store,
        project_id=project_id,
        since="2026-01-01T00:00:00+00:00",
    )

    assert [record["record_id"] for record in data.records] == [active["record_id"]]
    assert archived["record_id"] not in {record["record_id"] for record in data.records}
    assert data.metrics["active_records_sampled"] == 1
    assert data.metrics["active_records_total"] == 1
    assert data.metrics["archived_records_total"] == 1
    assert data.metrics["all_records_total"] == 2


def test_validate_clinic_output_requires_evidence_ids() -> None:
    """Clinic compiler validation returns retryable errors for missing evidence."""
    output = {
        "report": {
            "headline": "Diagnosis",
            "readiness_score": 80,
            "summary": [],
            "findings": [
                {
                    "title": "Gap",
                    "pattern_type": "verification_gap",
                    "severity": "medium",
                    "confidence": "medium",
                    "summary": "A diagnosis without evidence is unsafe.",
                    "why_it_matters": "It could invent project truth.",
                    "evidence_record_ids": [],
                }
            ],
            "recommended_actions": [],
            "questions": [],
        }
    }

    assert (
        validate_clinic_output(output, valid_record_ids={"rec_1"})
        == "run_clinic_findings_missing_record_id"
    )


def test_sanitize_report_drops_uncited_items_and_adds_cited_fallback() -> None:
    """Clinic report sanitization refuses uncited model diagnosis."""
    data = RunClinicData(
        records=(
            {
                "record_id": "rec_1",
                "title": "Use explicit validation",
            },
        ),
        versions=(),
        sessions=(),
        metrics={"readiness_score": 40},
    )
    report = {
        "headline": "Diagnosis",
        "readiness_score": 40,
        "summary": [],
        "findings": [
            {
                "title": "Uncited gap",
                "pattern_type": "verification_gap",
                "severity": "medium",
                "confidence": "medium",
                "summary": "Missing evidence.",
                "why_it_matters": "Unsafe.",
                "evidence_record_ids": [],
            }
        ],
        "recommended_actions": [],
        "questions": [],
        "metrics": data.metrics,
    }

    sanitized = sanitize_report(report, data=data, valid_record_ids={"rec_1"})

    assert sanitized["findings"][0]["evidence_record_ids"] == ["rec_1"]
    assert sanitized["findings"][0]["pattern_type"] == "evidence_gap"


def test_runtime_run_clinic_refresh_writes_current_artifacts(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    mock_embeddings,
):
    """Runtime refresh writes dated and stable Run Clinic artifacts."""
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = replace(make_config(tmp_path / ".lerim"), projects={"repo": str(repo)})
    store = ContextStore(cfg.context_db_path)
    project_id = _register_seeded_project(store, repo)
    record = store.create_record(
        project_id=project_id,
        session_id="sess_run_clinic",
        kind="constraint",
        record_role="failure_mode",
        title="Avoid hidden fallback behavior",
        body="Missing providers must fail visibly instead of adding fallback behavior.",
    )

    class FakeRunClinicPipeline:
        """Runtime test double that keeps the Clinic write path deterministic."""

        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __call__(self):
            data = load_run_clinic_data(
                self.kwargs["store"],
                project_id=self.kwargs["project"].identity.project_id,
                since=self.kwargs["window_started_at"],
            )
            report = {
                "headline": "Failure-mode evidence needs visibility.",
                "readiness_score": 72,
                "summary": ["The project has reusable failure-mode evidence."],
                "findings": [
                    {
                        "title": "Visible failure policy matters",
                        "pattern_type": "verification_gap",
                        "severity": "medium",
                        "confidence": "high",
                        "summary": "Provider failures should remain explicit.",
                        "why_it_matters": "Silent fallback hides product truth.",
                        "evidence_record_ids": [record["record_id"]],
                    }
                ],
                "recommended_actions": [],
                "questions": [],
                "metrics": data.metrics,
            }
            return {
                "data": data,
                "report": report,
                "record_ids": (record["record_id"],),
                "events": [{"kind": "model_step", "stage": "compile_run_clinic"}],
                "done": True,
            }

    monkeypatch.setattr("lerim.server.runtime.RunClinicPipeline", FakeRunClinicPipeline)

    runtime = LerimRuntime(default_cwd=str(repo), config=cfg)
    result = runtime.run_clinic(repo_root=repo, project_name="repo", force=True)
    paths = run_clinic_paths(cfg, project_id)

    assert result["status"] == "generated"
    assert result["records_included"] >= 1
    assert paths.current_file.is_file()
    assert paths.current_report.is_file()
    assert Path(result["run_folder"], RUN_CLINIC_FILENAME).is_file()
    assert Path(result["run_folder"], RUN_CLINIC_REPORT_FILENAME).is_file()
    assert "Failure-mode evidence" in paths.current_file.read_text(encoding="utf-8")


def test_run_clinic_status_json_reports_report_path(
    tmp_path,
    mock_embeddings,
) -> None:
    """Run Clinic status includes report and trend-window metadata."""
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = replace(make_config(tmp_path / ".lerim"), projects={"repo": str(repo)})
    store = ContextStore(cfg.context_db_path)
    project_id = _register_seeded_project(store, repo)
    paths = run_clinic_paths(cfg, project_id)
    paths.current_dir.mkdir(parents=True)
    paths.current_file.write_text("# Run Clinic\n", encoding="utf-8")
    paths.current_report.write_text("{}", encoding="utf-8")
    paths.current_manifest.write_text(
        json.dumps(
            {
                "generated_at": "2100-01-01T00:00:00+00:00",
                "window_started_at": "2099-12-01T00:00:00+00:00",
                "window_days": 30,
                "records_included": 0,
                "records_considered": 0,
                "recent_versions_considered": 0,
                "sessions_considered": 0,
            }
        ),
        encoding="utf-8",
    )
    project = type(
        "Project",
        (),
        {"name": "repo", "identity": resolve_project_identity(repo)},
    )()

    payload = run_clinic_status_to_dict(
        run_clinic_status(config=cfg, store=store, project=project)
    )

    assert payload["availability"] == "available"
    assert payload["current_report"] == str(paths.current_report)
    assert payload["window_days"] == 30


def test_cli_clinic_show_reads_existing_artifact(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    mock_embeddings,
) -> None:
    """CLI show prints Run Clinic freshness before the current file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    config_path = write_test_config(tmp_path, projects={"repo": str(repo)})
    monkeypatch.setenv("LERIM_CONFIG", str(config_path))
    from lerim.config.settings import reload_config

    cfg = reload_config()
    store = ContextStore(cfg.context_db_path)
    project_id = _register_seeded_project(store, repo)
    paths = run_clinic_paths(cfg, project_id)
    paths.current_dir.mkdir(parents=True)
    paths.current_file.write_text("# Run Clinic\n\nhello clinic\n", encoding="utf-8")
    paths.current_report.write_text("{}", encoding="utf-8")
    paths.current_manifest.write_text(
        json.dumps(
            {
                "generated_at": "2100-01-01T00:00:00+00:00",
                "window_started_at": "2099-12-01T00:00:00+00:00",
                "window_days": 30,
                "records_included": 0,
                "records_considered": 0,
                "recent_versions_considered": 0,
                "sessions_considered": 0,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(repo)
    monkeypatch.setattr(
        "lerim.server.cli.run_clinic_for_project",
        lambda **_kwargs: pytest.fail("show must not refresh"),
    )

    code, output = run_cli(["clinic", "show"])

    assert code == 0
    assert "Run Clinic Live Status:" in output
    assert "hello clinic" in output
