"""
radar_ui.py - Real-time CLI radar visualization
RapidOs Mobile Recon Radar
"""

import math
import time
import threading
from typing import List, Callable, Optional

from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from utils import rssi_to_distance, signal_bar, timestamp

console = Console()

# ─── Radar canvas settings ────────────────────────────────────────────────────
RADAR_WIDTH  = 61   # must be odd
RADAR_HEIGHT = 31   # must be odd
SWEEP_FRAMES = 36   # 360 ° / 10° per frame


def _rssi_to_ring(rssi: int, rings: int = 4) -> int:
    """Map RSSI → ring index (0 = outer / weak, rings-1 = inner / strong)."""
    if rssi >= -50:
        return rings - 1
    if rssi >= -65:
        return rings - 2
    if rssi >= -80:
        return 1
    return 0


def _polar_to_canvas(angle_deg: float, ring: int, rings: int,
                     cx: int, cy: int, rx: int, ry: int):
    """Convert polar (angle, ring) to canvas (col, row)."""
    frac    = (ring + 1) / rings
    angle_r = math.radians(angle_deg)
    col     = int(cx + rx * frac * math.cos(angle_r))
    row     = int(cy - ry * frac * math.sin(angle_r))
    return col, row


def _build_radar_frame(devices: List[dict], sweep_angle: float,
                       width: int = RADAR_WIDTH,
                       height: int = RADAR_HEIGHT,
                       rings: int = 4) -> Text:
    """
    Render one frame of the ASCII radar.
    devices: list of dicts with at minimum 'rssi' and optionally 'name', 'mac'.
    """
    cx = width  // 2
    cy = height // 2
    rx = cx - 1
    ry = cy - 1

    # blank canvas
    canvas = [[" "] * width for _ in range(height)]

    # draw ring circles
    for ring in range(1, rings + 1):
        frac = ring / rings
        for a in range(360):
            rad = math.radians(a)
            col = int(cx + rx * frac * math.cos(rad))
            row = int(cy - ry * frac * math.sin(rad))
            if 0 <= row < height and 0 <= col < width:
                canvas[row][col] = "·"

    # cross-hairs
    canvas[cy][cx] = "+"
    for c in range(width):
        if canvas[cy][c] == " ":
            canvas[cy][c] = "─"
    for r in range(height):
        if canvas[r][cx] == " ":
            canvas[r][cx] = "│"

    # sweep line
    for dist in range(1, max(rx, ry) + 1):
        rad = math.radians(sweep_angle)
        col = int(cx + dist * math.cos(rad))
        row = int(cy - dist * math.sin(rad))
        if 0 <= row < height and 0 <= col < width:
            canvas[row][col] = "/"

    # place device blips
    blip_chars = ["◉", "●", "○", "◎"]
    colors: dict = {}
    for i, dev in enumerate(devices[:20]):   # cap at 20 blips
        rssi  = dev.get("rssi", -90)
        ring  = _rssi_to_ring(rssi, rings)
        angle = (i * (360 / max(len(devices), 1))) % 360
        col, row = _polar_to_canvas(angle, ring, rings, cx, cy, rx, ry)
        if 0 <= row < height and 0 <= col < width:
            blip = blip_chars[ring % len(blip_chars)]
            canvas[row][col] = blip
            if rssi >= -50:
                colors[(row, col)] = "bold green"
            elif rssi >= -65:
                colors[(row, col)] = "green"
            elif rssi >= -80:
                colors[(row, col)] = "yellow"
            else:
                colors[(row, col)] = "red"

    # assemble rich Text
    text = Text()
    for r, row_chars in enumerate(canvas):
        for c, ch in enumerate(row_chars):
            color = colors.get((r, c))
            if ch == "/" and not color:
                text.append(ch, style="dim green")
            elif color:
                text.append(ch, style=color)
            elif ch in "·─│+":
                text.append(ch, style="dim cyan")
            else:
                text.append(ch)
        text.append("\n")
    return text


def _build_legend(devices: List[dict]) -> Table:
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold",
                  title="[cyan]Detected Devices[/cyan]")
    table.add_column("#",      style="dim",  width=3)
    table.add_column("Name",   style="cyan", width=22)
    table.add_column("MAC/BSSID", style="white", width=19)
    table.add_column("RSSI",   style="green", width=8)
    table.add_column("Signal", style="white", width=22)
    table.add_column("Dist",   style="blue",  width=8)
    table.add_column("Type",   style="magenta", width=12)

    for i, dev in enumerate(sorted(devices,
                                    key=lambda x: x.get("rssi", -100),
                                    reverse=True)[:20], start=1):
        mac  = dev.get("mac") or dev.get("bssid", "")
        name = dev.get("name") or dev.get("ssid") or "(unknown)"
        table.add_row(
            str(i),
            name[:22],
            mac,
            str(dev.get("rssi", "?")),
            signal_bar(dev.get("rssi", -100)),
            f"{dev.get('distance_m', '?')} m",
            dev.get("device_type", dev.get("scan_type", "")),
        )
    return table


# ─── Live radar loop ──────────────────────────────────────────────────────────

def run_radar(scan_callback: Callable[[], List[dict]],
              refresh_interval: int = 5,
              duration: Optional[int] = None):
    """
    Run a live radar display.

    scan_callback : callable that returns a list of device/network dicts
    refresh_interval : seconds between full rescans
    duration : total seconds to run (None = run until Ctrl-C)
    """
    console.print("[bold cyan]Starting radar — press Ctrl-C to stop[/bold cyan]")

    devices:   List[dict] = []
    frame_idx: int        = 0
    sweep_deg: float      = 0.0
    last_scan: float      = 0.0
    start:     float      = time.time()

    def _update_scan():
        nonlocal devices, last_scan
        try:
            devices  = scan_callback()
            last_scan = time.time()
        except Exception as exc:
            console.print(f"[red]Scan error: {exc}[/red]")

    # initial scan in background
    t = threading.Thread(target=_update_scan, daemon=True)
    t.start()

    with Live(console=console, refresh_per_second=4, screen=False) as live:
        try:
            while True:
                elapsed = time.time() - start
                if duration and elapsed > duration:
                    break

                # trigger rescan periodically
                if time.time() - last_scan >= refresh_interval:
                    t = threading.Thread(target=_update_scan, daemon=True)
                    t.start()

                # advance sweep
                sweep_deg = (sweep_deg + 10) % 360

                radar_frame = _build_radar_frame(devices, sweep_deg)
                legend      = _build_legend(devices)

                panel = Panel(
                    radar_frame,
                    title=f"[bold cyan]RapidOs Recon Radar[/bold cyan]  "
                          f"[dim]{timestamp()}[/dim]",
                    subtitle=f"[dim]{len(devices)} device(s) — "
                             f"next scan in {max(0, int(refresh_interval - (time.time()-last_scan)))}s[/dim]",
                    border_style="cyan",
                )

                live.update(Columns([panel, legend]))
                time.sleep(0.25)

        except KeyboardInterrupt:
            console.print("\n[yellow]Radar stopped.[/yellow]")
