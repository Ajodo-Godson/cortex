#!/usr/bin/env bash
set -e

REPO="https://github.com/Ajodo-Godson/cortex"
INSTALL_DIR="$HOME/.cortex-src"

echo "==> Installing Cortex"

# Rust
if ! command -v cargo &>/dev/null; then
  echo "==> Installing Rust..."
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path
  source "$HOME/.cargo/env"
fi

# pipx
if ! command -v pipx &>/dev/null; then
  if command -v brew &>/dev/null; then
    brew install pipx
  else
    python3 -m pip install --user pipx
  fi
fi
pipx ensurepath

# Clone or update
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "==> Updating cortex source..."
  git -C "$INSTALL_DIR" pull --ff-only
else
  echo "==> Cloning cortex..."
  git clone "$REPO" "$INSTALL_DIR"
fi

# Install
echo "==> Installing cortex..."
pipx install -e "$INSTALL_DIR/[all]" --force

# MCP and provider deps
pipx inject cortex "mcp>=1.0"

# .env
if [ ! -f "$INSTALL_DIR/.env" ]; then
  cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
  echo ""
  echo "==> Edit $INSTALL_DIR/.env to add your API key."
fi

echo ""
echo "Done. Open a new terminal, then run 'cortex start' in any git repo."
