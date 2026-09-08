"""Tests pinning what the recorder does when the distance unit option changes.

The README's "Upgrading from a version without this setting" section tells
users what happens to long-term statistics when they correct a wrong unit, and
that the fix is to delete the sensor's statistics. These tests exist so that
advice is checked against a running recorder rather than a reading of it.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from homeassistant.components.recorder import Recorder
from homeassistant.components.recorder.statistics import list_statistic_ids
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM, UnitSystem
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
    do_adhoc_statistics,
    get_start_time,
    statistics_during_period,
)

from custom_components.lubelogger.const import (
    CONF_DISTANCE_UNIT,
    CONF_URL,
    DISTANCE_UNIT_KILOMETERS,
    DISTANCE_UNIT_MILES,
    DOMAIN,
)

from .conftest import ODOMETER_RAW

ODOMETER_UNIQUE_ID = "1_last_reported_odometer"

# ODOMETER_RAW read as miles and converted to kilometers, and vice versa.
ODOMETER_AS_KM = 103844.530944
ODOMETER_AS_MILES = 40094.5975503062


async def _flip_the_unit_across_two_statistics_periods(
    hass: HomeAssistant, freezer: Any, unit_system: UnitSystem
) -> tuple[str, list[dict[str, Any]]]:
    """Record the odometer under `miles`, then under `kilometers`.

    Each reading lands in its own five minute statistics period, mimicking a
    user who corrects the option some time after the sensor started recording.
    Returns the odometer entity id and its two statistics points.
    """
    hass.config.units = unit_system
    zero = get_start_time(dt_util.utcnow())

    freezer.move_to(zero + timedelta(minutes=1))
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="https://lubelogger.example",
        data={
            CONF_URL: "https://lubelogger.example",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
        },
        options={CONF_DISTANCE_UNIT: DISTANCE_UNIT_MILES},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, ODOMETER_UNIQUE_ID
    )
    assert entity_id is not None

    await async_wait_recording_done(hass)
    do_adhoc_statistics(hass, start=zero)
    await async_wait_recording_done(hass)

    freezer.move_to(zero + timedelta(minutes=6))
    hass.config_entries.async_update_entry(
        entry, options={CONF_DISTANCE_UNIT: DISTANCE_UNIT_KILOMETERS}
    )
    await hass.async_block_till_done()

    await async_wait_recording_done(hass)
    do_adhoc_statistics(hass, start=zero + timedelta(minutes=5))
    await async_wait_recording_done(hass)

    stats = statistics_during_period(
        hass, zero, period="5minute", statistic_ids={entity_id}
    )
    points = stats[entity_id]
    assert len(points) == 2
    return entity_id, points


def _units_changed_issues(hass: HomeAssistant) -> list[str]:
    """Return the ids of any recorder units_changed repairs that were raised."""
    return [
        issue.issue_id
        for issue in ir.async_get(hass).issues.values()
        if (issue.data or {}).get("issue_type") == "units_changed"
    ]


@pytest.mark.usefixtures("mock_api")
async def test_correcting_the_unit_raises_no_units_changed_repair(
    recorder_mock: Recorder, hass: HomeAssistant, freezer: Any
) -> None:
    """Correcting the unit must not produce a units_changed repair.

    The README tells users no warning appears and that they have to notice the
    step themselves. If HA ever did start flagging this, that paragraph would
    be sending users looking for a repair that is already on screen.
    """
    entity_id, _ = await _flip_the_unit_across_two_statistics_periods(
        hass, freezer, US_CUSTOMARY_SYSTEM
    )

    assert _units_changed_issues(hass) == []
    assert ir.async_get(hass).async_get_issue("sensor", f"units_changed_{entity_id}") is None


@pytest.mark.usefixtures("mock_api")
async def test_readings_after_the_flip_are_rescaled_into_the_recorded_unit(
    recorder_mock: Recorder, hass: HomeAssistant, freezer: Any
) -> None:
    """The statistics unit stays put and later readings are converted into it.

    This is the claim the README's advice rests on: deleting the sensor's
    long-term statistics is only the right fix if the old points are stranded
    in the old unit. If new points were instead recorded in the corrected unit,
    the history would heal itself and the advice would be wrong.
    """
    entity_id, points = await _flip_the_unit_across_two_statistics_periods(
        hass, freezer, US_CUSTOMARY_SYSTEM
    )

    metadata = await hass.async_add_executor_job(list_statistic_ids, hass)
    odometer_metadata = next(
        entry for entry in metadata if entry["statistic_id"] == entity_id
    )
    assert odometer_metadata["statistics_unit_of_measurement"] == "mi"

    assert points[0]["state"] == pytest.approx(ODOMETER_RAW)
    assert points[1]["state"] == pytest.approx(ODOMETER_AS_MILES)


@pytest.mark.usefixtures("mock_api")
async def test_the_rescaled_drop_is_treated_as_a_meter_reset(
    recorder_mock: Recorder, hass: HomeAssistant, freezer: Any
) -> None:
    """The drop restarts the total_increasing sum rather than going backwards.

    A reset is what makes the step visible in the energy-style dashboards that
    read `sum`, and it is why the README warns about it at all. Without the
    reset handling the sum would go negative by the size of the conversion.
    """
    _, points = await _flip_the_unit_across_two_statistics_periods(
        hass, freezer, US_CUSTOMARY_SYSTEM
    )

    assert points[0]["sum"] == pytest.approx(0)
    # A continuing meter would have summed the delta, 40094.6 - 64526, and gone
    # negative. Starting again from the new reading is the reset.
    assert points[1]["sum"] == pytest.approx(ODOMETER_AS_MILES)


@pytest.mark.usefixtures("mock_api")
async def test_a_metric_install_steps_in_kilometers_not_miles(
    recorder_mock: Recorder, hass: HomeAssistant, freezer: Any
) -> None:
    """The step happens on a metric install too, in the other direction.

    The statistics unit follows the HA unit system, not the option, so a metric
    user correcting the same mistake sees kilometers throughout and a drop from
    the inflated value back to the real one. The README's worked example only
    covers the US customary case.
    """
    entity_id, points = await _flip_the_unit_across_two_statistics_periods(
        hass, freezer, METRIC_SYSTEM
    )

    metadata = await hass.async_add_executor_job(list_statistic_ids, hass)
    odometer_metadata = next(
        entry for entry in metadata if entry["statistic_id"] == entity_id
    )
    assert odometer_metadata["statistics_unit_of_measurement"] == "km"

    assert points[0]["state"] == pytest.approx(ODOMETER_AS_KM)
    assert points[1]["state"] == pytest.approx(ODOMETER_RAW)
    assert _units_changed_issues(hass) == []
