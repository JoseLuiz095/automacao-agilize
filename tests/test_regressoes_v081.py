from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import updater


def _release(version: str, complete: bool = True) -> dict:
    return {
        "version": version,
        "release_url": f"https://example/release/{version}",
        "notes": "",
        "download_url": "https://example/AutomacaoAgilize-Setup.exe" if complete else "",
        "asset_name": "AutomacaoAgilize-Setup.exe",
        "checksum_url": "https://example/AutomacaoAgilize-Setup.exe.sha256" if complete else "",
    }


def main() -> None:
    original_version = updater.__version__
    original_release = updater._release_snapshot
    original_repo = updater._repository_snapshot
    original_source = updater._source_snapshot
    original_token = updater._github_token
    try:
        # Reproduz exatamente o caso observado: app v0.7.3, Release ainda v0.7.3,
        # mas VERSAO.txt ja esta em v0.8.1. Nao pode dizer "sistema atualizado".
        updater.__version__ = "0.7.3"
        updater._github_token = lambda: ""
        updater._release_snapshot = lambda: _release("0.7.3", True)
        updater._repository_snapshot = lambda: {
            "default_branch": "main",
            "private": False,
            "html_url": "https://example/repo",
        }
        updater._source_snapshot = lambda branch=None: {
            "version": "0.8.1",
            "branch": "main",
            "url": "https://example/VERSAO.txt",
        }
        info = updater.verificar_atualizacao()
        assert info.state == updater.STATE_RELEASE_PENDING, info
        assert info.available is True
        assert info.can_install is False
        assert info.latest_version == "0.8.1"

        # Assim que o GitHub Actions termina e publica os dois assets, a mesma
        # verificacao precisa virar atualizacao instalavel.
        updater._release_snapshot = lambda: _release("0.8.1", True)
        info = updater.verificar_atualizacao()
        assert info.state == updater.STATE_UPDATE_AVAILABLE, info
        assert info.available is True
        assert info.can_install is True
        assert info.latest_version == "0.8.1"

        # O modo "Aguardar instalador" deve retornar assim que a Release oficial
        # estiver completa, sem exigir nova abertura da aplicacao.
        ready = updater.aguardar_instalador("0.8.1", timeout_seconds=5, interval_seconds=3)
        assert ready.can_install is True
        assert ready.state == updater.STATE_UPDATE_AVAILABLE

        print("[OK] Release antiga + VERSAO nova vira 'aguardar instalador'")
        print("[OK] Release completa habilita atualizacao")
        print("[OK] espera automatica reconhece instalador publicado")
    finally:
        updater.__version__ = original_version
        updater._release_snapshot = original_release
        updater._repository_snapshot = original_repo
        updater._source_snapshot = original_source
        updater._github_token = original_token


if __name__ == "__main__":
    main()
