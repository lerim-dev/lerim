"""Smoke test: extraction completes without crashing."""

import pytest

from tests.integration.extract_helpers import run_extract_case

pytestmark = [
	pytest.mark.smoke,
	pytest.mark.llm,
	pytest.mark.agent,
]


def test_extract_completes(live_config, live_repo_root):
	"""Verify extraction completes without crashing.

	Uses the smallest fixture: routine_operational_no_memory.jsonl (5 lines).
	This trace contains routine cleanup work with no durable memory.
	"""
	outcome = run_extract_case(
		case_name="routine_operational_no_memory",
		live_config=live_config,
		live_repo_root=live_repo_root,
	)

	assert outcome.result is not None, "Extraction returned no result"
	assert outcome.result.completion_summary, "Extraction returned empty summary"
