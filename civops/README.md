# RapidOs Mobile Recon Radar

> **Turn any Android phone into a lightweight wireless reconnaissance platform.**

RapidOs Mobile Recon Radar is a complete Android reconnaissance toolkit that runs inside
[Termux](https://termux.dev). It scans nearby WiFi networks and BLE/Bluetooth devices,
visualises them on a real-time CLI radar, geo-tags every result, logs data to JSON/CSV/TXT,
and alerts you when something interesting appears — **100% offline after installation**.

---

## Features

| Feature | Details |
|---|---|
| **WiFi Recon** | SSID, BSSID, channel, signal strength, encryption type, hidden network detection |
| **BLE Scanner** | Device name, MAC, RSSI, distance estimate, device-type classification |
| **Real-Time Radar** | ASCII radar canvas, sweep animation, colour-coded signal rings |
| **Geo Tagging** | GPS coordinates attached to every scan record (via Termux:API or gpsd) |
| **Offline Operation** | No internet required after installation |
| **Data Logging** | JSON, CSV and TXT — written continuously during scans |
| **Auto-Scan Mode** | Continuous loop with configurable interval |
| **Device Profiling** | Phone · Laptop · Router · IoT · Beacon categories |
| **Alert System** | New device, signal spike, unknown encrypted network |
| **Recon Report** | Human-readable summary report generated on demand |

---

## Project Structure

```
civops/
├── main.py           ← CLI entry point
├── wifi_scanner.py   ← WiFi reconnaissance (iwlist / nmcli / nmap backends)
├── ble_scanner.py    ← BLE/Bluetooth scanning (bluepy / bleak / hcitool)
├── radar_ui.py       ← Real-time ASCII radar visualisation
├── logger.py         ← Data logging + auto-scan scheduler + report generator
├── gps.py            ← GPS via Termux:API (termux-location) or gpsd
└── utils.py          ← OUI lookup, device classification, alert system, helpers

install.sh            ← One-shot Termux installer
requirements.txt      ← Python dependencies
```

---

## Installation (Termux)

### Prerequisites

1. Install [Termux](https://f-droid.org/en/packages/com.termux/) from F-Droid  
2. Install [Termux:API](https://f-droid.org/en/packages/com.termux.api/) from F-Droid  
3. Open Termux:API and **grant Location + Bluetooth permissions**

### One-Command Install

```bash
# Clone or download the toolkit
git clone https://github.com/your-username/civops-recon.git
cd civops-recon

# Run the installer
bash install.sh
```

The installer will:
- Update Termux packages  
- Install system tools (`nmap`, `bluez`, `wireless-tools`, `termux-api`)  
- Copy civops files to `~/civops/`  
- Install Python dependencies  
- Create a `civops` launcher at `$PREFIX/bin/civops`

---

## Usage

### WiFi Scan

```bash
civops scan wifi
civops scan wifi --iface wlan1
civops scan wifi --no-geo --export
```

**Output columns:** SSID · BSSID · Channel · RSSI (dBm) · Signal bar · Distance (m) · Encryption · Hidden · GPS

### BLE / Bluetooth Scan

```bash
civops scan ble
civops scan ble --duration 20
civops scan ble --export
```

**Output columns:** Name · MAC Address · RSSI · Signal bar · Distance (m) · Device Type · GPS

### Real-Time Radar

```bash
civops radar
civops radar --mode wifi
civops radar --mode ble
civops radar --mode both --interval 15
```

The radar shows:
- Concentric signal rings (outer = weak, inner = strong)
- Animated sweep line
- Colour-coded device blips (green = excellent, yellow = fair, red = poor)
- Live legend with all detected devices

### Auto-Scan (Continuous Logging)

```bash
# Start scanning every 30 seconds
civops log start --interval 30 --mode wifi

# Check status
civops log status

# Stop
civops log stop
```

### Export Data

```bash
civops export csv             # export WiFi+BLE to CSV
civops export json            # export to JSON
civops export csv --type wifi # export only WiFi records
civops export all             # export JSON + CSV + TXT
```

### Generate Report

```bash
civops report
```

Generates a human-readable `recon_report_<timestamp>.txt` in `~/civops_logs/`.

### View Alerts

```bash
civops alerts
```

Shows all alerts fired during the current session:
- 🔔 New device/network detected  
- ⚡ Signal strength spike (+10 dBm or more)  
- 🔒 Unknown encrypted network detected  

---

## Log Files

All data is saved to `~/civops_logs/` with session timestamps:

```
~/civops_logs/
├── wifi_20241225_143000.json
├── wifi_20241225_143000.csv
├── wifi_20241225_143000.txt
├── ble_20241225_143000.json
├── ble_20241225_143000.csv
└── recon_report_20241225_143000.txt
```

---

## Example Output

### WiFi Scan
```
                    📡  WiFi Networks
 ─────────────────────────────────────────────────────────────
  SSID              BSSID              Ch  RSSI  Signal         Dist    Enc    Hidden
 ─────────────────────────────────────────────────────────────
  HomeNetwork       AA:BB:CC:DD:EE:FF   6  -52  ▇▇▇▇▇ Excellent  1.2m   WPA2
  CoffeeShop_WiFi   11:22:33:44:55:66  11  -67  ▇▇▇░░ Fair       8.4m   WPA2
  (hidden)          AA:11:BB:22:CC:33   1  -81  ▇▇░░░ Weak       42.1m  WPA3  ✓
```

### BLE Scan
```
               🔵  BLE / Bluetooth Devices
 ─────────────────────────────────────────────────────────────
  Name              MAC Address        RSSI  Signal         Dist   Type
 ─────────────────────────────────────────────────────────────
  Galaxy S22        A1:B2:C3:D4:E5:F6  -48  ▇▇▇▇▇ Excellent 0.9m   Phone
  Tile Mate         FF:EE:DD:CC:BB:AA  -71  ▇▇▇░░ Fair       12.3m  Beacon
  Unknown           12:34:56:78:9A:BC  -88  ▇░░░░ Poor        —     Unknown
```

---

## Permissions Required

| Feature | Permission |
|---|---|
| WiFi Scan | `ACCESS_FINE_LOCATION` + WiFi enabled |
| BLE Scan | `BLUETOOTH_SCAN` + `ACCESS_FINE_LOCATION` |
| GPS | Location permission via Termux:API |
| Root features | Optional — improves raw packet capture |

---

## Technology Stack

| Component | Technology |
|---|---|
| Language | Python 3 + Bash |
| UI | [Rich](https://github.com/Textualize/rich) |
| WiFi | iwlist / nmcli / python-nmap + scapy |
| BLE | bluepy · bleak · hcitool |
| GPS | termux-location (Termux:API) · gpsd |
| Data | pandas · json · csv |

---

## Packaging for Distribution

To package civops as a distributable digital product:

```bash
# Create a tarball
tar -czf civops-recon-v1.0.tar.gz civops/ install.sh requirements.txt README.md

# Or a zip
zip -r civops-recon-v1.0.zip civops/ install.sh requirements.txt README.md
```

Customers receive the archive, extract it, and run `bash install.sh`.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
