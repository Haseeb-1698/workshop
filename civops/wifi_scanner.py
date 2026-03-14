"""
wifi_scanner.py - WiFi network reconnaissance
RapidOs Mobile Recon Radar

Supports three backends (tried in order):
  1. python-nmap  (nmap must be installed)
  2. iwlist       (Linux wireless-tools)
  3. nmcli        (NetworkManager)
"""

import re
import subprocess
import time
from typing import List, Optional

from rich.console import Console
from rich.live import Live

from utils import (
    classify_device, rssi_to_distance, signal_bar,
    timestamp, alert_system, make_scan_table
)
from gps import get_location, format_location
from logger import DataLogger

console = Console()


# ─── Parsing helpers ──────────────────────────────────────────────────────────

def _parse_iwlist(raw: str) -> List[dict]:
    """Parse output of `iwlist wlan0 scan`."""
    networks = []
    blocks = re.split(r"Cell \d+ - ", raw)
    for block in blocks[1:]:
        net = {
            "ssid":       "",
            "bssid":      "",
            "channel":    "",
            "rssi":       0,
            "encryption": "Open",
            "hidden":     False,
        }
        m = re.search(r'ESSID:"(.*?)"', block)
        if m:
            net["ssid"]   = m.group(1)
            net["hidden"] = net["ssid"] == ""
        m = re.search(r"Address: ([0-9A-Fa-f:]{17})", block)
        if m:
            net["bssid"] = m.group(1).upper()
        m = re.search(r"Channel[=:](\d+)", block)
        if m:
            net["channel"] = int(m.group(1))
        m = re.search(r"Signal level[=:](-?\d+)", block)
        if m:
            net["rssi"] = int(m.group(1))
        if re.search(r"Encryption key:on", block):
            net["encryption"] = "WPA/WPA2"
            if re.search(r"WPA2", block, re.IGNORECASE):
                net["encryption"] = "WPA2"
            if re.search(r"WPA3", block, re.IGNORECASE):
                net["encryption"] = "WPA3"
            if re.search(r"WEP", block, re.IGNORECASE):
                net["encryption"] = "WEP"
        networks.append(net)
    return networks


def _parse_nmcli(raw: str) -> List[dict]:
    """Parse output of `nmcli -f ALL dev wifi list`."""
    networks = []
    lines = raw.strip().splitlines()
    if len(lines) < 2:
        return networks
    for line in lines[1:]:
        parts = line.split()
        if not parts:
            continue
        try:
            bssid = parts[0] if len(parts[0]) == 17 else ""
            ssid  = parts[1] if len(parts) > 1 else ""
            chan  = parts[3] if len(parts) > 3 else ""
            rssi_str = ""
            enc  = "Open"
            for i, p in enumerate(parts):
                if p.lstrip("-").isdigit() and int(p) < 0:
                    rssi_str = p
                if p.upper() in ("WPA2", "WPA", "WEP", "WPA3"):
                    enc = p.upper()
            rssi = int(rssi_str) if rssi_str else 0
            networks.append({
                "ssid": ssid, "bssid": bssid.upper(),
                "channel": chan, "rssi": rssi,
                "encryption": enc, "hidden": ssid == "--" or ssid == "",
            })
        except (IndexError, ValueError):
            continue
    return networks


def _nmap_scan(interface: str = "wlan0") -> List[dict]:
    """Use python-nmap + nmap for network host discovery (root required)."""
    try:
        import nmap
        import socket
        import struct

        # Dynamically determine the local subnet from the interface
        try:
            import subprocess as _sp
            out = _sp.check_output(
                ["ip", "-o", "-f", "inet", "addr", "show", interface],
                text=True, timeout=5
            )
            # e.g. "2: wlan0    inet 192.168.1.42/24 ..."
            m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)/(\d+)", out)
            if m:
                ip_str  = m.group(1)
                prefix  = int(m.group(2))
                # Calculate network address
                ip_int  = struct.unpack("!I", socket.inet_aton(ip_str))[0]
                mask    = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
                net_int = ip_int & mask
                network = socket.inet_ntoa(struct.pack("!I", net_int))
                subnet  = f"{network}/{prefix}"
            else:
                subnet = "192.168.0.0/24"
        except Exception:
            subnet = "192.168.0.0/24"

        nm = nmap.PortScanner()
        nm.scan(hosts=subnet, arguments="-sn")
        results = []
        for host in nm.all_hosts():
            info = nm[host]
            results.append({
                "ssid":       info.hostname(),
                "bssid":      host,
                "channel":    "",
                "rssi":       0,
                "encryption": "Unknown",
                "hidden":     False,
            })
        return results
    except Exception:
        return []


# ─── Main scanner ─────────────────────────────────────────────────────────────

def scan_wifi(interface: str = "wlan0",
              logger: Optional[DataLogger] = None,
              geo_tag: bool = True) -> List[dict]:
    """
    Scan nearby WiFi networks.
    Returns a list of network dicts.
    """
    raw = ""
    backend = "none"

    # Backend 1: iwlist
    try:
        result = subprocess.run(
            ["iwlist", interface, "scan"],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode == 0 and "ESSID" in result.stdout:
            raw     = result.stdout
            backend = "iwlist"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Backend 2: nmcli
    if backend == "none":
        try:
            result = subprocess.run(
                ["nmcli", "-f", "ALL", "dev", "wifi", "list"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0 and len(result.stdout.strip().splitlines()) > 1:
                raw     = result.stdout
                backend = "nmcli"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    networks: List[dict] = []

    if backend == "iwlist":
        networks = _parse_iwlist(raw)
    elif backend == "nmcli":
        networks = _parse_nmcli(raw)
    else:
        networks = _nmap_scan(interface)

    # Enrich records
    loc = get_location() if geo_tag else {"provider": "disabled"}
    ts  = timestamp()

    for net in networks:
        net["timestamp"]   = ts
        net["scan_type"]   = "wifi"
        net["distance_m"]  = rssi_to_distance(net["rssi"])
        net["location"]    = loc
        net["device_type"] = "Router"

        alert_system.check_network(
            net["bssid"], net["ssid"], net["rssi"], net["encryption"]
        )

        if logger:
            flat = {**net, "lat": loc.get("latitude", 0),
                    "lon": loc.get("longitude", 0)}
            flat.pop("location", None)
            logger.log(flat)

    return networks


# ─── Display ──────────────────────────────────────────────────────────────────

def display_wifi(networks: List[dict]):
    columns = [
        ("SSID",        "cyan"),
        ("BSSID",       "white"),
        ("Ch",          "yellow"),
        ("RSSI (dBm)",  "green"),
        ("Signal",      "white"),
        ("Dist (m)",    "blue"),
        ("Encryption",  "magenta"),
        ("Hidden",      "red"),
        ("GPS",         "dim"),
    ]
    table = make_scan_table("📡  WiFi Networks", columns)

    for net in sorted(networks, key=lambda x: x.get("rssi", -100), reverse=True):
        loc  = net.get("location", {})
        gps  = (f"{loc.get('latitude', 0):.4f},{loc.get('longitude', 0):.4f}"
                if loc.get("provider") != "unavailable" and loc.get("provider") != "disabled"
                else "—")
        table.add_row(
            net.get("ssid") or "[dim](hidden)[/dim]",
            net.get("bssid", ""),
            str(net.get("channel", "")),
            str(net.get("rssi", "")),
            signal_bar(net.get("rssi", -100)),
            str(net.get("distance_m", "")),
            net.get("encryption", ""),
            "✓" if net.get("hidden") else "",
            gps,
        )

    console.print(table)
    console.print(f"[dim]Found {len(networks)} network(s)  •  {timestamp()}[/dim]")
