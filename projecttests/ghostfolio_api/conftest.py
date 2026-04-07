"""Pytest fixtures for Ghostfolio API integration tests.

Prerequisites:
  A running Ghostfolio instance reachable at GHOSTFOLIO_API_URL
  (default: http://localhost:3333).

  The instance must allow new user registration (ENABLE_FEATURE_RESTRICTED_VIEW=false).
  The first user created becomes an admin, which is required to seed market data.

Quick start with Docker:
  cd projects/ghostfolio
  cp .env.example .env   # fill in passwords
  docker compose -f docker/docker-compose.yml up -d
  # wait for health check, then run tests
"""
from __future__ import annotations

import os
import pytest

from .client import GhostfolioClient


@pytest.fixture(scope="session")
def api_url() -> str:
    return os.environ.get("GHOSTFOLIO_API_URL", "http://localhost:3335")


@pytest.fixture
def gf(api_url: str):
    """Create a fresh Ghostfolio user, yield (client, access_token), then delete the user."""
    client = GhostfolioClient(api_url)
    print("conftest.py:" + repr(33) + ":api_url:" + repr(api_url))
    access_token, auth_token = client.create_user()
    client.set_auth(auth_token)
    yield client, access_token
    try:
        client.delete_own_user(access_token)
    except Exception:
        pass  # best-effort cleanup
