from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from config import CONFIG_DIR, SETTINGS_FILE


@dataclass
class Credenciais:
    email: str = ""
    senha: str = ""
    login_automatico: bool = True
    navegador: str = "auto"


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes):
    buf = ctypes.create_string_buffer(data, len(data))
    return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))), buf


def _dpapi_encrypt(texto: str) -> str:
    if os.name != "nt":
        raise RuntimeError("O armazenamento seguro de senha requer Windows.")
    raw = texto.encode("utf-8")
    entrada, _entrada_buf = _blob(raw)
    saida = DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(entrada),
        "Automacao Agilize",
        None,
        None,
        None,
        0,
        ctypes.byref(saida),
    )
    if not ok:
        raise ctypes.WinError()
    try:
        encrypted = ctypes.string_at(saida.pbData, saida.cbData)
        return base64.b64encode(encrypted).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(saida.pbData)


def _dpapi_decrypt(value: str) -> str:
    if not value or os.name != "nt":
        return ""
    try:
        encrypted = base64.b64decode(value.encode("ascii"))
    except Exception:
        return ""
    entrada, _entrada_buf = _blob(encrypted)
    saida = DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(entrada), None, None, None, None, 0, ctypes.byref(saida)
    )
    if not ok:
        return ""
    try:
        raw = ctypes.string_at(saida.pbData, saida.cbData)
        return raw.decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(saida.pbData)


def _ler_settings() -> dict:
    try:
        if SETTINGS_FILE.exists():
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _salvar_settings(settings: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    temp = SETTINGS_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(SETTINGS_FILE)


def carregar_credenciais() -> Credenciais:
    settings = _ler_settings()
    email = str(settings.get("email", "")).strip()
    login_automatico = bool(settings.get("login_automatico", True))
    navegador = str(settings.get("navegador", "auto") or "auto").strip().lower()
    try:
        senha = _dpapi_decrypt(str(settings.get("senha_protegida", "")))
    except Exception:
        senha = ""
    return Credenciais(email, senha, login_automatico, navegador)


def salvar_credenciais(email: str, senha: str, login_automatico: bool = True, navegador: str = "auto") -> None:
    email = (email or "").strip()
    if not email:
        raise ValueError("Informe o e-mail do Agilize.")
    if not senha:
        raise ValueError("Informe a senha do Agilize.")
    _salvar_settings({
        "email": email,
        "login_automatico": bool(login_automatico),
        "navegador": (navegador or "auto").strip().lower(),
        "senha_protegida": _dpapi_encrypt(senha),
    })


def salvar_navegador(navegador: str) -> None:
    settings = _ler_settings()
    settings["navegador"] = (navegador or "auto").strip().lower()
    _salvar_settings(settings)


def remover_credenciais() -> None:
    settings = _ler_settings()
    navegador = str(settings.get("navegador", "auto") or "auto")
    _salvar_settings({
        "email": "",
        "login_automatico": True,
        "navegador": navegador,
        "senha_protegida": "",
    })
