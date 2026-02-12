# Ista VDM for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

This is a custom integration for Home Assistant that retrieves heating and hot water consumption data from the ista VDM (Verbrauchsdatenmanagement) portal.

## Features

- [DATA] **Automatic Data Retrieval**: Fetches consumption data once per day
- [HOME] **Complete History**: Full historical data in sensor attributes  
- [BUILDING] **Flat Information**: Displays address, square meters, and other details
- [WORLD] **Multi-Language**: English, German, French, Spanish support
- [SYNC] **Re-authentication**: Easy password updates via UI
- [CHART] **Diagnostics**: Download diagnostic data for troubleshooting

## Installation

1. Ensure [HACS](https://hacs.xyz/) is installed
2. Go to HACS -> Integrations
3. Click ... -> Custom repositories
4. Add: `https://github.com/BeniKing99/ista-vdm-hacs`
5. Select Category: **Integration**
6. Install "Ista VDM"
7. Restart Home Assistant

## Configuration

1. Go to **Settings** -> **Devices & Services**
2. Click **Add Integration**
3. Search for "Ista VDM"
4. Enter your ista VDM portal credentials
5. Click **Submit**

## Support

- [GitHub Issues](https://github.com/BeniKing99/ista-vdm-hacs/issues)
- [Documentation](https://github.com/BeniKing99/ista-vdm-hacs/blob/main/README.md)

## License

MIT License
