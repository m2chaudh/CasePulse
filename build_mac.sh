#!/bin/bash
# CasePulse — macOS Build Script
# Usage: ./build_mac.sh
#
# Prerequisites:
#   pip install pyinstaller pywebview pystray Pillow
#
# Output:
#   dist/CasePulse.app      — macOS application bundle
#   dist/CasePulse.dmg      — Disk image (if create-dmg is installed)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== CasePulse macOS Build ==="

# Activate venv
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "ERROR: Virtual environment not found. Run: python3.11 -m venv venv && source venv/bin/activate && pip install -r requirements.txt -r requirements-desktop.txt"
    exit 1
fi

# Check dependencies
echo "Checking build dependencies..."
python -c "import pywebview; import PyInstaller" 2>/dev/null || {
    echo "Installing desktop build dependencies..."
    pip install -r requirements-desktop.txt
}

# Generate icons if missing
if [ ! -f "icon.icns" ]; then
    echo "Generating icons..."
    cd assets && python generate_icon.py && cp icon.icns icon.ico icon.png .. && cd ..
fi

# Clean previous build
echo "Cleaning previous build..."
rm -rf build/CasePulse dist/CasePulse dist/CasePulse.app

# Run PyInstaller
echo "Building with PyInstaller..."
pyinstaller casepulse.spec --noconfirm

echo ""
echo "=== Build Complete ==="
echo "App bundle: dist/CasePulse.app"
echo ""

# Create DMG if create-dmg is available
if command -v create-dmg &> /dev/null; then
    echo "Creating DMG..."
    rm -f dist/CasePulse.dmg
    create-dmg \
        --volname "CasePulse" \
        --volicon "icon.icns" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "CasePulse.app" 150 190 \
        --app-drop-link 450 190 \
        --no-internet-enable \
        "dist/CasePulse.dmg" \
        "dist/CasePulse.app"
    echo "DMG created: dist/CasePulse.dmg"
else
    echo "Tip: Install 'create-dmg' for .dmg packaging:"
    echo "  brew install create-dmg"
    echo ""
    echo "Or create a simple DMG manually:"
    echo "  hdiutil create -volname CasePulse -srcfolder dist/CasePulse.app -ov -format UDZO dist/CasePulse.dmg"
fi
