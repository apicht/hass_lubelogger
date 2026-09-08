"""Helpers shared between the LubeLogger config flow, repairs and platforms."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import CONF_DISTANCE_UNIT, DISTANCE_UNIT_KILOMETERS, DISTANCE_UNIT_MILES


def default_distance_unit(hass: HomeAssistant) -> str:
    """Return the distance unit implied by Home Assistant's own unit system.

    LubeLogger stores odometer readings as bare numbers whose unit comes from
    its fuel mileage settings, and no API endpoint exposes them. Home
    Assistant's unit system is the best available guess, but it is only a
    guess: a metric install paired with LubeLogger's UK MPG mode reports
    distances in miles. Guesses are therefore confirmed via a repairs issue
    rather than trusted indefinitely.
    """
    if hass.config.units is METRIC_SYSTEM:
        return DISTANCE_UNIT_KILOMETERS
    return DISTANCE_UNIT_MILES


def resolve_distance_unit(hass: HomeAssistant, options: Mapping[str, Any]) -> str:
    """Return the distance unit to interpret LubeLogger odometer values with.

    A stored unit always wins. Entries created before the setting existed have
    nothing stored, so they fall back to Home Assistant's unit system rather
    than to a hardcoded imperial default (issue #2).
    """
    return options.get(CONF_DISTANCE_UNIT) or default_distance_unit(hass)


def distance_unit_selector() -> SelectSelector:
    """Return the distance unit dropdown, labelled from translations."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[DISTANCE_UNIT_MILES, DISTANCE_UNIT_KILOMETERS],
            mode=SelectSelectorMode.DROPDOWN,
            translation_key=CONF_DISTANCE_UNIT,
        )
    )
