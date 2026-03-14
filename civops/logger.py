"""
logger.py - Data logging (JSON / CSV / TXT) and auto-scan scheduling
RapidOs Mobile Recon Radar
"""

import os
import csv
import json
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from rich.console import Console

console = Console()

DEFAULT_LOG_DIR = os.path.expanduser("~/civops_logs")


# ─── Core logger ──────────────────────────────────────────────────────────────

class DataLogger:
    """Persists scan records to JSON, CSV and TXT formats."""

    def __init__(self, log_dir: str = DEFAULT_LOG_DIR):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._session = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._records: list = []
        self._lock = threading.Lock()

    # ── Internal helpers ────────────────────────────────────────────────────

    def _json_path(self, prefix: str) -> Path:
        return self.log_dir / f"{prefix}_{self._session}.json"

    def _csv_path(self, prefix: str) -> Path:
        return self.log_dir / f"{prefix}_{self._session}.csv"

    def _txt_path(self, prefix: str) -> Path:
        return self.log_dir / f"{prefix}_{self._session}.txt"

    # ── Public API ──────────────────────────────────────────────────────────

    def log(self, record: dict):
        """Add a single record to the in-memory buffer and append to TXT."""
        record.setdefault("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        with self._lock:
            self._records.append(record)
        # append to TXT immediately so nothing is lost on crash
        prefix = record.get("scan_type", "scan")
        with open(self._txt_path(prefix), "a") as f:
            f.write(f"[{record.get('timestamp', '')}]\n")
            for k, v in record.items():
                if k != "timestamp":
                    f.write(f"  {k}: {v}\n")
            f.write("\n")

    def save_json(self, prefix: str = "scan") -> str:
        path = self._json_path(prefix)
        with self._lock:
            data = [r for r in self._records if r.get("scan_type", "scan") == prefix]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return str(path)

    def save_csv(self, prefix: str = "scan") -> str:
        path = self._csv_path(prefix)
        with self._lock:
            data = [r for r in self._records if r.get("scan_type", "scan") == prefix]
        if not data:
            return str(path)
        fieldnames = list(data[0].keys())
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(data)
        return str(path)

    def export_all(self, prefix: str = "scan") -> dict:
        """Export buffered records to all three formats."""
        return {
            "json": self.save_json(prefix),
            "csv":  self.save_csv(prefix),
            "txt":  str(self._txt_path(prefix)),
        }

    def get_records(self, prefix: Optional[str] = None) -> list:
        with self._lock:
            if prefix:
                return [r for r in self._records if r.get("scan_type") == prefix]
            return list(self._records)

    def summary(self) -> dict:
        with self._lock:
            total = len(self._records)
            by_type: dict = {}
            for r in self._records:
                t = r.get("scan_type", "unknown")
                by_type[t] = by_type.get(t, 0) + 1
        return {"total": total, "by_type": by_type, "log_dir": str(self.log_dir)}


# ─── Auto-scan scheduler ──────────────────────────────────────────────────────

class AutoScanner:
    """
    Runs a scan callback repeatedly at a fixed interval.

    Usage:
        auto = AutoScanner(interval=30, callback=my_scan_fn, logger=my_logger)
        auto.start()
        # ... later ...
        auto.stop()
    """

    def __init__(self, interval: int, callback: Callable, logger: DataLogger,
                 scan_type: str = "auto"):
        self.interval  = interval
        self.callback  = callback
        self.logger    = logger
        self.scan_type = scan_type
        self._running  = False
        self._thread: Optional[threading.Thread] = None
        self._count    = 0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        console.print(f"[green]Auto-scan started — interval={self.interval}s[/green]")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.interval + 2)
        console.print(f"[yellow]Auto-scan stopped after {self._count} iterations.[/yellow]")

    def _loop(self):
        while self._running:
            try:
                results = self.callback()
                if results:
                    for rec in (results if isinstance(results, list) else [results]):
                        rec["scan_type"] = self.scan_type
                        self.logger.log(rec)
                self._count += 1
                console.print(f"[dim]Auto-scan #{self._count} complete "
                              f"({len(results) if results else 0} records)[/dim]")
            except Exception as exc:
                console.print(f"[red]Auto-scan error: {exc}[/red]")
            for _ in range(self.interval):
                if not self._running:
                    return
                time.sleep(1)


# ─── Recon report generator ───────────────────────────────────────────────────

def generate_report(logger: DataLogger, output_path: Optional[str] = None) -> str:
    """Generate a human-readable recon report from all logged data."""
    records  = logger.get_records()
    summary  = logger.summary()
    ts       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "=" * 72,
        "  RapidOs Mobile Recon Radar — Reconnaissance Report",
        f"  Generated : {ts}",
        f"  Log dir   : {summary['log_dir']}",
        "=" * 72,
        "",
        f"Total records : {summary['total']}",
    ]
    for stype, count in summary["by_type"].items():
        lines.append(f"  {stype:<20} {count} records")
    lines.append("")

    # WiFi section
    wifi = [r for r in records if r.get("scan_type") == "wifi"]
    if wifi:
        lines += ["─" * 72, "  WiFi Networks", "─" * 72]
        for w in wifi:
            lines.append(
                f"  SSID={w.get('ssid','?'):<30}  BSSID={w.get('bssid','?')}  "
                f"Ch={w.get('channel','?'):<3}  RSSI={w.get('rssi','?'):<5}  "
                f"Enc={w.get('encryption','?')}"
            )
        lines.append("")

    # BLE section
    ble = [r for r in records if r.get("scan_type") == "ble"]
    if ble:
        lines += ["─" * 72, "  BLE / Bluetooth Devices", "─" * 72]
        for b in ble:
            lines.append(
                f"  Name={b.get('name','?'):<25}  MAC={b.get('mac','?')}  "
                f"RSSI={b.get('rssi','?'):<5}  Type={b.get('device_type','?')}"
            )
        lines.append("")

    lines += ["=" * 72, "  End of Report", "=" * 72]

    report_text = "\n".join(lines)

    if not output_path:
        output_path = str(logger.log_dir / f"recon_report_{logger._session}.txt")
    with open(output_path, "w") as f:
        f.write(report_text)

    return output_path
