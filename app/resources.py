from __future__ import annotations

import os
import sys
from pathlib import Path

APP_USER_MODEL_ID = "JoseLuiz.AutomacaoAgilize"


def bundle_root() -> Path:
    """Root containing files bundled by PyInstaller."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).resolve().parents[1]


def resource_path(*parts: str) -> Path:
    return bundle_root().joinpath(*parts)


def apply_windows_app_id() -> None:
    """Give Windows a stable taskbar identity for this application."""
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def apply_window_icon(window) -> None:
    """Apply the .ico/.png to a Tk window in dev and frozen builds."""
    ico = resource_path("assets", "automacao-agilize.ico")
    png = resource_path("assets", "automacao-agilize.png")

    if ico.exists():
        try:
            window.iconbitmap(default=str(ico))
        except Exception:
            pass

    if png.exists():
        try:
            import tkinter as tk

            image = tk.PhotoImage(file=str(png))
            window.iconphoto(True, image)
            # Keep a reference so Tk does not garbage-collect it.
            window._app_icon_image = image
        except Exception:
            pass
