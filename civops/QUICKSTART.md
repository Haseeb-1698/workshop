# RapidOs Mobile Recon Radar

> Turn any Android phone into a lightweight wireless reconnaissance platform.

See [civops/README.md](civops/README.md) for the full documentation, installation guide,
CLI usage manual, and example output.

## Quick Start (Termux)

```bash
bash install.sh
civops scan wifi
civops scan ble
civops radar
```

## Project Layout

```
civops/          ← Python toolkit (main entry point: civops/main.py)
install.sh       ← Automated Termux installer
requirements.txt ← Python dependencies
```
