"""Tests for the LubeLogger sensor platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lubelogger.const import (
    CONF_DISTANCE_UNIT,
    CONF_URL,
    DISTANCE_UNIT_KILOMETERS,
    DISTANCE_UNIT_MILES,
    DOMAIN,
)

from .conftest import ODOMETER_RAW

ODOMETER_UNIQUE_ID = "1_last_reported_odometer"


async def _setup(
    hass: HomeAssistant, options: dict[str, Any] | None = None
) -> MockConfigEntry:
    """Add a config entry and run setup, returning the entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="https://lubelogger.example",
        data={
            CONF_URL: "https://lubelogger.example",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
        },
        options=options or {},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _odometer_state(hass: HomeAssistant) -> tuple[float, str]:
    """Return the odometer sensor's displayed value and unit."""
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, ODOMETER_UNIQUE_ID
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    return float(state.state), state.attributes["unit_of_measurement"]


@pytest.mark.usefixtures("mock_api")
async def test_metric_hass_treats_unset_option_as_kilometers(
    hass: HomeAssistant,
) -> None:
    """Issue #2: a metric HA install must not read LubeLogger's km as miles.

    With no distance_unit option stored, the odometer reading has to be taken at
    face value on a metric install. Declaring it as miles made HA multiply by
    1.609, which is what turned 64526 km into 103844 km for the reporter.
    """
    hass.config.units = METRIC_SYSTEM

    await _setup(hass)

    value, unit = _odometer_state(hass)
    assert unit == "km"
    assert value == pytest.approx(ODOMETER_RAW)


@pytest.mark.usefixtures("mock_api")
async def test_us_customary_hass_treats_unset_option_as_miles(
    hass: HomeAssistant,
) -> None:
    """A US install with no option stored keeps the previous miles behaviour."""
    hass.config.units = US_CUSTOMARY_SYSTEM

    await _setup(hass)

    value, unit = _odometer_state(hass)
    assert unit == "mi"
    assert value == pytest.approx(ODOMETER_RAW)


@pytest.mark.usefixtures("mock_api")
async def test_explicit_miles_option_overrides_metric_hass(
    hass: HomeAssistant,
) -> None:
    """An explicit miles option wins over HA's unit system.

    A metric HA user running LubeLogger in miles should get the reading
    converted for display rather than taken at face value.
    """
    hass.config.units = METRIC_SYSTEM

    await _setup(hass, {CONF_DISTANCE_UNIT: DISTANCE_UNIT_MILES})

    value, unit = _odometer_state(hass)
    assert unit == "km"
    assert value == pytest.approx(103844.5, abs=1)


@pytest.mark.usefixtures("mock_api")
async def test_explicit_kilometers_option_overrides_us_customary_hass(
    hass: HomeAssistant,
) -> None:
    """An explicit kilometers option wins over a US customary HA install."""
    hass.config.units = US_CUSTOMARY_SYSTEM

    await _setup(hass, {CONF_DISTANCE_UNIT: DISTANCE_UNIT_KILOMETERS})

    value, unit = _odometer_state(hass)
    assert unit == "mi"
    assert value == pytest.approx(40094.7, abs=1)


@pytest.mark.usefixtures("mock_api")
async def test_changing_the_option_reloads_the_entry(hass: HomeAssistant) -> None:
    """Updating the option must take effect without a manual restart."""
    hass.config.units = METRIC_SYSTEM

    entry = await _setup(hass, {CONF_DISTANCE_UNIT: DISTANCE_UNIT_MILES})
    assert _odometer_state(hass)[0] == pytest.approx(103844.5, abs=1)

    hass.config_entries.async_update_entry(
        entry, options={CONF_DISTANCE_UNIT: DISTANCE_UNIT_KILOMETERS}
    )
    await hass.async_block_till_done()

    value, unit = _odometer_state(hass)
    assert unit == "km"
    assert value == pytest.approx(ODOMETER_RAW)


async def test_currency_sensors_follow_hass_currency(
    hass: HomeAssistant, mock_api: AsyncMock
) -> None:
    """Cost sensors use hass.config.currency rather than a hardcoded USD."""
    hass.config.currency = "EUR"

    await _setup(hass)

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, "1_gas_record_cost"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["unit_of_measurement"] == "EUR"
