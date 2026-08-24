from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - Windows only
    winreg = None


@dataclass(frozen=True)
class BrowserOption:
    key: str
    label: str
    channel: str
    executable: str = ""


_BROWSER_DEFS = {
    "edge": {
        "label": "Microsoft Edge",
        "channel": "msedge",
        "exe": "msedge.exe",
        "paths": [
            ("PROGRAMFILES(X86)", "Microsoft/Edge/Application/msedge.exe"),
            ("PROGRAMFILES", "Microsoft/Edge/Application/msedge.exe"),
            ("LOCALAPPDATA", "Microsoft/Edge/Application/msedge.exe"),
        ],
    },
    "chrome": {
        "label": "Google Chrome",
        "channel": "chrome",
        "exe": "chrome.exe",
        "paths": [
            ("PROGRAMFILES", "Google/Chrome/Application/chrome.exe"),
            ("PROGRAMFILES(X86)", "Google/Chrome/Application/chrome.exe"),
            ("LOCALAPPDATA", "Google/Chrome/Application/chrome.exe"),
        ],
    },
}


def _registry_app_path(exe_name: str) -> str:
    if os.name != "nt" or winreg is None:
        return ""

    subkey = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}"
    roots = [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]
    views = [0, getattr(winreg, "KEY_WOW64_64KEY", 0), getattr(winreg, "KEY_WOW64_32KEY", 0)]

    for root in roots:
        for view in views:
            try:
                with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | view) as key:
                    value, _ = winreg.QueryValueEx(key, None)
                    if value and Path(value).exists():
                        return str(Path(value))
            except OSError:
                continue
    return ""


def _find_browser(key: str) -> BrowserOption | None:
    info = _BROWSER_DEFS[key]

    found = shutil.which(info["exe"]) or ""
    if found and Path(found).exists():
        return BrowserOption(key, info["label"], info["channel"], found)

    reg = _registry_app_path(info["exe"])
    if reg:
        return BrowserOption(key, info["label"], info["channel"], reg)

    for env_name, relative in info["paths"]:
        base = os.environ.get(env_name, "")
        if not base:
            continue
        path = Path(base) / Path(relative)
        if path.exists():
            return BrowserOption(key, info["label"], info["channel"], str(path))

    return None


def detectar_navegadores() -> list[BrowserOption]:
    encontrados: list[BrowserOption] = []
    for key in ("edge", "chrome"):
        item = _find_browser(key)
        if item:
            encontrados.append(item)
    return encontrados


def labels_para_combo() -> tuple[list[str], dict[str, str]]:
    encontrados = detectar_navegadores()
    labels = ["Automatico (recomendado)"]
    mapping = {labels[0]: "auto"}
    for item in encontrados:
        label = f"{item.label} (instalado)"
        labels.append(label)
        mapping[label] = item.key
    return labels, mapping


def label_para_preferencia(key: str) -> str:
    if key == "auto":
        return "Automatico (recomendado)"
    for item in detectar_navegadores():
        if item.key == key:
            return f"{item.label} (instalado)"
    return "Automatico (recomendado)"


def resolver_navegador(preferencia: str) -> BrowserOption:
    encontrados = detectar_navegadores()
    if not encontrados:
        raise RuntimeError(
            "Nenhum navegador compativel foi encontrado. Instale Microsoft Edge ou Google Chrome."
        )

    pref = (preferencia or "auto").strip().lower()
    if pref != "auto":
        for item in encontrados:
            if item.key == pref:
                return item

    # Edge primeiro porque ele ja vem instalado na maioria das maquinas Windows.
    for key in ("edge", "chrome"):
        for item in encontrados:
            if item.key == key:
                return item
    return encontrados[0]
