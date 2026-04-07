"""Pytest fixtures for Arquero API integration tests.

Prerequisites:
  A running Arquero API server reachable at ARQUERO_API_URL
  (default: http://localhost:3336).

Quick start:
  cd projects/arquero/api && npm install && node server.mjs
"""
from __future__ import annotations

import os
import pytest

from .client import ArqueroClient


@pytest.fixture(scope="session")
def api_url() -> str:
    return os.environ.get("ARQUERO_API_URL", "http://localhost:3336")


@pytest.fixture(scope="session")
def aq(api_url: str) -> ArqueroClient:
    """Session-scoped client — the API is stateless, no teardown needed."""
    return ArqueroClient(api_url)
