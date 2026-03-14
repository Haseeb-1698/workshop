"""
gps.py - GPS coordinate capture via gpsd / Termux GPS API
RapidOs Mobile Recon Radar
"""

import os
import json
import time
import subprocess
from typing import Optional, Tuple

try:
    import gpsd
    GPSD_AVAILABLE = True
except ImportError:
    GPSD_AVAILABLE = False


# ─── Termux GPS helper (no root, uses Termux:API) ────────────────────────────

def _termux_location() -> Optional[dict]:
    """Try to get location via termux-location (requires Termux:API app)."""
    try:
        result = subprocess.run(
            ["termux-location", "-p", "gps", "-r", "once"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            return {
                "latitude":  data.get("latitude",  0.0),
                "longitude": data.get("longitude", 0.0),
                "altitude":  data.get("altitude",  0.0),
                "accuracy":  data.get("accuracy",  0.0),
                "provider":  "termux-location",
            }
    except (FileNotFoundError, subprocess.TimeoutExpired,
            json.JSONDecodeError, Exception):
        pass
    return None


def _gpsd_location() -> Optional[dict]:
    """Get location via gpsd daemon."""
    if not GPSD_AVAILABLE:
        return None
    try:
        gpsd.connect()
        packet = gpsd.get_current()
        if packet.mode >= 2:
            return {
                "latitude":  packet.lat,
                "longitude": packet.lon,
                "altitude":  getattr(packet, "alt", 0.0),
                "accuracy":  getattr(packet, "error", {}).get("y", 0.0),
                "provider":  "gpsd",
            }
    except Exception:
        pass
    return None


def get_location() -> dict:
    """
    Return current GPS coordinates.  Falls back gracefully:
      1. Termux:API  (termux-location)
      2. gpsd daemon
      3. Placeholder zeros with a note
    """
    loc = _termux_location()
    if loc:
        return loc

    loc = _gpsd_location()
    if loc:
        return loc

    return {
        "latitude":  0.0,
        "longitude": 0.0,
        "altitude":  0.0,
        "accuracy":  0.0,
        "provider":  "unavailable",
    }


def format_location(loc: dict) -> str:
    if loc["provider"] == "unavailable":
        return "GPS unavailable"
    return (f"Lat={loc['latitude']:.6f}  Lon={loc['longitude']:.6f}  "
            f"Alt={loc['altitude']:.1f}m  ±{loc['accuracy']:.1f}m  "
            f"[{loc['provider']}]")
