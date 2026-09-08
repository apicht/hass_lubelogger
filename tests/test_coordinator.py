"""Tests for the coordinator's handling of LubeLogger's response shapes."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lubelogger.api import (
    LubeLoggerAuthError,
    LubeLoggerConnectionError,
)
from custom_components.lubelogger.const import CONF_URL, DOMAIN
from custom_components.lubelogger.coordinator import LubeLoggerDataUpdateCoordinator

from .conftest import ODOMETER_RAW

TWO_VEHICLES = [
    {"id": 1, "make": "Ford", "model": "Kuga"},
    {"id": 2, "make": "Ford", "model": "F-150"},
]

STATS = {"lastReportedOdometer": ODOMETER_RAW, "gasRecordCost": 12.5}


def _coordinator(
    hass: HomeAssistant, client: AsyncMock
) -> LubeLoggerDataUpdateCoordinator:
    """Return a coordinator wired to the given client."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "https://lubelogger.example",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
        },
    )
    entry.add_to_hass(hass)
    return LubeLoggerDataUpdateCoordinator(hass, client, entry)


def _client(vehicle_info: Any, vehicles: list[dict[str, Any]] | None = None) -> AsyncMock:
    """Return a stub API client returning the given vehicle info shape."""
    client = AsyncMock()
    client.get_vehicles.return_value = vehicles or [TWO_VEHICLES[0]]
    client.get_vehicle_info.return_value = vehicle_info
    client.get_gas_records.return_value = []
    return client


@pytest.mark.parametrize(
    "shape",
    [[STATS], STATS],
    ids=["single_element_list", "bare_object"],
)
async def test_stats_are_merged_from_either_response_shape(
    hass: HomeAssistant, shape: Any
) -> None:
    """LubeLogger wraps one vehicle's stats in a list; older builds do not.

    The sensors read ``lastReportedOdometer`` off the merged dict, so if the
    unwrap regressed they would all go unavailable against a live instance
    while every mocked test still passed.
    """
    coordinator = _coordinator(hass, _client(shape))

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.data[1]["lastReportedOdometer"] == ODOMETER_RAW
    assert coordinator.data[1]["make"] == "Ford"


@pytest.mark.parametrize("shape", [[], None], ids=["empty_list", "null"])
async def test_empty_vehicle_info_does_not_abort_the_refresh(
    hass: HomeAssistant, shape: Any
) -> None:
    """One vehicle returning no stats must not take the other vehicles down.

    Neither shape is a mapping, so merging it raises ``TypeError`` - which is
    not a ``LubeLoggerApiError`` and so escapes the per-vehicle handler and
    fails the whole update. The vehicle keeps its basic info instead.
    """
    client = _client(shape, vehicles=TWO_VEHICLES)
    coordinator = _coordinator(hass, client)

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert set(coordinator.data) == {1, 2}
    assert coordinator.data[1]["model"] == "Kuga"
    assert "lastReportedOdometer" not in coordinator.data[1]


async def test_one_failing_vehicle_keeps_the_others(hass: HomeAssistant) -> None:
    """A per-vehicle API error is logged and skipped, not propagated."""
    client = _client([STATS], vehicles=TWO_VEHICLES)
    client.get_vehicle_info.side_effect = [
        LubeLoggerConnectionError("vehicle 1 timed out"),
        [STATS],
    ]
    coordinator = _coordinator(hass, client)

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert "lastReportedOdometer" not in coordinator.data[1]
    assert coordinator.data[2]["lastReportedOdometer"] == ODOMETER_RAW


async def test_failing_gas_records_keep_the_vehicle_stats(hass: HomeAssistant) -> None:
    """Gas records are an extra; losing them must not lose the cost sensors."""
    client = _client([STATS])
    client.get_gas_records.side_effect = LubeLoggerConnectionError("gone")
    coordinator = _coordinator(hass, client)

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.data[1]["gasRecordCost"] == 12.5
    assert "lastGasRecord" not in coordinator.data[1]


async def test_most_recent_gas_record_is_the_last_one(hass: HomeAssistant) -> None:
    """LubeLogger returns gas records oldest-first, so the tail is the latest.

    The gas cost sensor's attributes come from this record; reading [0] instead
    would pin them to the vehicle's first ever fill-up.
    """
    client = _client([STATS])
    client.get_gas_records.return_value = [
        {"date": "2026-01-01", "cost": 10.0},
        {"date": "2026-02-01", "cost": 20.0},
    ]
    coordinator = _coordinator(hass, client)

    await coordinator.async_refresh()

    assert coordinator.data[1]["lastGasRecord"]["date"] == "2026-02-01"


async def test_auth_failure_asks_home_assistant_for_reauth(
    hass: HomeAssistant,
) -> None:
    """Only ``ConfigEntryAuthFailed`` starts the reauth flow.

    Anything else is retried forever, so a rotated password would leave the
    entities unavailable with no prompt to fix it.
    """
    client = _client([STATS])
    client.get_vehicles.side_effect = LubeLoggerAuthError("nope")
    coordinator = _coordinator(hass, client)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_connection_failure_is_retried_not_reauthed(
    hass: HomeAssistant,
) -> None:
    """An unreachable instance is transient; it must not prompt for credentials."""
    client = _client([STATS])
    client.get_vehicles.side_effect = LubeLoggerConnectionError("no route")
    coordinator = _coordinator(hass, client)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
