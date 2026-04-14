"""CasePulse Desktop Launcher — PyWebView + Streamlit.

Starts a Streamlit server as a subprocess, shows a splash screen
while it boots, then opens a native desktop window via pywebview.
Data is stored in ~/CasePulse/.
"""
from __future__ import annotations

import atexit
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


def get_app_root() -> Path:
    """Get the application root (source dir or PyInstaller bundle)."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


def find_free_port() -> int:
    """Find an available port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_server(port: int, timeout: float = 60.0) -> bool:
    """Wait until the Streamlit server is responding."""
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = urllib.request.urlopen(
                f"http://127.0.0.1:{port}/_stcore/health", timeout=2
            )
            if resp.status == 200:
                return True
        except Exception:
            pass
        time.sleep(0.4)
    return False


def start_streamlit(port: int) -> subprocess.Popen:
    """Start Streamlit as a subprocess."""
    app_root = get_app_root()
    app_path = str(app_root / "app.py")

    env = os.environ.copy()
    env["CASEPULSE_DESKTOP"] = "1"
    env["PYTHONPATH"] = str(app_root) + os.pathsep + env.get("PYTHONPATH", "")

    # Use the same Python that's running us
    python = sys.executable

    cmd = [
        python, "-m", "streamlit", "run", app_path,
        f"--server.port={port}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--server.fileWatcherType=none",
        "--global.developmentMode=false",
    ]

    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Ensure cleanup on exit
    def cleanup():
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    atexit.register(cleanup)
    return proc


def main():
    port = find_free_port()

    # Show splash screen while server starts
    splash = None
    try:
        root = str(get_app_root())
        if root not in sys.path:
            sys.path.insert(0, root)
        from casepulse.desktop.splash import SplashScreen
        splash = SplashScreen()
        splash.show()
    except Exception:
        pass  # Splash is optional

    # Start Streamlit as subprocess
    proc = start_streamlit(port)
    print(f"Starting CasePulse on port {port}...")

    if not wait_for_server(port, timeout=60):
        if splash:
            splash.close()
        print("ERROR: Streamlit server failed to start within 60 seconds.")
        proc.terminate()
        sys.exit(1)

    print("Server ready. Opening window...")

    # Close splash before opening main window
    if splash:
        splash.close()
        time.sleep(0.2)

    # Start system tray (optional)
    try:
        from casepulse.desktop.tray import create_tray

        def quit_app():
            proc.terminate()
            os._exit(0)

        create_tray(port, on_quit=quit_app)
    except Exception:
        pass

    import webview

    window = webview.create_window(
        "CasePulse",
        f"http://127.0.0.1:{port}",
        width=1400,
        height=900,
        min_size=(900, 600),
        text_select=True,
    )

    def on_closed():
        proc.terminate()
        os._exit(0)

    window.events.closed += on_closed

    webview.start(
        gui=None,
        debug=not getattr(sys, "frozen", False),
    )


if __name__ == "__main__":
    main()
