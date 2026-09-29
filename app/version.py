from __future__ import annotations

from resources import resource_path

APP_NAME = "Automação Agilize"
GITHUB_REPOSITORY = "JoseLuiz095/automacao-agilize"
GITHUB_URL = f"https://github.com/{GITHUB_REPOSITORY}"


def _read_version() -> str:
    try:
        value = resource_path("VERSAO.txt").read_text(encoding="utf-8-sig").strip()
        if value:
            return value
    except Exception:
        pass
    return "0.10.4"


__version__ = _read_version()
