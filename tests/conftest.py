"""Fixtures for the LubeLogger integration tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Enable loading of the custom_components directory in every test."""
    yield


# Odometer value straight from the reporter's LubeLogger instance in issue #2,
# where LubeLogger is configured for metric so the number is kilometers.
ODOMETER_RAW = 64526


@pytest.fixture
def vehicle_list() -> list[dict[str, Any]]:
    """Return a minimal /api/vehicles payload."""
    return [
        {
            "id": 1,
            "year": 2022,
            "make": "Ford",
            "model": "Kuga",
            "licensePlate": "",
        }
    ]


@pytest.fixture
def vehicle_info() -> list[dict[str, Any]]:
    """Return a minimal /api/vehicle/info payload."""
    return [
        {
            "serviceRecordCost": 0.0,
            "repairRecordCost": 0.0,
            "upgradeRecordCost": 0.0,
            "taxRecordCost": 0.0,
            "gasRecordCost": 0.0,
            "lastReportedOdometer": ODOMETER_RAW,
            "nextReminder": None,
        }
    ]


@pytest.fixture
def mock_api(
    vehicle_list: list[dict[str, Any]],
    vehicle_info: list[dict[str, Any]],
) -> Generator[AsyncMock]:
    """Patch the LubeLogger API client so no HTTP requests are made."""
    with patch(
        "custom_components.lubelogger.LubeLoggerApiClient", autospec=True
    ) as init_client, patch(
        "custom_components.lubelogger.config_flow.LubeLoggerApiClient", autospec=True
    ) as flow_client:
        client = init_client.return_value
        client.get_vehicles.return_value = vehicle_list
        client.get_vehicle_info.return_value = vehicle_info
        client.get_gas_records.return_value = []
        client.test_connection.return_value = True
        flow_client.return_value = client
        yield client
