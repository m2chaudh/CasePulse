"""Splash screen shown while Streamlit server starts."""
from __future__ import annotations

import threading

try:
    import tkinter as tk
    HAS_TK = True
except ImportError:
    HAS_TK = False


class SplashScreen:
    """A simple splash window that shows while Streamlit boots."""

    def __init__(self):
        self._root: tk.Tk | None = None
        self._thread: threading.Thread | None = None

    def show(self) -> None:
        """Show the splash screen in a background thread."""
        if not HAS_TK:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        if not HAS_TK:
            return
        self._root = tk.Tk()
        self._root.overrideredirect(True)
        self._root.configure(bg="#1a1a2e")

        # Center on screen
        w, h = 420, 220
        sw = self._root.winfo_screenwidth()
        sh = self._root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self._root.geometry(f"{w}x{h}+{x}+{y}")

        # Keep on top
        self._root.attributes("-topmost", True)

        # Content
        frame = tk.Frame(self._root, bg="#1a1a2e", padx=30, pady=20)
        frame.pack(expand=True, fill="both")

        tk.Label(
            frame, text="CasePulse", font=("Helvetica", 28, "bold"),
            fg="#00d4ff", bg="#1a1a2e",
        ).pack(pady=(15, 5))

        tk.Label(
            frame, text="Legal Email Aggregation & Analysis",
            font=("Helvetica", 12), fg="#888888", bg="#1a1a2e",
        ).pack(pady=(0, 20))

        tk.Label(
            frame, text="Starting server...",
            font=("Helvetica", 11), fg="#aaaaaa", bg="#1a1a2e",
        ).pack()

        self._root.mainloop()

    def close(self) -> None:
        """Close the splash screen."""
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass
        self._root = None
