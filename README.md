# LubeLogger Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/apicht/hass_lubelogger)](https://github.com/apicht/hass_lubelogger/releases)
[![License](https://img.shields.io/github/license/apicht/hass_lubelogger)](https://github.com/apicht/hass_lubelogger/blob/main/LICENSE)

A Home Assistant custom integration for [LubeLogger](https://github.com/hargata/lubelog), a self-hosted, open-source vehicle maintenance and fuel mileage tracker.

## Features

- **Multi-vehicle support** - Each vehicle appears as a separate device in Home Assistant
- **Cost tracking sensors** - Monitor service, repair, upgrade, tax, and fuel costs
- **Odometer tracking** - View last reported odometer reading
- **Reminder integration** - See upcoming maintenance reminders with due dates and distances
- **Services for automation** - Add odometer records, fuel/charging records, and reminders via Home Assistant automations
- **EV friendly** - Track electric vehicle charging sessions as "gas" records

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots in the top right corner
3. Select "Custom repositories"
4. Add `https://github.com/apicht/hass_lubelogger` with category "Integration"
5. Click "Add"
6. Search for "LubeLogger" and install
7. Restart Home Assistant

### Manual Installation

1. Download the latest release from [GitHub](https://github.com/apicht/hass_lubelogger/releases)
2. Extract and copy the `custom_components/lubelogger` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "LubeLogger"
4. Enter your LubeLogger server details:
   - **URL**: Full URL to your LubeLogger instance (e.g., `https://lubelogger.example.com`)
   - **Username**: Your LubeLogger username
   - **Password**: Your LubeLogger password

### OIDC Users

If you use OIDC (OpenID Connect) for LubeLogger web login, the API still requires Basic Authentication credentials. You'll need to create a dedicated API user:

1. Log in to LubeLogger as an admin
2. Go to **Settings** → **Admin Panel** (or navigate to `/Admin`)
3. Click **Manage Tokens** → **Generate** (uncheck **Notify**)
4. Enter an email address for the API user (can be any email, e.g., `api@localhost`)
5. Copy the generated token
6. Navigate directly to the registration page:
   ```
   https://your-lubelogger-url/Login/Registration?token=YOUR_TOKEN&email=api@localhost
   ```
7. Create a username and password for the API user
8. Use these credentials when configuring the Home Assistant integration

**Note:** The registration page is accessible even when "Disable Regular Login" is enabled, as long as "Disable Registration" is not checked in Server Settings.

## Sensors

For each vehicle, the integration creates the following sensors:

| Sensor | Description | Device Class |
|--------|-------------|--------------|
| Service Record Cost | Total cost of all service records | Monetary |
| Repair Record Cost | Total cost of all repair records | Monetary |
| Upgrade Record Cost | Total cost of all upgrade records | Monetary |
| Tax Record Cost | Total cost of all tax records | Monetary |
| Gas Record Cost | Total cost of all fuel/charging records | Monetary |
| Odometer | Last reported odometer reading | Distance |
| Next Reminder | Description of the next upcoming reminder | - |

### Next Reminder Attributes

The Next Reminder sensor includes additional attributes:

- `reminder_id` - LubeLogger reminder ID
- `urgency` - Urgency level (e.g., "NotUrgent", "Urgent", "VeryUrgent")
- `metric` - Tracking method ("Date", "Odometer", or "Both")
- `due_date` - When the reminder is due
- `due_odometer` - Odometer reading when due
- `due_days` - Days until due
- `due_distance` - Distance until due

## Services

### lubelogger.add_odometer_record

Add a new odometer reading to a vehicle.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `device_id` | Yes | The Home Assistant device ID (use device picker in UI) |
| `date` | Yes | Date of reading (YYYY-MM-DD) |
| `odometer` | Yes | Odometer value |
| `notes` | No | Optional notes |
| `tags` | No | Comma-separated tags |

### lubelogger.add_gas_record

Add a fuel or charging record. Works for both gas/diesel vehicles and EVs.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `device_id` | Yes | The Home Assistant device ID (use device picker in UI) |
| `date` | Yes | Date of fill-up (YYYY-MM-DD) |
| `odometer` | Yes | Odometer at fill-up |
| `fuel_consumed` | Yes | Amount of fuel (gallons/liters) or energy (kWh) |
| `cost` | Yes | Total cost |
| `is_fill_to_full` | No | Complete fill-up? (default: true) |
| `missed_fuel_up` | No | Previous fill missed? (default: false) |
| `notes` | No | Optional notes |
| `tags` | No | Comma-separated tags |

### lubelogger.add_reminder

Add a maintenance reminder.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `device_id` | Yes | The Home Assistant device ID (use device picker in UI) |
| `description` | Yes | Reminder description |
| `due_date` | No | Due date (YYYY-MM-DD) |
| `due_odometer` | No | Due odometer reading |
| `metric` | No | "Date", "Odometer", or "Both" (default) |
| `notes` | No | Optional notes |
| `tags` | No | Comma-separated tags |

## Example Automations

### Log EV Charging from FordPass

Automatically log charging sessions when your Ford EV finishes charging. This example uses the [ha-fordpass](https://github.com/marq24/ha-fordpass) integration:

```yaml
automation:
  - alias: "Log EV Charging to LubeLogger"
    trigger:
      - platform: state
        entity_id: sensor.2021_ford_mustang_mach_e_elvehcharging
        from: "IN_PROGRESS"
        to:
          - "COMPLETED"
          - "NOT_READY"
          - "STOPPED"
    variables:
      charge_sensor: sensor.2021_ford_mustang_mach_e_energytransferlogentry
      energy_kwh: "{{ states(charge_sensor) | float }}"
      last_soc: "{{ state_attr(charge_sensor, 'stateOfCharge').lastSOC }}"
      target_soc: "{{ state_attr(charge_sensor, 'targetSoc') }}"
    action:
      - service: lubelogger.add_gas_record
        data:
          device_id: "abc123def456"  # Your LubeLogger device ID
          date: "{{ now().strftime('%Y-%m-%d') }}"
          odometer: "{{ states('sensor.2021_ford_mustang_mach_e_odometer') | float }}"
          fuel_consumed: "{{ energy_kwh }}"
          cost: "{{ (energy_kwh * states('sensor.electric_rate') | float) | round(2) }}"
          is_fill_to_full: "{{ last_soc | int >= target_soc | int }}"
          notes: "Charged {{ last_soc }}% (target {{ target_soc }}%)"
          tags: "ev,charging"
```

**Note:** Replace `2021_ford_mustang_mach_e` with your vehicle's entity prefix. FordPass sensors use the format `sensor.<vehicle_name>_<sensor_key>`. The `is_fill_to_full` is set to true when the vehicle reaches its target charge level.

### Log Odometer on Arrival Home

Record odometer when arriving home using FordPass device tracker:

```yaml
automation:
  - alias: "Log Odometer on Arrival Home"
    trigger:
      - platform: zone
        entity_id: device_tracker.2021_ford_mustang_mach_e_tracker
        zone: zone.home
        event: enter
    action:
      - service: lubelogger.add_odometer_record
        data:
          device_id: "abc123def456"  # Your LubeLogger device ID
          date: "{{ now().strftime('%Y-%m-%d') }}"
          odometer: "{{ states('sensor.2021_ford_mustang_mach_e_odometer') | float }}"
          notes: "Auto-logged on arrival home"
```

### Notify on Urgent Reminders

Get notified when a maintenance reminder becomes urgent:

```yaml
automation:
  - alias: "LubeLogger Urgent Reminder Notification"
    trigger:
      - platform: state
        entity_id: sensor.2021_ford_mustang_mach_e_next_reminder
        attribute: urgency
        to: "Urgent"
    action:
      - service: notify.mobile_app
        data:
          title: "Vehicle Maintenance Due"
          message: >
            {{ state_attr('sensor.2021_ford_mustang_mach_e_next_reminder', 'description') }}
            is due in {{ state_attr('sensor.2021_ford_mustang_mach_e_next_reminder', 'due_days') }} days
            or {{ state_attr('sensor.2021_ford_mustang_mach_e_next_reminder', 'due_distance') }} miles
```

## Finding Your Device ID

When creating automations in the Home Assistant UI, simply use the device picker to select your vehicle - no need to know the device ID.

For YAML automations, you can find the device ID by:
1. Go to **Settings** → **Devices & Services** → **Devices**
2. Find and click on your LubeLogger vehicle
3. The device ID is in the URL (e.g., `/config/devices/device/abc123def456`)

## Troubleshooting

### Cannot Connect

- Verify the URL is correct and includes the protocol (`https://` or `http://`)
- Ensure your LubeLogger server is accessible from your Home Assistant instance
- Check that authentication is enabled in LubeLogger

### Invalid Authentication

- Verify your username and password
- If using OIDC, make sure you have a password set or use a dedicated API user
- Note: Neither username nor password can contain a colon (`:`) character due to Basic Auth requirements

### Sensors Show Unknown

- Check that you have at least one vehicle configured in LubeLogger
- Verify the API is accessible at `https://your-lubelogger-url/api`
- Enable debug logging for more details:

```yaml
logger:
  default: info
  logs:
    custom_components.lubelogger: debug
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [LubeLogger](https://github.com/hargata/lubelog) - The excellent self-hosted vehicle maintenance tracker this integration connects to
- [Home Assistant](https://www.home-assistant.io/) - The open-source home automation platform
