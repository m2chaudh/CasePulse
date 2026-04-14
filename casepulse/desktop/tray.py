"""System tray icon for CasePulse desktop app."""
from __future__ import annotations

import os
import sys
import threading
import webbrowser
from pathlib import Path


def get_icon_path() -> Path:
    """Get the path to the tray icon image."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent.parent.parent
    # Try multiple locations
    for candidate in [base / "icon.png", base / "assets" / "icon.png"]:
        if candidate.exists():
            return candidate
    return base / "icon.png"  # fallback


def create_tray(port: int, on_quit: callable) -> None:
    """Create a system tray icon. Runs in a background thread."""
    try:
        import pystray
        from PIL import Image
    except ImportError:
        # pystray/Pillow not installed — skip tray
        return

    icon_path = get_icon_path()
    if icon_path.exists():
        image = Image.open(str(icon_path))
    else:
        # Generate a simple colored icon
        image = Image.new("RGB", (64, 64), color=(0, 212, 255))

    def open_browser(icon, item):
        webbrowser.open(f"http://127.0.0.1:{port}")

    def quit_app(icon, item):
        icon.stop()
        on_quit()

    menu = pystray.Menu(
        pystray.MenuItem("Open CasePulse", open_browser, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", quit_app),
    )

    icon = pystray.Icon("CasePulse", image, "CasePulse", menu)

    tray_thread = threading.Thread(target=icon.run, daemon=True)
    tray_thread.start()
    return icon
