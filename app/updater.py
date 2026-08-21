from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
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
RELEASE_SHA_ASSET = f"{RELEASE_SETUP_ASSET}.sha256"
REPOSITORY_API_URL = f"https://api.github.com/repos/{GITHUB_REPOSITORY}"
RELEASE_API_URL = f"{REPOSITORY_API_URL}/releases/latest"
CONTENTS_API_URL = f"{REPOSITORY_API_URL}/contents/VERSAO.txt"
REPO_CLONE_URL = f"https://github.com/{GITHUB_REPOSITORY}.git"
UPDATE_LOG = LOG_DIR / "update.log"
UPDATE_CACHE = UPDATE_DIR / "last_update_check.json"

STATE_UPDATED = "updated"
STATE_UPDATE_AVAILABLE = "update_available"
STATE_RELEASE_PENDING = "release_pending"
STATE_WAITING_INSTALLER = "waiting_installer"
STATE_NO_RELEASE = "no_release"
STATE_LOCAL_NEWER = "local_newer"
STATE_REPOSITORY_UNAVAILABLE = "repository_unavailable"
STATE_OFFLINE = "offline"
STATE_RATE_LIMITED = "rate_limited"
STATE_CHECK_FAILED = "check_failed"

TOKEN_ENV_NAMES = ("AUTOMACAO_AGILIZE_GITHUB_TOKEN", "GITHUB_TOKEN")
_GITHUB_TOKEN_CACHE = ""
_GITHUB_TOKEN_RESOLVED = False


@dataclass
class UpdateInfo:
    current_version: str
    latest_version: str = ""
    available: bool = False
    can_install: bool = False
    provider: str = ""
    state: str = ""
    download_url: str = ""
    checksum_url: str = ""
    asset_name: str = ""
    release_url: str = ""
    notes: str = ""
    source_version: str = ""
    message: str = ""
    detail: str = ""
    error: str = ""
    diagnostic: str = ""
    checked_at: str = ""
    repository_accessible: bool = False
    repository_private: bool = False
    default_branch: str = ""
    authenticated: bool = False


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
    """Return 1 when remote is newer, 0 when equal and -1 when local is newer."""
    a = _version_tuple(local)
    b = _version_tuple(remote)
    width = max(len(a), len(b))
    a += (0,) * (width - len(a))
    b += (0,) * (width - len(b))
    return (b > a) - (b < a)


def _github_token() -> str:
    """Return a GitHub token without ever persisting or logging it.

    Priority:
    1. explicit environment variable;
    2. Git Credential Manager already authenticated on this Windows account.

    The GCM fallback is important for private repositories used by the developer:
    Git may be authenticated even when the Python process has no GITHUB_TOKEN.
    End-user machines that do not have Git credentials simply continue using the
    anonymous/public Release channel.
    """
    global _GITHUB_TOKEN_CACHE, _GITHUB_TOKEN_RESOLVED

    for name in TOKEN_ENV_NAMES:
        value = str(os.environ.get(name) or "").strip()
        if value:
            return value

    if _GITHUB_TOKEN_RESOLVED:
        return _GITHUB_TOKEN_CACHE
    _GITHUB_TOKEN_RESOLVED = True

    git = shutil.which("git")
    if not git:
        return ""
    try:
        env = os.environ.copy()
        env["GCM_INTERACTIVE"] = "never"
        env["GIT_TERMINAL_PROMPT"] = "0"
        proc = subprocess.run(
            [git, "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env=env,
            check=False,
        )
        if proc.returncode == 0:
            values = {}
            for line in (proc.stdout or "").splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    values[key.strip().lower()] = value.strip()
            token = values.get("password", "")
            if token:
                _GITHUB_TOKEN_CACHE = token
                return token
    except Exception:
        pass
    return ""


def _request(url: str, timeout: int = 20, *, json_api: bool = False, asset: bool = False):
    headers = {
        "User-Agent": f"AutomacaoAgilize/{__version__}",
        "Cache-Control": "no-cache",
    }
    token = _github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if asset:
        headers["Accept"] = "application/octet-stream"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    elif json_api:
        headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )
    req = urllib.request.Request(url, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout)


def _request_json(url: str) -> dict:
    with _request(url, json_api=True) as response:
        return json.loads(response.read().decode("utf-8"))


def _request_text(url: str, timeout: int = 15) -> str:
    with _request(url, timeout=timeout) as response:
        return response.read().decode("utf-8-sig", errors="replace").strip()


def _repository_snapshot() -> dict:
    """Read repository metadata separately from the Release endpoint.

    GitHub returns HTTP 404 for /releases/latest both when the repository is
    inaccessible and when an accessible repository simply has no Releases.  The
    old updater treated those two cases as the same thing.  This call removes
    that ambiguity.
    """
    data = _request_json(REPOSITORY_API_URL)
    return {
        "name": str(data.get("full_name") or GITHUB_REPOSITORY),
        "default_branch": str(data.get("default_branch") or "main"),
        "private": bool(data.get("private", False)),
        "html_url": str(data.get("html_url") or GITHUB_URL),
    }


def _asset_download_url(asset: dict) -> str:
    """Use GitHub's authenticated asset API when a token is available."""
    if _github_token():
        return str(asset.get("url") or asset.get("browser_download_url") or "")
    return str(asset.get("browser_download_url") or asset.get("url") or "")


def _release_snapshot() -> dict:
    data = _request_json(RELEASE_API_URL)
    tag = str(data.get("tag_name", "")).strip()
    latest = tag.lstrip("vV")
    if not latest or _version_tuple(latest) == (0,):
        raise RuntimeError("O ultimo Release nao possui uma versao identificavel.")

    exe = None
    checksum = None
    for asset in data.get("assets") or []:
        name = str(asset.get("name", ""))
        low = name.lower()
        if low == RELEASE_SETUP_ASSET.lower():
            exe = asset
        elif low in {RELEASE_SHA_ASSET.lower(), "automacaoagilize-setup.sha256"}:
            checksum = asset

    return {
        "version": latest,
        "tag": tag,
        "release_url": str(data.get("html_url") or GITHUB_URL),
        "notes": str(data.get("body") or "").strip(),
        "download_url": _asset_download_url(exe or {}),
        "asset_name": str((exe or {}).get("name") or RELEASE_SETUP_ASSET),
        "checksum_url": _asset_download_url(checksum or {}),
        "authenticated_asset": bool(_github_token()),
    }


def _source_snapshot(branch: str | None = None) -> dict:
    """Read VERSAO.txt from the repository's real default branch.

    The previous updater guessed main/master through raw.githubusercontent.com.
    That produced a second 404 when the branch or file differed, making an
    existing repository look unavailable.  The Contents API is authoritative
    and also supports private repositories when a token is supplied.
    """
    if not branch:
        repo = _repository_snapshot()
        branch = str(repo.get("default_branch") or "main")
    url = CONTENTS_API_URL + "?ref=" + urllib.parse.quote(branch, safe="")
    data = _request_json(url)
    encoded = str(data.get("content") or "").replace("\n", "")
    if not encoded:
        raise RuntimeError("VERSAO.txt existe, mas nao possui conteudo legivel.")
    try:
        version = base64.b64decode(encoded).decode("utf-8-sig", errors="replace").strip()
    except Exception as exc:
        raise RuntimeError(f"Nao foi possivel decodificar VERSAO.txt: {exc}") from exc
    if _version_tuple(version) == (0,):
        raise RuntimeError("VERSAO.txt nao possui uma versao valida.")
    return {"version": version.lstrip("vV"), "branch": branch, "url": url}


def _git_source_snapshot() -> dict:
    """Developer fallback compatible with the Carat project.

    If the repository is private but this Windows account is already authenticated
    in Git Credential Manager, a shallow clone can still read VERSAO.txt.  This is
    diagnostic only: installers continue to come from GitHub Releases.
    """
    git = shutil.which("git")
    if not git:
        raise RuntimeError("Git for Windows nao encontrado para fallback autenticado.")
    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with tempfile.TemporaryDirectory(prefix="automacao-agilize-update-") as td:
        dest = Path(td) / "repo"
        proc = subprocess.run(
            [git, "clone", "--depth", "1", "--single-branch", REPO_CLONE_URL, str(dest)],
            cwd=td,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            creationflags=create_no_window,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "git clone falhou").strip())
        version_file = dest / "VERSAO.txt"
        if not version_file.exists():
            raise RuntimeError("Repositorio clonado, mas VERSAO.txt nao foi encontrado.")
        version = version_file.read_text(encoding="utf-8-sig", errors="replace").strip().lstrip("vV")
        if _version_tuple(version) == (0,):
            raise RuntimeError("VERSAO.txt clonado nao possui versao valida.")
        branch_proc = subprocess.run(
            [git, "-C", str(dest), "branch", "--show-current"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            creationflags=create_no_window,
            check=False,
        )
        branch = branch_proc.stdout.strip() or "main"
        return {"version": version, "branch": branch, "url": REPO_CLONE_URL}


def _failure_kind(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 404:
            return "not_found"
        if exc.code in (401, 403, 429):
            return "rate_limited"
        return "http_error"
    if isinstance(exc, urllib.error.URLError):
        return "offline"
    if isinstance(exc, TimeoutError):
        return "offline"
    return "unknown"


def _save_cache(info: UpdateInfo) -> None:
    try:
        UPDATE_DIR.mkdir(parents=True, exist_ok=True)
        payload = asdict(info)
        payload["saved_at_epoch"] = int(time.time())
        UPDATE_CACHE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _load_cache(max_age_hours: int = 24) -> UpdateInfo | None:
    try:
        payload = json.loads(UPDATE_CACHE.read_text(encoding="utf-8"))
        saved = int(payload.pop("saved_at_epoch", 0) or 0)
        if not saved or time.time() - saved > max_age_hours * 3600:
            return None
        fields = UpdateInfo.__dataclass_fields__
        clean = {k: v for k, v in payload.items() if k in fields}
        return UpdateInfo(**clean)
    except Exception:
        return None


def _finish(info: UpdateInfo) -> UpdateInfo:
    info.checked_at = datetime.now().astimezone().isoformat(timespec="seconds")
    _log(
        f"Resultado: state={info.state}; local=v{info.current_version}; "
        f"remoto=v{info.latest_version or '-'}; available={info.available}; "
        f"can_install={info.can_install}; provider={info.provider or '-'}; "
        f"repo_accessible={info.repository_accessible}; repo_private={info.repository_private}; "
        f"authenticated={info.authenticated}; diagnostic={info.diagnostic or '-'}"
    )
    if info.state in {
        STATE_UPDATED,
        STATE_UPDATE_AVAILABLE,
        STATE_RELEASE_PENDING,
        STATE_WAITING_INSTALLER,
        STATE_NO_RELEASE,
        STATE_LOCAL_NEWER,
    }:
        _save_cache(info)
    return info


def _apply_source_without_release(info: UpdateInfo, source: dict, *, repo_private: bool = False) -> UpdateInfo:
    latest = str(source.get("version") or "")
    info.latest_version = latest
    info.source_version = latest
    info.provider = "github_source"
    cmp = _compare_versions(__version__, latest)
    info.available = cmp > 0
    info.can_install = False
    if cmp > 0:
        info.state = STATE_RELEASE_PENDING
        info.message = f"Nova versao v{latest} detectada; preparando instalador."
        info.detail = (
            "O codigo novo ja foi publicado. O GitHub Actions deve gerar automaticamente "
            "o Setup.exe e o SHA-256. Voce pode clicar em 'Aguardar instalador' para o "
            "sistema acompanhar a publicacao e atualizar assim que ela terminar."
        )
    elif cmp < 0:
        info.state = STATE_LOCAL_NEWER
        info.message = f"Versao instalada v{__version__} e mais nova que o codigo remoto v{latest}."
        info.detail = "Nenhuma atualizacao sera aplicada."
    else:
        info.state = STATE_NO_RELEASE
        info.message = f"Repositorio conectado · v{__version__}."
        info.detail = (
            "A versao do codigo confere, mas ainda nao existe uma Release instalavel publicada. "
            "Publique AutomacaoAgilize-Setup.exe e o arquivo .sha256 para habilitar Atualizar agora."
        )
    if repo_private:
        info.detail += " O repositorio foi acessado com autenticacao."
    return info


def _release_to_info(release: dict, current_version: str | None = None) -> UpdateInfo:
    current = current_version or __version__
    latest = str(release.get("version") or "")
    info = UpdateInfo(current_version=current)
    info.latest_version = latest
    info.provider = "github_release"
    info.repository_accessible = True
    info.release_url = str(release.get("release_url") or GITHUB_URL)
    info.notes = str(release.get("notes") or "")
    info.download_url = str(release.get("download_url") or "")
    info.checksum_url = str(release.get("checksum_url") or "")
    info.asset_name = str(release.get("asset_name") or RELEASE_SETUP_ASSET)
    info.authenticated = bool(_github_token())
    cmp = _compare_versions(current, latest)
    info.available = cmp > 0
    info.can_install = bool(info.available and info.download_url and info.checksum_url)
    if cmp > 0 and info.can_install:
        info.state = STATE_UPDATE_AVAILABLE
        info.message = f"Nova versao v{latest} disponivel."
        info.detail = "O instalador e o SHA-256 da Release estao prontos para atualizacao."
    elif cmp > 0:
        info.state = STATE_RELEASE_PENDING
        missing = []
        if not info.download_url:
            missing.append(RELEASE_SETUP_ASSET)
        if not info.checksum_url:
            missing.append(RELEASE_SHA_ASSET)
        info.message = f"Release v{latest} publicada; instalador ainda sendo preparado."
        info.detail = "Aguardando: " + ", ".join(missing) + "."
    elif cmp < 0:
        info.state = STATE_LOCAL_NEWER
        info.message = f"Versao instalada v{current} e mais nova que a Release v{latest}."
        info.detail = "Nenhuma atualizacao sera aplicada."
    else:
        info.state = STATE_UPDATED
        info.message = f"Sistema atualizado · v{current}."
        info.detail = "A versao instalada corresponde a ultima Release publicada no GitHub."
    return info


def aguardar_instalador(
    target_version: str,
    *,
    timeout_seconds: int = 600,
    interval_seconds: int = 12,
    progress: Optional[ProgressCallback] = None,
) -> UpdateInfo:
    """Wait for GitHub Actions to publish an installable Release.

    This bridges the short window between VERSAO.txt being pushed and the Windows
    installer finishing in GitHub Actions. It does not build software on the user's
    machine; it only polls the official Release channel and returns when both the
    Setup.exe and SHA-256 are available.
    """
    started = time.time()
    target = str(target_version or "").lstrip("vV")
    last_error = ""
    _log(f"Aguardando Release instalavel para v{target}; timeout={timeout_seconds}s.")

    while True:
        elapsed = int(time.time() - started)
        if elapsed >= timeout_seconds:
            raise RuntimeError(
                f"O instalador da v{target} ainda nao foi publicado apos {timeout_seconds // 60} minutos. "
                "Verifique a aba Actions/Release do GitHub e tente novamente."
            )
        try:
            release = _release_snapshot()
            latest = str(release.get("version") or "")
            cmp_target = _compare_versions(target, latest)
            has_assets = bool(release.get("download_url") and release.get("checksum_url"))
            if cmp_target >= 0 and has_assets:
                ready = _release_to_info(release, current_version=__version__)
                if _compare_versions(__version__, latest) > 0 and ready.can_install:
                    ready.state = STATE_UPDATE_AVAILABLE
                    _log(f"Release instalavel encontrada durante espera: v{latest}.")
                    return ready
        except Exception as exc:
            last_error = str(exc)

        if progress:
            pct = min(95, max(1, int(elapsed * 100 / max(1, timeout_seconds))))
            suffix = f" Ultimo retorno: {last_error}" if last_error and elapsed > 30 else ""
            progress(pct, f"Aguardando GitHub gerar o instalador da v{target}...{suffix}")
        time.sleep(max(3, interval_seconds))


def verificar_atualizacao() -> UpdateInfo:
    """Check GitHub updates using Release first, with precise 404 diagnostics.

    Update strategy:
    * GitHub Release is the installable channel.
    * VERSAO.txt is also compared so a build-in-progress is visible immediately.
    * When source is newer than Release, the UI can wait for GitHub Actions.
    * Private developer repositories may reuse an existing Git Credential Manager token.
    * Git clone remains a diagnostic fallback when API access is unavailable.
    """
    info = UpdateInfo(current_version=__version__, authenticated=bool(_github_token()))
    release_exc: Exception | None = None

    # 1) Preferred install channel: latest GitHub Release.  Even when a Release
    # exists, also compare VERSAO.txt if the Release is not newer than this app.
    # This fixes the window where code vX was pushed but GitHub Actions is still
    # building the installer and the latest Release is still vX-1.
    try:
        release = _release_snapshot()
        release_info = _release_to_info(release, current_version=__version__)
        latest_release = release_info.latest_version
        _log(f"Release consultada com sucesso: v{latest_release}.")

        # If an installable newer Release already exists, it is authoritative.
        if release_info.state == STATE_UPDATE_AVAILABLE and release_info.can_install:
            return _finish(release_info)

        # If the Release itself is newer but its assets are incomplete, keep the
        # pending state and let the UI wait/poll for the installer.
        if release_info.state == STATE_RELEASE_PENDING and release_info.available:
            return _finish(release_info)

        # Release is equal/older. Check source metadata too so a freshly pushed
        # version is visible while Actions is building the new Release.
        try:
            repo_now = _repository_snapshot()
            branch_now = str(repo_now.get("default_branch") or "main")
            source_now = _source_snapshot(branch_now)
            source_version = str(source_now.get("version") or "")
            if _compare_versions(__version__, source_version) > 0 and _compare_versions(latest_release, source_version) > 0:
                info = release_info
                info.repository_accessible = True
                info.repository_private = bool(repo_now.get("private", False))
                info.default_branch = branch_now
                info.release_url = str(repo_now.get("html_url") or info.release_url or GITHUB_URL)
                _apply_source_without_release(info, source_now, repo_private=info.repository_private)
                info.diagnostic = (
                    f"Release atual v{latest_release}; codigo remoto v{source_version}; "
                    "GitHub Actions aguardado."
                )
                _log(info.diagnostic)
                return _finish(info)
        except Exception as source_after_release_exc:
            _log(f"Comparacao Release x VERSAO.txt indisponivel: {source_after_release_exc}")

        return _finish(release_info)
    except Exception as exc:
        release_exc = exc
        _log(f"Release GitHub indisponivel: {exc}")

    # 2) A 404 em /releases/latest is ambiguous. Check the repository itself.
    repo_exc: Exception | None = None
    repo: dict | None = None
    try:
        repo = _repository_snapshot()
        info.repository_accessible = True
        info.repository_private = bool(repo.get("private"))
        info.default_branch = str(repo.get("default_branch") or "main")
        info.release_url = str(repo.get("html_url") or GITHUB_URL)
        _log(
            f"Repositorio acessivel: branch={info.default_branch}; "
            f"private={info.repository_private}; auth={info.authenticated}."
        )
    except Exception as exc:
        repo_exc = exc
        _log(f"Metadados do repositorio indisponiveis: {exc}")

    # 3) Accessible repository but no latest Release: read VERSAO from actual branch.
    if repo is not None:
        source_exc: Exception | None = None
        try:
            source = _source_snapshot(info.default_branch)
            _apply_source_without_release(info, source, repo_private=info.repository_private)
            info.diagnostic = f"Release indisponivel: {release_exc}"
            _log(f"VERSAO.txt consultado: v{info.latest_version} ({info.default_branch}).")
            return _finish(info)
        except Exception as exc:
            source_exc = exc
            _log(f"VERSAO.txt indisponivel no repositorio acessivel: {exc}")

        # Repo exists, but neither a Release nor VERSAO.txt is ready. This is not a 404 repo error.
        info.state = STATE_NO_RELEASE
        info.provider = "github_repository"
        info.latest_version = __version__
        info.available = False
        info.can_install = False
        info.message = "Repositorio conectado, mas o canal de Release ainda nao esta pronto."
        info.detail = (
            f"O GitHub encontrou {GITHUB_REPOSITORY}, porem nao ha uma Release instalavel e "
            f"VERSAO.txt nao foi lido na branch {info.default_branch}. "
            "Publique a Release com o Setup.exe e SHA-256 para ativar a atualizacao automatica."
        )
        info.diagnostic = f"Release: {release_exc} | VERSAO.txt: {source_exc}"
        return _finish(info)

    # 4) Developer/private fallback through Git Credential Manager.
    git_exc: Exception | None = None
    try:
        source = _git_source_snapshot()
        info.repository_accessible = True
        info.default_branch = str(source.get("branch") or "")
        _apply_source_without_release(info, source, repo_private=True)
        info.provider = "git_authenticated"
        info.detail += " O acesso foi confirmado pelo Git/Git Credential Manager desta maquina."
        info.diagnostic = f"Release/API indisponiveis: {release_exc} | Repo API: {repo_exc}"
        _log(f"Fallback Git autenticado funcionou: v{info.latest_version}.")
        return _finish(info)
    except Exception as exc:
        git_exc = exc
        _log(f"Fallback Git autenticado indisponivel: {exc}")

    # 5) Classify a real connectivity/authentication problem.
    kinds = {_failure_kind(e) for e in (release_exc, repo_exc) if e is not None}
    cached = _load_cache()

    if "rate_limited" in kinds:
        info.state = STATE_RATE_LIMITED
        info.message = "Verificacao temporariamente limitada pelo GitHub."
        info.detail = "Tente novamente em alguns minutos. Isso nao interfere no lancamento de notas."
    elif "offline" in kinds:
        info.state = STATE_OFFLINE
        info.message = "Sem acesso ao GitHub neste momento."
        info.detail = "Verifique a conexao com a internet e tente novamente."
    elif "not_found" in kinds:
        info.state = STATE_REPOSITORY_UNAVAILABLE
        info.message = "Repositorio nao acessivel para atualizacao automatica."
        if info.authenticated:
            info.detail = (
                f"O GitHub retornou 404 para {GITHUB_REPOSITORY} mesmo com token configurado. "
                "Confira o nome do repositorio e as permissoes do token."
            )
        else:
            info.detail = (
                f"O GitHub retornou 404 para {GITHUB_REPOSITORY}. Isso normalmente ocorre quando o repositorio "
                "e privado ou nao existe para acesso anonimo. Se ele abre apenas quando voce esta logado no navegador, "
                "os computadores dos usuarios tambem nao conseguirao consultar Releases sem autenticacao. "
                "Para atualizacao automatica sem token, o canal de Releases precisa ser publico."
            )
    else:
        info.state = STATE_CHECK_FAILED
        info.message = "Nao foi possivel concluir a verificacao de atualizacao."
        info.detail = "Consulte update.log para o diagnostico tecnico. A Automacao Agilize continua funcionando normalmente."
        info.error = info.message

    info.diagnostic = f"Release: {release_exc} | Repo API: {repo_exc} | Git: {git_exc}"

    if cached and info.state in {STATE_RATE_LIMITED, STATE_OFFLINE, STATE_CHECK_FAILED}:
        info.latest_version = cached.latest_version
        info.source_version = cached.source_version
        info.provider = "cache"
        if cached.latest_version:
            info.detail += f" Ultima verificacao valida: v{cached.latest_version}."

    return _finish(info)


def _download(url: str, destino: Path, progress: Optional[ProgressCallback] = None) -> None:
    # Asset API URLs require application/octet-stream and optional auth token.
    is_asset_api = url.startswith("https://api.github.com/repos/") and "/releases/assets/" in url
    with _request(url, timeout=90, asset=is_asset_api) as response, destino.open("wb") as f:
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
    if not info.download_url or not info.checksum_url:
        raise RuntimeError("A versao detectada ainda nao possui instalador e SHA-256 completos na Release.")

    UPDATE_DIR.mkdir(parents=True, exist_ok=True)
    for old in UPDATE_DIR.glob("AutomacaoAgilize-Setup*.exe"):
        try:
            old.unlink()
        except OSError:
            pass

    destino = UPDATE_DIR / (info.asset_name or RELEASE_SETUP_ASSET)
    _download(info.download_url, destino, progress)

    if not destino.exists() or destino.stat().st_size < 100_000:
        raise RuntimeError("O instalador baixado parece invalido ou incompleto.")

    checksum_file = UPDATE_DIR / RELEASE_SHA_ASSET
    _download(info.checksum_url, checksum_file)
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
    _log(f"SHA-256 confirmado para {destino.name}.")
    return destino


def iniciar_instalador(path: str | Path) -> None:
    """Schedule update after this process exits, then reopen the app."""
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
    create_no_window = 0x08000000
    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-Command", ps],
        creationflags=create_no_window,
        close_fds=True,
    )
    _log(f"Atualizador agendado para {instalador}.")


def abrir_repositorio() -> None:
    webbrowser.open(GITHUB_URL)


if __name__ == "__main__":
    result = verificar_atualizacao()
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
