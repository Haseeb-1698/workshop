#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  install.sh — RapidOs Mobile Recon Radar
#  Automated installer for Termux (Android)
# ============================================================

set -e

CIVOPS_DIR="$HOME/civops"
BIN_LINK="$PREFIX/bin/civops"

# ── Colour helpers ────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}[*]${RESET} $*"; }
success() { echo -e "${GREEN}[✓]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[!]${RESET} $*"; }
error()   { echo -e "${RED}[✗]${RESET} $*"; exit 1; }

banner() {
cat <<'EOF'
  ____             _     _  ___
 |  _ \ __ _ _ __ (_) __| |/ _ \___
 | |_) / _` | '_ \| |/ _` | | | / __|
 |  _ < (_| | |_) | | (_| | |_| \__ \
 |_| \_\__,_| .__/|_|\__,_|\___/|___/
            |_|
  Mobile Recon Radar  —  Termux Installer
EOF
}

banner

# ── Step 1: Update Termux packages ───────────────────────────
info "Updating Termux package list …"
pkg update -y && pkg upgrade -y

# ── Step 2: Install system packages ──────────────────────────
info "Installing system packages …"
PKGS=(
    python
    python-pip
    nmap
    bluez
    bluez-utils
    wireless-tools
    net-tools
    git
    termux-api        # for GPS via termux-location
    libzmq
    libffi
    openssl
)

for pkg in "${PKGS[@]}"; do
    if pkg list-installed 2>/dev/null | grep -q "^$pkg/"; then
        success "  $pkg (already installed)"
    else
        info "  Installing $pkg …"
        pkg install -y "$pkg" || warn "  Could not install $pkg — skipping"
    fi
done

# ── Step 3: Copy civops files ─────────────────────────────────
info "Installing civops to $CIVOPS_DIR …"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$SCRIPT_DIR" != "$CIVOPS_DIR" ]; then
    mkdir -p "$CIVOPS_DIR"
    cp "$SCRIPT_DIR/civops/"*.py  "$CIVOPS_DIR/"
    cp "$SCRIPT_DIR/requirements.txt" "$CIVOPS_DIR/"
fi
success "Files copied."

# ── Step 4: Install Python dependencies ──────────────────────
info "Installing Python dependencies …"
pip install --upgrade pip setuptools wheel

# Install each dependency individually for better error handling
PYTHON_PKGS=(
    "rich>=13.0.0"
    "bleak>=0.21.0"
    "pandas>=2.0.0"
)

for dep in "${PYTHON_PKGS[@]}"; do
    pip install "$dep" || warn "Could not install $dep — some features may be unavailable"
done

# These may fail on some Android versions; non-fatal
OPTIONAL_PKGS=(
    "scapy>=2.5.0"
    "python-nmap>=0.7.1"
    "bluepy>=1.3.0"
    "gpsd-py3>=0.3.0"
)

for dep in "${OPTIONAL_PKGS[@]}"; do
    pip install "$dep" 2>/dev/null \
        && success "  Installed $dep" \
        || warn    "  Optional: $dep not installed — fallback will be used"
done

# ── Step 5: Create civops launcher script ────────────────────
info "Creating civops launcher …"
cat > "$BIN_LINK" <<LAUNCHER
#!/data/data/com.termux/files/usr/bin/bash
exec python "$CIVOPS_DIR/main.py" "\$@"
LAUNCHER

chmod +x "$BIN_LINK"
success "Launcher created at $BIN_LINK"

# ── Step 6: Permissions reminder ─────────────────────────────
echo ""
warn "──────────────────────────────────────────────────────"
warn "PERMISSIONS REQUIRED:"
warn "  • Open Termux:API app and grant Location permission"
warn "  • For WiFi scanning, run civops as root or use"
warn "    Android WiFi scanning APIs"
warn "  • For BLE scanning, grant Bluetooth permissions"
warn "    via Termux:API"
warn "──────────────────────────────────────────────────────"
echo ""

# ── Done ──────────────────────────────────────────────────────
success "Installation complete!"
echo ""
echo -e "${BOLD}Quick start:${RESET}"
echo "  civops scan wifi"
echo "  civops scan ble"
echo "  civops radar"
echo "  civops log start --interval 30"
echo "  civops export csv"
echo "  civops report"
echo ""
echo -e "${CYAN}Log files are saved to:${RESET}  ~/civops_logs/"
echo ""
