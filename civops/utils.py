"""
utils.py - Utility functions, device profiling, and alert system
RapidOs Mobile Recon Radar
"""

import os
import math
import time
import threading
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()

# ─── Device OUI prefix → vendor lookup (partial, offline) ────────────────────
OUI_MAP = {
    "00:50:56": "VMware",
    "00:0C:29": "VMware",
    "00:1A:11": "Google",
    "AC:37:43": "HTC",
    "F4:F5:DB": "Apple",
    "3C:5A:B4": "Google",
    "DC:A6:32": "Raspberry Pi",
    "B8:27:EB": "Raspberry Pi",
    "00:17:88": "Philips Hue",
    "18:B4:30": "Nest",
    "44:65:0D": "Amazon Echo",
    "FC:65:DE": "Amazon",
    "74:C2:46": "Amazon",
    "00:1B:44": "SanDisk",
    "00:26:BB": "Apple",
    "00:1F:F3": "Apple",
    "00:23:12": "Apple",
    "B8:E8:56": "Apple",
    "AC:BC:32": "Apple",
    "A4:C3:F0": "Apple",
    "28:CF:E9": "Apple",
    "00:1C:42": "Parallels",
    "08:00:27": "VirtualBox",
    "52:54:00": "QEMU/KVM",
}

# ─── Device category classification rules ────────────────────────────────────
DEVICE_CATEGORIES = {
    "router": ["router", "gateway", "ap", "access", "dlink", "netgear", "linksys",
               "asus", "tp-link", "tplink", "cisco", "ubiquiti", "mikrotik"],
    "phone":  ["iphone", "android", "galaxy", "pixel", "huawei", "xiaomi", "oneplus",
               "oppo", "vivo", "samsung", "motorola", "nokia"],
    "laptop": ["macbook", "laptop", "thinkpad", "dell", "hp", "lenovo", "asus laptop",
               "surface", "chromebook"],
    "iot":    ["hue", "nest", "echo", "alexa", "ring", "wyze", "iot", "sensor",
               "thermostat", "camera", "smart", "arduino", "esp32", "esp8266",
               "raspberry pi", "raspberrypi"],
    "beacon": ["beacon", "estimote", "kontakt", "ibeacon", "eddystone", "tile"],
}


def classify_device(name: str = "", mac: str = "") -> str:
    """Return a human-readable device category."""
    name_lower = (name or "").lower()
    mac_prefix  = (mac or "")[:8].upper()

    vendor = OUI_MAP.get(mac_prefix, "")

    for category, keywords in DEVICE_CATEGORIES.items():
        for kw in keywords:
            if kw in name_lower or kw.lower() in vendor.lower():
                return category.capitalize()

    return "Unknown"


def rssi_to_distance(rssi: int, tx_power: int = -59) -> float:
    """
    Estimate distance (metres) from RSSI using the log-distance path loss model.
    Reference: Beacon Indoor Positioning (Kontakt.io, 2015) and the simplified
    two-slope model commonly used for BLE/WiFi path-loss estimation:
      d < 1 m  →  d = (RSSI / tx_power) ^ 10
      d >= 1 m →  d = 0.89976 * (ratio ^ 7.7095) + 0.111
    tx_power is the measured RSSI at 1 metre (default -59 dBm is typical BLE).
    """
    if rssi == 0:
        return -1.0
    ratio = rssi * 1.0 / tx_power
    if ratio < 1.0:
        return round(math.pow(ratio, 10), 2)
    distance = (0.89976) * math.pow(ratio, 7.7095) + 0.111
    return round(distance, 2)


def signal_bar(rssi: int) -> str:
    """Return a coloured bar representation of signal strength."""
    if rssi >= -50:
        return "[bold green]▇▇▇▇▇ Excellent[/bold green]"
    if rssi >= -60:
        return "[green]▇▇▇▇░ Good[/green]"
    if rssi >= -70:
        return "[yellow]▇▇▇░░ Fair[/yellow]"
    if rssi >= -80:
        return "[orange3]▇▇░░░ Weak[/orange3]"
    return "[red]▇░░░░ Poor[/red]"


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ─── Alert system ─────────────────────────────────────────────────────────────

class AlertSystem:
    """Tracks seen devices and fires alerts on new arrivals or signal spikes."""

    def __init__(self):
        self._seen_devices: dict = {}   # mac → last_rssi
        self._lock = threading.Lock()
        self._alerts: list = []

    def check(self, mac: str, name: str, rssi: int, category: str = "Unknown"):
        with self._lock:
            if mac not in self._seen_devices:
                msg = (f"[bold cyan]🔔 NEW DEVICE  [{category}]  "
                       f"{name or 'Unknown'}  ({mac})  RSSI={rssi} dBm[/bold cyan]")
                self._fire(msg)
            else:
                delta = rssi - self._seen_devices[mac]
                if delta >= 10:
                    msg = (f"[bold yellow]⚡ SIGNAL SPIKE  {name or mac}  "
                           f"RSSI {self._seen_devices[mac]}→{rssi} dBm (+{delta})[/bold yellow]")
                    self._fire(msg)
            self._seen_devices[mac] = rssi

    def check_network(self, bssid: str, ssid: str, rssi: int, encryption: str):
        """Alert on unknown encrypted networks."""
        with self._lock:
            key = bssid
            is_new = key not in self._seen_devices
            if is_new:
                if encryption.upper() not in ("OPEN", "NONE", ""):
                    msg = (f"[bold red]🔒 UNKNOWN ENCRYPTED NETWORK  "
                           f"'{ssid}'  ({bssid})  {encryption}  RSSI={rssi} dBm[/bold red]")
                    self._fire(msg)
                else:
                    msg = (f"[bold cyan]📡 NEW NETWORK  '{ssid}'  "
                           f"({bssid})  OPEN  RSSI={rssi} dBm[/bold cyan]")
                    self._fire(msg)
            self._seen_devices[key] = rssi

    def _fire(self, message: str):
        ts = timestamp()
        full = f"[dim]{ts}[/dim]  {message}"
        self._alerts.append({"time": ts, "message": message})
        rprint(full)

    def get_alerts(self) -> list:
        with self._lock:
            return list(self._alerts)


alert_system = AlertSystem()


def print_banner():
    console.print("""[bold cyan]
 ██████╗  █████╗ ██████╗ ██╗██████╗  ██████╗ ███████╗
 ██╔══██╗██╔══██╗██╔══██╗██║██╔══██╗██╔═══██╗██╔════╝
 ██████╔╝███████║██████╔╝██║██║  ██║██║   ██║███████╗
 ██╔══██╗██╔══██║██╔═══╝ ██║██║  ██║██║   ██║╚════██║
 ██║  ██║██║  ██║██║     ██║██████╔╝╚██████╔╝███████║
 ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚═════╝  ╚═════╝ ╚══════╝

  Mobile Recon Radar  v1.0  —  RapidOs Toolkit
  Running on Termux / Android
[/bold cyan]""")


def make_scan_table(title: str, columns: list) -> Table:
    """Create a styled Rich table for scan results."""
    table = Table(title=title, show_header=True, header_style="bold magenta",
                  border_style="dim", expand=True)
    for col_name, col_style in columns:
        table.add_column(col_name, style=col_style)
    return table
