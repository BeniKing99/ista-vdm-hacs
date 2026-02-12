# Ista VDM Home Assistant Integration

[![Quality Scale](https://img.shields.io/badge/quality-platinum-FFD700)](https://developers.home-assistant.io/docs/integration_quality_scale_index)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

This is a custom integration for Home Assistant that retrieves heating and hot water consumption data from the ista VDM (Verbrauchsdatenmanagement) portal.

## About ista VDM

ista VDM is a consumption data management system used by property management companies in Austria and other countries to track heating and hot water usage in apartments. This integration allows you to automatically import your monthly consumption data into Home Assistant.

## Features

- ✅ **Automatic Data Retrieval**: Fetches consumption data once per day
- ✅ **Current & Historical Data**: Shows latest month + full history in attributes
- ✅ **Device Information**: Displays address, square meters, and other flat details
- ✅ **Multi-Language Support**: English, German, French, Spanish
- ✅ **Platinum Quality Scale**: Meets all Home Assistant quality standards
- ✅ **Re-authentication Support**: Easy password updates via UI
- ✅ **Diagnostics**: Download diagnostic data for troubleshooting

## Supported Regions

This integration is designed for the Austrian ista VDM portal (https://ista-vdm.at/). It may work with other regional portals with similar implementations.

## Prerequisites

Before using this integration, you need:

1. An active account on the ista VDM portal (https://ista-vdm.at/)
2. Your login credentials (email and password)
3. At least one consumption period with available data

## Installation

### HACS (Recommended - Coming Soon)

1. Install [HACS](https://hacs.xyz/) if you haven't already
2. Add this repository as a custom repository
3. Search for "Ista VDM" and install
4. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/your-repo/ista-vdm/releases)
2. Copy the `custom_components/ista_vdm` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant

## Configuration

The integration is configured entirely through the Home Assistant UI:

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Ista VDM"
4. Enter your credentials:
   - **Email**: Your ista VDM portal email address
   - **Password**: Your ista VDM portal password
5. Click **Submit**

The integration will test the connection and create all sensors automatically.

## Updating Credentials / Re-authentication

If you change your password or the integration needs to re-authenticate:

1. Go to **Settings** → **Devices & Services**
2. Find the Ista VDM integration
3. Click the three dots menu (⋯) → **Reconfigure**
4. Enter your new password
5. Click **Submit**

## Sensors

### Consumption Sensors

These sensors show your current month's consumption with historical data in attributes.

#### Heating Consumption
- **Entity ID**: `sensor.ista_vdm_heating_consumption`
- **Unit**: kWh (kilowatt-hours)
- **Device Class**: Energy
- **State Class**: Total
- **Icon**: mdi:radiator
- **Update Frequency**: Once per day

**Attributes:**
- `period_start`: Start date of current period (ISO format)
- `period_end`: End date of current period (ISO format)
- `history`: Complete list of all historical consumption data
- `total_months`: Number of months of historical data available

Example attribute structure:
```yaml
history:
  - period_start: "2025-12-01"
    period_end: "2025-12-31"
    consumption_kwh: 392.1
  - period_start: "2025-11-01"
    period_end: "2025-11-30"
    consumption_kwh: 327.8
  # ... more entries
total_months: 11
```

#### Hot Water Consumption
- **Entity ID**: `sensor.ista_vdm_hot_water_consumption`
- **Unit**: m³ (cubic meters)
- **Device Class**: Water
- **State Class**: Total
- **Icon**: mdi:water-boiler

### Flat Information Sensors (Diagnostic)

These sensors provide static information about your flat and are marked as diagnostic (hidden by default).

- **City**: `sensor.ista_vdm_flat_city` (mdi:city)
- **Street**: `sensor.ista_vdm_flat_street` (mdi:road)
- **House Number**: `sensor.ista_vdm_flat_housenumber` (mdi:numeric)
- **Door**: `sensor.ista_vdm_flat_door` (mdi:door)
- **Square Meters**: `sensor.ista_vdm_flat_squaremeter` (mdi:ruler-square)
- **Postal Code**: `sensor.ista_vdm_flat_postalcode` (mdi:mailbox)

### Last Updated

Shows when the integration last successfully fetched data from ista VDM.
- **Entity ID**: `sensor.ista_vdm_last_updated`
- **Device Class**: Timestamp

## Viewing Historical Data

### Method 1: Developer Tools (Quick Check)
1. Go to **Developer Tools** → **States**
2. Search for `sensor.ista_vdm_heating_consumption`
3. View the `history` attribute

### Method 2: Template Sensor (For Automations)
Create a template sensor to access specific months:

```yaml
template:
  - sensor:
      - name: "Heating Last Month"
        state: "{{ state_attr('sensor.ista_vdm_heating_consumption', 'history')[1]['consumption_kwh'] }}"
        unit_of_measurement: "kWh"
```

### Method 3: Custom Dashboard Card
Use the `history` attribute in a custom Lovelace card or automation.

## Automation Examples

### Alert When Consumption is High

```yaml
automation:
  - alias: "High Heating Consumption Alert"
    trigger:
      - platform: state
        entity_id: sensor.ista_vdm_heating_consumption
    condition:
      - condition: template
        value_template: "{{ states('sensor.ista_vdm_heating_consumption') | float > 400 }}"
    action:
      - service: notify.mobile_app_phone
        data:
          message: "High heating consumption detected: {{ states('sensor.ista_vdm_heating_consumption') }} kWh"
```

### Monthly Consumption Report

```yaml
automation:
  - alias: "Monthly Consumption Report"
    trigger:
      - platform: time
        at: "08:00:00"
      - platform: template
        value_template: "{{ now().day == 1 }}"
    action:
      - service: notify.mobile_app_phone
        data:
          message: >
            Monthly Consumption Report:
            Heating: {{ states('sensor.ista_vdm_heating_consumption') }} kWh
            Hot Water: {{ states('sensor.ista_vdm_hot_water_consumption') }} m³
```

## Troubleshooting

### Authentication Errors

**Problem**: "Invalid authentication" error during setup

**Solutions**:
1. Verify your email and password are correct by logging in at https://ista-vdm.at/
2. Check if your account is active and has consumption data
3. Try reconfiguring the integration with updated credentials

### No Data Available

**Problem**: Sensors show "unavailable" or "unknown"

**Solutions**:
1. Check if consumption data is available in the ista VDM portal
2. Verify the CSV export can be downloaded from the portal
3. Wait for the next data update (once per day)
4. Check Home Assistant logs for errors

### High Memory Usage

**Problem**: Integration using too much memory

**Note**: The integration stores historical data in sensor attributes. If you have many years of data, this can consume memory. This is normal behavior.

## Diagnostics

To download diagnostic data for troubleshooting:

1. Go to **Settings** → **Devices & Services**
2. Find the Ista VDM integration
3. Click the three dots menu (⋯) → **Download Diagnostics**
4. This will download a JSON file with debug information

**Note**: Diagnostic data is automatically redacted to remove sensitive information like passwords.

## Known Limitations

1. **Data Update Frequency**: ista only updates consumption data once per month, so the integration polls once per day
2. **No Real-time Data**: This is not a real-time meter - data is always from the previous billing period
3. **CSV Format Dependency**: The integration depends on the CSV export format from ista VDM. If ista changes their format, the integration may break
4. **Historical Data Only**: Home Assistant cannot backfill state history. Historical data is available in sensor attributes only

## Supported Devices

This integration supports:
- ✅ All ista VDM apartments with heating meters
- ✅ All ista VDM apartments with hot water meters
- ✅ Multi-flat buildings with individual metering

Not supported:
- ❌ Commercial/industrial properties with different meter types
- ❌ Properties using different portal systems (e.g., not ista-vdm.at)

## Data Update Process

The integration follows this workflow:

1. **Authentication**: Logs into the ista VDM portal using OAuth2
2. **Data Retrieval**: Downloads the consumption CSV export
3. **Parsing**: Extracts heating and hot water consumption data
4. **Sensor Update**: Updates sensors with latest data
5. **Attribute Storage**: Stores all historical data in sensor attributes

This process runs automatically once every 24 hours.

## How to Contribute

Contributions are welcome! Please feel free to submit issues or pull requests.

### Reporting Issues

When reporting issues, please include:
1. Home Assistant version
2. Integration version
3. Error messages from logs
4. Diagnostic data (with sensitive info removed)

### Development

To set up a development environment:

```bash
# Clone the repository
git clone https://github.com/your-repo/ista-vdm.git
cd ista-vdm

# Install dependencies
pip install -r requirements.txt
pip install -r requirements.test.txt

# Run tests
pytest tests/
```

## Testing

A standalone test script is included to verify authentication and data retrieval:

```bash
# Test with credentials
python test_ista_vdm.py --email your@email.com --password yourpassword

# Or use environment variables
export ISTA_EMAIL=your@email.com
export ISTA_PASSWORD=yourpassword
python test_ista_vdm.py

# Test CSV parsing with a local file
python test_ista_vdm.py --csv-file VERBRAUCH-0014.csv

# Save downloaded CSV for inspection
python test_ista_vdm.py --email your@email.com --password yourpassword --save-csv output.csv
```

## Use Cases

### Energy Monitoring
Track your heating consumption over time to identify trends and optimize energy usage.

### Budget Planning
Use historical data to predict future heating costs and budget accordingly.

### Comparison
Compare consumption between different months or years to identify anomalies.

### Automation
Create automations based on consumption thresholds, such as alerts when usage is unusually high.

### Integration with Energy Dashboard
Use the consumption sensors in Home Assistant's Energy Dashboard for comprehensive energy monitoring.

## Technical Details

### API Authentication
The integration uses OAuth2 authentication via Keycloak (ista's identity provider). This is the same authentication method used by the official ista VDM web portal.

### Data Privacy
- All credentials are stored securely in Home Assistant's config entry system
- No data is sent to third parties
- Diagnostic logs are automatically redacted to remove sensitive information

### Rate Limiting
The integration respects ista's servers by:
- Updating only once per day (configurable)
- Using efficient API calls
- C authentication tokens

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Disclaimer

This is an unofficial integration and is not affiliated with or endorsed by ista SE. Use at your own risk. Always verify the data with your official ista VDM portal. The authors are not responsible for any issues arising from the use of this integration.

## Acknowledgments

- Thanks to the Home Assistant community for testing and feedback
- Thanks to ista for providing the VDM portal (unofficial integration)

## Support

For support and questions:
- [GitHub Issues](https://github.com/your-repo/ista-vdm/issues)
- [Home Assistant Community Forum](https://community.home-assistant.io/)

---

**Note**: This integration was built following the Home Assistant Integration Quality Scale guidelines to ensure the best possible user experience and code quality.