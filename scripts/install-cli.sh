#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  ARIIA CLI Installer
#  Creates a global 'ariia' command symlink
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARIIA_SCRIPT="$SCRIPT_DIR/ariia"
SYMLINK_PATH="/usr/local/bin/ariia"

echo ""
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║  ARIIA CLI Installer                                     ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo ""

# Check if script exists
if [ ! -f "$ARIIA_SCRIPT" ]; then
  echo "  ✗ Error: ariia script not found at $ARIIA_SCRIPT"
  exit 1
fi

# Ensure script is executable
chmod +x "$ARIIA_SCRIPT"

# Create symlink
if [ -L "$SYMLINK_PATH" ] || [ -f "$SYMLINK_PATH" ]; then
  echo "  ⚠ Existing installation found at $SYMLINK_PATH"
  echo "  ▸ Updating..."
  sudo rm -f "$SYMLINK_PATH"
fi

sudo ln -s "$ARIIA_SCRIPT" "$SYMLINK_PATH"

# Install dialog if not present
if ! command -v dialog &>/dev/null; then
  echo "  ▸ Installing dialog for TUI..."
  sudo apt-get update -qq && sudo apt-get install -y -qq dialog >/dev/null 2>&1
fi

# Create backup directory
sudo mkdir -p /var/backups/ariia
sudo chown "$(whoami)" /var/backups/ariia

# Create log file
sudo touch /var/log/ariia-deploy.log
sudo chown "$(whoami)" /var/log/ariia-deploy.log

echo ""
echo "  ✓ ARIIA CLI installed successfully!"
echo ""
echo "  Usage:"
echo "    ariia              Launch interactive TUI"
echo "    ariia --help       Show all commands"
echo "    ariia --status     Service status overview"
echo "    ariia --update     Smart update & rebuild"
echo "    ariia --backup     Create full backup"
echo ""
echo "  Run 'ariia --help' for the full command reference."
echo ""
