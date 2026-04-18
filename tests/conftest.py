"""Shared test fixtures for Lerim's maintained unit test suite.

This file only supports the DB-only runtime.
It provides temporary global Lerim roots and trace fixture paths.
"""

import os
from pathlib import Path

import pytest

from tests.helpers import make_config


FIXTURES_DIR = Path(__file__).parent / "fixtures"
TRACES_DIR = FIXTURES_DIR / "traces"
TEST_CONFIG_PATH = Path(__file__).parent / "test_config.toml"


@pytest.fixture
def tmp_lerim_root(tmp_path):
    """Temporary global Lerim root with canonical folder structure."""
    (tmp_path / "workspace").mkdir()
    (tmp_path / "index").mkdir()
    return tmp_path


@pytest.fixture
def tmp_config(tmp_path, tmp_lerim_root):
    """Temporary config pointing at tmp_lerim_root."""
    return make_config(tmp_lerim_root)


def skip_unless_env(var_name):
    """Skip test unless environment variable is set."""
    return pytest.mark.skipif(
        not os.environ.get(var_name),
        reason=f"{var_name} not set",
    )
