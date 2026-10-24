#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
# KnaCLI — Termux Installation Script
# Run once after copying the project to your Termux home dir
# ============================================================

set -e

# Resolve the project root (directory this script lives in)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo ""
echo "🧲  KnaCLI — Termux Setup"
echo "================================"
echo "  Project root : $SCRIPT_DIR"
echo "  Venv path    : $VENV_DIR"
echo ""

# 1. Update packages
echo "[1/5] Updating Termux packages..."
pkg update -y && pkg upgrade -y

# 2. Install system deps
echo "[2/5] Installing Python, aria2, git..."
pkg install -y python aria2 git

# 3. Create virtual environment
echo "[3/5] Creating Python virtual environment (.venv)..."
python -m venv "$VENV_DIR"
echo "  ✅ venv created at: $VENV_DIR"

# 4. Install Python deps inside the venv
echo "[4/5] Installing Python packages into venv..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install textual httpx rich

# 5. Create default download folder
echo "[5/5] Creating default download directory..."
mkdir -p /storage/emulated/0/Downloads/torrent_downloads
echo "  ✅ Created: /storage/emulated/0/Downloads/torrent_downloads"

# ── Write a convenience launcher script ────────────────────
LAUNCHER="$SCRIPT_DIR/run.sh"
cat > "$LAUNCHER" << 'LAUNCHER_EOF'
#!/data/data/com.termux/files/usr/bin/bash
# KnaCLI launcher — activates venv then starts the app
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.venv/bin/activate"
python "$SCRIPT_DIR/main.py"
LAUNCHER_EOF
chmod +x "$LAUNCHER"
echo "  ✅ Launcher written to: $LAUNCHER"

echo ""
echo "================================"
echo "✅  Installation complete!"
echo ""
echo "  ── Option 1: Use the launcher (easiest) ──────────"
echo "  bash ~/knacli/run.sh"
echo ""
echo "  ── Option 2: Activate venv manually ──────────────"
echo "  cd ~/knacli"
echo "  source .venv/bin/activate"
echo "  python main.py"
echo ""
echo "  ── Option 3: Run directly without activating ──────"
echo "  ~/knacli/.venv/bin/python ~/knacli/main.py"
echo ""
echo "  Press [?] inside the app for help."
echo "================================"
