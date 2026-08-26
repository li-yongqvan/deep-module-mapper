"""Shared fixtures: paths under parser/tests/fixtures."""

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def sample_pkg() -> Path:
    return FIXTURES / "sample_pkg"
