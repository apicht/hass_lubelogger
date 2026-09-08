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
   - **Distance unit**: The unit your LubeLogger instance uses for odometer readings

### Distance Unit

LubeLogger stores odometer readings as plain numbers, and its API does not report
which unit they are in. The integration therefore has to be told, so that Home
Assistant labels the Odometer sensor correctly instead of converting the value.

Look at **Settings** → **Formatting** in LubeLogger. Two separate toggles put it
in miles:

| LubeLogger setting | Choose |
|--------------------|--------|
| "Use imperial calculation for fuel mileage (MPG)" **enabled** | Miles |
| "Use UK MPG calculation" **enabled** (even with MPG off) | Miles |
| Both **disabled** | Kilometers |

UK MPG is the easy one to miss: it means miles per *imperial* gallon, so distances
are in miles while the rest of the setup looks metric.

The setup form pre-selects the unit matching your Home Assistant unit system
(kilometers for metric, miles for US customary). To change it later, go to
**Settings** → **Devices & Services** → **LubeLogger** → **Configure**.

#### Upgrading from a version without this setting

Existing configurations have no unit stored. On upgrade the integration writes
the unit implied by your Home Assistant unit system and raises a repair under
**Settings** → **Repairs** asking you to confirm it, because that guess is wrong
for exactly the UK MPG case above. Confirming or correcting it dismisses the
repair.

If the guess was wrong, or if you correct a unit that was wrong before, expect a
step in the sensor's history. Home Assistant will **not** warn you about it. The
unit your statistics are recorded in is fixed by your Home Assistant unit system,
not by this setting, so correcting the setting changes the number without
changing the unit — there is no unit change for Home Assistant to flag, and new
readings are silently rescaled into the unit already on record. On a US customary
install a 64526 km reading previously stored as `64526 mi` starts arriving as
`40094 mi`; on a metric install one previously stored as `103844 km` starts
arriving as `64526 km`. Either way the drop reads as a meter reset, because the
Odometer sensor is `total_increasing`.

To start clean, delete the sensor's long-term statistics under **Developer
Tools** → **Statistics** before or after correcting the unit. There is nothing to
fix if the unit was already right.

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

### Gas Record Cost Attributes

The Gas Record Cost sensor includes attributes from the most recent fuel/charging record:

- `last_odometer` - Odometer reading at last fill-up
- `last_date` - Date of last fill-up
- `last_fuel_consumed` - Fuel/energy amount of last fill-up
- `last_cost` - Cost of last fill-up

**Note:** Use `last_odometer` instead of the Odometer sensor when calculating distance driven between fill-ups. The Odometer sensor reflects the latest reading from any record type (service, tax, etc.), which can cause incorrect fuel economy calculations.

### Next Reminder Attributes

The Next Reminder sensor includes additional attributes:

- `reminder_id` - LubeLogger reminder ID
- `urgency` - Urgency level (e.g., "NotUrgent", "Urgent", "VeryUrgent")
- `metric` - Tracking method ("Date", "Odometer", or "Both")
- `due_date` - When the reminder is due
- `due_odometer` - Odometer reading when due
- `due_days` - Days until due
- `due_distance` - Distance until due

**Note:** Attribute values are passed through from LubeLogger unchanged, so
`last_odometer`, `due_odometer`, and `due_distance` are in whatever unit your
LubeLogger instance uses. Only the Odometer sensor carries a unit and gets
converted for display.

## Services

**Note:** `odometer` and `due_odometer` are sent to LubeLogger as-is, so pass them
in LubeLogger's unit. If you feed them from a Home Assistant template, remember
that templates return the sensor's *displayed* value.

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
| `starting_soc` | No | EV state of charge (%) before the session, 0-100 |
| `ending_soc` | No | EV state of charge (%) after the session, 0-100 |
| `notes` | No | Optional notes |
| `tags` | No | Comma-separated tags |

**On the SoC fields:** these require a LubeLogger version whose gas record screen
exposes state of charge. Leave them out for non-EVs. Note that LubeLogger does not
store a null when they are omitted — it substitutes its own defaults of 20% and 80%,
so pass real values whenever you have them.

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
      first_soc: "{{ state_attr(charge_sensor, 'stateOfCharge').firstSOC }}"
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
          starting_soc: "{{ first_soc | round(0) | int }}"
          ending_soc: "{{ last_soc | round(0) | int }}"
          notes: "Charged {{ first_soc }}% -> {{ last_soc }}% (target {{ target_soc }}%)"
          tags: "ev,charging"
```

**Note:** Replace `2021_ford_mustang_mach_e` with your vehicle's entity prefix. FordPass sensors use the format `sensor.<vehicle_name>_<sensor_key>`. The `is_fill_to_full` is set to true when the vehicle reaches its target charge level. FordPass only refreshes the charge log entry once Ford's servers have the session, so check its `timeStamp` attribute before trusting `firstSOC`/`lastSOC` — see `ev_charging_lubelogger.yaml` for a version that falls back to live sensors when the entry is stale.

### Log EV Charging with Notification Summary

Extended version that sends a notification after logging with cost, energy consumed, distance driven, and fuel economy:

```yaml
automation:
  - alias: "Log EV Charging to LubeLogger with Notification"
    trigger:
      - platform: state
        entity_id: sensor.2023_ford_mustang_mach_e_elvehcharging
        from: "IN_PROGRESS"
        to:
          - "COMPLETED"
          - "NOT_READY"
          - "STOPPED"
    variables:
      # FordPass sensors
      charge_sensor: sensor.2023_ford_mustang_mach_e_energytransferlogentry
      fordpass_odometer: sensor.2023_ford_mustang_mach_e_odometer
      # LubeLogger sensor for last fuel record odometer
      lubelogger_gas_cost: sensor.2023_ford_mustang_mach_e_gas_record_cost
      # Values from FordPass
      energy_kwh: "{{ states(charge_sensor) | float }}"
      first_soc: "{{ state_attr(charge_sensor, 'stateOfCharge').firstSOC }}"
      last_soc: "{{ state_attr(charge_sensor, 'stateOfCharge').lastSOC }}"
      target_soc: "{{ state_attr(charge_sensor, 'targetSoc') }}"
      current_odometer: "{{ states(fordpass_odometer) | float }}"
      previous_odometer: "{{ state_attr(lubelogger_gas_cost, 'last_odometer') | float }}"
      total_cost: "{{ (energy_kwh * states('sensor.electric_rate') | float) | round(2) }}"
      # Calculated values for notification
      miles_driven: "{{ (current_odometer - previous_odometer) | round(1) }}"
      fuel_economy: "{{ ((current_odometer - previous_odometer) / energy_kwh) | round(2) if energy_kwh > 0 else 'N/A' }}"
    action:
      - service: lubelogger.add_gas_record
        data:
          device_id: "abc123def456"  # Your LubeLogger device ID
          date: "{{ now().strftime('%Y-%m-%d') }}"
          odometer: "{{ current_odometer }}"
          fuel_consumed: "{{ energy_kwh }}"
          cost: "{{ total_cost }}"
          is_fill_to_full: "{{ last_soc | int >= target_soc | int }}"
          starting_soc: "{{ first_soc | round(0) | int }}"
          ending_soc: "{{ last_soc | round(0) | int }}"
          notes: "Charged {{ first_soc }}% -> {{ last_soc }}% (target {{ target_soc }}%)"
          tags: "ev,charging"
      - service: notify.mobile_app_your_phone
        data:
          title: "EV Charging Logged"
          message: >
            Added {{ energy_kwh }} kWh for ${{ total_cost }}
            Miles since last charge: {{ miles_driven }}
            Fuel economy: {{ fuel_economy }} mi/kWh
```

**Note:** This example uses the `last_odometer` attribute from the Gas Record Cost sensor to get the odometer reading from the last fuel record. This ensures accurate fuel economy calculations even if you've added service or other records between fill-ups.

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
            or {{ state_attr('sensor.2021_ford_mustang_mach_e_next_reminder', 'due_distance') }} mi/km
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

## Development

Run the test suite against the Home Assistant test harness:

```bash
uv venv --python 3.13 .venv-test
VIRTUAL_ENV=.venv-test uv pip install -r requirements-test.txt
.venv-test/bin/python -m pytest
```

Run HACS validation locally:

```bash
docker run --rm -v $(pwd):/github/workspace ghcr.io/hacs/action:main
```

Run hassfest validation locally:

```bash
docker run --rm -v $(pwd)/custom_components:/github/workspace/custom_components ghcr.io/home-assistant/hassfest
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [LubeLogger](https://github.com/hargata/lubelog) - The excellent self-hosted vehicle maintenance tracker this integration connects to
- [Home Assistant](https://www.home-assistant.io/) - The open-source home automation platform
