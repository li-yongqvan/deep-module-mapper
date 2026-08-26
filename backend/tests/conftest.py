"""Shared test fixtures for the backend API."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from backend.app import app


@pytest.fixture
def mini_pkg() -> Path:
    """Return the path to a valid Python fixture package."""
    return Path(__file__).parent / "fixtures" / "mini_pkg"


@pytest.fixture
def broken_pkg() -> Path:
    """Return the path to a fixture package containing a syntax error."""
    return Path(__file__).parent / "fixtures" / "broken_pkg"


@pytest.fixture
def client() -> TestClient:
    """Return a Starlette TestClient for the backend app."""
    return TestClient(app)
