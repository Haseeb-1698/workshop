"""
ble_scanner.py - BLE / Bluetooth device scanning
RapidOs Mobile Recon Radar

Backends (tried in order):
  1. bluepy   (BLE, Linux)
  2. bleak    (BLE, cross-platform async)
  3. hcitool  (classic BT + BLE via subprocess)
"""

import re
import subprocess
import time
import asyncio
from typing import List, Optional

from rich.console import Console

from utils import (
    classify_device, rssi_to_distance, signal_bar,
    timestamp, alert_system, make_scan_table
)
from gps import get_location
from logger import DataLogger

console = Console()

BLE_SCAN_SECONDS = 10   # how long to scan by default


# ─── bluepy backend ───────────────────────────────────────────────────────────

def _scan_bluepy(duration: int = BLE_SCAN_SECONDS) -> List[dict]:
    try:
        from bluepy.btle import Scanner, DefaultDelegate

        class _Delegate(DefaultDelegate):
            def __init__(self):
                DefaultDelegate.__init__(self)

        scanner = Scanner().withDelegate(_Delegate())
        entries = scanner.scan(duration)
        results = []
        for dev in entries:
            name = ""
            for (adtype, desc, value) in dev.getScanData():
                if desc in ("Complete Local Name", "Shortened Local Name"):
                    name = value
                    break
            results.append({
                "name":     name,
                "mac":      dev.addr.upper(),
                "rssi":     dev.rssi,
                "addr_type": dev.addrType,
            })
        return results
    except Exception:
        return []


# ─── bleak backend (async) ────────────────────────────────────────────────────

def _scan_bleak(duration: int = BLE_SCAN_SECONDS) -> List[dict]:
    try:
        import bleak

        async def _discover():
            devices = await bleak.BleakScanner.discover(timeout=duration)
            return devices

        # Use existing event loop if one is running (e.g. inside Jupyter / async context)
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _discover())
                raw_devices = future.result(timeout=duration + 5)
        except RuntimeError:
            # No running loop — safe to use asyncio.run()
            raw_devices = asyncio.run(_discover())

        results = []
        for d in raw_devices:
            results.append({
                "name":      d.name or "",
                "mac":       d.address.upper(),
                "rssi":      d.rssi,
                "addr_type": "ble",
            })
        return results
    except Exception:
        return []


# ─── hcitool backend ─────────────────────────────────────────────────────────

def _scan_hcitool(duration: int = BLE_SCAN_SECONDS) -> List[dict]:
    results = []

    # BLE lescan
    try:
        proc = subprocess.Popen(
            ["hcitool", "lescan", "--duplicates"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        time.sleep(duration)
        proc.terminate()
        out, _ = proc.communicate(timeout=5)
        for line in out.splitlines():
            m = re.match(r"([0-9A-Fa-f:]{17})\s+(.*)", line)
            if m:
                results.append({
                    "name":      m.group(2).strip(),
                    "mac":       m.group(1).upper(),
                    "rssi":      0,
                    "addr_type": "ble",
                })
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass

    # Classic BT scan as fallback
    if not results:
        try:
            out = subprocess.check_output(
                ["hcitool", "scan"], timeout=duration + 5, text=True
            )
            for line in out.splitlines()[1:]:
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    results.append({
                        "name":      parts[1].strip(),
                        "mac":       parts[0].strip().upper(),
                        "rssi":      0,
                        "addr_type": "classic",
                    })
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass

    return results


# ─── RSSI enrichment via hcitool rssi ────────────────────────────────────────

def _get_rssi_hcitool(mac: str) -> int:
    try:
        out = subprocess.check_output(
            ["hcitool", "rssi", mac], timeout=5, text=True
        )
        m = re.search(r"RSSI return value: (-?\d+)", out)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return 0


# ─── Main scanner ─────────────────────────────────────────────────────────────

def scan_ble(duration: int = BLE_SCAN_SECONDS,
             logger: Optional[DataLogger] = None,
             geo_tag: bool = True) -> List[dict]:
    """
    Scan nearby BLE / Bluetooth devices.
    Returns enriched list of device dicts.
    """
    console.print(f"[cyan]Scanning BLE devices for {duration}s …[/cyan]")

    devices: List[dict] = []

    # Try backends in order
    for backend_fn, label in [
        (_scan_bluepy, "bluepy"),
        (_scan_bleak,  "bleak"),
        (_scan_hcitool, "hcitool"),
    ]:
        devices = backend_fn(duration)
        if devices:
            console.print(f"[dim]Backend: {label}[/dim]")
            break

    if not devices:
        console.print("[yellow]No BLE devices found (check bluetooth permissions / root)[/yellow]")

    loc = get_location() if geo_tag else {"provider": "disabled"}
    ts  = timestamp()

    for dev in devices:
        dev["timestamp"]   = ts
        dev["scan_type"]   = "ble"
        dev["device_type"] = classify_device(dev.get("name", ""), dev.get("mac", ""))
        dev["distance_m"]  = rssi_to_distance(dev.get("rssi", 0))
        dev["location"]    = loc

        alert_system.check(
            dev["mac"], dev.get("name", ""), dev.get("rssi", 0), dev["device_type"]
        )

        if logger:
            flat = {**dev, "lat": loc.get("latitude", 0),
                    "lon": loc.get("longitude", 0)}
            flat.pop("location", None)
            logger.log(flat)

    return devices


# ─── Display ──────────────────────────────────────────────────────────────────

def display_ble(devices: List[dict]):
    columns = [
        ("Name",       "cyan"),
        ("MAC Address","white"),
        ("RSSI (dBm)", "green"),
        ("Signal",     "white"),
        ("Dist (m)",   "blue"),
        ("Type",       "magenta"),
        ("Addr Type",  "yellow"),
        ("GPS",        "dim"),
    ]
    table = make_scan_table("🔵  BLE / Bluetooth Devices", columns)

    for dev in sorted(devices, key=lambda x: x.get("rssi", -100), reverse=True):
        loc = dev.get("location", {})
        gps = (f"{loc.get('latitude', 0):.4f},{loc.get('longitude', 0):.4f}"
               if loc.get("provider") not in ("unavailable", "disabled")
               else "—")
        table.add_row(
            dev.get("name") or "[dim](unknown)[/dim]",
            dev.get("mac", ""),
            str(dev.get("rssi", 0)),
            signal_bar(dev.get("rssi", -100)),
            str(dev.get("distance_m", "")),
            dev.get("device_type", ""),
            dev.get("addr_type", ""),
            gps,
        )

    console.print(table)
    console.print(f"[dim]Found {len(devices)} device(s)  •  {timestamp()}[/dim]")
