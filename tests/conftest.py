"""Shared fixtures for the Smart Oil Gauge tests."""

import json
from pathlib import Path

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"

FIXTURES = Path(__file__).parent / "fixtures"
# 2026-10-11 13:12:38 UTC, a few minutes after the fixture's last reading.
NOW = 1791725558
NOW_ISO = "2026-10-11T13:12:38+00:00"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield
