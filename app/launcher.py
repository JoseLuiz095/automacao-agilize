from __future__ import annotations

import ctypes
import datetime as dt
import os
import sys
import traceback
from pathlib import Path

from resources import APP_USER_MODEL_ID, apply_windows_app_id

MUTEX_NAME = "Local\\JoseLuiz.AutomacaoAgilize.Singleton"
_mutex_handle = None


def _app_home() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    return base / "AutomacaoAgilize"


def _log_file() -> Path:
    folder = _app_home() / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"inicializacao_{dt.datetime.now():%Y%m%d_%H%M%S}.log"


def _write(log: Path, text: str) -> None:
    try:
        with log.open("a", encoding="utf-8") as f:
            f.write(text.rstrip() + "\n")
    except Exception:
        pass
    try:
        print(text, flush=True)
    except Exception:
        pass


def _show_message(title: str, text: str, error: bool = False) -> None:
    if os.name == "nt":
        try:
            flags = 0x10 if error else 0x40
            ctypes.windll.user32.MessageBoxW(0, text, title, flags)
            return
        except Exception:
            pass


def _acquire_single_instance() -> bool:
    global _mutex_handle
    if os.name != "nt":
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        _mutex_handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        if not _mutex_handle:
            return True
        already_exists = kernel32.GetLastError() == 183
        return not already_exists
    except Exception:
        return True


def main() -> int:
    apply_windows_app_id()
    log = _log_file()
    _write(log, "=" * 72)
    _write(log, "Automacao Agilize - inicializacao")
    _write(log, f"AppUserModelID: {APP_USER_MODEL_ID}")
    _write(log, f"Python: {sys.version}")
    _write(log, f"Executavel: {sys.executable}")
    _write(log, "=" * 72)

    if not _acquire_single_instance():
        _show_message("Automação Agilize", "A Automação Agilize já está aberta.")
        return 0

    try:
        import tkinter  # noqa: F401
        import fitz  # noqa: F401
        from playwright.sync_api import sync_playwright  # noqa: F401
        from tkinterdnd2 import TkinterDnD  # noqa: F401

        _write(log, "[OK] Dependencias principais")
        from app import App

        _write(log, "[OK] Codigo da aplicacao importado")
        app = App()
        app.mainloop()
        _write(log, "Aplicacao encerrada normalmente.")
        return 0
    except BaseException:
        error = traceback.format_exc()
        _write(log, "ERRO AO INICIAR:\n" + error)
        _show_message(
            "Automação Agilize - falha ao iniciar",
            "A aplicação não conseguiu iniciar.\n\n"
            f"Log de diagnóstico:\n{log}\n\n"
            "Detalhe:\n" + error[-1800:],
            error=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
