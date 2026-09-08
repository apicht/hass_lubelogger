"""Tests for the version 1 → 2 config entry migration."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lubelogger import CONFIG_ENTRY_VERSION, distance_unit_issue_id
from custom_components.lubelogger.const import (
    CONF_DISTANCE_UNIT,
    CONF_DISTANCE_UNIT_CONFIRMED,
    CONF_URL,
    DISTANCE_UNIT_KILOMETERS,
    DISTANCE_UNIT_MILES,
    DOMAIN,
)

ENTRY_DATA = {
    CONF_URL: "https://lubelogger.example",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
}


async def _setup_v1(
    hass: HomeAssistant, options: dict[str, Any] | None = None
) -> MockConfigEntry:
    """Add a version 1 entry and set it up, running the migration."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=ENTRY_DATA, options=options or {}, version=1
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _has_issue(hass: HomeAssistant, entry: MockConfigEntry) -> bool:
    """Return whether the confirm-the-unit repair is raised for this entry."""
    return (
        ir.async_get(hass).async_get_issue(DOMAIN, distance_unit_issue_id(entry))
        is not None
    )


@pytest.mark.parametrize(
    ("unit_system", "expected"),
    [
        (METRIC_SYSTEM, DISTANCE_UNIT_KILOMETERS),
        (US_CUSTOMARY_SYSTEM, DISTANCE_UNIT_MILES),
    ],
    ids=["metric", "us_customary"],
)
@pytest.mark.usefixtures("mock_api")
async def test_entry_without_a_unit_is_seeded_and_flagged(
    hass: HomeAssistant, unit_system, expected: str
) -> None:
    """An entry predating the setting gets a guess plus a repair to confirm it."""
    hass.config.units = unit_system

    entry = await _setup_v1(hass)

    assert entry.version == CONFIG_ENTRY_VERSION
    assert entry.options[CONF_DISTANCE_UNIT] == expected
    assert entry.options[CONF_DISTANCE_UNIT_CONFIRMED] is False
    assert _has_issue(hass, entry)


@pytest.mark.usefixtures("mock_api")
async def test_unit_already_chosen_is_treated_as_confirmed(
    hass: HomeAssistant,
) -> None:
    """A unit set through the old options flow must not raise a repair.

    Those users already answered the question. Nagging them would be worse
    than the bug being fixed, and it would ask about a value that is right.
    """
    hass.config.units = METRIC_SYSTEM

    entry = await _setup_v1(hass, {CONF_DISTANCE_UNIT: DISTANCE_UNIT_MILES})

    assert entry.version == CONFIG_ENTRY_VERSION
    assert entry.options[CONF_DISTANCE_UNIT] == DISTANCE_UNIT_MILES
    assert entry.options[CONF_DISTANCE_UNIT_CONFIRMED] is True
    assert not _has_issue(hass, entry)


@pytest.mark.usefixtures("mock_api")
async def test_migration_preserves_unrelated_options(hass: HomeAssistant) -> None:
    """Migrating must not drop options this version does not know about."""
    hass.config.units = METRIC_SYSTEM

    entry = await _setup_v1(hass, {"some_future_option": "keep me"})

    assert entry.options["some_future_option"] == "keep me"
    assert entry.options[CONF_DISTANCE_UNIT] == DISTANCE_UNIT_KILOMETERS


@pytest.mark.usefixtures("mock_api")
async def test_migration_is_idempotent(hass: HomeAssistant) -> None:
    """Reloading a migrated entry must not re-flag a confirmed unit."""
    hass.config.units = METRIC_SYSTEM
    entry = await _setup_v1(hass, {CONF_DISTANCE_UNIT: DISTANCE_UNIT_MILES})

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == CONFIG_ENTRY_VERSION
    assert entry.options[CONF_DISTANCE_UNIT] == DISTANCE_UNIT_MILES
    assert entry.options[CONF_DISTANCE_UNIT_CONFIRMED] is True
    assert not _has_issue(hass, entry)


@pytest.mark.usefixtures("mock_api")
async def test_entry_from_a_newer_version_is_not_loaded(
    hass: HomeAssistant,
) -> None:
    """A downgrade must fail cleanly rather than misread the entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        options={},
        version=CONFIG_ENTRY_VERSION + 1,
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert not _has_issue(hass, entry)
