"""Repairs flow for confirming LubeLogger's distance unit."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_DISTANCE_UNIT, CONF_DISTANCE_UNIT_CONFIRMED
from .util import distance_unit_selector, resolve_distance_unit


class DistanceUnitRepairFlow(RepairsFlow):
    """Ask the user which unit their LubeLogger instance reports distances in."""

    def __init__(self, entry_id: str) -> None:
        """Store the config entry this flow is repairing."""
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Start the flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show the unit picker and persist the confirmed answer."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return self.async_abort(reason="entry_not_found")

        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                entry,
                options={
                    **entry.options,
                    CONF_DISTANCE_UNIT: user_input[CONF_DISTANCE_UNIT],
                    CONF_DISTANCE_UNIT_CONFIRMED: True,
                },
            )
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DISTANCE_UNIT,
                        default=resolve_distance_unit(self.hass, entry.options),
                    ): distance_unit_selector(),
                }
            ),
            description_placeholders={"title": entry.title},
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the flow that fixes an unconfirmed distance unit."""
    entry_id = str((data or {}).get("entry_id", ""))
    return DistanceUnitRepairFlow(entry_id)
