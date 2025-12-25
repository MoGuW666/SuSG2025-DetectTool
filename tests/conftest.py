"""
Pytest configuration and shared fixtures.

This file is automatically loaded by pytest and provides
common fixtures and configuration for all test files.
"""
from __future__ import annotations
import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def fixtures_dir():
    """Return the test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def config_path(project_root):
    """Return path to the default rules configuration."""
    return project_root / "configs" / "rules.yaml"


@pytest.fixture(scope="session")
def test_log_path(fixtures_dir):
    """Return path to the test log file."""
    return fixtures_dir / "test.log"
