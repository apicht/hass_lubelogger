"""Unit tests for distance unit resolution."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from custom_components.lubelogger.const import (
    CONF_DISTANCE_UNIT,
    DISTANCE_UNIT_KILOMETERS,
    DISTANCE_UNIT_MILES,
)
from custom_components.lubelogger.util import (
    default_distance_unit,
    resolve_distance_unit,
)


@pytest.mark.parametrize(
    ("unit_system", "expected"),
    [
        (METRIC_SYSTEM, DISTANCE_UNIT_KILOMETERS),
        (US_CUSTOMARY_SYSTEM, DISTANCE_UNIT_MILES),
    ],
    ids=["metric", "us_customary"],
)
async def test_default_follows_unit_system(
    hass: HomeAssistant, unit_system, expected: str
) -> None:
    """The guess is derived from HA's unit system."""
    hass.config.units = unit_system

    assert default_distance_unit(hass) == expected


@pytest.mark.parametrize("stored", [None, ""], ids=["missing", "empty"])
async def test_falsy_stored_values_fall_back(hass: HomeAssistant, stored) -> None:
    """A missing or blank stored unit falls back to HA's unit system."""
    hass.config.units = METRIC_SYSTEM
    options = {} if stored is None else {CONF_DISTANCE_UNIT: stored}

    assert resolve_distance_unit(hass, options) == DISTANCE_UNIT_KILOMETERS


async def test_stored_value_wins_over_unit_system(hass: HomeAssistant) -> None:
    """An explicitly stored unit is never second-guessed."""
    hass.config.units = METRIC_SYSTEM

    assert (
        resolve_distance_unit(hass, {CONF_DISTANCE_UNIT: DISTANCE_UNIT_MILES})
        == DISTANCE_UNIT_MILES
    )


async def test_unrecognised_stored_value_is_returned_verbatim(
    hass: HomeAssistant,
) -> None:
    """An unknown stored value is passed through, not silently remapped.

    Only the two selector values are ever written, so this documents the
    contract rather than a supported configuration: the caller in sensor.py
    treats anything that is not "kilometers" as miles.
    """
    hass.config.units = METRIC_SYSTEM

    assert resolve_distance_unit(hass, {CONF_DISTANCE_UNIT: "km"}) == "km"
