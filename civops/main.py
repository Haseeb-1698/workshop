#!/usr/bin/env python3
"""
main.py - CLI entry point for RapidOs Mobile Recon Radar
RapidOs Mobile Recon Radar

Usage:
  civops scan wifi   [--iface IFACE] [--no-geo] [--export]
  civops scan ble    [--duration SECS] [--no-geo] [--export]
  civops radar       [--mode wifi|ble|both] [--interval SECS]
  civops log start   [--interval SECS] [--mode wifi|ble]
  civops log stop
  civops log status
  civops export csv|json|txt  [--type wifi|ble|scan]
  civops report
  civops alerts
"""

import sys
import os
import time
import argparse
import signal
import threading

# Ensure civops package directory is on the path when running directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.panel import Panel

from utils import print_banner, timestamp, alert_system
from logger import DataLogger, AutoScanner, generate_report
from wifi_scanner import scan_wifi, display_wifi
from ble_scanner import scan_ble, display_ble
from radar_ui import run_radar

console = Console()

# Global shared logger and auto-scanner (persist across sub-commands)
_logger: DataLogger       = DataLogger()
_auto_scanner: AutoScanner | None = None


# ─── Sub-command handlers ─────────────────────────────────────────────────────

def cmd_scan_wifi(args):
    console.print(Panel("[bold cyan]WiFi Reconnaissance Scan[/bold cyan]",
                        border_style="cyan"))
    networks = scan_wifi(
        interface=args.iface,
        logger=_logger,
        geo_tag=not args.no_geo,
    )
    display_wifi(networks)
    if args.export or getattr(args, "export_fmt", None):
        _do_export("wifi", getattr(args, "export_fmt", "csv"))


def cmd_scan_ble(args):
    console.print(Panel("[bold blue]BLE / Bluetooth Scan[/bold blue]",
                        border_style="blue"))
    devices = scan_ble(
        duration=args.duration,
        logger=_logger,
        geo_tag=not args.no_geo,
    )
    display_ble(devices)
    if args.export or getattr(args, "export_fmt", None):
        _do_export("ble", getattr(args, "export_fmt", "csv"))


def cmd_radar(args):
    mode = getattr(args, "mode", "both")

    def _combined_scan():
        results = []
        if mode in ("wifi", "both"):
            results += scan_wifi(logger=_logger)
        if mode in ("ble", "both"):
            results += scan_ble(duration=5, logger=_logger)
        return results

    run_radar(
        scan_callback=_combined_scan,
        refresh_interval=getattr(args, "interval", 10),
    )


def cmd_log_start(args):
    global _auto_scanner
    if _auto_scanner and _auto_scanner._running:
        console.print("[yellow]Auto-scan is already running.[/yellow]")
        return

    mode     = getattr(args, "mode", "wifi")
    interval = getattr(args, "interval", 30)

    def _scan():
        results = []
        if mode in ("wifi", "both"):
            results += scan_wifi(logger=_logger)
        if mode in ("ble", "both"):
            results += scan_ble(duration=5, logger=_logger)
        return results

    _auto_scanner = AutoScanner(
        interval=interval,
        callback=_scan,
        logger=_logger,
        scan_type=mode,
    )
    _auto_scanner.start()

    console.print(f"[green]Auto-scan running every {interval}s.  "
                  "Press Ctrl-C to stop.[/green]")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        _auto_scanner.stop()


def cmd_log_stop(_args):
    global _auto_scanner
    if _auto_scanner and _auto_scanner._running:
        _auto_scanner.stop()
        _auto_scanner = None
    else:
        console.print("[yellow]No auto-scan is running.[/yellow]")


def cmd_log_status(_args):
    summary = _logger.summary()
    console.print(f"[cyan]Log directory:[/cyan]  {summary['log_dir']}")
    console.print(f"[cyan]Total records:[/cyan]  {summary['total']}")
    for stype, count in summary["by_type"].items():
        console.print(f"  [dim]{stype:<20}[/dim]  {count} records")
    if _auto_scanner and _auto_scanner._running:
        console.print("[green]Auto-scan: RUNNING[/green]")
    else:
        console.print("[yellow]Auto-scan: STOPPED[/yellow]")


def cmd_export(args):
    fmt  = getattr(args, "fmt", "csv")
    stype = getattr(args, "type", "scan")
    _do_export(stype, fmt)


def _do_export(prefix: str, fmt: str):
    if fmt == "json":
        path = _logger.save_json(prefix)
    elif fmt == "csv":
        path = _logger.save_csv(prefix)
    else:
        paths = _logger.export_all(prefix)
        for f, p in paths.items():
            console.print(f"[green]Exported {f.upper()}:[/green]  {p}")
        return
    console.print(f"[green]Exported {fmt.upper()}:[/green]  {path}")


def cmd_report(_args):
    path = generate_report(_logger)
    console.print(f"[green]Recon report saved:[/green]  {path}")


def cmd_alerts(_args):
    alerts = alert_system.get_alerts()
    if not alerts:
        console.print("[dim]No alerts recorded in this session.[/dim]")
        return
    for a in alerts:
        console.print(f"[dim]{a['time']}[/dim]  {a['message']}")


# ─── Argument parser ──────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="civops",
        description="RapidOs Mobile Recon Radar — Android/Termux toolkit",
    )
    sub = parser.add_subparsers(dest="command")

    # ── scan ──────────────────────────────────────────────────────────────────
    scan_p = sub.add_parser("scan", help="Run a scan")
    scan_sub = scan_p.add_subparsers(dest="scan_type")

    wifi_p = scan_sub.add_parser("wifi", help="Scan WiFi networks")
    wifi_p.add_argument("--iface",  default="wlan0", help="Wireless interface (default: wlan0)")
    wifi_p.add_argument("--no-geo", action="store_true", help="Skip GPS tagging")
    wifi_p.add_argument("--export", action="store_true", help="Export results to CSV after scan")

    ble_p = scan_sub.add_parser("ble", help="Scan BLE/Bluetooth devices")
    ble_p.add_argument("--duration", type=int, default=10, help="Scan duration in seconds")
    ble_p.add_argument("--no-geo",   action="store_true", help="Skip GPS tagging")
    ble_p.add_argument("--export",   action="store_true", help="Export results to CSV after scan")

    # ── radar ─────────────────────────────────────────────────────────────────
    radar_p = sub.add_parser("radar", help="Live radar display")
    radar_p.add_argument("--mode",     choices=["wifi", "ble", "both"], default="both")
    radar_p.add_argument("--interval", type=int, default=10, help="Rescan interval (seconds)")

    # ── log ───────────────────────────────────────────────────────────────────
    log_p   = sub.add_parser("log", help="Manage auto-scan logging")
    log_sub = log_p.add_subparsers(dest="log_cmd")

    start_p = log_sub.add_parser("start", help="Start continuous scanning")
    start_p.add_argument("--interval", type=int, default=30, help="Scan interval in seconds")
    start_p.add_argument("--mode",     choices=["wifi", "ble", "both"], default="wifi")

    log_sub.add_parser("stop",   help="Stop continuous scanning")
    log_sub.add_parser("status", help="Show logging status")

    # ── export ────────────────────────────────────────────────────────────────
    export_p = sub.add_parser("export", help="Export scan data")
    export_p.add_argument("fmt",  choices=["csv", "json", "txt", "all"], default="csv", nargs="?")
    export_p.add_argument("--type", dest="type", default="scan",
                          help="Record type to export (wifi|ble|scan|auto)")

    # ── report ────────────────────────────────────────────────────────────────
    sub.add_parser("report", help="Generate recon report")

    # ── alerts ────────────────────────────────────────────────────────────────
    sub.add_parser("alerts", help="Show session alerts")

    return parser


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    print_banner()
    parser = build_parser()
    args   = parser.parse_args()

    if args.command == "scan":
        if args.scan_type == "wifi":
            cmd_scan_wifi(args)
        elif args.scan_type == "ble":
            cmd_scan_ble(args)
        else:
            parser.print_help()

    elif args.command == "radar":
        cmd_radar(args)

    elif args.command == "log":
        if args.log_cmd == "start":
            cmd_log_start(args)
        elif args.log_cmd == "stop":
            cmd_log_stop(args)
        elif args.log_cmd == "status":
            cmd_log_status(args)
        else:
            parser.parse_args(["log", "--help"])

    elif args.command == "export":
        cmd_export(args)

    elif args.command == "report":
        cmd_report(args)

    elif args.command == "alerts":
        cmd_alerts(args)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
