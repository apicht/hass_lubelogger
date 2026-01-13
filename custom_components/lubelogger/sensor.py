"""Sensor platform for LubeLogger."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DUE_DATE,
    ATTR_DUE_DAYS,
    ATTR_DUE_DISTANCE,
    ATTR_DUE_ODOMETER,
    ATTR_LAST_COST,
    ATTR_LAST_DATE,
    ATTR_LAST_FUEL_CONSUMED,
    ATTR_LAST_ODOMETER,
    ATTR_METRIC,
    ATTR_REMINDER_ID,
    ATTR_TAGS,
    ATTR_URGENCY,
    CONF_DISTANCE_UNIT,
    DISTANCE_UNIT_KILOMETERS,
    DISTANCE_UNIT_MILES,
    DOMAIN,
    SENSOR_GAS_COST,
    SENSOR_NEXT_REMINDER,
    SENSOR_ODOMETER,
    SENSOR_REPAIR_COST,
    SENSOR_SERVICE_COST,
    SENSOR_TAX_COST,
    SENSOR_UPGRADE_COST,
    UNIT_TYPE_CURRENCY,
    UNIT_TYPE_DISTANCE,
)
from .coordinator import LubeLoggerDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class LubeLoggerSensorEntityDescription(SensorEntityDescription):
    """Describes a LubeLogger sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any]
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    unit_type: str | None = None


def _get_reminder_attributes(reminder: dict[str, Any] | None) -> dict[str, Any]:
    """Extract reminder attributes from the nextReminder object.

    Args:
        reminder: The nextReminder dictionary from vehicle info.

    Returns:
        Dictionary of reminder attributes for the sensor.
    """
    if not reminder:
        return {}

    return {
        ATTR_REMINDER_ID: reminder.get("id"),
        ATTR_URGENCY: reminder.get("urgency"),
        ATTR_METRIC: reminder.get("metric"),
        ATTR_DUE_DATE: reminder.get("dueDate"),
        ATTR_DUE_ODOMETER: reminder.get("dueOdometer"),
        ATTR_DUE_DAYS: reminder.get("dueDays"),
        ATTR_DUE_DISTANCE: reminder.get("dueDistance"),
        ATTR_TAGS: reminder.get("tags"),
    }


def _get_gas_record_attributes(gas_record: dict[str, Any] | None) -> dict[str, Any]:
    """Extract attributes from the last gas record.

    Args:
        gas_record: The lastGasRecord dictionary from vehicle data.

    Returns:
        Dictionary of gas record attributes for the sensor.
    """
    if not gas_record:
        return {}

    return {
        ATTR_LAST_ODOMETER: gas_record.get("odometer"),
        ATTR_LAST_DATE: gas_record.get("date"),
        ATTR_LAST_FUEL_CONSUMED: gas_record.get("fuelConsumed"),
        ATTR_LAST_COST: gas_record.get("cost"),
    }


SENSOR_DESCRIPTIONS: tuple[LubeLoggerSensorEntityDescription, ...] = (
    LubeLoggerSensorEntityDescription(
        key=SENSOR_SERVICE_COST,
        translation_key=SENSOR_SERVICE_COST,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        unit_type=UNIT_TYPE_CURRENCY,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("serviceRecordCost"),
    ),
    LubeLoggerSensorEntityDescription(
        key=SENSOR_REPAIR_COST,
        translation_key=SENSOR_REPAIR_COST,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        unit_type=UNIT_TYPE_CURRENCY,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("repairRecordCost"),
    ),
    LubeLoggerSensorEntityDescription(
        key=SENSOR_UPGRADE_COST,
        translation_key=SENSOR_UPGRADE_COST,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        unit_type=UNIT_TYPE_CURRENCY,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("upgradeRecordCost"),
    ),
    LubeLoggerSensorEntityDescription(
        key=SENSOR_TAX_COST,
        translation_key=SENSOR_TAX_COST,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        unit_type=UNIT_TYPE_CURRENCY,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("taxRecordCost"),
    ),
    LubeLoggerSensorEntityDescription(
        key=SENSOR_GAS_COST,
        translation_key=SENSOR_GAS_COST,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        unit_type=UNIT_TYPE_CURRENCY,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("gasRecordCost"),
        attributes_fn=lambda data: _get_gas_record_attributes(data.get("lastGasRecord")),
    ),
    LubeLoggerSensorEntityDescription(
        key=SENSOR_ODOMETER,
        translation_key=SENSOR_ODOMETER,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        unit_type=UNIT_TYPE_DISTANCE,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("lastReportedOdometer"),
    ),
    LubeLoggerSensorEntityDescription(
        key=SENSOR_NEXT_REMINDER,
        translation_key=SENSOR_NEXT_REMINDER,
        icon="mdi:bell-ring",
        value_fn=lambda data: (
            data.get("nextReminder", {}).get("description")
            if data.get("nextReminder")
            else None
        ),
        attributes_fn=lambda data: _get_reminder_attributes(data.get("nextReminder")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LubeLogger sensors from a config entry.

    Creates sensor entities for each vehicle tracked by this LubeLogger instance.
    Each vehicle gets all sensor types defined in SENSOR_DESCRIPTIONS.
    """
    coordinator: LubeLoggerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[LubeLoggerSensor] = []

    for vehicle_id in coordinator.data:
        for description in SENSOR_DESCRIPTIONS:
            entities.append(
                LubeLoggerSensor(
                    coordinator=coordinator,
                    vehicle_id=vehicle_id,
                    description=description,
                )
            )

    async_add_entities(entities)


class LubeLoggerSensor(CoordinatorEntity[LubeLoggerDataUpdateCoordinator], SensorEntity):
    """Representation of a LubeLogger sensor.

    Each sensor is associated with a specific vehicle and tracks one aspect
    of that vehicle's data (cost totals, odometer, or next reminder).
    """

    entity_description: LubeLoggerSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LubeLoggerDataUpdateCoordinator,
        vehicle_id: int,
        description: LubeLoggerSensorEntityDescription,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: The data update coordinator.
            vehicle_id: The ID of the vehicle this sensor is for.
            description: Entity description defining sensor behavior.
        """
        super().__init__(coordinator)
        self.entity_description = description
        self._vehicle_id = vehicle_id
        self._attr_unique_id = f"{vehicle_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity.

        Groups all sensors for a vehicle under a single device entry.
        """
        vehicle_data = self.coordinator.data.get(self._vehicle_id, {})
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._vehicle_id))},
            name=self._get_vehicle_name(vehicle_data),
            manufacturer=vehicle_data.get("make", "Unknown"),
            model=vehicle_data.get("model"),
            sw_version=str(vehicle_data.get("year", "")),
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        vehicle_data = self.coordinator.data.get(self._vehicle_id, {})
        return self.entity_description.value_fn(vehicle_data)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement based on config.

        Dynamically resolves units:
        - Currency sensors use hass.config.currency
        - Distance sensors use the unit configured in integration options
        """
        if self.entity_description.unit_type == UNIT_TYPE_CURRENCY:
            return self.hass.config.currency or "USD"

        if self.entity_description.unit_type == UNIT_TYPE_DISTANCE:
            # Get user's configured distance unit from options
            distance_unit = self.coordinator.config_entry.options.get(
                CONF_DISTANCE_UNIT, DISTANCE_UNIT_MILES
            )
            if distance_unit == DISTANCE_UNIT_KILOMETERS:
                return UnitOfLength.KILOMETERS
            return UnitOfLength.MILES

        return self.entity_description.native_unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes.

        Used by the next_reminder sensor to expose reminder details.
        """
        if self.entity_description.attributes_fn is None:
            return None

        vehicle_data = self.coordinator.data.get(self._vehicle_id, {})
        return self.entity_description.attributes_fn(vehicle_data)

    def _get_vehicle_name(self, vehicle_data: dict[str, Any]) -> str:
        """Generate a display name for a vehicle.

        Creates a name from year, make, and model (e.g., "2020 Toyota Camry").
        Falls back to "Vehicle {id}" if no info is available.
        """
        year = vehicle_data.get("year", "")
        make = vehicle_data.get("make", "")
        model = vehicle_data.get("model", "")

        name_parts = [str(year), make, model]
        name = " ".join(p for p in name_parts if p).strip()

        return name or f"Vehicle {self._vehicle_id}"
