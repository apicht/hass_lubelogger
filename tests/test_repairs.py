"""Tests for the distance unit repairs flow."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lubelogger import distance_unit_issue_id
from custom_components.lubelogger.const import (
    CONF_DISTANCE_UNIT,
    CONF_DISTANCE_UNIT_CONFIRMED,
    CONF_URL,
    DISTANCE_UNIT_KILOMETERS,
    DISTANCE_UNIT_MILES,
    DOMAIN,
)
from custom_components.lubelogger.repairs import async_create_fix_flow

ENTRY_DATA = {
    CONF_URL: "https://lubelogger.example",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
}


async def _setup(
    hass: HomeAssistant, options: dict[str, Any] | None = None
) -> MockConfigEntry:
    """Add an entry with the given options and set it up."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, options=options or {})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.usefixtures("mock_api")
async def test_legacy_entry_gets_guess_persisted_and_flagged(
    hass: HomeAssistant,
) -> None:
    """An entry with no unit stored is seeded and raises a repair.

    Persisting the guess is what stops the odometer's meaning from drifting if
    the user later changes Home Assistant's unit system, and the repair is what
    keeps the change from being silent for anyone the guess gets wrong.
    """
    hass.config.units = METRIC_SYSTEM

    entry = await _setup(hass)

    assert entry.options[CONF_DISTANCE_UNIT] == DISTANCE_UNIT_KILOMETERS
    assert entry.options[CONF_DISTANCE_UNIT_CONFIRMED] is False
    assert ir.async_get(hass).async_get_issue(DOMAIN, distance_unit_issue_id(entry))


@pytest.mark.usefixtures("mock_api")
async def test_persisted_guess_survives_unit_system_change(
    hass: HomeAssistant,
) -> None:
    """Changing HA's unit system must not change what the reading means.

    HA's unit system is a display preference; using it as a live claim about
    what LubeLogger stores would silently rescale the odometer.
    """
    hass.config.units = METRIC_SYSTEM
    entry = await _setup(hass)
    assert entry.options[CONF_DISTANCE_UNIT] == DISTANCE_UNIT_KILOMETERS

    hass.config.units = US_CUSTOMARY_SYSTEM
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.options[CONF_DISTANCE_UNIT] == DISTANCE_UNIT_KILOMETERS


@pytest.mark.usefixtures("mock_api")
async def test_confirmed_entry_raises_no_repair(hass: HomeAssistant) -> None:
    """An entry whose unit was chosen explicitly is left alone."""
    hass.config.units = METRIC_SYSTEM

    entry = await _setup(
        hass,
        {
            CONF_DISTANCE_UNIT: DISTANCE_UNIT_MILES,
            CONF_DISTANCE_UNIT_CONFIRMED: True,
        },
    )

    assert entry.options[CONF_DISTANCE_UNIT] == DISTANCE_UNIT_MILES
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, distance_unit_issue_id(entry))
        is None
    )


@pytest.mark.usefixtures("mock_api")
async def test_repair_flow_corrects_the_unit_and_clears_the_issue(
    hass: HomeAssistant,
) -> None:
    """The UK MPG case: metric HA, but LubeLogger reports miles."""
    assert await async_setup_component(hass, "repairs", {})
    hass.config.units = METRIC_SYSTEM
    entry = await _setup(hass)
    issue_id = distance_unit_issue_id(entry)
    assert entry.options[CONF_DISTANCE_UNIT] == DISTANCE_UNIT_KILOMETERS

    flow = await async_create_fix_flow(hass, issue_id, {"entry_id": entry.entry_id})
    flow.hass = hass

    form = await flow.async_step_init()
    assert form["type"] == "form"
    assert form["step_id"] == "confirm"

    result = await flow.async_step_confirm({CONF_DISTANCE_UNIT: DISTANCE_UNIT_MILES})
    await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert entry.options[CONF_DISTANCE_UNIT] == DISTANCE_UNIT_MILES
    assert entry.options[CONF_DISTANCE_UNIT_CONFIRMED] is True
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.usefixtures("mock_api")
async def test_repair_flow_aborts_when_entry_is_gone(hass: HomeAssistant) -> None:
    """A stale repair for a removed entry aborts instead of raising."""
    flow = await async_create_fix_flow(hass, "whatever", {"entry_id": "missing"})
    flow.hass = hass

    result = await flow.async_step_init()

    assert result["type"] == "abort"
    assert result["reason"] == "entry_not_found"


@pytest.mark.usefixtures("mock_api")
async def test_saving_options_confirms_the_unit(hass: HomeAssistant) -> None:
    """Using the Configure dialog is an explicit choice, so the repair clears."""
    hass.config.units = METRIC_SYSTEM
    entry = await _setup(hass)
    issue_id = distance_unit_issue_id(entry)
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DISTANCE_UNIT: DISTANCE_UNIT_MILES}
    )
    await hass.async_block_till_done()

    assert entry.options[CONF_DISTANCE_UNIT] == DISTANCE_UNIT_MILES
    assert entry.options[CONF_DISTANCE_UNIT_CONFIRMED] is True
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
