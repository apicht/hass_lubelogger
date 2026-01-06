"""The LubeLogger integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LubeLoggerApiClient, LubeLoggerApiError
from .const import (
    CONF_URL,
    DOMAIN,
    SERVICE_ADD_GAS,
    SERVICE_ADD_ODOMETER,
    SERVICE_ADD_REMINDER,
)
from .coordinator import LubeLoggerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Service schemas
SERVICE_ADD_ODOMETER_SCHEMA = vol.Schema(
    {
        vol.Required("vehicle_id"): cv.positive_int,
        vol.Required("date"): cv.string,
        vol.Required("odometer"): vol.Coerce(float),
        vol.Optional("notes", default=""): cv.string,
        vol.Optional("tags", default=""): cv.string,
    }
)

SERVICE_ADD_GAS_SCHEMA = vol.Schema(
    {
        vol.Required("vehicle_id"): cv.positive_int,
        vol.Required("date"): cv.string,
        vol.Required("odometer"): vol.Coerce(float),
        vol.Required("fuel_consumed"): vol.Coerce(float),
        vol.Required("cost"): vol.Coerce(float),
        vol.Optional("is_fill_to_full", default=True): cv.boolean,
        vol.Optional("missed_fuel_up", default=False): cv.boolean,
        vol.Optional("notes", default=""): cv.string,
        vol.Optional("tags", default=""): cv.string,
    }
)

SERVICE_ADD_REMINDER_SCHEMA = vol.Schema(
    {
        vol.Required("vehicle_id"): cv.positive_int,
        vol.Required("description"): cv.string,
        vol.Optional("due_date"): cv.string,
        vol.Optional("due_odometer"): vol.Coerce(float),
        vol.Optional("metric", default="Both"): vol.In(["Date", "Odometer", "Both"]),
        vol.Optional("notes", default=""): cv.string,
        vol.Optional("tags", default=""): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LubeLogger from a config entry.

    This function:
    1. Creates the API client and coordinator
    2. Fetches initial data
    3. Registers devices for each vehicle
    4. Sets up sensor platform
    5. Registers services

    Args:
        hass: Home Assistant instance.
        entry: Config entry containing connection details.

    Returns:
        True if setup was successful.
    """
    session = async_get_clientsession(hass)
    client = LubeLoggerApiClient(
        session,
        entry.data[CONF_URL],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    coordinator = LubeLoggerDataUpdateCoordinator(hass, client, entry)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator for platforms to access
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Register devices for each vehicle
    device_registry = dr.async_get(hass)
    for vehicle_id, vehicle_data in coordinator.data.items():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, str(vehicle_id))},
            name=_get_vehicle_name(vehicle_data),
            manufacturer=vehicle_data.get("make", "Unknown"),
            model=vehicle_data.get("model"),
            sw_version=str(vehicle_data.get("year", "")),
        )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (only once, not per entry)
    await _async_register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Args:
        hass: Home Assistant instance.
        entry: Config entry to unload.

    Returns:
        True if unload was successful.
    """
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def _get_vehicle_name(vehicle_data: dict[str, Any]) -> str:
    """Generate a display name for a vehicle.

    Args:
        vehicle_data: Vehicle data dictionary from the API.

    Returns:
        Human-readable vehicle name.
    """
    year = vehicle_data.get("year", "")
    make = vehicle_data.get("make", "")
    model = vehicle_data.get("model", "")
    license_plate = vehicle_data.get("licensePlate", "")

    name_parts = [str(year), make, model]
    name = " ".join(p for p in name_parts if p).strip()

    if license_plate:
        name = f"{name} ({license_plate})" if name else license_plate

    return name or f"Vehicle {vehicle_data.get('id', 'Unknown')}"


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services.

    Services are registered once globally for the integration,
    not per config entry.
    """
    # Skip if already registered
    if hass.services.has_service(DOMAIN, SERVICE_ADD_ODOMETER):
        return

    async def handle_add_odometer(call: ServiceCall) -> None:
        """Handle add_odometer_record service call."""
        vehicle_id = call.data["vehicle_id"]
        coordinator = _get_coordinator_for_vehicle(hass, vehicle_id)
        if coordinator is None:
            _LOGGER.error("Vehicle %s not found in any LubeLogger instance", vehicle_id)
            return

        try:
            await coordinator.client.add_odometer_record(
                vehicle_id=vehicle_id,
                date=call.data["date"],
                odometer=call.data["odometer"],
                notes=call.data.get("notes", ""),
                tags=call.data.get("tags", ""),
            )
            _LOGGER.debug("Added odometer record for vehicle %s", vehicle_id)

            # Refresh data after adding record
            await coordinator.async_request_refresh()
        except LubeLoggerApiError as err:
            _LOGGER.error("Failed to add odometer record: %s", err)

    async def handle_add_gas(call: ServiceCall) -> None:
        """Handle add_gas_record service call."""
        vehicle_id = call.data["vehicle_id"]
        coordinator = _get_coordinator_for_vehicle(hass, vehicle_id)
        if coordinator is None:
            _LOGGER.error("Vehicle %s not found in any LubeLogger instance", vehicle_id)
            return

        try:
            await coordinator.client.add_gas_record(
                vehicle_id=vehicle_id,
                date=call.data["date"],
                odometer=call.data["odometer"],
                fuel_consumed=call.data["fuel_consumed"],
                cost=call.data["cost"],
                is_fill_to_full=call.data.get("is_fill_to_full", True),
                missed_fuel_up=call.data.get("missed_fuel_up", False),
                notes=call.data.get("notes", ""),
                tags=call.data.get("tags", ""),
            )
            _LOGGER.debug("Added gas record for vehicle %s", vehicle_id)

            # Refresh data after adding record
            await coordinator.async_request_refresh()
        except LubeLoggerApiError as err:
            _LOGGER.error("Failed to add gas record: %s", err)

    async def handle_add_reminder(call: ServiceCall) -> None:
        """Handle add_reminder service call."""
        vehicle_id = call.data["vehicle_id"]
        coordinator = _get_coordinator_for_vehicle(hass, vehicle_id)
        if coordinator is None:
            _LOGGER.error("Vehicle %s not found in any LubeLogger instance", vehicle_id)
            return

        try:
            await coordinator.client.add_reminder(
                vehicle_id=vehicle_id,
                description=call.data["description"],
                due_date=call.data.get("due_date"),
                due_odometer=call.data.get("due_odometer"),
                metric=call.data.get("metric", "Both"),
                notes=call.data.get("notes", ""),
                tags=call.data.get("tags", ""),
            )
            _LOGGER.debug("Added reminder for vehicle %s", vehicle_id)

            # Refresh data after adding reminder
            await coordinator.async_request_refresh()
        except LubeLoggerApiError as err:
            _LOGGER.error("Failed to add reminder: %s", err)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_ODOMETER,
        handle_add_odometer,
        schema=SERVICE_ADD_ODOMETER_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_GAS,
        handle_add_gas,
        schema=SERVICE_ADD_GAS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_REMINDER,
        handle_add_reminder,
        schema=SERVICE_ADD_REMINDER_SCHEMA,
    )


def _get_coordinator_for_vehicle(
    hass: HomeAssistant, vehicle_id: int
) -> LubeLoggerDataUpdateCoordinator | None:
    """Find the coordinator that has the specified vehicle.

    Searches all LubeLogger config entries to find which one
    contains the requested vehicle.

    Args:
        hass: Home Assistant instance.
        vehicle_id: The vehicle ID to find.

    Returns:
        The coordinator containing the vehicle, or None if not found.
    """
    for coordinator in hass.data.get(DOMAIN, {}).values():
        if vehicle_id in coordinator.data:
            return coordinator
    return None
