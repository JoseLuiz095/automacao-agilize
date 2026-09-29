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


@dataclass
class CredenciaisZimbra:
    email: str = ""
    senha: str = ""
    servidor: str = ""
    porta: int = 993
    pasta: str = "INBOX"
    remetente: str = ""
    destino: str = ""


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
    settings = _ler_settings()
    settings.update({
        "email": email,
        "login_automatico": bool(login_automatico),
        "navegador": (navegador or "auto").strip().lower(),
        "senha_protegida": _dpapi_encrypt(senha),
    })
    _salvar_settings(settings)


def salvar_navegador(navegador: str) -> None:
    settings = _ler_settings()
    settings["navegador"] = (navegador or "auto").strip().lower()
    _salvar_settings(settings)


def remover_credenciais() -> None:
    settings = _ler_settings()
    settings.update({
        "email": "",
        "login_automatico": True,
        "navegador": str(settings.get("navegador", "auto") or "auto"),
        "senha_protegida": "",
    })
    _salvar_settings(settings)


def carregar_credenciais_zimbra() -> CredenciaisZimbra:
    settings = _ler_settings()
    z = settings.get("zimbra", {}) if isinstance(settings.get("zimbra", {}), dict) else {}
    email = str(z.get("email", "") or "").strip()
    servidor = str(z.get("servidor", "") or "").strip()
    pasta = str(z.get("pasta", "INBOX") or "INBOX").strip()
    remetente = str(z.get("remetente", "") or "").strip()
    destino = str(z.get("destino", "") or "").strip()
    try:
        porta = int(z.get("porta", 993) or 993)
    except Exception:
        porta = 993
    try:
        senha = _dpapi_decrypt(str(z.get("senha_protegida", "") or ""))
    except Exception:
        senha = ""
    return CredenciaisZimbra(email, senha, servidor, porta, pasta, remetente, destino)


def salvar_credenciais_zimbra(
    email: str,
    senha: str,
    servidor: str = "",
    porta: int = 993,
    pasta: str = "INBOX",
    remetente: str = "",
    destino: str = "",
) -> None:
    email = (email or "").strip()
    if not email:
        raise ValueError("Informe o e-mail do Zimbra.")
    if not senha:
        raise ValueError("Informe a senha do Zimbra.")
    settings = _ler_settings()
    settings["zimbra"] = {
        "email": email,
        "servidor": (servidor or "").strip(),
        "porta": int(porta or 993),
        "pasta": (pasta or "INBOX").strip(),
        "remetente": (remetente or "").strip(),
        "destino": (destino or "").strip(),
        "senha_protegida": _dpapi_encrypt(senha),
    }
    _salvar_settings(settings)
