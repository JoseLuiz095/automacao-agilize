from __future__ import annotations

import sys
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))


def _http_404(url: str):
    return urllib.error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)


def test_release_is_authoritative() -> None:
    import updater
    old_release = updater._release_snapshot
    try:
        updater._release_snapshot = lambda: {
            "version": "99.0.0",
            "release_url": "https://example/release",
            "notes": "",
            "download_url": "https://example/AutomacaoAgilize-Setup.exe",
            "asset_name": "AutomacaoAgilize-Setup.exe",
            "checksum_url": "https://example/AutomacaoAgilize-Setup.exe.sha256",
        }
        info = updater.verificar_atualizacao()
        assert info.state == updater.STATE_UPDATE_AVAILABLE
        assert info.available is True
        assert info.can_install is True
        assert info.latest_version == "99.0.0"
    finally:
        updater._release_snapshot = old_release


def test_repository_404_is_not_application_error() -> None:
    import updater
    old_release = updater._release_snapshot
    old_repo = updater._repository_snapshot
    old_git = updater._git_source_snapshot
    try:
        updater._release_snapshot = lambda: (_ for _ in ()).throw(_http_404(updater.RELEASE_API_URL))
        updater._repository_snapshot = lambda: (_ for _ in ()).throw(_http_404(updater.REPOSITORY_API_URL))
        updater._git_source_snapshot = lambda: (_ for _ in ()).throw(RuntimeError("git indisponivel"))
        info = updater.verificar_atualizacao()
        assert info.state == updater.STATE_REPOSITORY_UNAVAILABLE
        assert info.available is False
        assert info.can_install is False
        assert info.error == ""
    finally:
        updater._release_snapshot = old_release
        updater._repository_snapshot = old_repo
        updater._git_source_snapshot = old_git


def test_source_newer_without_release_is_pending_not_error() -> None:
    import updater
    old_release = updater._release_snapshot
    old_repo = updater._repository_snapshot
    old_source = updater._source_snapshot
    try:
        updater._release_snapshot = lambda: (_ for _ in ()).throw(_http_404(updater.RELEASE_API_URL))
        updater._repository_snapshot = lambda: {
            "default_branch": "main", "private": False, "html_url": updater.GITHUB_URL
        }
        updater._source_snapshot = lambda branch=None: {"version": "99.0.0", "branch": branch or "main"}
        info = updater.verificar_atualizacao()
        assert info.state == updater.STATE_RELEASE_PENDING
        assert info.available is True
        assert info.can_install is False
        assert info.error == ""
    finally:
        updater._release_snapshot = old_release
        updater._repository_snapshot = old_repo
        updater._source_snapshot = old_source


def test_same_release_is_updated() -> None:
    import updater
    old_release = updater._release_snapshot
    try:
        updater._release_snapshot = lambda: {
            "version": updater.__version__,
            "release_url": "https://example/release",
            "notes": "",
            "download_url": "https://example/AutomacaoAgilize-Setup.exe",
            "asset_name": "AutomacaoAgilize-Setup.exe",
            "checksum_url": "https://example/AutomacaoAgilize-Setup.exe.sha256",
        }
        info = updater.verificar_atualizacao()
        assert info.state == updater.STATE_UPDATED
        assert info.available is False
        assert info.can_install is False
        assert info.error == ""
    finally:
        updater._release_snapshot = old_release


def main() -> int:
    test_release_is_authoritative(); print("[OK] release autoritativa")
    test_repository_404_is_not_application_error(); print("[OK] 404 nao vira falha de software")
    test_source_newer_without_release_is_pending_not_error(); print("[OK] versao em preparacao")
    test_same_release_is_updated(); print("[OK] sistema atualizado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
