from __future__ import annotations

import base64
import os
import sys
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))


def _http_404(url: str):
    return urllib.error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)


def test_release_404_repo_exists_is_not_repo_missing() -> None:
    import updater
    old_release = updater._release_snapshot
    old_repo = updater._repository_snapshot
    old_source = updater._source_snapshot
    try:
        updater._release_snapshot = lambda: (_ for _ in ()).throw(_http_404(updater.RELEASE_API_URL))
        updater._repository_snapshot = lambda: {
            "default_branch": "develop",
            "private": False,
            "html_url": updater.GITHUB_URL,
        }
        updater._source_snapshot = lambda branch=None: {"version": updater.__version__, "branch": branch}
        info = updater.verificar_atualizacao()
        assert info.state == updater.STATE_NO_RELEASE
        assert info.repository_accessible is True
        assert info.default_branch == "develop"
        assert "Repositorio conectado" in info.message
    finally:
        updater._release_snapshot = old_release
        updater._repository_snapshot = old_repo
        updater._source_snapshot = old_source


def test_source_uses_contents_api_and_real_branch() -> None:
    import updater
    old_json = updater._request_json
    try:
        encoded = base64.b64encode(b"0.7.9\n").decode("ascii")
        seen = []
        def fake(url: str):
            seen.append(url)
            return {"content": encoded}
        updater._request_json = fake
        snap = updater._source_snapshot("release/v1")
        assert snap["version"] == "0.7.9"
        assert "ref=release%2Fv1" in seen[0]
    finally:
        updater._request_json = old_json


def test_private_token_environment_is_supported() -> None:
    import updater
    old = os.environ.get("AUTOMACAO_AGILIZE_GITHUB_TOKEN")
    try:
        os.environ["AUTOMACAO_AGILIZE_GITHUB_TOKEN"] = "token-test"
        assert updater._github_token() == "token-test"
    finally:
        if old is None:
            os.environ.pop("AUTOMACAO_AGILIZE_GITHUB_TOKEN", None)
        else:
            os.environ["AUTOMACAO_AGILIZE_GITHUB_TOKEN"] = old


def main() -> int:
    test_release_404_repo_exists_is_not_repo_missing(); print("[OK] 404 de Release nao confunde repositorio existente")
    test_source_uses_contents_api_and_real_branch(); print("[OK] VERSAO.txt usa Contents API + branch real")
    test_private_token_environment_is_supported(); print("[OK] token opcional para repositorio privado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
