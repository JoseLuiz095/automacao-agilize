from __future__ import annotations

import urllib.error

import updater


def _release(version: str, complete: bool = True) -> dict:
    return {
        "version": version,
        "tag": f"v{version}",
        "release_url": f"https://github.com/{updater.GITHUB_REPOSITORY}/releases/tag/v{version}",
        "notes": "teste",
        "published_at": "2026-08-21T18:00:00Z",
        "download_url": (
            f"https://github.com/{updater.GITHUB_REPOSITORY}/releases/download/v{version}/AutomacaoAgilize-Setup.exe"
            if complete else ""
        ),
        "checksum_url": (
            f"https://github.com/{updater.GITHUB_REPOSITORY}/releases/download/v{version}/AutomacaoAgilize-Setup.exe.sha256"
            if complete else ""
        ),
    }


def test_release_completa_habilita_update():
    original = updater._release_snapshot
    try:
        updater._release_snapshot = lambda: _release("9.9.9", True)
        info = updater.verificar_atualizacao()
        assert info.state == updater.STATE_UPDATE_AVAILABLE
        assert info.available is True
        assert info.can_install is True
    finally:
        updater._release_snapshot = original


def test_release_404_nao_aguarda_actions():
    original = updater._release_snapshot
    try:
        def missing():
            raise urllib.error.HTTPError(updater.RELEASE_API_URL, 404, "Not Found", {}, None)
        updater._release_snapshot = missing
        info = updater.verificar_atualizacao()
        assert info.state == updater.STATE_NO_RELEASE
        assert info.available is False
        assert info.can_install is False
        assert "nenhuma release" in info.message.lower()
    finally:
        updater._release_snapshot = original


def test_release_incompleta_e_falha_de_publicacao():
    original = updater._release_snapshot
    try:
        updater._release_snapshot = lambda: _release("9.9.9", False)
        info = updater.verificar_atualizacao()
        assert info.state == updater.STATE_CHECK_FAILED
        assert info.available is False
        assert info.can_install is False
        assert "incompleta" in info.message.lower()
    finally:
        updater._release_snapshot = original


def test_mesma_release_e_atualizado():
    original = updater._release_snapshot
    try:
        updater._release_snapshot = lambda: _release(updater.__version__, True)
        info = updater.verificar_atualizacao()
        assert info.state == updater.STATE_UPDATED
        assert info.available is False
    finally:
        updater._release_snapshot = original


if __name__ == "__main__":
    for test in [
        test_release_completa_habilita_update,
        test_release_404_nao_aguarda_actions,
        test_release_incompleta_e_falha_de_publicacao,
        test_mesma_release_e_atualizado,
    ]:
        test()
        print(f"[OK] {test.__name__}")
