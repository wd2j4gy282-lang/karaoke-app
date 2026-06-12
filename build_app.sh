#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
#  build_app.sh — builds "Karaoke.app" from app.py
#  and optionally adds it to the Dock.
#
#  Run from the script's folder:
#    cd ~/Scripts/karaoke-app
#    bash build_app.sh
# ──────────────────────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Karaoke"
APP_PATH="$HOME/Applications/$APP_NAME.app"
ICON_PNG="$SCRIPT_DIR/karaoke_icon.png"   # optional: drop a PNG here for a custom icon
PY_SCRIPT="$SCRIPT_DIR/app.py"

if [ -x "$SCRIPT_DIR/venv/bin/python" ]; then
  PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
else
  PYTHON_BIN="$(which python3)"
fi

echo ""
echo "🎤  Building \"$APP_NAME.app\""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Pre-flight checks ───────────────────────────────────────────────────────
if [ ! -f "$PY_SCRIPT" ]; then
  echo "❌  Script not found: $PY_SCRIPT"
  echo "   Run this from the karaoke-app folder."
  exit 1
fi
if [ ! -f "$PYTHON_BIN" ]; then
  echo "❌  python3 not found. Install it from python.org first."
  exit 1
fi
mkdir -p "$HOME/Applications"

# ── 2. Write AppleScript source ───────────────────────────────────────────────
APPLESCRIPT_SRC=$(cat << ASEOF
tell application "Terminal"
    activate
    -- Open a new window if Terminal is already running
    if (count of windows) = 0 then
        do script "cd '$SCRIPT_DIR' && '$PYTHON_BIN' '$PY_SCRIPT'"
    else
        do script "cd '$SCRIPT_DIR' && '$PYTHON_BIN' '$PY_SCRIPT'" in window 1
    end if
end tell
ASEOF
)

# ── 3. Compile AppleScript to .app ───────────────────────────────────────────
echo "  Compiling AppleScript…"
echo "$APPLESCRIPT_SRC" | osacompile -o "$APP_PATH" -
echo "  ✅  App created at: $APP_PATH"

# ── 4. Apply custom icon (if icon PNG exists) ─────────────────────────────────
if [ -f "$ICON_PNG" ]; then
  echo "  Applying custom icon…"

  ICONSET_DIR="/tmp/Karaoke.iconset"
  ICNS_PATH="/tmp/Karaoke.icns"
  rm -rf "$ICONSET_DIR"
  mkdir -p "$ICONSET_DIR"

  # Generate required icon sizes
  sips -z 16   16   "$ICON_PNG" --out "$ICONSET_DIR/icon_16x16.png"       > /dev/null 2>&1
  sips -z 32   32   "$ICON_PNG" --out "$ICONSET_DIR/icon_16x16@2x.png"    > /dev/null 2>&1
  sips -z 32   32   "$ICON_PNG" --out "$ICONSET_DIR/icon_32x32.png"       > /dev/null 2>&1
  sips -z 64   64   "$ICON_PNG" --out "$ICONSET_DIR/icon_32x32@2x.png"    > /dev/null 2>&1
  sips -z 128  128  "$ICON_PNG" --out "$ICONSET_DIR/icon_128x128.png"     > /dev/null 2>&1
  sips -z 256  256  "$ICON_PNG" --out "$ICONSET_DIR/icon_128x128@2x.png"  > /dev/null 2>&1
  sips -z 256  256  "$ICON_PNG" --out "$ICONSET_DIR/icon_256x256.png"     > /dev/null 2>&1
  sips -z 512  512  "$ICON_PNG" --out "$ICONSET_DIR/icon_256x256@2x.png"  > /dev/null 2>&1
  sips -z 512  512  "$ICON_PNG" --out "$ICONSET_DIR/icon_512x512.png"     > /dev/null 2>&1
  sips -z 1024 1024 "$ICON_PNG" --out "$ICONSET_DIR/icon_512x512@2x.png"  > /dev/null 2>&1

  # Convert to .icns
  iconutil -c icns "$ICONSET_DIR" -o "$ICNS_PATH" 2>/dev/null

  if [ -f "$ICNS_PATH" ]; then
    # Replace the app's default icon
    cp "$ICNS_PATH" "$APP_PATH/Contents/Resources/applet.icns"
    # Force Finder to refresh the icon cache for this app
    touch "$APP_PATH"
    echo "  ✅  Icon applied"
  else
    echo "  ⚠️  Could not create .icns — icon not applied (app still works fine)"
  fi

  rm -rf "$ICONSET_DIR" "$ICNS_PATH" 2>/dev/null
else
  echo "  ℹ️   No icon PNG found at $ICON_PNG — using default Script Editor icon"
  echo "      (paste a custom icon via Get Info if you want one)"
fi

# ── 5. First-launch Gatekeeper fix ────────────────────────────────────────────
# Remove the quarantine flag so macOS doesn't block the first launch
xattr -rd com.apple.quarantine "$APP_PATH" 2>/dev/null || true

# ── 6. Offer to add to Dock ───────────────────────────────────────────────────
echo ""
read -p "  Add \"$APP_NAME\" to your Dock? (y/n): " ADD_DOCK
if [[ "$ADD_DOCK" =~ ^[Yy] ]]; then
  # Add to Dock using defaults + killall
  APP_ABS="$(python3 -c "import os; print(os.path.realpath('$APP_PATH'))")"
  DOCK_ENTRY="<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>$APP_ABS</string><key>_CFURLStringType</key><integer>0</integer></dict></dict></dict>"
  defaults write com.apple.dock persistent-apps -array-add "$DOCK_ENTRY"
  killall Dock
  echo "  ✅  Added to Dock — it will appear after Dock restarts (takes a moment)"
else
  echo "  ℹ️   Skipped — drag \"$APP_NAME.app\" from ~/Applications to your Dock anytime"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅  Done!"
echo ""
echo "  App location: $APP_PATH"
echo ""
echo "  First launch: right-click → Open (bypasses Gatekeeper)"
echo "  After that:   double-click works normally"
echo ""
echo "  The app opens a Terminal window and starts the web server."
echo "  The browser opens automatically."
echo "  Close Terminal when you're done (or use Quit App in the page)."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
