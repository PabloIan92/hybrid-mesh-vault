#!/usr/bin/env bash
set -e

echo "=========================================================="
echo " 🌌 Installing Hybrid Mesh Vault CLI & Engine"
echo "=========================================================="

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_PATH="$REPO_DIR/bin/mesh-vault"
TARGET_BIN="/usr/local/bin/mesh-vault"

chmod +x "$BIN_PATH"

if [ -w "/usr/local/bin" ]; then
    ln -sf "$BIN_PATH" "$TARGET_BIN"
    echo "✅ Linked $TARGET_BIN -> $BIN_PATH"
else
    mkdir -p "$HOME/.local/bin"
    ln -sf "$BIN_PATH" "$HOME/.local/bin/mesh-vault"
    echo "✅ Linked $HOME/.local/bin/mesh-vault -> $BIN_PATH"
    echo "⚠️ Ensure $HOME/.local/bin is in your PATH."
fi

# Verify dependencies
if ! command -v rsync >/dev/null 2>&1; then
    echo "⚠️ rsync not found. Installing..."
    sudo apt-get update && sudo apt-get install -y rsync
fi

if ! command -v tailscale >/dev/null 2>&1; then
    echo "ℹ️ Tailscale not found on standard PATH. Ensure Tailscale is installed on both nodes."
fi

echo "🚀 Installation complete! Run 'mesh-vault status' to test."
