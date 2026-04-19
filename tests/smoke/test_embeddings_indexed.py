"""Smoke test: embeddings are indexed after extraction."""

import pytest

from lerim.context import ContextStore
from tests.integration.extract_helpers import run_extract_case

pytestmark = [
	pytest.mark.smoke,
	pytest.mark.llm,
	pytest.mark.agent,
]


def test_embeddings_indexed(live_config, live_repo_root):
	"""Verify embeddings are indexed after extracting a decision.

	Uses clear_decision_with_noise fixture which creates a durable record.
	"""
	outcome = run_extract_case(
		case_name="clear_decision_with_noise",
		live_config=live_config,
		live_repo_root=live_repo_root,
	)

	assert outcome.result is not None, "Extraction returned no result"

	store = ContextStore(live_config.context_db_path)
	with store.connect() as conn:
		count = conn.execute("SELECT COUNT(*) FROM record_embeddings").fetchone()[0]

	assert count > 0, "No embeddings indexed after extraction"
