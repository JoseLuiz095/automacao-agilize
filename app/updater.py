from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from config import LOG_DIR, UPDATE_DIR
from version import GITHUB_REPOSITORY, GITHUB_URL, __version__

ProgressCallback = Callable[[int, str], None]
RELEASE_SETUP_ASSET = "AutomacaoAgilize-Setup.exe"
RELEASE_SHA_ASSET = "AutomacaoAgilize-Setup.exe.sha256"
RELEASE_API_URL = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
UPDATE_LOG = LOG_DIR / "update.log"
UPDATE_CACHE = UPDATE_DIR / "last_update_check.json"

STATE_UPDATED = "updated"
STATE_UPDATE_AVAILABLE = "update_available"
STATE_NO_RELEASE = "no_release"
STATE_LOCAL_NEWER = "local_newer"
STATE_OFFLINE = "offline"
STATE_RATE_LIMITED = "rate_limited"
STATE_CHECK_FAILED = "check_failed"

# Compatibilidade de import com versoes anteriores. Nao sao usados no fluxo novo.
STATE_RELEASE_PENDING = "release_pending"
STATE_WAITING_INSTALLER = "waiting_installer"
STATE_REPOSITORY_UNAVAILABLE = "repository_unavailable"


@dataclass
class UpdateInfo:
    current_version: str
    latest_version: str = ""
    available: bool = False
    can_install: bool = False
    provider: str = "github_release"
    state: str = ""
    download_url: str = ""
    checksum_url: str = ""
    checksum: str = ""
    asset_name: str = RELEASE_SETUP_ASSET
    release_url: str = ""
    notes: str = ""
    source_version: str = ""
    message: str = ""
    detail: str = ""
    error: str = ""
    diagnostic: str = ""
    checked_at: str = ""
    repository_accessible: bool = True
    repository_private: bool = False
    default_branch: str = "main"
    authenticated: bool = False
    published_at: str = ""


def _log(text: str) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
        with UPDATE_LOG.open("a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {text}\n")
    except Exception:
        pass


def _version_tuple(value: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", value or "")
    return tuple(int(x) for x in nums[:4]) or (0,)


def _compare_versions(local: str, remote: str) -> int:
    """1 = remoto mais novo; 0 = igual; -1 = local mais novo."""
    a = _version_tuple(local)
    b = _version_tuple(remote)
    width = max(len(a), len(b))
    a += (0,) * (width - len(a))
    b += (0,) * (width - len(b))
    return (b > a) - (b < a)


def _request(url: str, timeout: int = 30):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"AutomacaoAgilize/{__version__}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Cache-Control": "no-cache",
        },
    )
    return urllib.request.urlopen(req, timeout=timeout)


def _request_json(url: str) -> dict:
    with _request(url) as response:
        return json.loads(response.read().decode("utf-8"))


def _release_snapshot() -> dict:
    """Le somente a Release mais recente.

    Nao consulta VERSAO.txt e nao acompanha GitHub Actions. A Release e a unica
    fonte de verdade. Se nao existe Release, nao existe atualizacao anunciada.
    """
    data = _request_json(RELEASE_API_URL)
    tag = str(data.get("tag_name") or "").strip()
    version = tag.lstrip("vV")
    if not version or _version_tuple(version) == (0,):
        raise RuntimeError("A ultima Release nao possui uma versao valida.")

    exe = None
    sha = None
    for asset in data.get("assets") or []:
        name = str(asset.get("name") or "")
        if name.lower() == RELEASE_SETUP_ASSET.lower():
            exe = asset
        elif name.lower() == RELEASE_SHA_ASSET.lower():
            sha = asset

    return {
        "version": version,
        "tag": tag,
        "release_url": str(data.get("html_url") or f"{GITHUB_URL}/releases/tag/{tag}"),
        "notes": str(data.get("body") or "").strip(),
        "published_at": str(data.get("published_at") or ""),
        "download_url": str((exe or {}).get("browser_download_url") or ""),
        "checksum_url": str((sha or {}).get("browser_download_url") or ""),
    }


def _save_cache(info: UpdateInfo) -> None:
    try:
        UPDATE_DIR.mkdir(parents=True, exist_ok=True)
        payload = asdict(info)
        payload["saved_at_epoch"] = int(time.time())
        UPDATE_CACHE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _finish(info: UpdateInfo) -> UpdateInfo:
    info.checked_at = datetime.now().astimezone().isoformat(timespec="seconds")
    _log(
        f"Resultado: state={info.state}; local=v{info.current_version}; "
        f"release=v{info.latest_version or '-'}; available={info.available}; "
        f"can_install={info.can_install}; api={RELEASE_API_URL}; diagnostic={info.diagnostic or '-'}"
    )
    if info.state in {STATE_UPDATED, STATE_UPDATE_AVAILABLE, STATE_LOCAL_NEWER}:
        _save_cache(info)
    return info


def verificar_atualizacao() -> UpdateInfo:
    """Consulta somente GitHub Releases.

    O fluxo foi simplificado na v0.8.3: VERSAO.txt e GitHub Actions deixaram de
    participar da decisao. O publicador local cria a Release com Setup + SHA antes
    de qualquer usuario conseguir enxergar a nova versao.
    """
    info = UpdateInfo(current_version=__version__)
    try:
        release = _release_snapshot()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            info.state = STATE_NO_RELEASE
            info.latest_version = __version__
            info.message = "Nenhuma Release de atualizacao foi publicada ainda."
            info.detail = (
                "O repositorio esta acessivel, mas ainda nao existe uma Release. "
                "No computador de desenvolvimento, publique a versao com "
                "FERRAMENTAS\\07_PUBLICAR_VERSAO.bat."
            )
            info.diagnostic = f"HTTP 404 em {RELEASE_API_URL}"
            return _finish(info)
        if exc.code in (401, 403, 429):
            info.state = STATE_RATE_LIMITED
            info.message = "GitHub temporariamente indisponivel para consulta."
            info.detail = "Tente novamente em alguns minutos."
            info.diagnostic = f"HTTP {exc.code}: {exc}"
            return _finish(info)
        info.state = STATE_CHECK_FAILED
        info.error = f"HTTP {exc.code}"
        info.message = "Nao foi possivel verificar atualizacoes."
        info.detail = f"GitHub respondeu HTTP {exc.code}."
        info.diagnostic = str(exc)
        return _finish(info)
    except (urllib.error.URLError, TimeoutError) as exc:
        info.state = STATE_OFFLINE
        info.message = "Sem acesso ao GitHub neste momento."
        info.detail = "Verifique a conexao com a internet e tente novamente."
        info.diagnostic = str(exc)
        return _finish(info)
    except Exception as exc:
        info.state = STATE_CHECK_FAILED
        info.error = str(exc)
        info.message = "Nao foi possivel interpretar a Release de atualizacao."
        info.detail = "Consulte update.log para o diagnostico."
        info.diagnostic = str(exc)
        return _finish(info)

    latest = release["version"]
    info.latest_version = latest
    info.release_url = release["release_url"]
    info.notes = release["notes"]
    info.published_at = release["published_at"]
    info.download_url = release["download_url"]
    info.checksum_url = release["checksum_url"]

    cmp = _compare_versions(__version__, latest)
    if cmp > 0:
        info.available = True
        info.can_install = bool(info.download_url and info.checksum_url)
        if info.can_install:
            info.state = STATE_UPDATE_AVAILABLE
            info.message = f"Nova versao v{latest} disponivel."
            info.detail = "A Release possui Setup.exe e SHA-256 e esta pronta para instalar."
        else:
            info.state = STATE_CHECK_FAILED
            info.available = False
            info.can_install = False
            faltando = []
            if not info.download_url:
                faltando.append(RELEASE_SETUP_ASSET)
            if not info.checksum_url:
                faltando.append(RELEASE_SHA_ASSET)
            info.message = f"Release v{latest} incompleta."
            info.detail = "Republice a Release. Arquivos ausentes: " + ", ".join(faltando)
            info.error = info.detail
    elif cmp < 0:
        info.state = STATE_LOCAL_NEWER
        info.message = f"Versao instalada v{__version__} e mais nova que a Release v{latest}."
        info.detail = "Nenhuma atualizacao sera aplicada."
    else:
        info.state = STATE_UPDATED
        info.message = f"Sistema atualizado · v{__version__}."
        info.detail = "A versao instalada corresponde a ultima Release publicada."
    return _finish(info)


def _download(url: str, destino: Path, progress: Optional[ProgressCallback] = None) -> None:
    # browser_download_url redireciona para o armazenamento de assets do GitHub.
    req = urllib.request.Request(url, headers={"User-Agent": f"AutomacaoAgilize/{__version__}"})
    with urllib.request.urlopen(req, timeout=120) as response, destino.open("wb") as f:
        total = int(response.headers.get("Content-Length", "0") or "0")
        baixado = 0
        while True:
            chunk = response.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            baixado += len(chunk)
            if progress:
                pct = int(baixado * 100 / total) if total else 0
                progress(pct, f"Baixando atualizacao... {pct}%" if total else "Baixando atualizacao...")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower()


def baixar_instalador(info: UpdateInfo, progress: Optional[ProgressCallback] = None) -> Path:
    if not info.can_install or not info.download_url or not info.checksum_url:
        raise RuntimeError("A Release nao possui Setup.exe e SHA-256 completos.")

    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    for old in UPDATE_DIR.glob("AutomacaoAgilize-Setup*.exe"):
        try:
            old.unlink()
        except OSError:
            pass

    destino = UPDATE_DIR / RELEASE_SETUP_ASSET
    checksum_file = UPDATE_DIR / RELEASE_SHA_ASSET
    _download(info.download_url, destino, progress)
    _download(info.checksum_url, checksum_file)

    if not destino.exists() or destino.stat().st_size < 100_000:
        raise RuntimeError("O instalador baixado parece invalido ou incompleto.")

    expected_text = checksum_file.read_text(encoding="utf-8-sig", errors="ignore")
    match = re.search(r"\b([0-9a-fA-F]{64})\b", expected_text)
    if not match:
        raise RuntimeError("O arquivo SHA-256 da Release e invalido.")
    expected = match.group(1).lower()
    actual = _sha256(destino)
    if actual != expected:
        try:
            destino.unlink()
        except OSError:
            pass
        raise RuntimeError("A verificacao SHA-256 da atualizacao falhou.")

    info.checksum = expected
    _log(f"SHA-256 confirmado para {destino.name}: {actual}")
    return destino


def iniciar_instalador(path: str | Path) -> None:
    instalador = Path(path).resolve()
    if not instalador.exists():
        raise FileNotFoundError(instalador)

    if os.name != "nt":
        subprocess.Popen([str(instalador)], close_fds=True)
        return

    pid = os.getpid()
    installed_exe = (
        Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        / "Programs"
        / "AutomacaoAgilize"
        / "AutomacaoAgilize.exe"
    )
    ps = (
        f"$pidToWait={pid}; "
        "while (Get-Process -Id $pidToWait -ErrorAction SilentlyContinue) { Start-Sleep -Milliseconds 300 }; "
        f"$p=Start-Process -FilePath '{str(instalador).replace(chr(39), chr(39)*2)}' "
        "-ArgumentList '/SP-','/VERYSILENT','/NORESTART','/CLOSEAPPLICATIONS' -Wait -PassThru; "
        f"if ($p.ExitCode -eq 0 -and (Test-Path '{str(installed_exe).replace(chr(39), chr(39)*2)}')) "
        f"{{ Start-Process -FilePath '{str(installed_exe).replace(chr(39), chr(39)*2)}' }}"
    )
    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-Command", ps],
        creationflags=0x08000000,
        close_fds=True,
    )
    _log(f"Atualizador agendado para {instalador}.")


def abrir_repositorio() -> None:
    webbrowser.open(GITHUB_URL)


if __name__ == "__main__":
    result = verificar_atualizacao()
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
