#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=================================================="
echo "  Building Shadda Anti Detect v0.1 for macOS"
echo "=================================================="

VENV_PYTHON="$DIR/.venv/bin/python"
VENV_PYINSTALLER="$DIR/.venv/bin/pyinstaller"

if [ ! -f "$VENV_PYINSTALLER" ]; then
    echo "Error: PyInstaller not found in .venv"
    exit 1
fi

# Clean previous builds
rm -rf build dist dmg_staging

echo "[1/4] Building standalone macOS App Bundle with PyInstaller..."
"$VENV_PYINSTALLER" \
    --noconfirm \
    --clean \
    --windowed \
    --name "Shadda Anti Detect" \
    --icon "ShaddaAntiDetect.icns" \
    --add-data "static:static" \
    --add-data "anti_detect_extension:anti_detect_extension" \
    --add-data "bootstrap_config.json:." \
    --add-data "github_client.pyc:." \
    --add-data "github_accounts.json:." \
    --hidden-import "country_proxies" \
    --hidden-import "github_client" \
    --hidden-import "webview" \
    --hidden-import "objc" \
    --hidden-import "WebKit" \
    --hidden-import "Foundation" \
    --hidden-import "AppKit" \
    --hidden-import "websocket" \
    --hidden-import "bottle" \
    --hidden-import "proxy_tools" \
    --collect-all "webview" \
    --osx-bundle-identifier "com.shadda.antidetect" \
    server.py

APP_PATH="dist/Shadda Anti Detect.app"
if [ ! -d "$APP_PATH" ]; then
    echo "Error: $APP_PATH was not generated!"
    exit 1
fi

echo "[2/4] App bundle created successfully at $APP_PATH"

# Ensure executable permissions inside app bundle
chmod +x "$APP_PATH/Contents/MacOS/Shadda Anti Detect"

# Update Info.plist version and metadata
PLIST="$APP_PATH/Contents/Info.plist"
if [ -f "$PLIST" ]; then
    /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString 0.1" "$PLIST" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string 0.1" "$PLIST"
    /usr/libexec/PlistBuddy -c "Set :CFBundleVersion 0.1.0" "$PLIST" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :CFBundleVersion string 0.1.0" "$PLIST"
    /usr/libexec/PlistBuddy -c "Set :NSHumanReadableCopyright 'Copyright © 2026 Shadda Anti Detect'" "$PLIST" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Add :NSHumanReadableCopyright string 'Copyright © 2026 Shadda Anti Detect'" "$PLIST"
fi

echo "[3/4] Preparing DMG staging environment..."
mkdir -p dmg_staging
cp -R "$APP_PATH" dmg_staging/
ln -s /Applications dmg_staging/Applications

DMG_OUTPUT="dist/Shadda Anti Detect-0.1.dmg"
rm -f "$DMG_OUTPUT"

echo "[4/4] Creating macOS DMG image with hdiutil..."
hdiutil create \
    -volname "Shadda Anti Detect" \
    -srcfolder dmg_staging \
    -ov \
    -format UDZO \
    "$DMG_OUTPUT"

rm -rf dmg_staging

echo "=================================================="
echo "  BUILD SUCCESSFUL!"
echo "  DMG Installer: $DIR/$DMG_OUTPUT"
echo "  File size: $(du -sh "$DIR/$DMG_OUTPUT" | cut -f1)"
echo "=================================================="
