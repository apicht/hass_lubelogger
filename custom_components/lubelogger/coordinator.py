"""DataUpdateCoordinator for LubeLogger."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    LubeLoggerApiClient,
    LubeLoggerApiError,
    LubeLoggerAuthError,
    LubeLoggerConnectionError,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class LubeLoggerDataUpdateCoordinator(DataUpdateCoordinator[dict[int, dict[str, Any]]]):
    """Class to manage fetching LubeLogger data.

    This coordinator fetches data from the LubeLogger API and provides it to
    all entities. It handles:
    - Fetching the list of vehicles
    - Fetching detailed info for each vehicle
    - Error handling and retry logic
    - Authentication failure detection
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: LubeLoggerApiClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance.
            client: LubeLogger API client.
            config_entry: Config entry for this integration instance.
        """
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[int, dict[str, Any]]:
        """Fetch data from LubeLogger API.

        Returns:
            Dictionary mapping vehicle IDs to their data including:
            - Basic vehicle info (make, model, year, etc.)
            - Cost totals (service, repair, upgrade, tax, gas)
            - Last reported odometer
            - Next reminder info

        Raises:
            ConfigEntryAuthFailed: If authentication fails (triggers reauth).
            UpdateFailed: If data fetching fails (coordinator will retry).
        """
        try:
            # First, get list of all vehicles
            vehicles_list = await self.client.get_vehicles()

            # Then fetch detailed info for each vehicle
            data: dict[int, dict[str, Any]] = {}
            for vehicle in vehicles_list:
                vehicle_id = vehicle["id"]
                try:
                    vehicle_info = await self.client.get_vehicle_info(vehicle_id)

                    # Merge basic vehicle info with detailed info
                    data[vehicle_id] = {
                        **vehicle,
                        **vehicle_info,
                    }
                except LubeLoggerApiError as err:
                    # Log error but continue with other vehicles
                    _LOGGER.warning(
                        "Failed to fetch info for vehicle %s: %s", vehicle_id, err
                    )
                    # Include basic info even if detailed fetch fails
                    data[vehicle_id] = vehicle

            return data

        except LubeLoggerAuthError as err:
            # This will trigger reauthentication flow
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except LubeLoggerConnectionError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except LubeLoggerApiError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
