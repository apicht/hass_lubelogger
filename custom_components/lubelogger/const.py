"""Constants for the LubeLogger integration."""

from datetime import timedelta
from typing import Final

# Integration identifiers
DOMAIN: Final = "lubelogger"
MANUFACTURER: Final = "LubeLogger"

# Configuration keys (using Home Assistant's standard CONF_* where possible)
CONF_URL: Final = "url"

# Default values
DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=30)

# API endpoints
API_VEHICLES: Final = "/api/vehicles"
API_VEHICLE_INFO: Final = "/api/vehicle/info"
API_ADD_ODOMETER: Final = "/api/vehicle/odometerrecords/add"
API_ADD_GAS: Final = "/api/vehicle/gasrecords/add"
API_ADD_REMINDER: Final = "/api/vehicle/reminders/add"

# Sensor keys
SENSOR_SERVICE_COST: Final = "service_record_cost"
SENSOR_REPAIR_COST: Final = "repair_record_cost"
SENSOR_UPGRADE_COST: Final = "upgrade_record_cost"
SENSOR_TAX_COST: Final = "tax_record_cost"
SENSOR_GAS_COST: Final = "gas_record_cost"
SENSOR_ODOMETER: Final = "last_reported_odometer"
SENSOR_NEXT_REMINDER: Final = "next_reminder"

# Unit type markers for dynamic unit resolution
UNIT_TYPE_CURRENCY: Final = "currency"
UNIT_TYPE_DISTANCE: Final = "distance"

# Options flow
CONF_DISTANCE_UNIT: Final = "distance_unit"
DISTANCE_UNIT_MILES: Final = "miles"
DISTANCE_UNIT_KILOMETERS: Final = "kilometers"

# Service names
SERVICE_ADD_ODOMETER: Final = "add_odometer_record"
SERVICE_ADD_GAS: Final = "add_gas_record"
SERVICE_ADD_REMINDER: Final = "add_reminder"

# Attribute keys for next_reminder sensor
ATTR_REMINDER_ID: Final = "reminder_id"
ATTR_URGENCY: Final = "urgency"
ATTR_METRIC: Final = "metric"
ATTR_DUE_DATE: Final = "due_date"
ATTR_DUE_ODOMETER: Final = "due_odometer"
ATTR_DUE_DAYS: Final = "due_days"
ATTR_DUE_DISTANCE: Final = "due_distance"
ATTR_TAGS: Final = "tags"
