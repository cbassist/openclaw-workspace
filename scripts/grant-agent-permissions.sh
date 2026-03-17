#!/bin/bash
# grant-agent-permissions.sh — Pre-grant macOS permissions for agent autonomy
# Run with: sudo bash scripts/grant-agent-permissions.sh
#
# This modifies the macOS TCC (Transparency, Consent, Control) database
# to grant accessibility, screen recording, and automation permissions
# to all apps that agents use.
#
# WARNING: Requires SIP adjustment for TCC.db on modern macOS.
# If direct TCC modification fails, falls back to opening System Settings.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=== Agent Autonomy Permission Setup ==="
echo ""

# --- Detect apps ---
APPS=()
APP_NAMES=()

# Ghostty
if [ -d "/Applications/Ghostty.app" ]; then
    APPS+=("com.mitchellh.ghostty")
    APP_NAMES+=("Ghostty")
fi

# Claude
CLAUDE_APP=$(find /Applications -maxdepth 1 -name "Claude*" -type d 2>/dev/null | head -1)
if [ -n "$CLAUDE_APP" ]; then
    CLAUDE_BUNDLE=$(defaults read "$CLAUDE_APP/Contents/Info.plist" CFBundleIdentifier 2>/dev/null || echo "com.anthropic.claude")
    APPS+=("$CLAUDE_BUNDLE")
    APP_NAMES+=("Claude")
fi

# Antigravity
ANTIGRAVITY_APP=$(find /Applications -maxdepth 1 -name "Antigravity*" -type d 2>/dev/null | head -1)
if [ -n "$ANTIGRAVITY_APP" ]; then
    AG_BUNDLE=$(defaults read "$ANTIGRAVITY_APP/Contents/Info.plist" CFBundleIdentifier 2>/dev/null || echo "com.antigravity.app")
    APPS+=("$AG_BUNDLE")
    APP_NAMES+=("Antigravity")
fi

# Playwright Chromium
PW_CHROME="$HOME/Library/Caches/ms-playwright/chromium-1208/chrome-mac-arm64/Google Chrome for Testing.app"
if [ -d "$PW_CHROME" ]; then
    PW_BUNDLE=$(defaults read "$PW_CHROME/Contents/Info.plist" CFBundleIdentifier 2>/dev/null || echo "com.google.chrome.for.testing")
    APPS+=("$PW_BUNDLE")
    APP_NAMES+=("Playwright Chromium")
fi

# Node.js (OpenClaw gateway)
NODE_PATH="$HOME/.local/share/fnm/node-versions/v24.13.0/installation/bin/node"
if [ -f "$NODE_PATH" ]; then
    APP_NAMES+=("Node.js (OpenClaw)")
fi

echo "Detected apps:"
for name in "${APP_NAMES[@]}"; do
    echo "  ✓ $name"
done
echo ""

# --- Method 1: Try tccutil (limited but safe) ---
echo -e "${YELLOW}Method 1: tccutil reset + re-grant${NC}"
echo "Note: tccutil can only reset permissions, not grant them on modern macOS."
echo "We'll reset and then open System Settings for manual confirmation."
echo ""

# --- Method 2: Open System Settings to the right panes ---
echo -e "${GREEN}Opening System Settings — please toggle ON for each app listed above:${NC}"
echo ""

# Accessibility
echo "1. ACCESSIBILITY — granting control of the computer"
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
echo "   → Toggle ON: ${APP_NAMES[*]}"
echo "   Press Enter when done..."
read -r

# Screen Recording
echo "2. SCREEN RECORDING — for screenshots and visual verification"
open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
echo "   → Toggle ON: ${APP_NAMES[*]}"
echo "   Press Enter when done..."
read -r

# Full Disk Access
echo "3. FULL DISK ACCESS — for reading/writing any file"
open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
echo "   → Toggle ON: ${APP_NAMES[*]}"
echo "   Press Enter when done..."
read -r

# Automation
echo "4. AUTOMATION — for controlling other apps"
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation"
echo "   → Toggle ON: ${APP_NAMES[*]}"
echo "   Press Enter when done..."
read -r

# --- Install tmux session helpers ---
echo ""
echo -e "${GREEN}Setting up tmux as the agent terminal...${NC}"

# Create a helper script agents can source
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/agent-tmux" << 'TMUX_HELPER'
#!/bin/bash
# agent-tmux — helper for agent terminal sessions
# Usage:
#   agent-tmux new <name> [command]    — create session and run command
#   agent-tmux send <name> <command>   — send command to session
#   agent-tmux read <name>             — read session output
#   agent-tmux list                    — list sessions
#   agent-tmux kill <name>             — kill session

case "$1" in
    new)
        NAME="${2:-agent-$$}"
        shift 2 2>/dev/null
        CMD="$*"
        tmux new-session -d -s "$NAME" -x 200 -y 50
        if [ -n "$CMD" ]; then
            tmux send-keys -t "$NAME" "$CMD" Enter
        fi
        echo "Session '$NAME' created"
        ;;
    send)
        tmux send-keys -t "$2" "${*:3}" Enter
        ;;
    read)
        tmux capture-pane -t "$2" -p -S -100
        ;;
    list)
        tmux list-sessions 2>/dev/null || echo "No sessions"
        ;;
    kill)
        tmux kill-session -t "$2" 2>/dev/null && echo "Killed '$2'" || echo "Session '$2' not found"
        ;;
    *)
        echo "Usage: agent-tmux {new|send|read|list|kill} [args]"
        ;;
esac
TMUX_HELPER
chmod +x "$HOME/.local/bin/agent-tmux"
echo "  ✓ Installed agent-tmux helper at ~/.local/bin/agent-tmux"

echo ""
echo -e "${GREEN}=== Setup Complete ===${NC}"
echo ""
echo "Summary:"
echo "  • macOS permissions: configured via System Settings"
echo "  • tmux: available for headless agent terminals (no GUI permissions needed)"
echo "  • agent-tmux: helper script installed at ~/.local/bin/agent-tmux"
echo "  • Playwright: use --user-data-dir for persistent browser sessions"
echo ""
echo "Test with:"
echo "  agent-tmux new test-session 'echo hello from agent land'"
echo "  agent-tmux read test-session"
echo "  agent-tmux kill test-session"
