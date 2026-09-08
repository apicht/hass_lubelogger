"""Tests for the LubeLogger config and options flows."""

from __future__ import annotations

import pytest
import voluptuous as vol
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lubelogger.const import (
    CONF_DISTANCE_UNIT,
    CONF_URL,
    DISTANCE_UNIT_KILOMETERS,
    DISTANCE_UNIT_MILES,
    DOMAIN,
)

USER_INPUT = {
    CONF_URL: "https://lubelogger.example",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
}


def _schema_default(schema: vol.Schema, key: str) -> str:
    """Return the default value voluptuous will apply for a schema key."""
    for marker in schema.schema:
        if marker == key:
            return marker.default()
    pytest.fail(f"{key} missing from schema")


@pytest.mark.parametrize(
    ("unit_system", "expected_default"),
    [
        (METRIC_SYSTEM, DISTANCE_UNIT_KILOMETERS),
        (US_CUSTOMARY_SYSTEM, DISTANCE_UNIT_MILES),
    ],
)
@pytest.mark.usefixtures("mock_api")
async def test_user_step_defaults_unit_from_hass_unit_system(
    hass: HomeAssistant, unit_system, expected_default: str
) -> None:
    """The setup form pre-selects the unit implied by HA's unit system."""
    hass.config.units = unit_system

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert _schema_default(result["data_schema"], CONF_DISTANCE_UNIT) == expected_default


@pytest.mark.usefixtures("mock_api")
async def test_user_step_stores_unit_in_options(hass: HomeAssistant) -> None:
    """The chosen unit is written to entry options, not entry data."""
    hass.config.units = METRIC_SYSTEM

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**USER_INPUT, CONF_DISTANCE_UNIT: DISTANCE_UNIT_KILOMETERS},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_DISTANCE_UNIT: DISTANCE_UNIT_KILOMETERS}
    assert CONF_DISTANCE_UNIT not in result["data"]


@pytest.mark.usefixtures("mock_api")
async def test_options_flow_defaults_to_hass_unit_system_when_unset(
    hass: HomeAssistant,
) -> None:
    """An entry predating the setting shows HA's unit system, not miles."""
    hass.config.units = METRIC_SYSTEM
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert (
        _schema_default(result["data_schema"], CONF_DISTANCE_UNIT)
        == DISTANCE_UNIT_KILOMETERS
    )


@pytest.mark.usefixtures("mock_api")
async def test_options_flow_keeps_explicit_choice(hass: HomeAssistant) -> None:
    """A stored unit is shown as-is even when HA disagrees with it."""
    hass.config.units = METRIC_SYSTEM
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=USER_INPUT,
        options={CONF_DISTANCE_UNIT: DISTANCE_UNIT_MILES},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert (
        _schema_default(result["data_schema"], CONF_DISTANCE_UNIT)
        == DISTANCE_UNIT_MILES
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DISTANCE_UNIT: DISTANCE_UNIT_KILOMETERS}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_DISTANCE_UNIT] == DISTANCE_UNIT_KILOMETERS
